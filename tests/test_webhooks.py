"""
Razorpay Webhook Verification & Idempotency Test Suite.

Tests:
1. Valid HMAC-SHA256 signature processing for payment.captured and audit ledger update.
2. Idempotent duplicate event_id processing (skips re-update).
3. Invalid signature rejection (HTTP 400 Bad Request).
4. payment.failed event handling.
"""

import hashlib
import hmac
import json
import time
from fastapi.testclient import TestClient

from backend.audit.db import (
    get_decision_by_order_id,
    init_db,
    record_decision,
)
from backend.config import settings
from backend.control.app import app

client = TestClient(app)


def test_webhook_valid_signature_payment_captured_updates_audit_ledger():
    """
    Test 1: Valid webhook signature processing.
    Constructs a signed payment.captured webhook payload, sends it to POST /webhooks/razorpay,
    verifies HTTP 200, and asserts that the audit ledger decision row is updated to 'confirmed_paid'.
    Re-posting the same event_id asserts idempotent 'already_processed' response.
    """
    init_db()
    order_id = f"order_wh_captured_{int(time.time())}"
    agent_id = "test_webhook_agent"

    # Seed originating gate decision in DB
    audit_id = record_decision(
        agent_id=agent_id,
        amount_paise=29900,
        amount_inr=299.0,
        verdict="ALLOW",
        confidence=1.0,
        primary_factor="policy_cleared",
        summary="Test decision for webhook confirmation",
        evidence={"test": "webhook_seed"},
        razorpay_order_id=order_id,
    )

    event_id = f"evt_wh_captured_{int(time.time() * 1000)}"
    payload_dict = {
        "entity": "event",
        "account_id": "acc_razorgate_test",
        "event": "payment.captured",
        "event_id": event_id,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_test_{int(time.time())}",
                    "entity": "payment",
                    "amount": 29900,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": order_id,
                    "invoice_id": None,
                    "international": False,
                    "method": "card",
                    "amount_refunded": 0,
                    "refund_status": None,
                    "captured": True,
                    "description": "NVIDIA H100 GPU compute instance",
                    "card_id": "card_test_123",
                    "bank": None,
                    "wallet": None,
                    "vpa": None,
                    "email": "buyer@agent.ai",
                    "contact": "+919876543210",
                    "fee": 598,
                    "tax": 91,
                    "error_code": None,
                    "error_description": None,
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time()),
    }

    raw_payload_bytes = json.dumps(payload_dict).encode("utf-8")
    secret = (settings.razorpay_webhook_secret or "razorgate_webhook_secret_dev").encode("utf-8")
    signature = hmac.new(secret, raw_payload_bytes, hashlib.sha256).hexdigest()

    # 1. Post valid webhook payload
    res = client.post(
        "/webhooks/razorpay",
        content=raw_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    res_data = res.json()
    assert res_data["status"] == "processed"
    assert res_data["payment_status"] == "confirmed_paid"
    assert res_data["audit_id"] == audit_id
    assert res_data["razorpay_order_id"] == order_id

    # Verify audit decision ledger in DB
    updated_record = get_decision_by_order_id(order_id)
    assert updated_record is not None
    assert updated_record["webhook_status"] == "confirmed_paid"
    assert updated_record["webhook_confirmed_at"] is not None

    # 2. Idempotency test: Re-post identical webhook event
    res_duplicate = client.post(
        "/webhooks/razorpay",
        content=raw_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert res_duplicate.status_code == 200
    dup_data = res_duplicate.json()
    assert dup_data["status"] == "already_processed"
    assert dup_data["idempotency_hit"] is True
    assert dup_data["event_id"] == event_id


def test_webhook_invalid_signature_rejection():
    """
    Test 2: Invalid signature rejection.
    Constructs a webhook payload with a tampered / invalid X-Razorpay-Signature header,
    posts to POST /webhooks/razorpay, and asserts HTTP 400 Bad Request.
    """
    payload_dict = {
        "entity": "event",
        "account_id": "acc_razorgate_test",
        "event": "payment.captured",
        "event_id": f"evt_tampered_{int(time.time())}",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_tampered_123",
                    "order_id": "order_tampered_123",
                    "status": "captured",
                }
            }
        },
    }

    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    forged_signature = "bad_forged_hmac_signature_00000000000000000000000000000000"

    res = client.post(
        "/webhooks/razorpay",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": forged_signature,
        },
    )

    assert res.status_code == 400
    assert "Invalid Razorpay webhook signature" in res.json()["detail"]


def test_webhook_payment_failed_event():
    """
    Test 3: payment.failed event handling.
    Posts a signed payment.failed webhook payload and asserts the decision record
    is updated to 'payment_failed'.
    """
    init_db()
    order_id = f"order_wh_failed_{int(time.time())}"
    agent_id = "test_failed_webhook_agent"

    audit_id = record_decision(
        agent_id=agent_id,
        amount_paise=15000,
        amount_inr=150.0,
        verdict="ALLOW",
        confidence=1.0,
        primary_factor="policy_cleared",
        summary="Test decision for failed webhook",
        evidence={"test": "failed_webhook_seed"},
        razorpay_order_id=order_id,
    )

    event_id = f"evt_wh_failed_{int(time.time() * 1000)}"
    payload_dict = {
        "entity": "event",
        "account_id": "acc_razorgate_test",
        "event": "payment.failed",
        "event_id": event_id,
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_failed_{int(time.time())}",
                    "entity": "payment",
                    "amount": 15000,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": order_id,
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment failed due to customer cancellation",
                }
            }
        },
    }

    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    secret = (settings.razorpay_webhook_secret or "razorgate_webhook_secret_dev").encode("utf-8")
    signature = hmac.new(secret, raw_bytes, hashlib.sha256).hexdigest()

    res = client.post(
        "/webhooks/razorpay",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "processed"
    assert res_data["payment_status"] == "payment_failed"
    assert res_data["audit_id"] == audit_id

    updated_record = get_decision_by_order_id(order_id)
    assert updated_record is not None
    assert updated_record["webhook_status"] == "payment_failed"
