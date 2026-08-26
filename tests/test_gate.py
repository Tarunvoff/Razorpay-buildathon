import time
from unittest.mock import MagicMock, patch
from backend.gate import adapter
from backend.gate.behavior import BehaviorAnalyzer, InMemoryWindowStore


def test_normal_call_evaluates_non_blocking_apiris_action():
    """
    Phase 2 verification (Correction 1 applied): proves that a clean, realistic
    Razorpay payment call is evaluated by Apiris without error, maps to raw
    action 'pass_through', exhibits healthy CIA scores, and does not use removed signal vocabulary.
    """
    clean_call = {
        "amount": 50000,
        "currency": "INR",
        "merchant_id": "merchant_test_123",
        "order_id": "order_clean_001",
        "receipt": "rcpt_001",
        "action": "create_order",
        "timing_ms": 120.0,
    }

    # 1. Direct Apiris evaluation check
    raw_eval = adapter.score_payment_call(clean_call)
    decision = raw_eval.get("decision", {})
    scores = decision.get("scores", {})

    assert decision.get("action") == "pass_through", f"Expected pass_through, got {decision.get('action')}"
    assert scores.get("C_score", 0.0) >= 0.5, f"C_score too low: {scores.get('C_score')}"
    assert scores.get("A_score", 0.0) >= 0.5, f"A_score too low: {scores.get('A_score')}"
    assert scores.get("D_score", 0.0) >= 0.5, f"D_score too low: {scores.get('D_score')}"

    # 2. Gate check wrapper verification (verifies raw action & no signal field)
    gate_result = adapter.check(clean_call)
    assert gate_result["verdict"] == "ALLOW"
    assert "signal" not in gate_result["apiris_score"], "Removed 'signal' field must not be present"
    assert gate_result["apiris_score"]["action"] == "pass_through"
    assert gate_result["confidence"] >= 0.5


def test_degraded_api_telemetry_triggers_apiris_mitigation():
    """
    Proves that degraded telemetry (500 server error + latency surge)
    drops the Availability score directly.
    """
    degraded_call = {
        "amount": 50000,
        "currency": "INR",
        "action": "create_order",
        "timing_ms": 3500.0,
        "mock_response": {
            "status": 500,
            "headers": {"content-type": "application/json"},
            "body": '{"error": {"code": "BAD_GATEWAY_ERROR"}}',
        },
        "error": {"type": "HTTPError", "message": "Gateway timeout / 500 error"},
    }

    raw_eval = adapter.score_payment_call(degraded_call)
    decision = raw_eval.get("decision", {})
    scores = decision.get("scores", {})

    assert scores.get("A_score", 1.0) < 0.5, "Degraded call should lower A_score"


def test_health_score_to_risk_weight_inversion():
    """
    Correction 2 verification: verifies the explicit inversion contract:
      risk_weight = 1.0 - health_score
    - Near-1.0 health produces near-0.0 risk_weight (safe).
    - Near-0.0 health produces near-1.0 risk_weight (high risk).
    """
    # 1. Clean call: high health (~1.0) -> low risk_weight (~0.0)
    clean_call = {
        "amount": 50000,
        "currency": "INR",
        "timing_ms": 100.0,
    }
    clean_result = adapter.check(clean_call)
    clean_risk = clean_result["apiris_score"]["risk_weight"]
    assert clean_risk <= 0.2, f"Clean call expected near-0.0 risk_weight, got {clean_risk}"

    # 2. Degraded call: low health (~0.0) -> high risk_weight (~1.0)
    degraded_call = {
        "amount": 50000,
        "currency": "INR",
        "timing_ms": 3500.0,
        "mock_response": {
            "status": 500,
            "headers": {"content-type": "application/json"},
            "body": '{"error": {"code": "INTERNAL_SERVER_ERROR"}}',
        },
        "error": {"type": "HTTPError", "message": "500 Internal Server Error"},
    }
    degraded_result = adapter.check(degraded_call)
    degraded_risk = degraded_result["apiris_score"]["risk_weight"]
    assert degraded_risk >= 0.8, f"Degraded call expected near-1.0 risk_weight, got {degraded_risk}"


def test_behavior_burst_flags_while_isolated_call_does_not():
    """
    Phase 3 Exit Criterion:
    Fires a burst of rapid calls (exceeding frequency_threshold=5) for 'burst_agent'
    within the window and asserts it flags with 'high_frequency' in reasons.
    In the same test, runs a single isolated call for 'isolated_agent' and asserts
    it does not flag.
    """
    store = InMemoryWindowStore()
    analyzer = BehaviorAnalyzer(window_seconds=300.0, frequency_threshold=5, store=store)

    # 1. Burst of 6 calls for 'burst_agent' (threshold is 5)
    burst_results = []
    base_time = time.time()
    for i in range(6):
        res = analyzer.record_and_evaluate(
            agent_id="burst_agent",
            amount_paise=10000,
            timestamp=base_time + i * 2,  # 2 seconds apart
        )
        burst_results.append(res)

    last_burst_result = burst_results[-1]
    assert last_burst_result["flag"] is True, "Burst exceeding threshold must flag"
    assert "high_frequency" in last_burst_result["reasons"], f"Expected 'high_frequency' in reasons, got {last_burst_result['reasons']}"
    assert last_burst_result["session_call_count"] == 6

    # 2. Single isolated call for 'isolated_agent' in the same window
    isolated_result = analyzer.record_and_evaluate(
        agent_id="isolated_agent",
        amount_paise=10000,
        timestamp=base_time + 15,
    )
    assert isolated_result["flag"] is False, "Single isolated call must NOT flag"
    assert isolated_result["reasons"] == [], f"Expected empty reasons, got {isolated_result['reasons']}"
    assert isolated_result["session_call_count"] == 1


def test_block_prevents_downstream_razorpay_call():
    """
    The core safety contract of this whole project: when the gate says
    BLOCK, the Razorpay order-creation call must never fire.
    This test SHOULD FAIL right now (stub returns ALLOW until Phase 4) —
    it starts failing red on purpose and turns green once real gate
    policy enforcement is implemented.
    """
    oversized_call = {
        "amount": 999_999_999,
        "merchant_id": "test_merchant",
        "order_id": "order_test_1",
        "action": "create_order",
    }
    with patch("backend.payments.razorpay_client.create_order") as mock_create:
        result = adapter.check(oversized_call)
        if result["verdict"] != "BLOCK":
            from backend.payments import razorpay_client
            razorpay_client.create_order(amount_paise=oversized_call["amount"], receipt="r1")
        assert result["verdict"] == "BLOCK", "Gate logic not yet implemented — expected failure this session"
        mock_create.assert_not_called()
