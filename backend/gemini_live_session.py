import os
import asyncio
import base64
import json
import websockets
from pathlib import Path
from typing import Optional, Callable
from backend.config import get_gemini_api_key, BASE_DIR
from backend.rag_engine import search_rag_context

MODEL = "models/gemini-2.5-flash-native-audio-latest"

def load_system_instruction(user_query_hint: str = "") -> str:
    prompt_path = BASE_DIR / "rag" / "ai agent .md fayllar uchun" / "system-prompt.txt"
    if not prompt_path.exists():
        for root, dirs, files in os.walk(BASE_DIR / "rag"):
            if "system-prompt.txt" in files:
                prompt_path = Path(root) / "system-prompt.txt"
                break
    system_rules = ""
    if prompt_path.exists():
        try:
            with open(prompt_path, 'r', encoding='utf-8', errors='ignore') as f:
                system_rules = f.read().strip()
        except Exception as e:
            print(f"Error reading system prompt file: {e}")

    rag_context = search_rag_context(user_query_hint) if user_query_hint else ""

    instruction = (
        "Siz — Urganch shahrining intellektual, nihoyatda bilimdon, samimiy va xushmuomala 'Aqlli Yordamchi' sun'iy intellekt suhbatdoshisiz.\n\n"
        "SIZNING SHAXSIYATINGIZ VA SUHBAT MADANIYATINGIZ:\n"
        "1. Siz shunchaki oddiy robot emassiz, siz insonni chuqur tushunadigan, har qanday mavzuda (Urganch shahri, mahalla hayoti, fan, ta'lim, madaniyat, kommunal soha yoki shaxsiy maslahat) maroqli, jonli va nihoyatda go'zal o'zbek adabiy tilida suhbatlashadigan intellektual yordamchisiz.\n"
        "2. Har bir so'zingizda samimiyat, hurmat, odob va yuqori aql-idrok sezilib tursin. Suhbatdoshni diqqat bilan tinglang, uning ko'nglini ko'taring va savollariga dona-dona, mazmunli va to'liq yechim bering.\n"
        "3. So'zlarni qisqa yoki mexanik qilib uzib qo'ymang. Gaplaringiz jonli insoniy ohangda, ravon, jozibador va tushunarli bo'lsin.\n\n"
        "O'ZBEK TILI FONETIKASI VA TALAFUZ MEZONI (BEQISYOS TINIQLIK):\n"
        "1. 'O' harfini har doim sof, ochiq va chuqur 'O' deb ayting (ona, osmon, hokim, soliq, olimpiya). Ruscha 'akan'ye' (o ni a qilish) aslo bo'lmasin!\n"
        "2. 'A' va 'I' harflarini sof va jarangdor talaffuz qiling (albatta, assalomu alaykum, inson, ishonch).\n"
        "3. Urg'uni o'zbek tili qonuniyatiga binoan faqat va faqat so'zning OXIRGI BO'G'INIGA qo'ying.\n"
        "4. Salomlashish: \"Assalomu alaykum! Men Urganch shahrining 'Aqlli Yordamchi' intellektual tizimiman. Siz bilan suhbatlashishdan juda mamnunman, qanday masalada yordam bera olaman?\"\n\n"
        "MOSLASHUVCHAN SUHBAT STRATEGIYASI:\n"
        "- Agar fuqaro muammo/shikoyat aytsa: unga chin dildan hamdardlik bildirib, muammoni hal qilish yo'llarini (mahalladagi mas'ullar, muddatlar, raqamlar) tushuntiring va arizasini qayd etishni taklif qiling.\n"
        "- Agar fuqaro umumiy savol yoki qiziqarli mavzuda gap ochsa: keng dunyoqarash bilan, qiziqarli faktlar va aniq ma'lumotlar bilan boyitilgan ajoyib suhbat quring.\n\n"
    )

    if system_rules:
        instruction += f"=== QO'SHIMCHA RASMIY TIZIM PROMPT QOIDALARI ===\n{system_rules}\n\n"
    if rag_context:
        instruction += f"=== RASMIY BILIMLAR BAZASI (RAG TO'LIQ CONTEXT) ===\n{rag_context}\n\n"

    return instruction

class GeminiLiveSession:
    def __init__(
        self,
        on_audio_chunk,
        on_input_transcript,
        on_output_transcript,
        on_turn_complete,
        on_interrupted=None,
        query_hint="",
        voice_name="Puck"
    ):
        self._ws = None
        self._recv_task = None
        self.on_audio_chunk = on_audio_chunk
        self.on_input_transcript = on_input_transcript
        self.on_output_transcript = on_output_transcript
        self.on_turn_complete = on_turn_complete
        self.on_interrupted = on_interrupted
        self.query_hint = query_hint
        self.voice_name = voice_name if voice_name in ["Puck", "Aoede", "Charon", "Fenrir", "Kore"] else "Puck"

    async def connect(self):
        api_key = get_gemini_api_key()
        ws_uri = (
            "wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
            f"?key={api_key}"
        )

        print(f"[Gemini 3.1 Live] WebSocket'ga ulanilmoqda ({self.voice_name} ovozi)...")
        last_err = None
        for attempt in range(1, 4):
            try:
                self._ws = await websockets.connect(ws_uri, max_size=None, open_timeout=8)
                break
            except Exception as e:
                last_err = e
                print(f"[Gemini 3.1 Live] Ulanish urinishi {attempt}/3 ({e}), qayta urinilmoqda...")
                await asyncio.sleep(0.5)
        else:
            raise last_err

        system_prompt = load_system_instruction(self.query_hint)

        setup_msg = {
            "setup": {
                "model": MODEL,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": self.voice_name
                            }
                        }
                    }
                },
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "inputAudioTranscription": {},
                "outputAudioTranscription": {},
            }
        }
        await self._ws.send(json.dumps(setup_msg))
        response = json.loads(await self._ws.recv())
        if "setupComplete" not in response:
            raise RuntimeError(f"Gemini Live sozlash muvaffaqiyatsiz: {response}")

        print(f"[Gemini 3.1 Live] Ulanildi, {self.voice_name} emotsional ovozi sozlandi")
        self._recv_task = asyncio.create_task(self._receive_loop())

    async def send_text_turn(self, text):
        msg = {
            "clientContent": {
                "turns": [{"role": "user", "parts": [{"text": text}]}],
                "turnComplete": True,
            }
        }
        if self._ws:
            await self._ws.send(json.dumps(msg))

    async def send_audio_chunk(self, pcm16k_bytes):
        msg = {
            "realtimeInput": {
                "audio": {
                    "data": base64.b64encode(pcm16k_bytes).decode("ascii"),
                    "mimeType": "audio/pcm;rate=16000",
                }
            }
        }
        if self._ws:
            await self._ws.send(json.dumps(msg))

    async def _receive_loop(self):
        try:
            async for message in self._ws:
                data = json.loads(message)
                server_content = data.get("serverContent")
                if not server_content:
                    continue

                if server_content.get("interrupted") and self.on_interrupted:
                    await self.on_interrupted()

                model_turn = server_content.get("modelTurn")
                if model_turn:
                    for part in model_turn.get("parts", []):
                        inline = part.get("inlineData")
                        if inline:
                            await self.on_audio_chunk(base64.b64decode(inline["data"]))

                if "inputTranscription" in server_content:
                    text = server_content["inputTranscription"].get("text", "")
                    if text and self.on_input_transcript:
                        await self.on_input_transcript(text)

                if "outputTranscription" in server_content:
                    text = server_content["outputTranscription"].get("text", "")
                    if text and self.on_output_transcript:
                        await self.on_output_transcript(text)

                if server_content.get("turnComplete") and self.on_turn_complete:
                    await self.on_turn_complete()
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[Gemini 3.1 Live] Ulanish yopildi: {e}")
        except Exception as e:
            print(f"[Gemini 3.1 Live] Receive loop error: {e}")

    async def close(self):
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws:
            await self._ws.close()
        print("[Gemini 3.1 Live] Sessiya yopildi")
