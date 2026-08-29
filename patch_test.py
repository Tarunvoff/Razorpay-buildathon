import time

with open('tests/test_gate.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix assertions
content = content.replace('assert "Forbidden" in res_invalid.json()["detail"]', 'assert res_invalid.json()["detail"] == "token_invalid"')
content = content.replace('old_timestamp = time.time() - 45.0  # 45 seconds ago', 'old_timestamp = time.time() - 100.0  # 100 seconds ago')
content = content.replace('assert "Forbidden" in res_expired.json()["detail"]', 'assert res_expired.json()["detail"] == "token_expired"')
content = content.replace('assert "Forbidden" in res_agent_mismatch.json()["detail"]', 'assert "token_invalid" in res_agent_mismatch.json()["detail"]')
content = content.replace('assert "Forbidden" in res_amount_mismatch.json()["detail"]', 'assert "token_invalid" in res_amount_mismatch.json()["detail"]')
content = content.replace('assert "Forbidden" in res_receipt_mismatch.json()["detail"]', 'assert "token_invalid" in res_receipt_mismatch.json()["detail"]')

new_tests = '''
def test_allow_token_ttl_race_refresh():
    """
    Simulates the LLM latency race condition: a token is minted, but 
    time passes beyond the 90s TTL. Validates that /gate/refresh-token
    can re-mint a valid token based on the original audit_id.
    """
    init_db()
    client = TestClient(app)
    agent_id = f"latency_agent_{int(time.time())}"
    
    # 1. Gate check produces ALLOW
    check_res = client.post(
        "/gate/check",
        json={
            "amount": 25000,
            "currency": "INR",
            "agent_id": agent_id,
            "receipt": "rcpt_latency",
            "action": "create_order",
        },
    )
    assert check_res.status_code == 200
    check_data = check_res.json()
    audit_id = check_data["audit_id"]
    original_token = check_data["allow_token"]
    
    # 2. Fast-forward clock to simulate agent thinking
    future_time = time.time() + 100.0
    with patch("backend.payments.razorpay_client.time.time", return_value=future_time):
        order_res = client.post(
            "/orders",
            json={
                "agent_id": agent_id,
                "amount_paise": 25000,
                "receipt": "rcpt_latency",
                "allow_token": original_token,
                "currency": "INR",
                "audit_id": audit_id,
            },
        )
        assert order_res.status_code == 403
        assert order_res.json()["detail"] == "token_expired"
        
    # 3. Call refresh-token
    with patch("backend.payments.razorpay_client.time.time", return_value=future_time):
        refresh_res = client.post(
            "/gate/refresh-token",
            json={
                "audit_id": audit_id,
                "agent_id": agent_id,
                "amount_paise": 25000,
                "receipt": "rcpt_latency"
            }
        )
    assert refresh_res.status_code == 200
    refresh_data = refresh_res.json()
    assert refresh_data["status"] == "refreshed"
    new_token = refresh_data["allow_token"]
    assert new_token != original_token

def test_orders_endpoint_idempotency_key_passed():
    """
    Confirms POST /orders passes X-Idempotency-Key if audit_id is provided.
    """
    client = TestClient(app)
    
    valid_token = razorpay_client.mint_allow_token(
        agent_id="agent_alice",
        amount_paise=10000,
        receipt="rcpt_idem",
    )
    
    with patch.object(razorpay_client.client.order, "create") as mock_create:
        mock_create.return_value = {"id": "order_idem_123", "status": "created"}
        
        res = client.post(
            "/orders",
            json={
                "agent_id": "agent_alice",
                "amount_paise": 10000,
                "receipt": "rcpt_idem",
                "allow_token": valid_token,
                "audit_id": 9999,
            }
        )
        assert res.status_code == 200
        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args
        assert "headers" in kwargs, "Expected headers in client.order.create kwargs"
        assert kwargs["headers"].get("X-Idempotency-Key") == "9999"

def test_behavior_analyzer_thread_safety():
    """
    Proves that BehaviorAnalyzer correctly handles true concurrent access
    using a threading Lock to prevent race conditions during read-modify-write.
    """
    from concurrent.futures import ThreadPoolExecutor
    from backend.gate.behavior import BehaviorAnalyzer, InMemoryWindowStore
    import time
    
    store = InMemoryWindowStore()
    analyzer = BehaviorAnalyzer(window_seconds=300.0, frequency_threshold=5, store=store)
    agent_id = "concurrent_agent_123"
    
    # Fire 10 simultaneous threads hitting the same analyzer
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(
                analyzer.record_and_evaluate,
                agent_id=agent_id,
                amount_paise=10000,
                timestamp=time.time()
            )
            for _ in range(10)
        ]
        
    results = [f.result() for f in futures]
    
    call_counts = sorted([r["session_call_count"] for r in results])
    assert call_counts == list(range(1, 11)), f"Race condition detected! Counts: {call_counts}"
    
    flagged_results = [r for r in results if r["flag"] is True]
    assert len(flagged_results) == 5, f"Expected exactly 5 flagged results (counts 6-10), got {len(flagged_results)}"
'''

with open('tests/test_gate.py', 'w', encoding='utf-8') as f:
    f.write(content + '\n\n' + new_tests + '\n')
print('Tests appended successfully')
