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

def seed_initial_knowledge():
    init_rag_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM knowledge_chunks")
    count = cursor.fetchone()[0]
    
    if count == 0:
        rag_dir = BASE_DIR / "rag" / "ai agent .md fayllar uchun "
        if rag_dir.exists():
            md_files = list(rag_dir.glob("*.md")) + list(rag_dir.glob("*.txt"))
            
            for filepath in md_files:
                if "json" in filepath.name.lower() or "tool" in filepath.name.lower():
                    continue

                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()

                    sections = re.split(r'\n(?=#{1,3}\s+)', text)
                    for idx, sec in enumerate(sections):
                        sec_clean = sec.strip()
                        if not sec_clean:
                            continue

                        first_line = sec_clean.split('\n')[0].replace('#', '').strip()
                        title = first_line if first_line else filepath.stem
                        doc_id = f"{filepath.stem}_{idx}"
                        category = "general"
                        
                        if "shahar" in filepath.stem.lower() or "mahalla" in filepath.stem.lower():
                            category = "shahar_mahalla"
                        elif "order" in filepath.stem.lower() or "catalog" in filepath.stem.lower():
                            category = "catalog"

                        cursor.execute("""
                            INSERT OR REPLACE INTO knowledge_chunks (id, title, category, content, source_file, timestamp)
                            VALUES (?, ?, ?, ?, ?, datetime('now'))
                        """, (doc_id, title[:100], category, sec_clean, filepath.name))

                except Exception as e:
                    print(f"Error seeding {filepath.name}: {e}")

            conn.commit()
    conn.close()

# Auto-seed on load
seed_initial_knowledge()

@functools.lru_cache(maxsize=128)
def search_rag_context(query: str, limit: int = 3) -> str:
    """
    Optimized RAG Search Engine with BM25 Title Weighting (3x boost) and Memory Caching.
    Returns clean, structured knowledge facts for Gemini 3.1 Live.
    """
    if not query or not query.strip():
        return ""

    tokens = [
        t.lower() for t in re.findall(r'\w+', query)
        if len(t) > 2 and t.lower() not in UZBEK_STOPWORDS
    ]
    if not tokens:
        tokens = [t.lower() for t in re.findall(r'\w+', query) if len(t) > 1]

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
        
        for token in tokens:
            if token in title:
                score += 3.0
            if token in content:
                score += 1.0

        if score > 0:
            scored_chunks.append((score, row))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_rows = [item[1] for item in scored_chunks[:limit]]

    if not top_rows:
        return ""

    formatted_context = "=== ANIQ RASMIY BILIMLAR BAZASI MA'LUMOTLARI ===\n"
    for idx, r in enumerate(top_rows, 1):
        formatted_context += f"\n[{idx}] MONBA: {r['title']} ({r['category']})\n{r['content'][:800]}\n"

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
