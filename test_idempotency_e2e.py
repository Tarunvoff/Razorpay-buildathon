import requests
import time
import json

BASE_URL = "http://127.0.0.1:8008"

def run_test():
    agent_id = f"test_idem_{int(time.time())}"
    receipt = f"rcpt_{int(time.time())}"
    amount_paise = 15000
    
    print(f"--- Step 1: /gate/check ---")
    gate_payload = {
        "amount": amount_paise,
        "currency": "INR",
        "agent_id": agent_id,
        "receipt": receipt,
        "action": "create_order"
    }
    gate_res = requests.post(f"{BASE_URL}/gate/check", json=gate_payload)
    gate_data = gate_res.json()
    print("Gate response:", json.dumps(gate_data, indent=2))
    
    if gate_data["verdict"] != "ALLOW":
        print("Expected ALLOW, got:", gate_data["verdict"])
        return
        
    audit_id = gate_data["audit_id"]
    allow_token = gate_data["allow_token"]
    
    print(f"\n--- Step 2: First /orders call ---")
    order_payload = {
        "agent_id": agent_id,
        "amount_paise": amount_paise,
        "receipt": receipt,
        "allow_token": allow_token,
        "audit_id": audit_id
    }
    order_res_1 = requests.post(f"{BASE_URL}/orders", json=order_payload)
    order_data_1 = order_res_1.json()
    print("Order 1 response:", json.dumps(order_data_1, indent=2))
    
    print(f"\n--- Step 3: Second /orders call (Duplicate) ---")
    order_res_2 = requests.post(f"{BASE_URL}/orders", json=order_payload)
    order_data_2 = order_res_2.json()
    print("Order 2 response:", json.dumps(order_data_2, indent=2))
    
    print(f"\n--- Step 4: Verification ---")
    if "order" in order_data_1 and "order" in order_data_2:
        id1 = order_data_1["order"]["id"]
        id2 = order_data_2["order"]["id"]
        if id1 == id2:
            print(f"SUCCESS: Razorpay honored X-Idempotency-Key. Same ID: {id1}")
        else:
            print(f"FAILURE: Razorpay returned different IDs! {id1} vs {id2}")
    else:
        print("Could not verify. Response missing order object.")
        
    print(f"\n--- Step 5: Mismatched amount call ---")
    order_payload_mismatch = {
        "agent_id": agent_id,
        "amount_paise": 25000,
        "receipt": receipt,
        "allow_token": allow_token,
        "audit_id": audit_id
    }
    order_res_3 = requests.post(f"{BASE_URL}/orders", json=order_payload_mismatch)
    print(f"Order 3 (mismatched) status: {order_res_3.status_code}")
    print("Order 3 response:", json.dumps(order_res_3.json(), indent=2))

if __name__ == "__main__":
    run_test()
