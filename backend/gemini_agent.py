import os
import re
from pathlib import Path
from typing import Dict, Any, List
from backend.config import get_gemini_api_key, BASE_DIR
from backend.rag_engine import search_rag_context

GEMINI_MODEL_VERSION = "gemini-2.0-flash"

def load_system_prompt_guidelines() -> str:
    prompt_path = BASE_DIR / "rag" / "ai agent .md fayllar uchun" / "system-prompt.txt"
    if not prompt_path.exists():
        for root, dirs, files in os.walk(BASE_DIR / "rag"):
            if "system-prompt.txt" in files:
                prompt_path = Path(root) / "system-prompt.txt"
                break

    if prompt_path.exists():
        try:
            with open(prompt_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read().strip()
        except Exception as e:
            print(f"Error loading system prompt: {e}")

    return (
        "Siz Urganch shahrining 'Aqlli shahar' va 'Aqlli mahalla' tizimlari uchun ishlaydigan "
        "ovozli va matnli AI yordamchisiz. Nomingiz — 'Aqlli Yordamchi'. "
        "Siz fuqarolar bilan tabiiy, hurmatli, samimiy, batafsil va xushmuomala o'zbek tilida muloqot qilasiz."
    )

def generate_ai_response(user_query: str, chat_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    rag_context = search_rag_context(user_query)
    system_rules = load_system_prompt_guidelines()
    api_key = get_gemini_api_key()

    system_instruction = (
        f"=== TIZIMNING ASOSIY PROMPT QOIDALARI (SYSTEM PROMPT) ===\n"
        f"{system_rules}\n\n"
        f"=== QAT'IY MULOQOT VA SUHBAT QOIDALARI ===\n"
        f"1. Siz Urganch shahrining yuksak intellektli, bilimdon, samimiy va xushmuomala 'Aqlli Yordamchi' suhbatdoshisiz.\n"
        f"2. Suhbatdosh bilan xuddi dono, samimiy va jonli do'st yoki maslahatchidek go'zal, boy o'zbek adabiy tilida suhbatlashing.\n"
        f"3. Savollarga yuzaki yoki mexanik tarzda qisqa javob bermang. Fuqaroga kerakli ma'lumotlarni to'liq, batafsil, tushunarli, bosqichma-bosqich va foydali tarzda bayon qiling.\n"
        f"4. Agarda RAG Bilimlar Bazasidan rasmiy faktlar, rahbarlar, xizmatlar, statistika yoki ro'yxatlar mavjud bo'lsa, ularni to'liq qamrab oling.\n"
        f"5. Ovozli ijro etish (Speech) uchun raqamlarni aniq va tushunarli so'zlar bilan ifodalang.\n"
    )

    if rag_context:
        prompt_with_rag = (
            f"{system_instruction}\n"
            f"=== RASMIY BILIMLAR BAZASI (RAG CONTEXT) ===\n"
            f"{rag_context}\n"
            f"===========================================\n\n"
            f"Foydalanuvchi so'rovi: {user_query}\n"
            f"Aqlli Yordamchi javobi:"
        )
    else:
        prompt_with_rag = (
            f"{system_instruction}\n"
            f"Foydalanuvchi so'rovi: {user_query}\n"
            f"Aqlli Yordamchi javobi:"
        )

    if api_key and api_key != "your_gemini_api_key_here":
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=GEMINI_MODEL_VERSION,
                contents=prompt_with_rag,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                )
            )
            if response and response.text:
                return {
                    "text": response.text,
                    "rag_used": bool(rag_context),
                    "context_snippet": rag_context[:300] if rag_context else None,
                    "model_used": GEMINI_MODEL_VERSION,
                    "status": "success"
                }
        except Exception as e:
            print(f"Gemini 2.5 Flash API Call Error: {e}")

    fallback_text = create_smart_fallback(user_query, rag_context)
    return {
        "text": fallback_text,
        "rag_used": bool(rag_context),
        "context_snippet": rag_context[:300] if rag_context else None,
        "model_used": f"{GEMINI_MODEL_VERSION} (RAG Local)",
        "status": "fallback"
    }

def create_smart_fallback(query: str, rag_context: str) -> str:
    q_lower = query.lower()
    
    if any(w in q_lower for w in ["salom", "assalomu alaykum", "xayrli"]):
        return "Assalomu alaykum! Men Urganch shahrining 'Aqlli Yordamchi' AI tizimiman. Sizga qanday yordam bera olaman?"
    
    if any(w in q_lower for w in ["shikoyat", "muammo", "buzuq", "chiroq", "yo'l", "gaz", "suv"]):
        return "Tushundim. Muammoni ko'rib chiqish va mas'ullarga yuborish uchun 'Shikoyat yuborish' tugmasi orqali arizangizni rasmiylashtiring."

    if any(w in q_lower for w in ["taklif", "g'oya"]):
        return "Ajoyib taklif! Mahallamiz va shahrimizni rivojlantirish bo'yicha g'oyalaringiz bo'lsa, 'Taklif bildirish' bo'limida qoldiring."

    if rag_context:
        lines = rag_context.split('\n')
        clean_lines = [l for l in lines if not l.startswith('📌') and not l.startswith('---')]
        return "\n".join(clean_lines[:8]).strip()

    return f"Sizning savolingiz: '{query}'. Ushbu masala bo'yicha bilimlar bazasidan qidiruv o'tkazildi. Qo'shimcha ma'lumot olish yoki rasmiy murojaat qoldirish uchun xizmatlarimizdan foydalanishingiz mumkin."
