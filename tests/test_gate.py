import time
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.audit.db import get_recent_decisions, init_db, record_decision
from backend.audit.explainer import build_explanation
from backend.control.app import app
from backend.gate import adapter
from backend.gate.behavior import BehaviorAnalyzer, InMemoryWindowStore


def test_normal_call_evaluates_non_blocking_apiris_action():
    """
    Proves that a clean, realistic Razorpay payment call is evaluated by Apiris
    without error, maps to raw action 'pass_through', exhibits healthy CIA scores,
    and does not use removed signal vocabulary.
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
    assert gate_result["confidence"] == 1.0, f"Clean call expected confidence 1.0, got {gate_result['confidence']}"


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
    Verifies the explicit inversion contract:
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
    Phase 3 Exit Criterion (High Frequency):
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


def test_behavior_amount_deviation_flags_outlier():
    """
    Item 1 Verification (Amount Deviation):
    Same agent_id, several calls at a stable baseline amount (e.g. ₹100 / 10,000 paise),
    then one call at a significantly different outlier amount (₹5,000 / 500,000 paise)
    with total calls under frequency threshold (N=4 <= 5), asserting 'amount_deviation' flags.
    """
    store = InMemoryWindowStore()
    analyzer = BehaviorAnalyzer(window_seconds=300.0, frequency_threshold=5, std_dev_threshold=3.0, store=store)
    base_time = time.time()
    agent_id = "agent_spending_drift"

    # 1. Establish stable baseline with 3 calls of ₹100 (10,000 paise)
    for i in range(3):
        res = analyzer.record_and_evaluate(
            agent_id=agent_id,
            amount_paise=10000,
            timestamp=base_time + i * 5,
        )
        assert res["flag"] is False, f"Baseline call {i+1} should not flag"

    # 2. Outlier call: sudden ₹5,000 (500,000 paise) purchase on 4th call
    outlier_res = analyzer.record_and_evaluate(
        agent_id=agent_id,
        amount_paise=500000,
        timestamp=base_time + 20,
    )

    assert outlier_res["flag"] is True, "Outlier amount must trigger behavioral flag"
    assert "amount_deviation" in outlier_res["reasons"], f"Expected 'amount_deviation' in reasons, got {outlier_res['reasons']}"
    assert "high_frequency" not in outlier_res["reasons"], "Must not flag high_frequency under frequency limit (N=4)"
    assert outlier_res["session_call_count"] == 4
    assert outlier_res["amount_deviation_zscore"] > 3.0, f"Expected z-score > 3.0, got {outlier_res['amount_deviation_zscore']}"


def test_block_prevents_downstream_razorpay_call():
    """
    Phase 4 Safety Contract:
    When the gate says BLOCK (amount exceeds ceiling), the Razorpay
    order-creation call must never fire. Confirms confidence is 1.0 (deterministic).
    """
    oversized_call = {
        "amount": 999_999_999,  # 9,999,999.99 INR > 50,000 INR ceiling
        "merchant_id": "test_merchant",
        "order_id": "order_test_1",
        "action": "create_order",
        "agent_id": "agent_oversized_test",
    }
    with patch("backend.payments.razorpay_client.create_order") as mock_create:
        result = adapter.check(oversized_call)
        if result["verdict"] != "BLOCK":
            from backend.payments import razorpay_client
            razorpay_client.create_order(amount_paise=oversized_call["amount"], receipt="r1")
        assert result["verdict"] == "BLOCK", "Oversized call must be BLOCKed by policy ceiling"
        assert result["decision"]["primary_factor"] == "amount_exceeded_ceiling"
        assert result["confidence"] == 1.0, "Ceiling BLOCK confidence must be 1.0 deterministic"
        mock_create.assert_not_called()


def test_clean_under_ceiling_call_produces_allow():
    """
    Phase 4 Test 2:
    Proves that a normal, clean, under-ceiling call evaluates to ALLOW
    with high confidence and primary_factor 'policy_cleared'.
    """
    clean_call = {
        "amount": 50000,  # 500 INR < 50,000 INR ceiling
        "currency": "INR",
        "merchant_id": "merchant_test_123",
        "order_id": "order_clean_allow",
        "receipt": "rcpt_allow_01",
        "action": "create_order",
        "agent_id": "agent_clean_test",
        "timing_ms": 110.0,
    }
    result = adapter.check(clean_call)
    assert result["verdict"] == "ALLOW", f"Expected ALLOW, got {result['verdict']}"
    assert result["decision"]["primary_factor"] == "policy_cleared"
    assert result["confidence"] == 1.0, "Clean call with zero risk weight should have confidence 1.0"
    assert result["decision"]["amount_inr"] == 500.0


def test_behavior_flag_with_clean_apiris_produces_flag_never_block():
    """
    Phase 4 Test 3:
    Proves the asymmetry rule: A clean Apiris signal combined with a behavior.py
    anomaly flag produces FLAG, NEVER BLOCK. Behavior anomalies can only ever escalate
    toward FLAG.
    """
    behavior_flagged_call = {
        "amount": 25000,  # 250 INR < 50,000 INR ceiling
        "currency": "INR",
        "order_id": "order_behavior_flag",
        "agent_id": "agent_behavior_test",
        "timing_ms": 100.0,
        "mock_behavior_signal": {
            "flag": True,
            "reasons": ["high_frequency", "amount_deviation"],
            "session_call_count": 8,
            "frequency": 8,
            "amount_deviation_zscore": 3.45,
            "window_mean_amount": 10000.0,
            "window_std_amount": 2500.0,
        },
    }
    result = adapter.check(behavior_flagged_call)
    assert result["verdict"] == "FLAG", f"Expected FLAG for behavior anomaly, got {result['verdict']}"
    assert result["verdict"] != "BLOCK", "Behavior anomaly must NEVER trigger BLOCK on its own"
    assert result["decision"]["primary_factor"] == "behavior_anomaly"
    assert result["decision"]["behavior_flag"] is True
    assert result["confidence"] >= 0.70


def test_apiris_high_risk_produces_block():
    """
    Proves that an under-ceiling call with degraded telemetry (risk_weight >= 0.80)
    triggers BLOCK via Rule 2.
    """
    high_risk_call = {
        "amount": 15000,  # 150 INR < ceiling
        "currency": "INR",
        "order_id": "order_high_risk",
        "agent_id": "agent_risk_test",
        "timing_ms": 3800.0,
        "mock_response": {
            "status": 500,
            "headers": {"content-type": "application/json"},
            "body": '{"error": {"code": "SERVICE_UNAVAILABLE"}}',
        },
        "error": {"type": "HTTPError", "message": "500 Service Unavailable"},
    }
    result = adapter.check(high_risk_call)
    assert result["verdict"] == "BLOCK", f"Expected BLOCK for high risk, got {result['verdict']}"
    assert result["decision"]["primary_factor"] == "apiris_high_risk"


def test_block_decision_explanation_names_primary_factor():
    """
    Phase 5 Test 1:
    Confirms that a BLOCK decision's explanation explicitly names the ceiling
    or risk factor as primary_factor in the structured explanation record,
    not a generic placeholder.
    """
    oversized_call = {
        "amount": 8000000,  # ₹80,000.00 > ₹50,000.00
        "currency": "INR",
        "agent_id": "agent_explainer_test",
    }
    result = adapter.check(oversized_call)
    assert result["verdict"] == "BLOCK"
    assert result["primary_factor"] == "amount_exceeded_ceiling"
    assert "₹80,000.00 BLOCKED: Exceeds policy amount ceiling" in result["summary"]
    assert result["explanation_record"]["evidence"]["policy"]["primary_factor"] == "amount_exceeded_ceiling"


def test_audit_db_persistence_and_retrieval():
    """
    Phase 5 Test 2:
    Confirms a row written via check() / control plane is persistently stored in
    SQLite and retrievable via get_recent_decisions() / /decisions read path.
    """
    init_db()
    client = TestClient(app)
    unique_agent = f"audit_agent_{int(time.time())}"

    # 1. Post payment check through FastAPI control plane
    post_res = client.post(
        "/gate/check",
        json={
            "amount": 25000,  # ₹250.00
            "currency": "INR",
            "agent_id": unique_agent,
            "action": "create_order",
        },
    )
    assert post_res.status_code == 200
    res_data = post_res.json()
    assert res_data["verdict"] == "ALLOW"
    audit_id = res_data.get("audit_id")
    assert audit_id is not None and audit_id > 0

    # 2. Retrieve through GET /decisions read path filtered by agent_id
    get_res = client.get(f"/decisions?agent_id={unique_agent}")
    assert get_res.status_code == 200
    rows = get_res.json()
    assert len(rows) >= 1
    latest = rows[0]
    assert latest["agent_id"] == unique_agent
    assert latest["amount_inr"] == 250.0
    assert latest["verdict"] == "ALLOW"
    assert latest["primary_factor"] == "policy_cleared"
    assert "APPROVED" in latest["summary"]
    assert latest["evidence"]["policy"]["amount_inr"] == 250.0
