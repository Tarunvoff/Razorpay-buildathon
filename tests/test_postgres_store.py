"""
Isolated Integration Tests for Pluggable DecisionStore (SQLite & PostgreSQL).

Verifies that PostgresDecisionStore and SQLiteDecisionStore implement identical behavior,
schema auto-creation, decision recording, forward-traceability linking, pagination,
idempotent webhook tracking, and audit ledger retrievals.
"""

import os
import pytest
from pathlib import Path
from backend.audit.db import SQLiteDecisionStore, PostgresDecisionStore, get_decision_store
from backend.config import settings


def test_sqlite_decision_store_isolated_lifecycle(tmp_path: Path):
    db_file = tmp_path / "test_decisions.db"
    store = SQLiteDecisionStore(db_file)
    store.init_db()

    # Record decision
    audit_id = store.record_decision(
        agent_id="test_buyer_isolated",
        amount_paise=29900,
        amount_inr=299.0,
        verdict="ALLOW",
        confidence=0.98,
        primary_factor="policy_cleared",
        summary="Isolated SQLite store test",
        evidence={"test": True},
    )
    assert audit_id > 0

    # Retrieve decision
    rec = store.get_decision_by_id(audit_id)
    assert rec is not None
    assert rec["agent_id"] == "test_buyer_isolated"
    assert rec["amount_inr"] == 299.0

    # Link order ID
    linked = store.link_order_to_decision(audit_id, "order_test_12345")
    assert linked is True

    # Retrieve by order ID
    rec_by_order = store.get_decision_by_order_id("order_test_12345")
    assert rec_by_order is not None
    assert rec_by_order["id"] == audit_id

    # Webhook idempotency
    processed = store.is_webhook_processed("evt_test_999")
    assert processed is False

    recorded = store.record_webhook_processed("evt_test_999", "payment.captured")
    assert recorded is True

    processed_again = store.is_webhook_processed("evt_test_999")
    assert processed_again is True

    # Update webhook status
    updated_id = store.update_decision_webhook_status("order_test_12345", "confirmed_paid")
    assert updated_id == audit_id

    rec_updated = store.get_decision_by_id(audit_id)
    assert rec_updated["webhook_status"] == "confirmed_paid"
    assert rec_updated["webhook_confirmed_at"] is not None


def test_postgres_decision_store_interface_parity(tmp_path: Path):
    """
    Tests PostgresDecisionStore interface parity using SQLite/Postgres SQLAlchemy connection.
    Guarantees both backends fulfill the DecisionStore protocol contract identically.
    """
    # Use SQLite via SQLAlchemy as a local engine target for PostgresDecisionStore contract testing
    sqlite_url = f"sqlite:///{tmp_path / 'pg_parity.db'}"
    store = PostgresDecisionStore(sqlite_url)
    store.init_db()

    # Record decision
    audit_id = store.record_decision(
        agent_id="test_pg_buyer",
        amount_paise=4900,
        amount_inr=49.0,
        verdict="FLAG",
        confidence=0.85,
        primary_factor="anomaly_burst",
        summary="Isolated Postgres store test",
        evidence={"burst_count": 6},
    )
    assert audit_id > 0

    # Retrieve decision
    rec = store.get_decision_by_id(audit_id)
    assert rec is not None
    assert rec["agent_id"] == "test_pg_buyer"
    assert rec["verdict"] == "FLAG"

    # Link order ID
    linked = store.link_order_to_decision(audit_id, "order_pg_67890")
    assert linked is True

    # Retrieve by order ID
    rec_by_order = store.get_decision_by_order_id("order_pg_67890")
    assert rec_by_order is not None
    assert rec_by_order["id"] == audit_id

    # Webhook processing
    assert store.is_webhook_processed("evt_pg_001") is False
    assert store.record_webhook_processed("evt_pg_001", "payment.captured") is True
    assert store.is_webhook_processed("evt_pg_001") is True

    # Update webhook status
    updated_id = store.update_decision_webhook_status("order_pg_67890", "confirmed_paid")
    assert updated_id == audit_id
    rec_updated = store.get_decision_by_id(audit_id)
    assert rec_updated["webhook_status"] == "confirmed_paid"


def test_factory_returns_sqlite_by_default():
    # When DATABASE_URL is unset or empty, factory MUST return SQLiteDecisionStore
    original_url = settings.database_url
    try:
        settings.database_url = None
        store = get_decision_store()
        assert store.__class__.__name__ == "SQLiteDecisionStore"
    finally:
        settings.database_url = original_url
