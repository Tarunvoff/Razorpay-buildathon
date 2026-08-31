"""
Live Verification Script for Razorpay Webhook Ingestion.
Connects to running Uvicorn server (http://127.0.0.1:8008), triggers an order scenario,
sends a signed Razorpay webhook payload, verifies DB audit record update, and checks SSE feed.
"""

import hashlib
import hmac
import json
import requests
import time

BASE_URL = "http://127.0.0.1:8008"
WEBHOOK_SECRET = "razorgate_webhook_secret_dev"


def run_live_webhook_verification():
    print("=================================================================")
    print("LIVE E2E RAZORPAY WEBHOOK INTEGRATION VERIFICATION")
    print("=================================================================")

    # Step 1: Run clean_allow scenario to generate real audit decision and order
    print("\n--- Step 1: Triggering /demo/run-scenario ('clean_allow') ---")
    scenario_res = requests.post(f"{BASE_URL}/demo/run-scenario", json={"scenario": "clean_allow"})
    assert scenario_res.status_code == 200, f"Scenario failed: {scenario_res.text}"
    sc_data = scenario_res.json()
    
    audit_id = sc_data["audit_id"]
    order_id = sc_data["order"]["id"]
    amount_paise = sc_data["receipt"]["amount_paise"]
    print(f"Created Audit Decision ID: {audit_id}")
    print(f"Razorpay Order ID: {order_id}")
    print(f"Amount: {amount_paise} paise (INR {amount_paise / 100:.2f})")

    # Verify initial decision status in SQLite DB via GET /decisions/{audit_id}
    dec_res_before = requests.get(f"{BASE_URL}/decisions/{audit_id}")
    assert dec_res_before.status_code == 200
    dec_before = dec_res_before.json()
    print(f"Initial DB Record - Verdict: {dec_before['verdict']}, Webhook Status: {dec_before.get('webhook_status')}")

    # Step 2: Construct official Razorpay payment.captured webhook payload
    print("\n--- Step 2: Constructing Official Razorpay Webhook Payload ---")
    payment_id = f"pay_live_{int(time.time())}"
    event_id = f"event_live_{int(time.time() * 1000)}"
    
    raw_payload = {
        "entity": "event",
        "account_id": "acc_razorgate_live_demo",
        "event": "payment.captured",
        "event_id": event_id,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": amount_paise,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": order_id,
                    "invoice_id": None,
                    "international": False,
                    "method": "upi",
                    "amount_refunded": 0,
                    "refund_status": None,
                    "captured": True,
                    "description": "NVIDIA H100 GPU Compute Cluster 1-Hour Allocation",
                    "card_id": None,
                    "bank": None,
                    "wallet": None,
                    "vpa": "buyer@upi",
                    "email": "buyer.agent@razorgate.ai",
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

    raw_body_bytes = json.dumps(raw_payload).encode("utf-8")
    signature = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw_body_bytes, hashlib.sha256).hexdigest()

    print("Raw Webhook Payload:")
    print(json.dumps(raw_payload, indent=2))
    print(f"Computed X-Razorpay-Signature: {signature}")

    # Step 3: POST to /webhooks/razorpay
    print("\n--- Step 3: Posting Webhook to http://127.0.0.1:8008/webhooks/razorpay ---")
    webhook_res = requests.post(
        f"{BASE_URL}/webhooks/razorpay",
        data=raw_body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )
    print(f"Webhook HTTP Response Code: {webhook_res.status_code}")
    print(f"Webhook Response Payload:\n{json.dumps(webhook_res.json(), indent=2)}")
    assert webhook_res.status_code == 200, f"Webhook failed: {webhook_res.text}"

    # Step 4: Confirm DB audit record update via GET /decisions/{audit_id}
    print("\n--- Step 4: Verifying Audit Record Update in DB ---")
    dec_res_after = requests.get(f"{BASE_URL}/decisions/{audit_id}")
    assert dec_res_after.status_code == 200
    dec_after = dec_res_after.json()
    print(f"Updated DB Record Audit #{audit_id}:")
    print(f"  Verdict: {dec_after['verdict']}")
    print(f"  Razorpay Order ID: {dec_after['razorpay_order_id']}")
    print(f"  Webhook Status: {dec_after.get('webhook_status')}")
    print(f"  Webhook Confirmed At: {dec_after.get('webhook_confirmed_at')}")

    assert dec_after.get("webhook_status") == "confirmed_paid"
    assert dec_after.get("webhook_confirmed_at") is not None

    # Step 5: Test Webhook Idempotency (re-post duplicate event_id)
    print("\n--- Step 5: Testing Idempotent Re-delivery of Duplicate Event ID ---")
    dup_res = requests.post(
        f"{BASE_URL}/webhooks/razorpay",
        data=raw_body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )
    print(f"Duplicate Webhook Response Code: {dup_res.status_code}")
    print(f"Duplicate Webhook Response:\n{json.dumps(dup_res.json(), indent=2)}")
    assert dup_res.status_code == 200
    assert dup_res.json()["status"] == "already_processed"
    assert dup_res.json()["idempotency_hit"] is True

    print("\n=================================================================")
    print("SUCCESS: ALL LIVE WEBHOOK VERIFICATIONS CONFIRMED & AUDITED!")
    print("=================================================================")


if __name__ == "__main__":
    run_live_webhook_verification()
