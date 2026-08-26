import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import json

DB_PATH = Path(__file__).parent / "decisions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            request_json TEXT NOT NULL,
            verdict TEXT NOT NULL,
            confidence REAL,
            explanation TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_decision(request: dict, verdict: str, confidence: float, explanation: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO decisions (ts, request_json, verdict, confidence, explanation) VALUES (?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), json.dumps(request), verdict, confidence, explanation),
    )
    conn.commit()
    conn.close()

def get_recent_decisions(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
