import json
import asyncio
import io
import base64
import re
import logging
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

from backend.config import BASE_DIR
from backend.models import CitizenSubmission, KnowledgeDocument
from backend.citizen_services import save_submission, get_all_submissions, update_submission_status
from backend.rag_engine import add_knowledge_doc, get_all_knowledge_docs, delete_knowledge_doc, seed_initial_knowledge, search_rag_context
from backend.gemini_agent import generate_ai_response
from backend.gemini_live_session import GeminiLiveSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RoboticLive")

app = FastAPI(title="RoboticLive - Dynamic RAG Gemini 3.1 Live Server", version="6.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

seed_initial_knowledge()

# Native Uzbek Neural Voice Engine (uz-UZ-MadinaNeural)
@app.get("/api/tts")
async def text_to_speech(text: str):
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    # Clean text from markdown and symbols
    clean_text = re.sub(r'[*_#📌🔹⚠️✉️💡]', '', text).replace('---', ' ').replace('UH-', ' ').replace('YT-', ' ').replace('ST-', ' ').strip()[:800]

    # Explicit Uzbek Phonetic Guard (Prevents O -> A reduction)
    clean_text = re.sub(r'\bbera alaman\b', 'bera olaman', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\bbera alamanmi\b', 'bera olamanmi', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\balaman\b', 'olaman', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\balamanmi\b', 'olamanmi', clean_text, flags=re.IGNORECASE)

    try:
        import edge_tts
        # Official Microsoft Uzbek Female Voice (100% natural, eloquent, empathetic orator)
        communicate = edge_tts.Communicate(clean_text, 'uz-UZ-MadinaNeural', rate='+0%', pitch='+0Hz')
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                audio_data.extend(chunk['data'])
        
        if len(audio_data) > 0:
            return Response(content=bytes(audio_data), media_type="audio/mpeg")
    except Exception as e:
        logger.warning(f"EdgeTTS fallback: {e}")

    try:
        from gtts import gTTS
        tts = gTTS(text=clean_text, lang='ru', slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return Response(content=fp.getvalue(), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS Total Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_endpoint(payload: Dict[str, Any]):
    message = payload.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    response = generate_ai_response(message)
    return response

@app.post("/api/submissions", response_model=CitizenSubmission)
async def create_submission(submission: CitizenSubmission):
    return save_submission(submission)

@app.get("/api/submissions", response_model=List[CitizenSubmission])
async def list_submissions():
    return get_all_submissions()

@app.patch("/api/submissions/{sub_id}/status")
async def update_status(sub_id: str, payload: Dict[str, str]):
    status = payload.get("status", "Ko'rib chiqilmoqda")
    success = update_submission_status(sub_id, status)
    if not success:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"status": "updated", "new_status": status}

@app.get("/api/rag/docs", response_model=List[KnowledgeDocument])
async def list_rag_docs():
    return get_all_knowledge_docs()

@app.post("/api/rag/docs", response_model=KnowledgeDocument)
async def add_rag_doc(doc: KnowledgeDocument):
    return add_knowledge_doc(doc)

@app.delete("/api/rag/docs/{doc_id}")
async def delete_rag_doc(doc_id: str):
    success = delete_knowledge_doc(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}

# Direct Gemini 3.1 Live WebSocket Proxy with Dynamic RAG Context Injection on EVERY User Turn
@app.websocket("/ws/live")
async def websocket_gemini_live_proxy(websocket: WebSocket):
    await websocket.accept()
    print("[WS Live] Browser client connected for Dynamic RAG Gemini 3.1 Live")

    async def on_audio_chunk(pcm24k_bytes):
        b64_audio = base64.b64encode(pcm24k_bytes).decode('ascii')
        try:
            await websocket.send_json({
                "event": "gemini_audio_chunk",
                "audio_b64": b64_audio,
                "mime_type": "audio/pcm;rate=24000"
            })
        except Exception as e:
            print("WebSocket send error:", e)

    async def on_input_transcript(text):
        try:
            await websocket.send_json({"event": "input_transcript", "text": text})
        except Exception:
            pass

    async def on_output_transcript(text):
        try:
            await websocket.send_json({"event": "output_transcript", "text": text})
        except Exception:
            pass

    async def on_turn_complete():
        try:
            await websocket.send_json({"event": "turn_complete"})
        except Exception:
            pass

    async def on_interrupted():
        try:
            await websocket.send_json({"event": "interrupted"})
        except Exception:
            pass

    gemini_session = GeminiLiveSession(
        on_audio_chunk=on_audio_chunk,
        on_input_transcript=on_input_transcript,
        on_output_transcript=on_output_transcript,
        on_turn_complete=on_turn_complete,
        on_interrupted=on_interrupted
    )

    try:
        await gemini_session.connect()
        
        # Initial RAG greeting turn
        initial_rag = search_rag_context("Urganch shahri va Olimpiya mahallasi haqida umumiy ma'lumot")
        initial_prompt = (
            "Foydalanuvchi bilan samimiy salomlashing.\n"
            f"=== RASMIY RAG MA'LUMOTLARI ===\n{initial_rag}\n\n"
            "\"Assalomu alaykum! Men Urganch shahrining 'Aqlli Yordamchi' AI tizimiman. Qanday murojaatingiz bor?\" deb aytasiz."
        )
        await gemini_session.send_text_turn(initial_prompt)

        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            event_type = payload.get("event")

            if event_type in ["text_chunk", "speech_input"]:
                user_text = payload.get("text", "")
                if user_text.strip():
                    # 1. DYNAMIC RAG KNOWLEDGE RETRIEVAL ON EVERY SINGLE QUERY
                    rag_context = search_rag_context(user_text)
                    
                    if rag_context:
                        rag_turn_prompt = (
                            f"FOYDALANUVCHI SO'ROVI: \"{user_text}\"\n\n"
                            f"=== MONITORING RO'YXATIDAN TOPILGAN RASMIY RAG MA'LUMOTLARI ===\n{rag_context}\n\n"
                            "QO'LLANMA: Yuqoridagi rasmiy RAG ma'lumotlariga 100% tayanib, o'zbek tilida dona-dona, aniq va samimiy javob ber."
                        )
                    else:
                        rag_turn_prompt = user_text

                    # Notify browser that RAG context was injected
                    await websocket.send_json({
                        "event": "rag_applied",
                        "rag_used": bool(rag_context),
                        "user_text": user_text
                    })

                    # 2. Send RAG-enriched prompt to Gemini 3.1 Live
                    await gemini_session.send_text_turn(rag_turn_prompt)

            elif event_type == "audio_chunk":
                raw_pcm = base64.b64encode(payload.get("data", ""))
                if raw_pcm:
                    await gemini_session.send_audio_chunk(raw_pcm)

            elif event_type == "switch_voice":
                new_voice = payload.get("voice", "Puck")
                print(f"[WS Live] Switching voice profile to: {new_voice}")
                gemini_session.voice_name = new_voice

    except WebSocketDisconnect:
        print("[WS Live] Browser client disconnected")
    except Exception as e:
        print(f"[WS Live] Error: {e}")
    finally:
        await gemini_session.close()

app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")

@app.get("/")
async def get_index():
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>RoboticLive Dynamic RAG Server Running</h1>")

if __name__ == "__main__":
    import uvicorn
    from backend.config import HOST, PORT
    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=True)
