import asyncio
import json
import base64
import websockets
from typing import AsyncGenerator, Dict, Any
from backend.config import get_gemini_api_key, BASE_DIR
from backend.rag_engine import search_rag_context

GEMINI_BIDI_WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"

def load_system_prompt_rules() -> str:
    prompt_path = BASE_DIR / "rag" / "ai agent .md fayllar uchun " / "system-prompt.txt"
    if prompt_path.exists():
        try:
            with open(prompt_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read().strip()[:3000]
        except Exception as e:
            print(f"Error reading system prompt: {e}")
    return "Siz Urganch shahrining 'Aqlli Yordamchi' AI agentisiz. Xushmuomala o'zbek tilida muloqot qilasiz."

async def gemini_live_bidi_stream(user_text: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Connects to Google AI Studio Gemini Multimodal BidiGenerateContent WebSocket Live Protocol.
    Streams native audio PCM/WAV chunks directly from Google Gemini model.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        yield {"event": "error", "message": "Gemini API Key missing"}
        return

    url = f"{GEMINI_BIDI_WS_URL}?key={api_key}"
    rag_context = search_rag_context(user_text)
    system_rules = load_system_prompt_rules()

    full_system_prompt = (
        f"{system_rules}\n\n"
        f"=== RASMIY BILIMLAR BAZASI (RAG) ===\n{rag_context}\n\n" if rag_context else f"{system_rules}\n\n"
    )

    setup_message = {
        "setup": {
            "model": "models/gemini-2.5-flash",
            "generationConfig": {
                "responseModalities": ["AUDIO", "TEXT"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Aoede" # Aoede is Google's natural female AI voice model
                        }
                    }
                }
            },
            "systemInstruction": {
                "parts": [{"text": full_system_prompt}]
            }
        }
    }

    try:
        async with websockets.connect(url) as ws:
            # 1. Send Setup message to Gemini Bidi WebSocket
            await ws.send(json.dumps(setup_message))
            setup_response = await ws.recv()
            print("Gemini Bidi Setup confirmed:", setup_response[:100])

            # 2. Send User Real-Time Content
            user_msg = {
                "realtimeInput": {
                    "mediaChunks": [
                        {
                            "mimeType": "text/plain",
                            "data": base64.b64encode(user_text.encode('utf-8')).decode('utf-8')
                        }
                    ]
                }
            }
            await ws.send(json.dumps(user_msg))

            # 3. Stream back live response chunks directly from Gemini
            while True:
                try:
                    resp_data = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    msg = json.loads(resp_data)

                    server_content = msg.get("serverContent", {})
                    model_turn = server_content.get("modelTurn", {})
                    parts = model_turn.get("parts", [])

                    for part in parts:
                        # Extract Text Part
                        text_content = part.get("text")
                        if text_content:
                            yield {
                                "event": "text_chunk",
                                "text": text_content,
                                "rag_used": bool(rag_context)
                            }

                        # Extract Direct Native Gemini Audio Part (PCM / Audio stream)
                        inline_data = part.get("inlineData", {})
                        mime_type = inline_data.get("mimeType", "")
                        audio_b64 = inline_data.get("data", "")

                        if audio_b64:
                            yield {
                                "event": "audio_chunk",
                                "mime_type": mime_type,
                                "audio_b64": audio_b64,
                                "rag_used": bool(rag_context)
                            }

                    if server_content.get("turnComplete"):
                        break

                except asyncio.TimeoutError:
                    break

    except Exception as e:
        print(f"Gemini Bidi Live Stream Error: {e}")
        yield {"event": "error", "message": str(e)}
