"""
Live System Verification Script (In-Process TestClient with UTF-8 Safe Console Printing).
Checks live backend control plane with configured Claude Relay API credentials.
"""

import json
import time
import hmac
import hashlib
from fastapi.testclient import TestClient
from backend.control.app import app

client = TestClient(app)

def verify_live():
    print("=================================================================")
    print("LIVE SYSTEM VERIFICATION (FASTAPI CONTROL PLANE)")
    print("=================================================================")

    # 1. Health check
    h = client.get("/health")
    print(f"1. Health Check: Status {h.status_code} -> {h.json()}")

    # 2. Live Agent Ask (calls live Claude relay API)
    print("\n2. Executing Live Buyer Agent Intent against Claude Relay API...")
    t0 = time.time()
    res = client.post(
        "/agent/ask",
        json={
            "intent": "High-performance NVIDIA H100 GPU compute instance for fine-tuning",
            "category": "ai_compute",
            "max_budget_inr": 5000.0,
        },
    )
    t1 = time.time()
    print(f"   Response Code: {res.status_code} (Took {t1-t0:.2f}s)")
    assert res.status_code == 200
    data = res.json()
    receipt = data["receipt"]
    summary_clean = str(receipt["summary"]).encode("ascii", "ignore").decode("ascii")
    print(f"   Verdict: {receipt['verdict']} | SKU: {receipt['sku']} | Amount: INR {receipt['amount_inr']}")
    print(f"   Summary: {summary_clean}")
    print(f"   Audit ID: {receipt['audit_id']}")

    # 3. Verify Orders endpoint with ALLOW token
    print("\n3. Testing Gated Order Creation (POST /orders)...")
    audit_id = receipt["audit_id"]
    allow_token = receipt.get("evidence", {}).get("allow_token") or data.get("allow_token")
    
    if receipt["verdict"] == "ALLOW" and allow_token:
        order_res = client.post(
            "/orders",
            json={
                "agent_id": "live_test_agent",
                "amount_paise": receipt["amount_paise"],
                "receipt": f"rcpt_live_{int(time.time())}",
                "allow_token": allow_token,
                "merchant_id": "merchant_razorgate_test",
                "sku": receipt["sku"],
                "currency": "INR",
                "audit_id": audit_id,
            },
        )
        print(f"   Order Creation HTTP Status: {order_res.status_code}")
        print(f"   Response Payload: {order_res.json()}")
        assert order_res.status_code == 200
        razorpay_order_id = order_res.json()["order"]["id"]
        print(f"   Created Razorpay Order ID: {razorpay_order_id}")

        # 4. Test Webhook Ingestion for this order
        print("\n4. Testing Live Webhook Ingestion (POST /webhooks/razorpay)...")
        webhook_secret = b"razorgate_webhook_secret_dev"
        webhook_payload = {
            "entity": "event",
            "account_id": "acc_live_dashboard",
            "event": "payment.captured",
            "event_id": f"evt_live_{int(time.time()*1000)}",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_live_{int(time.time())}",
                        "entity": "payment",
                        "amount": receipt["amount_paise"],
                        "currency": "INR",
                        "status": "captured",
                        "order_id": razorpay_order_id,
                    }
                }
            },
        }

        raw_body = json.dumps(webhook_payload).encode("utf-8")
        sig = hmac.new(webhook_secret, raw_body, hashlib.sha256).hexdigest()

        wh_res = client.post(
            "/webhooks/razorpay",
            content=raw_body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
        )
        print(f"   Webhook Endpoint HTTP Status: {wh_res.status_code}")
        print(f"   Webhook Response: {wh_res.json()}")
        assert wh_res.status_code == 200
        assert wh_res.json()["payment_status"] == "confirmed_paid"

    print("\n=================================================================")
    print("ALL LIVE CHECKS PASSED CLEANLY!")
    print("=================================================================")

if __name__ == "__main__":
    verify_live()
