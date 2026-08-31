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

    # Auto-migrate razorpay_order_id, webhook_status, webhook_confirmed_at if not present
    if table_info and "razorpay_order_id" not in column_names:
        try:
            conn.execute("ALTER TABLE decisions ADD COLUMN razorpay_order_id TEXT")
        except Exception:
            pass
    if table_info and "webhook_status" not in column_names:
        try:
            conn.execute("ALTER TABLE decisions ADD COLUMN webhook_status TEXT")
        except Exception:
            pass
    if table_info and "webhook_confirmed_at" not in column_names:
        try:
            conn.execute("ALTER TABLE decisions ADD COLUMN webhook_confirmed_at TEXT")
        except Exception:
            pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_webhooks (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            processed_at TEXT NOT NULL
        )
    """)

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


def is_webhook_processed(event_id: str) -> bool:
    """Checks if a webhook event_id has already been processed (idempotency check)."""
    init_db()
    conn = get_db_connection()
    row = conn.execute("SELECT 1 FROM processed_webhooks WHERE event_id = ?", (event_id,)).fetchone()
    conn.close()
    return row is not None


def record_webhook_processed(event_id: str, event_type: str) -> bool:
    """Records a webhook event_id as processed in the database."""
    init_db()
    conn = get_db_connection()
    now_ts = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            "INSERT INTO processed_webhooks (event_id, event_type, processed_at) VALUES (?, ?, ?)",
            (event_id, event_type, now_ts),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_decision_by_order_id(razorpay_order_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single decision record by Razorpay Order ID."""
    init_db()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM decisions WHERE razorpay_order_id = ?", (razorpay_order_id,)).fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    try:
        item["evidence"] = json.loads(item["evidence_json"])
    except Exception:
        item["evidence"] = {}
    return item


def update_decision_webhook_status(razorpay_order_id: str, webhook_status: str) -> Optional[int]:
    """
    Updates the webhook_status and webhook_confirmed_at fields for a decision matching razorpay_order_id.
    Returns the updated decision audit_id if found, or None if no matching decision row.
    """
    init_db()
    now_ts = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM decisions WHERE razorpay_order_id = ?", (razorpay_order_id,)).fetchone()
    if not row:
        conn.close()
        return None
    audit_id = row["id"]
    conn.execute(
        "UPDATE decisions SET webhook_status = ?, webhook_confirmed_at = ? WHERE id = ?",
        (webhook_status, now_ts, audit_id),
    )
    conn.commit()
    conn.close()
    return audit_id

