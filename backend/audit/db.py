"""
Pluggable Audit Database and Store Interface for RazorGate.
Supports SQLite (default) and PostgreSQL (via opt-in DATABASE_URL configuration).

Maintains auditable, structured decision records for every payment evaluation,
with forward-traceability linking gate decisions to real Razorpay order IDs.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Protocol
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from backend.config import settings

DB_PATH = Path(__file__).parent / "decisions.db"


class DecisionStore(Protocol):
    """Abstract storage interface for audit decision ledger and webhooks."""

    def init_db(self) -> None:
        ...

    def record_decision(
        self,
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
        ...

    def link_order_to_decision(self, audit_id: int, razorpay_order_id: str) -> bool:
        ...

    def get_recent_decisions(
        self,
        limit: int = 50,
        offset: int = 0,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...

    def get_decision_by_id(self, decision_id: int) -> Optional[Dict[str, Any]]:
        ...

    def is_webhook_processed(self, event_id: str) -> bool:
        ...

    def record_webhook_processed(self, event_id: str, event_type: str) -> bool:
        ...

    def get_decision_by_order_id(self, razorpay_order_id: str) -> Optional[Dict[str, Any]]:
        ...

    def update_decision_webhook_status(
        self, razorpay_order_id: str, webhook_status: str
    ) -> Optional[int]:
        ...


class SQLiteDecisionStore:
    """SQLite reference implementation of DecisionStore."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        conn = self.get_connection()
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
        self,
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
        self.init_db()
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        evidence_json = json.dumps(evidence)

        conn = self.get_connection()
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

    def link_order_to_decision(self, audit_id: int, razorpay_order_id: str) -> bool:
        self.init_db()
        conn = self.get_connection()
        cursor = conn.execute(
            "UPDATE decisions SET razorpay_order_id = ? WHERE id = ?",
            (razorpay_order_id, audit_id),
        )
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        return rows_affected > 0

    def get_recent_decisions(
        self,
        limit: int = 50,
        offset: int = 0,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self.init_db()
        conn = self.get_connection()

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

    def get_decision_by_id(self, decision_id: int) -> Optional[Dict[str, Any]]:
        self.init_db()
        conn = self.get_connection()
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

    def is_webhook_processed(self, event_id: str) -> bool:
        self.init_db()
        conn = self.get_connection()
        row = conn.execute("SELECT 1 FROM processed_webhooks WHERE event_id = ?", (event_id,)).fetchone()
        conn.close()
        return row is not None

    def record_webhook_processed(self, event_id: str, event_type: str) -> bool:
        self.init_db()
        conn = self.get_connection()
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

    def get_decision_by_order_id(self, razorpay_order_id: str) -> Optional[Dict[str, Any]]:
        self.init_db()
        conn = self.get_connection()
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

    def update_decision_webhook_status(
        self, razorpay_order_id: str, webhook_status: str
    ) -> Optional[int]:
        self.init_db()
        now_ts = datetime.now(timezone.utc).isoformat()
        conn = self.get_connection()
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


class PostgresDecisionStore:
    """PostgreSQL implementation of DecisionStore using SQLAlchemy."""

    def __init__(self, db_url: str) -> None:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        self.db_url = db_url
        self.engine = create_engine(self.db_url, pool_pre_ping=True)

    def init_db(self) -> None:
        pk_ddl = "INTEGER PRIMARY KEY AUTOINCREMENT" if self.engine.dialect.name == "sqlite" else "SERIAL PRIMARY KEY"
        with self.engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS decisions (
                    id {pk_ddl},
                    timestamp VARCHAR(255) NOT NULL,
                    agent_id VARCHAR(255) NOT NULL,
                    amount_paise BIGINT NOT NULL,
                    amount_inr DOUBLE PRECISION NOT NULL,
                    verdict VARCHAR(50) NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    primary_factor VARCHAR(255) NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    razorpay_order_id VARCHAR(255),
                    webhook_status VARCHAR(255),
                    webhook_confirmed_at VARCHAR(255)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS processed_webhooks (
                    event_id VARCHAR(255) PRIMARY KEY,
                    event_type VARCHAR(255) NOT NULL,
                    processed_at VARCHAR(255) NOT NULL
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_decisions_agent ON decisions (agent_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions (timestamp DESC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_decisions_rzp_order ON decisions (razorpay_order_id)"))

    def record_decision(
        self,
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
        self.init_db()
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        evidence_json = json.dumps(evidence)

        with self.engine.begin() as conn:
            res = conn.execute(
                text("""
                INSERT INTO decisions (
                    timestamp, agent_id, amount_paise, amount_inr,
                    verdict, confidence, primary_factor, summary, evidence_json, razorpay_order_id
                ) VALUES (
                    :ts, :agent_id, :amount_paise, :amount_inr,
                    :verdict, :confidence, :primary_factor, :summary, :evidence_json, :razorpay_order_id
                )
                """),
                {
                    "ts": ts,
                    "agent_id": agent_id,
                    "amount_paise": amount_paise,
                    "amount_inr": amount_inr,
                    "verdict": verdict,
                    "confidence": confidence,
                    "primary_factor": primary_factor,
                    "summary": summary,
                    "evidence_json": evidence_json,
                    "razorpay_order_id": razorpay_order_id,
                },
            )
            row_id = getattr(res, "lastrowid", None)
            if row_id:
                return row_id

            max_res = conn.execute(text("SELECT MAX(id) FROM decisions"))
            max_row = max_res.fetchone()
            return max_row[0] if max_row and max_row[0] else 0

    def link_order_to_decision(self, audit_id: int, razorpay_order_id: str) -> bool:
        self.init_db()
        with self.engine.begin() as conn:
            res = conn.execute(
                text("UPDATE decisions SET razorpay_order_id = :razorpay_order_id WHERE id = :audit_id"),
                {"razorpay_order_id": razorpay_order_id, "audit_id": audit_id},
            )
            return res.rowcount > 0

    def get_recent_decisions(
        self,
        limit: int = 50,
        offset: int = 0,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self.init_db()
        with self.engine.connect() as conn:
            if agent_id:
                res = conn.execute(
                    text("SELECT * FROM decisions WHERE agent_id = :agent_id ORDER BY id DESC LIMIT :limit OFFSET :offset"),
                    {"agent_id": agent_id, "limit": limit, "offset": offset},
                )
            else:
                res = conn.execute(
                    text("SELECT * FROM decisions ORDER BY id DESC LIMIT :limit OFFSET :offset"),
                    {"limit": limit, "offset": offset},
                )
            rows = [dict(r._mapping) for r in res.fetchall()]

        for r in rows:
            try:
                r["evidence"] = json.loads(r["evidence_json"])
            except Exception:
                r["evidence"] = {}
        return rows

    def get_decision_by_id(self, decision_id: int) -> Optional[Dict[str, Any]]:
        self.init_db()
        with self.engine.connect() as conn:
            res = conn.execute(text("SELECT * FROM decisions WHERE id = :id"), {"id": decision_id})
            row = res.fetchone()
            if not row:
                return None
            item = dict(row._mapping)
            try:
                item["evidence"] = json.loads(item["evidence_json"])
            except Exception:
                item["evidence"] = {}
            return item

    def is_webhook_processed(self, event_id: str) -> bool:
        self.init_db()
        with self.engine.connect() as conn:
            res = conn.execute(text("SELECT 1 FROM processed_webhooks WHERE event_id = :event_id"), {"event_id": event_id})
            return res.fetchone() is not None

    def record_webhook_processed(self, event_id: str, event_type: str) -> bool:
        self.init_db()
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO processed_webhooks (event_id, event_type, processed_at) VALUES (:event_id, :event_type, :now_ts)"),
                    {"event_id": event_id, "event_type": event_type, "now_ts": now_ts},
                )
                return True
        except IntegrityError:
            return False

    def get_decision_by_order_id(self, razorpay_order_id: str) -> Optional[Dict[str, Any]]:
        self.init_db()
        with self.engine.connect() as conn:
            res = conn.execute(text("SELECT * FROM decisions WHERE razorpay_order_id = :razorpay_order_id"), {"razorpay_order_id": razorpay_order_id})
            row = res.fetchone()
            if not row:
                return None
            item = dict(row._mapping)
            try:
                item["evidence"] = json.loads(item["evidence_json"])
            except Exception:
                item["evidence"] = {}
            return item

    def update_decision_webhook_status(
        self, razorpay_order_id: str, webhook_status: str
    ) -> Optional[int]:
        self.init_db()
        now_ts = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as conn:
            res = conn.execute(
                text("SELECT id FROM decisions WHERE razorpay_order_id = :razorpay_order_id"),
                {"razorpay_order_id": razorpay_order_id},
            )
            row = res.fetchone()
            if not row:
                return None
            audit_id = row[0]
            conn.execute(
                text("UPDATE decisions SET webhook_status = :webhook_status, webhook_confirmed_at = :now_ts WHERE id = :audit_id"),
                {"webhook_status": webhook_status, "now_ts": now_ts, "audit_id": audit_id},
            )
            return audit_id


def get_decision_store() -> DecisionStore:
    """
    Factory returning appropriate DecisionStore backend.
    Defaults to SQLiteDecisionStore when DATABASE_URL is unset or empty.
    """
    db_url = settings.database_url
    if db_url and (db_url.startswith("postgresql") or db_url.startswith("postgres")):
        return PostgresDecisionStore(db_url)
    return SQLiteDecisionStore()


# High-level module helper functions (delegates to active DecisionStore backend)

def get_db_connection():
    store = get_decision_store()
    if isinstance(store, SQLiteDecisionStore):
        return store.get_connection()
    raise RuntimeError("get_db_connection() is specific to SQLite mode. Use get_decision_store().")


def init_db():
    get_decision_store().init_db()


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
    return get_decision_store().record_decision(
        agent_id=agent_id,
        amount_paise=amount_paise,
        amount_inr=amount_inr,
        verdict=verdict,
        confidence=confidence,
        primary_factor=primary_factor,
        summary=summary,
        evidence=evidence,
        timestamp=timestamp,
        razorpay_order_id=razorpay_order_id,
    )


def link_order_to_decision(audit_id: int, razorpay_order_id: str) -> bool:
    return get_decision_store().link_order_to_decision(audit_id, razorpay_order_id)


def get_recent_decisions(
    limit: int = 50,
    offset: int = 0,
    agent_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return get_decision_store().get_recent_decisions(limit=limit, offset=offset, agent_id=agent_id)


def get_decision_by_id(decision_id: int) -> Optional[Dict[str, Any]]:
    return get_decision_store().get_decision_by_id(decision_id)


def is_webhook_processed(event_id: str) -> bool:
    return get_decision_store().is_webhook_processed(event_id)


def record_webhook_processed(event_id: str, event_type: str) -> bool:
    return get_decision_store().record_webhook_processed(event_id, event_type)


def get_decision_by_order_id(razorpay_order_id: str) -> Optional[Dict[str, Any]]:
    return get_decision_store().get_decision_by_order_id(razorpay_order_id)


def update_decision_webhook_status(
    razorpay_order_id: str, webhook_status: str
) -> Optional[int]:
    return get_decision_store().update_decision_webhook_status(razorpay_order_id, webhook_status)
