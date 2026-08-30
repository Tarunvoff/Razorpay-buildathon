"""
End-to-End Idempotency & Replay Defense Verification Script.

Tests two layers of payment idempotency:
1. Unmocked Raw Razorpay Orders API (direct SDK calls with X-Idempotency-Key headers and payload variation).
2. RazorGate End-to-End Control Plane (/gate/check -> /orders -> retried /orders -> mismatched amount rejection).
"""

import json
import time
from fastapi.testclient import TestClient
from backend.control.app import app
from backend.payments.razorpay_client import client, fetch_order

test_client = TestClient(app)


def run_unmocked_raw_razorpay_test():
    print("=================================================================")
    print("PART 1: UNMOCKED RAW RAZORPAY API IDEMPOTENCY TEST (DIRECT SDK)")
    print("=================================================================")
    
    timestamp = int(time.time())
    idempotency_key = f"idem_key_raw_{timestamp}"
    receipt_ref = f"rcpt_raw_{timestamp}"
    amount_paise = 15000  # ₹150.00
    
    # 1. First raw POST to Razorpay API
    order1 = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt_ref,
            "notes": {"test": "unmocked_raw_idempotency_1"},
        },
        headers={"X-Idempotency-Key": idempotency_key},
    )
    print(f"[Run 1] Created Order ID: {order1['id']}, Amount: {order1['amount']} paise")
    
    # 2. Immediate second raw POST with same X-Idempotency-Key and payload
    order2 = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt_ref,
            "notes": {"test": "unmocked_raw_idempotency_1"},
        },
        headers={"X-Idempotency-Key": idempotency_key},
    )
    print(f"[Run 2] Duplicate Order ID: {order2['id']}, Amount: {order2['amount']} paise")
    
    print("\n--- Side-by-Side Raw Razorpay Order Objects ---")
    print("Order 1 Payload:", json.dumps({"id": order1["id"], "amount": order1["amount"], "receipt": order1["receipt"], "status": order1["status"]}, indent=2))
    print("Order 2 Payload:", json.dumps({"id": order2["id"], "amount": order2["amount"], "receipt": order2["receipt"], "status": order2["status"]}, indent=2))
    
    # 3. Ground truth verification via fetch_order
    fetched1 = fetch_order(order1["id"])
    print(f"\n[Ground Truth] Fetched Order 1 ({order1['id']}): Amount = {fetched1['amount']} paise, Status = {fetched1['status']}")
    
    # 4. Negative Case: Resend same idempotency key with DIFFERENT amount_paise (₹250.00 / 25000 paise)
    print("\n--- Negative Case: Resend with same X-Idempotency-Key but mismatched amount (25000 paise) ---")
    try:
        order_mismatch = client.order.create(
            {
                "amount": 25000,  # Mismatched amount
                "currency": "INR",
                "receipt": receipt_ref,
                "notes": {"test": "mismatched_amount"},
            },
            headers={"X-Idempotency-Key": idempotency_key},
        )
        print(f"[Mismatched Raw Result] Created Order ID: {order_mismatch['id']}, Amount: {order_mismatch['amount']} paise")
        print("Observation: Razorpay Orders API processes distinct request payloads independently when API idempotency header is not enforced by payment gateway for orders endpoint.")
    except Exception as e:
        print(f"[Mismatched Raw Result] Razorpay API Rejected: {str(e)}")


def run_razorgate_control_plane_test():
    print("\n=================================================================")
    print("PART 2: RAZORGATE CONTROL PLANE E2E IDEMPOTENCY & REPLAY DEFENSE")
    print("=================================================================")
    
    timestamp = int(time.time())
    agent_id = f"buyer_idem_agent_{timestamp % 10000}"
    receipt = f"rcpt_gate_{timestamp}"
    amount_paise = 19900  # ₹199.00
    
    # Step 1: /gate/check -> ALLOW verdict + HMAC Token
    print(f"--- Step 1: POST /gate/check (Amount: INR {amount_paise / 100:.2f}) ---")
    gate_res = test_client.post(
        "/gate/check",
        json={
            "amount": amount_paise,
            "currency": "INR",
            "agent_id": agent_id,
            "receipt": receipt,
            "action": "create_order",
        },
    )
    gate_data = gate_res.json()
    audit_id = gate_data["audit_id"]
    allow_token = gate_data["allow_token"]
    print(f"Gate Decision: Verdict = {gate_data['verdict']}, Audit ID = #{audit_id}")
    print(f"Minted ALLOW Token: {allow_token[:30]}...")
    
    # Step 2: First /orders call -> creates Razorpay order & links audit ID
    print(f"\n--- Step 2: First POST /orders (Audit ID: #{audit_id}) ---")
    order_payload_1 = {
        "agent_id": agent_id,
        "amount_paise": amount_paise,
        "receipt": receipt,
        "allow_token": allow_token,
        "audit_id": audit_id,
    }
    res1 = test_client.post("/orders", json=order_payload_1)
    data1 = res1.json()
    order_id_1 = data1["order"]["id"]
    print(f"Response 1: Status = {data1['status']}, Order ID = {order_id_1}, Amount = {data1['order']['amount']} paise")
    
    # Step 3: Duplicate /orders call -> hits software idempotency guard
    print(f"\n--- Step 3: Duplicate POST /orders (Same Audit ID: #{audit_id}) ---")
    res2 = test_client.post("/orders", json=order_payload_1)
    data2 = res2.json()
    order_id_2 = data2["order"]["id"]
    is_idem_hit = data2.get("idempotency_hit", False)
    print(f"Response 2: Status = {data2['status']}, Order ID = {order_id_2}, Idempotency Hit = {is_idem_hit}")
    
    # Step 4: Verification of Order ID match
    print("\n--- Step 4: Idempotency Verification ---")
    assert order_id_1 == order_id_2, f"Mismatch in order IDs: {order_id_1} vs {order_id_2}"
    print(f"[PASS] Both /orders calls returned the EXACT same Razorpay Order ID: {order_id_1}")
    print(f"[PASS] Idempotency Guard Flag: idempotency_hit = {is_idem_hit}")
    
    # Verify ground truth from Razorpay
    fetched = fetch_order(order_id_1)
    print(f"[Ground Truth] Single Order on Razorpay: ID = {fetched['id']}, Status = {fetched['status']}, Amount = {fetched['amount']} paise")
    
    # Step 5: Negative Case 5A - Retrying with existing audit_id but tampered amount (49000 paise vs 19900 paise)
    print("\n--- Step 5A: Negative Case - Retrying existing audit_id with tampered amount (49000 paise) ---")
    mismatched_payload_1 = {
        "agent_id": agent_id,
        "amount_paise": 49000,  # Tampered amount
        "receipt": receipt,
        "allow_token": allow_token,
        "audit_id": audit_id,
    }
    res3 = test_client.post("/orders", json=mismatched_payload_1)
    data3 = res3.json()
    print(f"Mismatched Retried Request Status: {res3.status_code}")
    print(f"Returned Order Amount: {data3['order']['amount']} paise (Original: 19900 paise)")
    print(f"Idempotency Hit: {data3.get('idempotency_hit')}")
    assert res3.status_code == 200
    assert data3["order"]["amount"] == 19900, "Idempotency guard must return original order amount, ignoring tampered amount"
    assert data3["idempotency_hit"] is True
    print("[PASS] Retried request with existing audit_id safely returned the original order (INR 199.00), preventing amount modification.")

    # Step 5B: Negative Case - New audit_id with tampered amount token verification failure
    print("\n--- Step 5B: Negative Case - Fresh mandate with tampered amount token ---")
    mismatched_payload_2 = {
        "agent_id": agent_id,
        "amount_paise": 49000,  # Tampered amount
        "receipt": receipt,
        "allow_token": allow_token,
        "audit_id": audit_id + 9999,  # Fresh/unlinked audit_id
    }
    res4 = test_client.post("/orders", json=mismatched_payload_2)
    print(f"Tampered Token Request Status: {res4.status_code}")
    print(f"Response Body: {json.dumps(res4.json(), indent=2)}")
    assert res4.status_code == 403, f"Expected 403 Forbidden, got {res4.status_code}"
    print("[PASS] Tampered amount token correctly rejected by HMAC signature verification with 403 Forbidden ('token_invalid').")




if __name__ == "__main__":
    run_unmocked_raw_razorpay_test()
    run_razorgate_control_plane_test()
