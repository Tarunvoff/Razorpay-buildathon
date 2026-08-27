"""
SQLite audit database for RazorGate.
Persists auditable, structured decision records for every payment evaluation.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent / "decisions.db"


def get_db_connection() -> sqlite3.Connection:
    """Creates a configured connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes SQLite schema for the decision audit ledger with auto-migration."""
    conn = get_db_connection()
    table_info = conn.execute("PRAGMA table_info(decisions)").fetchall()
    column_names = {row[1] for row in table_info}

    if table_info and "agent_id" not in column_names:
        # Legacy Phase 1 schema detected -> migrate to full Phase 5 schema
        conn.execute("DROP TABLE decisions")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            amount_paise INTEGER NOT NULL,
            amount_inr REAL NOT NULL,
            verdict TEXT NOT NULL,
            confidence REAL NOT NULL,
            primary_factor TEXT NOT NULL,
            summary TEXT NOT NULL,
            evidence_json TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_agent ON decisions (agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions (timestamp DESC)")
    conn.commit()
    conn.close()


def record_decision(
    agent_id: str,
    amount_paise: int,
    amount_inr: float,
    verdict: str,
    confidence: float,
    primary_factor: str,
    summary: str,
    evidence: Dict[str, Any],
    timestamp: Optional[str] = None,
) -> int:
    """
    Persists a decision record into the SQLite ledger.
    Returns the inserted row ID.
    """
    init_db()
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    evidence_json = json.dumps(evidence)

    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO decisions (
            timestamp, agent_id, amount_paise, amount_inr,
            verdict, confidence, primary_factor, summary, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            agent_id,
            amount_paise,
            amount_inr,
            verdict,
            confidence,
            primary_factor,
            summary,
            evidence_json,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id or 0


def log_decision(
    request: dict,
    verdict: str,
    confidence: float,
    explanation: str,
    primary_factor: str = "policy_evaluation",
    evidence: Optional[Dict[str, Any]] = None,
) -> int:
    """Backwards-compatible wrapper for legacy callers."""
    amount_paise = int(request.get("amount", 0))
    amount_inr = float(request.get("amount_inr", amount_paise / 100.0))
    agent_id = str(request.get("agent_id") or request.get("session_id") or "default_agent")
    evidence_data = evidence or {"request": request, "explanation": explanation}

    return record_decision(
        agent_id=agent_id,
        amount_paise=amount_paise,
        amount_inr=amount_inr,
        verdict=verdict,
        confidence=confidence,
        primary_factor=primary_factor,
        summary=explanation,
        evidence=evidence_data,
    )


def get_recent_decisions(
    limit: int = 50,
    offset: int = 0,
    agent_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves paginated decision records from the audit ledger.
    """
    init_db()
    conn = get_db_connection()

    if agent_id:
        rows = conn.execute(
            """
            SELECT * FROM decisions
            WHERE agent_id = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (agent_id, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM decisions
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    conn.close()

    results = []
    for r in rows:
        item = dict(r)
        try:
            item["evidence"] = json.loads(item["evidence_json"])
        except Exception:
            item["evidence"] = {}
        results.append(item)
    return results


def get_decision_by_id(decision_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single decision record by ID."""
    init_db()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    try:
        item["evidence"] = json.loads(item["evidence_json"])
    except Exception:
        item["evidence"] = {}
    return item
