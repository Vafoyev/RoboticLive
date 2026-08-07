import sqlite3
from typing import List, Optional
from backend.config import DB_DIR
from backend.models import CitizenSubmission

DB_PATH = DB_DIR / "submissions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            mahalla TEXT NOT NULL,
            address TEXT,
            topic TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_submission(sub: CitizenSubmission) -> CitizenSubmission:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO submissions (id, type, full_name, phone, mahalla, address, topic, description, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sub.id, sub.type, sub.full_name, sub.phone, sub.mahalla,
        sub.address, sub.topic, sub.description, sub.status, sub.timestamp
    ))
    conn.commit()
    conn.close()
    return sub

def get_all_submissions(limit: int = 100) -> List[CitizenSubmission]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, type, full_name, phone, mahalla, address, topic, description, status, timestamp FROM submissions ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append(CitizenSubmission(
            id=r[0], type=r[1], full_name=r[2], phone=r[3],
            mahalla=r[4], address=r[5], topic=r[6], description=r[7],
            status=r[8], timestamp=r[9]
        ))
    return results

def update_submission_status(sub_id: str, new_status: str) -> bool:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE submissions SET status = ? WHERE id = ?", (new_status, sub_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
