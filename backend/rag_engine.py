import sqlite3
import re
import functools
from pathlib import Path
from typing import List, Dict, Any
from backend.config import BASE_DIR, RAG_DB_PATH
from backend.models import KnowledgeDocument

UZBEK_STOPWORDS = {
    'va', 'bilan', 'uchun', 'haqda', 'haqida', 'deb', 'ham', 'emas', 'u', 'bu', 'shu', 
    'oson', 'kerak', 'bor', 'yoq', 'qanday', 'qaysi', 'nima', 'kim', 'boshqa', 'ha'
}

def normalize_uzbek_stem(word: str) -> str:
    """Normalize Uzbek word by stripping common grammatical suffixes."""
    word = word.lower()
    suffixes = [
        'larning', 'larining', 'lardagi', 'lardanda', 'larga', 'larda', 'lardan', 'larni', 'larim', 'lariz',
        'sining', 'sidan', 'siga', 'sida', 'sini', 'ining', 'idan', 'iga', 'ida', 'ini',
        'ning', 'dan', 'ga', 'da', 'ni', 'si', 'i', 'lik', 'li', 'siz', 'lar'
    ]
    for s in suffixes:
        if word.endswith(s) and len(word) - len(s) >= 3:
            return word[:-len(s)]
    return word

def get_db_connection():
    conn = sqlite3.connect(RAG_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_rag_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            content TEXT,
            source_file TEXT,
            timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

def seed_initial_knowledge(force_reseed: bool = False):
    init_rag_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not force_reseed:
        cursor.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE category = 'tool_json'")
        tool_count = cursor.fetchone()[0]
        if tool_count > 0:
            conn.close()
            return

    # Clear old chunks for clean re-seeding
    cursor.execute("DELETE FROM knowledge_chunks")
    conn.commit()
    
    rag_dir = BASE_DIR / "rag" / "ai agent .md fayllar uchun"
    if not rag_dir.exists():
        for d in (BASE_DIR / "rag").iterdir():
            if d.is_dir() and "ai agent" in d.name.lower():
                rag_dir = d
                break
                
    if rag_dir.exists():
        files = list(rag_dir.glob("*.md")) + list(rag_dir.glob("*.txt"))
        
        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                
                fn_lower = filepath.name.lower()
                if "tool" in fn_lower or "json" in fn_lower or "config" in fn_lower:
                    category = "tool_json"
                elif "rahbar" in fn_lower or "president" in fn_lower or "vazir" in fn_lower or "hokim" in fn_lower:
                    category = "rahbarlar"
                elif "yettilik" in fn_lower:
                    category = "yettilik"
                elif "shahar" in fn_lower or "mahalla" in fn_lower:
                    category = "shahar_mahalla"
                elif "soliq" in fn_lower or "yoshlar" in fn_lower:
                    category = "soliq_ijtimoiy"
                elif "uy" in fn_lower:
                    category = "uy_joy"
                elif "catalog" in fn_lower or "order" in fn_lower or "object" in fn_lower:
                    category = "catalog"
                else:
                    category = "general"

                # Text / JSON / config files
                if filepath.suffix == ".txt" or "json" in fn_lower:
                    doc_id = f"{filepath.stem}_0"
                    title = f"{filepath.stem} (Tizim va Tool JSON ma'lumotlari)"
                    cursor.execute("""
                        INSERT OR REPLACE INTO knowledge_chunks (id, title, category, content, source_file, timestamp)
                        VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """, (doc_id, title[:120], category, text, filepath.name))
                    continue

                # Markdown files: split by level 1 or level 2 headers so QA blocks stay together
                sections = re.split(r'\n(?=#{1,2}\s+)', text)
                for idx, sec in enumerate(sections):
                    sec_clean = sec.strip()
                    if not sec_clean:
                        continue

                    lines = [l for l in sec_clean.split('\n') if l.strip()]
                    first_line = lines[0].replace('#', '').strip() if lines else filepath.stem
                    doc_id = f"{filepath.stem}_{idx}"

                    cursor.execute("""
                        INSERT OR REPLACE INTO knowledge_chunks (id, title, category, content, source_file, timestamp)
                        VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """, (doc_id, first_line[:120], category, sec_clean, filepath.name))

            except Exception as e:
                print(f"Error seeding {filepath.name}: {e}")

        conn.commit()
    conn.close()

# Auto-seed on load
seed_initial_knowledge()

@functools.lru_cache(maxsize=256)
def search_rag_context(query: str, limit: int = 4) -> str:
    """
    Optimized RAG Search Engine with BM25 Title Weighting, Stem Normalization, and Memory Caching.
    Returns clean, structured knowledge facts for Gemini 3.1 / 2.0 Live.
    """
    if not query or not query.strip():
        return ""

    tokens = [
        t.lower() for t in re.findall(r'\w+', query)
        if len(t) > 1 and t.lower() not in UZBEK_STOPWORDS
    ]
    if not tokens:
        tokens = [t.lower() for t in re.findall(r'\w+', query) if len(t) > 0]

    stems = [normalize_uzbek_stem(t) for t in tokens]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, category, content, source_file FROM knowledge_chunks")
    rows = cursor.fetchall()
    conn.close()

    scored_chunks = []
    for row in rows:
        title = row['title'].lower()
        content = row['content'].lower()
        score = 0
        
        for t, st in zip(tokens, stems):
            if t in title:
                score += 4.0
            elif st in title:
                score += 3.0

            if t in content:
                score += 1.5
            elif st in content:
                score += 1.0

        if score > 0:
            scored_chunks.append((score, row))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_rows = [item[1] for item in scored_chunks[:limit]]

    if not top_rows:
        return ""

    formatted_context = "=== ANIQ VA TO'LIQ RASMIY BILIMLAR BAZASI MA'LUMOTLARI ===\n"
    for idx, r in enumerate(top_rows, 1):
        formatted_context += f"\n[{idx}] HUJJAT MANBASI: {r['title']} (Kategoriya: {r['category']})\n{r['content'][:3500]}\n"

    return formatted_context.strip()

def add_knowledge_doc(doc: KnowledgeDocument) -> KnowledgeDocument:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO knowledge_chunks (id, title, category, content, source_file, timestamp)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (doc.id, doc.title, doc.category, doc.content, "user_added"))
    conn.commit()
    conn.close()
    search_rag_context.cache_clear()
    return doc

def get_all_knowledge_docs() -> List[KnowledgeDocument]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, category, content, source_file, timestamp FROM knowledge_chunks")
    rows = cursor.fetchall()
    conn.close()
    
    docs = []
    for r in rows:
        docs.append(KnowledgeDocument(
            id=r['id'],
            title=r['title'],
            category=r['category'],
            content=r['content'],
            source_file=r['source_file'],
            timestamp=r['timestamp']
        ))
    return docs

def delete_knowledge_doc(doc_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge_chunks WHERE id = ?", (doc_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    search_rag_context.cache_clear()
    return deleted

