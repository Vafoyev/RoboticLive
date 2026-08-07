import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def get_gemini_api_key():
    load_dotenv(BASE_DIR / ".env", override=True)
    return os.getenv("GEMINI_API_KEY", "")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)
SUBMISSIONS_DB_PATH = DB_DIR / "submissions.json"
RAG_DB_PATH = BASE_DIR / "rag_knowledge.db"
