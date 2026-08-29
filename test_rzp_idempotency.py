import os
import time
from backend.config import settings
from backend.payments.razorpay_client import client

def test_idempotency():
    if not settings.razorpay_key_id.startswith("rzp_test_") or "dummy" in settings.razorpay_key_id:
        print("Real Razorpay credentials not found, skipping manual idempotency test.")
        return
        
    idem_key = f"manual_idem_{int(time.time())}"
    
    payload = {
        "amount": 15000,
        "currency": "INR",
        "receipt": "manual_receipt_1",
        "notes": {"reason": "testing_idempotency"}
    }
    
    print(f"Testing with X-Idempotency-Key: {idem_key}")
    
    # First call
    try:
        res1 = client.order.create(data=payload, **{"headers": {"X-Idempotency-Key": idem_key}})
        order_id_1 = res1.get("id")
        print(f"Call 1 Success. Order ID: {order_id_1}")
    except Exception as e:
        print(f"Call 1 Failed: {e}")
        return
        
    # Second call (exact same key and payload)
    try:
        res2 = client.order.create(data=payload, **{"headers": {"X-Idempotency-Key": idem_key}})
        order_id_2 = res2.get("id")
        print(f"Call 2 Success. Order ID: {order_id_2}")
    except Exception as e:
        print(f"Call 2 Failed: {e}")
        return
        
    if order_id_1 == order_id_2:
        print("Idempotency VERIFIED: Razorpay returned the exact same order ID.")
    else:
        print(f"Idempotency FAILED: Razorpay returned different order IDs ({order_id_1} vs {order_id_2}).")

if __name__ == "__main__":
    test_idempotency()
