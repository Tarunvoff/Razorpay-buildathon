"""
SQLite audit database for RazorGate.
Persists auditable, structured decision records for every payment evaluation,
with forward-traceability linking gate decisions to real Razorpay order IDs.
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
        conn.execute("DROP TABLE decisions")
        table_info = []
        column_names = set()

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
            evidence_json TEXT NOT NULL,
            razorpay_order_id TEXT
        )
    """)

    # Auto-migrate razorpay_order_id if not present
    if table_info and "razorpay_order_id" not in column_names:
        try:
            conn.execute("ALTER TABLE decisions ADD COLUMN razorpay_order_id TEXT")
        except Exception:
            pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_agent ON decisions (agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions (timestamp DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_rzp_order ON decisions (razorpay_order_id)")
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
    razorpay_order_id: Optional[str] = None,
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
            verdict, confidence, primary_factor, summary, evidence_json, razorpay_order_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            razorpay_order_id,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id or 0


def link_order_to_decision(audit_id: int, razorpay_order_id: str) -> bool:
    """
    Links a downstream Razorpay order ID back to the originating gate decision row.
    Enables forward-traceability from decision -> execution.
    """
    init_db()
    conn = get_db_connection()
    cursor = conn.execute(
        "UPDATE decisions SET razorpay_order_id = ? WHERE id = ?",
        (razorpay_order_id, audit_id),
    )
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


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
