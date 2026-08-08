import os
import asyncio
import base64
import json
import websockets
from pathlib import Path
from typing import Optional, Callable
from backend.config import get_gemini_api_key, BASE_DIR
from backend.rag_engine import search_rag_context

MODEL = "models/gemini-2.0-flash-exp"

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
        "Siz Urganch shahri va mahallalarida o'rnatilgan 'Aqlli Yordamchi' sun'iy intellekt AI yordamchisisiz. "
        "Siz ayol kishisiz va nihoyatda nazokatli, samimiy, bilag'on, muloyim va xushmuomala ayol kishi ovozida (Aoede) gapirasiz.\n\n"
        "BATAFSIL VA TO'LIQ MA'LUMOT BERISH QOIDASI (JUDA MUHIM):\n"
        "1. Savollarga hech qachon yuzaki yoki bir jumlada qisqa javob bermang! Fuqaro so'ragan masalani boshidan oxirigacha batafsil, tartibli, bosqichma-bosqich va to'liq tushuntiring.\n"
        "2. Agar RAG bilimlar bazasida tegishli rahbarlar, ro'yxatlar, muddatlar, statistika, telefonlar yoki aniq amallar ko'rsatilgan bo'lsa, ularning barchasini to'liq va erinmasdan bayon qiling.\n"
        "3. Tushuntirishlaringiz tinglovchiga to'liq yechim bersin: qayerga borish kerak, kim mas'ul, qanday tartibda amalga oshiriladi.\n\n"
        "O'ZBEK ADABIY TILI TALAFUZ VA FONETIKA QOIDALARI:\n"
        "1. O'zbek adabiy tilining barcha kelishik va qo'shimchalarini (kelishik: -ning, -ga, -ni, -da, -dan; egalik va nisbat suffikslarini) dona-dona, tiniq va benuqson talaffuz qiling.\n"
        "2. O'zbek alifbosidagi 'O'' va 'O', 'Q' va 'K', 'G'' va 'G', 'X' va 'H' harflarini so'z tarkibida juda aniq va to'g'ri ayting. Tutuq belgisini to'g'ri pauza bilan chiqaring.\n"
        "3. Urg'u va intonatsiyani o'zbek adabiy tili me'yorlariga qat'iy rioya qilgan holda, samimiy, vazmin va jozibador bering.\n"
        "4. Salomlashuvni ravon va jozibali qilib: \"Assalomu alaykum! Men Urganch shahrining 'Aqlli Yordamchi' AI tizimiman. Sizga qanday yordam bera olaman?\" deb aytasiz.\n"
        "5. Har doim o'rta me'yordagi insoniy sur'atda, dona-dona, tushunarli va batafsil gapirasiz.\n\n"
        "Muloqot tartibi va moslashuvchanlik:\n"
        "- AGAR TASHRIFCHI MUROJAAT/MUAMMO AYTSA (suv, gaz, chiroq, shikoyat, kommunal, obodonlashtirish):\n"
        "  Murojaatni tinglab tushunganingizni bildiring va murojaatni rasmiylashtirish uchun ma'lumotlarini (Ismi va familiyasi, Xonadon raqami, Telefon raqami) muloyimlik bilan so'rab oling.\n"
        "- AGAR TASHRIFCHI SAVOL BERSA (Urganch shahri, Mahalla yettiligi, hokim, vazir, yoshlar yetakchisi, Olimpiya mahallasi, soliqlar, uylar, loyihalar haqida):\n"
        "  Savolga darhol to'liq, batafsil, aniq va mazmunli javob bering! Barcha fakt va tafsilotlarni qamrab oling. Shaxsiy ma'lumotlarini so'rab majburlamang.\n\n"
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
        query_hint=""
    ):
        self._ws = None
        self._recv_task = None
        self.on_audio_chunk = on_audio_chunk
        self.on_input_transcript = on_input_transcript
        self.on_output_transcript = on_output_transcript
        self.on_turn_complete = on_turn_complete
        self.on_interrupted = on_interrupted
        self.query_hint = query_hint

    async def connect(self):
        api_key = get_gemini_api_key()
        ws_uri = (
            "wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
            f"?key={api_key}"
        )

        print("[Gemini 3.1 Live] WebSocket'ga ulanilmoqda...")
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
                                "voiceName": "Aoede"
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

        print("[Gemini 3.1 Live] Ulanildi, O'zbek adabiy fonetika qoidalari bilan Aoede sozlandi")
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
