import os
import time
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.audit.db import (
    get_decision_by_id,
    get_recent_decisions,
    init_db,
    link_order_to_decision,
    record_decision,
)
from backend.audit.explainer import build_explanation
from backend.config import settings
from backend.control.app import app
from backend.gate import adapter
from backend.gate.behavior import BehaviorAnalyzer, InMemoryWindowStore
from backend.payments import razorpay_client


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

    raw_eval = adapter.score_payment_call(clean_call)
    decision = raw_eval.get("decision", {})
    scores = decision.get("scores", {})

    assert decision.get("action") == "pass_through", f"Expected pass_through, got {decision.get('action')}"
    assert scores.get("C_score", 0.0) >= 0.5, f"C_score too low: {scores.get('C_score')}"
    assert scores.get("A_score", 0.0) >= 0.5, f"A_score too low: {scores.get('A_score')}"
    assert scores.get("D_score", 0.0) >= 0.5, f"D_score too low: {scores.get('D_score')}"

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
    """
    store = InMemoryWindowStore()
    analyzer = BehaviorAnalyzer(window_seconds=300.0, frequency_threshold=5, store=store)

    burst_results = []
    base_time = time.time()
    for i in range(6):
        res = analyzer.record_and_evaluate(
            agent_id="burst_agent",
            amount_paise=10000,
            timestamp=base_time + i * 2,
        )
        burst_results.append(res)

    last_burst_result = burst_results[-1]
    assert last_burst_result["flag"] is True, "Burst exceeding threshold must flag"
    assert "high_frequency" in last_burst_result["reasons"], f"Expected 'high_frequency' in reasons, got {last_burst_result['reasons']}"
    assert last_burst_result["session_call_count"] == 6

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
    Same agent_id, several calls at a stable baseline amount (₹100 / 10,000 paise),
    then one call at a significantly different outlier amount (₹5,000 / 500,000 paise)
    with total calls under frequency threshold (N=4 <= 5), asserting 'amount_deviation' flags.
    """
    store = InMemoryWindowStore()
    analyzer = BehaviorAnalyzer(window_seconds=300.0, frequency_threshold=5, std_dev_threshold=3.0, store=store)
    base_time = time.time()
    agent_id = "agent_spending_drift"

    for i in range(3):
        res = analyzer.record_and_evaluate(
            agent_id=agent_id,
            amount_paise=10000,
            timestamp=base_time + i * 5,
        )
        assert res["flag"] is False, f"Baseline call {i+1} should not flag"

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
    with high confidence and primary_factor 'policy_cleared', and mints an allow_token.
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
    assert result["allow_token"] is not None, "ALLOW verdict must mint a server-issued allow_token"


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


def test_flag_confidence_boundary_scaling():
    """
    Item 2 Verification:
    Asserts that a barely-flagged call (risk_weight=0.42 near flag threshold 0.40)
    produces a lower confidence score than a clearly-flagged call (risk_weight=0.75 near block threshold 0.80).
    """
    from backend.gate.policy import evaluate_policy

    barely_flagged_score = {"risk_weight": 0.42, "confidence": 1.0}
    clearly_flagged_score = {"risk_weight": 0.75, "confidence": 1.0}

    call = {"amount": 10000, "currency": "INR"}
    dec_barely = evaluate_policy(payment_call=call, apiris_score=barely_flagged_score)
    dec_clearly = evaluate_policy(payment_call=call, apiris_score=clearly_flagged_score)

    assert dec_barely.verdict == "FLAG"
    assert dec_clearly.verdict == "FLAG"
    assert dec_barely.confidence < dec_clearly.confidence, (
        f"Barely flagged confidence ({dec_barely.confidence}) must be lower than clearly flagged ({dec_clearly.confidence})"
    )
    assert dec_barely.confidence <= 0.75
    assert dec_clearly.confidence >= 0.90


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
    Phase 5 Test 2 & Item 3:
    Hits FastAPI endpoints directly via TestClient (/gate/check, /decisions, /decisions/{id})
    to confirm end-to-end HTTP persistence and paginated retrieval.
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
    assert res_data.get("allow_token") is not None

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

    # 3. Retrieve single record via GET /decisions/{id}
    single_res = client.get(f"/decisions/{audit_id}")
    assert single_res.status_code == 200
    single_item = single_res.json()
    assert single_item["id"] == audit_id
    assert single_item["agent_id"] == unique_agent


def test_amount_paise_and_inr_conversion_accuracy():
    """
    Item 4 Verification:
    Asserts exact 100:1 conversion between amount_paise and amount_inr in SQLite audit DB.
    """
    init_db()
    client = TestClient(app)
    agent_id = f"agent_unit_test_{int(time.time())}"
    test_amount_paise = 123456  # ₹1,234.56

    res = client.post(
        "/gate/check",
        json={
            "amount": test_amount_paise,
            "currency": "INR",
            "agent_id": agent_id,
            "action": "create_order",
        },
    )
    assert res.status_code == 200
    audit_id = res.json()["audit_id"]

    record = client.get(f"/decisions/{audit_id}").json()
    assert record["amount_paise"] == test_amount_paise
    assert record["amount_inr"] == round(test_amount_paise / 100.0, 2)
    assert record["amount_inr"] == 1234.56


def test_orders_endpoint_forbidden_without_valid_allow_token():
    """
    Phase 6 Test 1:
    Confirms POST /orders returns 403 Forbidden when called with missing,
    forged, or expired ALLOW tokens.
    """
    client = TestClient(app)

    # 1. Missing / invalid token
    res_invalid = client.post(
        "/orders",
        json={
            "agent_id": "buyer_agent_01",
            "amount_paise": 50000,
            "receipt": "rcpt_invalid_token",
            "allow_token": "forged.token12345",
        },
    )
    assert res_invalid.status_code == 403
    assert res_invalid.json()["detail"] == "token_invalid"

    # 2. Expired token (> 30s TTL)
    old_timestamp = time.time() - 100.0  # 100 seconds ago
    expired_token = razorpay_client.mint_allow_token(
        agent_id="buyer_agent_01",
        amount_paise=50000,
        receipt="rcpt_expired",
        timestamp=old_timestamp,
    )
    res_expired = client.post(
        "/orders",
        json={
            "agent_id": "buyer_agent_01",
            "amount_paise": 50000,
            "receipt": "rcpt_expired",
            "allow_token": expired_token,
        },
    )
    assert res_expired.status_code == 403
    assert res_expired.json()["detail"] == "token_expired"


def test_allow_token_mismatch_and_replay_defense():
    """
    Phase 6 Negative Path Test 2 (Replay / Tampering Defense):
    Proves that a cryptographically valid ALLOW token minted for:
      (agent='agent_alice', amount=10000, receipt='rcpt_1')
    is REJECTED with 403 Forbidden if presented by:
      (a) A different agent ('agent_bob')
      (b) A different/tampered amount (amount=50000)
      (c) A different receipt ('rcpt_2')
    """
    client = TestClient(app)
    valid_token = razorpay_client.mint_allow_token(
        agent_id="agent_alice",
        amount_paise=10000,
        receipt="rcpt_1",
    )

    # (a) Mismatched agent_id
    res_agent_mismatch = client.post(
        "/orders",
        json={
            "agent_id": "agent_bob",
            "amount_paise": 10000,
            "receipt": "rcpt_1",
            "allow_token": valid_token,
        },
    )
    assert res_agent_mismatch.status_code == 403
    assert "token_invalid" in res_agent_mismatch.json()["detail"]

    # (b) Tampered / escalated amount
    res_amount_mismatch = client.post(
        "/orders",
        json={
            "agent_id": "agent_alice",
            "amount_paise": 50000,  # Escalated from 10000 -> 50000
            "receipt": "rcpt_1",
            "allow_token": valid_token,
        },
    )
    assert res_amount_mismatch.status_code == 403
    assert "token_invalid" in res_amount_mismatch.json()["detail"]

    # (c) Mismatched receipt
    res_receipt_mismatch = client.post(
        "/orders",
        json={
            "agent_id": "agent_alice",
            "amount_paise": 10000,
            "receipt": "rcpt_forged_2",
            "allow_token": valid_token,
        },
    )
    assert res_receipt_mismatch.status_code == 403
    assert "token_invalid" in res_receipt_mismatch.json()["detail"]


def test_allow_token_sku_scoping_rejection():
    """
    Proves that an ALLOW token minted specifically for (merchant='merchant_a', sku='sku_l4')
    is REJECTED with 403 Forbidden / TokenInvalidError if presented for a different SKU ('sku_h100')
    or a different merchant ('merchant_b') at the exact same agent, amount, and receipt.
    """
    client = TestClient(app)
    agent_id = "agent_scoping_test"
    amount_paise = 29900
    receipt = "rcpt_scoping_1"

    # Mint token explicitly bound to merchant_a and sku_l4
    bound_token = razorpay_client.mint_allow_token(
        agent_id=agent_id,
        amount_paise=amount_paise,
        receipt=receipt,
        merchant_id="merchant_a",
        sku="sku_l4",
    )

    # 1. Matching merchant and SKU succeeds verification
    assert razorpay_client.verify_allow_token(
        token=bound_token,
        agent_id=agent_id,
        amount_paise=amount_paise,
        receipt=receipt,
        merchant_id="merchant_a",
        sku="sku_l4",
    ) is True

    # 2. Presentation for mismatched SKU fails via direct function call
    try:
        razorpay_client.verify_allow_token(
            token=bound_token,
            agent_id=agent_id,
            amount_paise=amount_paise,
            receipt=receipt,
            merchant_id="merchant_a",
            sku="sku_h100",  # Mismatched SKU!
        )
        assert False, "Should raise TokenInvalidError on SKU mismatch"
    except razorpay_client.TokenInvalidError:
        pass

    # 3. Presentation via HTTP POST /orders with mismatched SKU returns 403 Forbidden
    res_sku_mismatch = client.post(
        "/orders",
        json={
            "agent_id": agent_id,
            "amount_paise": amount_paise,
            "receipt": receipt,
            "merchant_id": "merchant_a",
            "sku": "sku_h100",  # Mismatched SKU
            "allow_token": bound_token,
        },
    )
    assert res_sku_mismatch.status_code == 403
    assert "token_invalid" in res_sku_mismatch.json()["detail"]


def test_orders_endpoint_creates_order_and_links_audit_id():
    """
    Phase 6 Test 3 (Audit-to-Order Link):
    Confirms that check() producing an ALLOW verdict yields an allow_token,
    which executes POST /orders within TTL and links the resulting razorpay_order_id
    back to the originating SQLite audit ledger row.
    """
    init_db()
    client = TestClient(app)
    agent_id = f"agent_buyer_{int(time.time())}"
    amount_paise = 25000
    receipt = f"rcpt_e2e_{int(time.time())}"

    # 1. Gate check produces ALLOW and returns audit_id + allow_token
    check_res = client.post(
        "/gate/check",
        json={
            "amount": amount_paise,
            "currency": "INR",
            "agent_id": agent_id,
            "receipt": receipt,
            "action": "create_order",
        },
    )
    assert check_res.status_code == 200
    check_data = check_res.json()
    assert check_data["verdict"] == "ALLOW"
    audit_id = check_data["audit_id"]
    allow_token = check_data["allow_token"]
    assert audit_id is not None
    assert allow_token is not None

    # 2. Call POST /orders with audit_id and allow_token
    mock_rzp_id = f"order_rzp_{int(time.time())}"
    with patch.object(
        razorpay_client.client.order,
        "create",
        return_value={
            "id": mock_rzp_id,
            "entity": "order",
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "status": "created",
        },
    ):
        order_res = client.post(
            "/orders",
            json={
                "agent_id": agent_id,
                "amount_paise": amount_paise,
                "receipt": receipt,
                "allow_token": allow_token,
                "currency": "INR",
                "audit_id": audit_id,
            },
        )
        assert order_res.status_code == 200
        order_body = order_res.json()
        assert order_body["status"] == "created"
        assert order_body["order"]["id"] == mock_rzp_id

    # 3. Verify SQLite decision row is updated with razorpay_order_id
    updated_record = client.get(f"/decisions/{audit_id}").json()
    assert updated_record["razorpay_order_id"] == mock_rzp_id


def test_created_order_is_retrievable_from_razorpay():
    """
    Phase 6 Test 4:
    Automated regression guard proving that creating an order and fetching it back
    via client.order.fetch(order_id) retrieves the exact same order structure.
    Executes live against real Razorpay API when real credentials are present.
    """
    agent_id = "test_fetch_agent"
    amount_paise = 30000
    receipt = f"rcpt_fetch_{int(time.time())}"

    # If real test credentials are configured, run against live Razorpay API
    is_live_key = settings.razorpay_key_id.startswith("rzp_test_") and "dummy" not in settings.razorpay_key_id

    if is_live_key:
        token = razorpay_client.mint_allow_token(agent_id, amount_paise, receipt)
        created = razorpay_client.create_gated_order(
            agent_id=agent_id,
            amount_paise=amount_paise,
            receipt=receipt,
            allow_token=token,
        )
        assert created["id"].startswith("order_")
        assert created["status"] == "created"

        fetched = razorpay_client.fetch_order(created["id"])
        assert fetched["id"] == created["id"]
        assert fetched["amount"] == amount_paise
        assert fetched["receipt"] == receipt
        assert fetched["status"] == "created"
    else:
        # Deterministic unit test fallback
        expected_order_id = f"order_fetch_{int(time.time())}"
        order_payload = {
            "id": expected_order_id,
            "entity": "order",
            "amount": amount_paise,
            "amount_paid": 0,
            "amount_due": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "status": "created",
            "attempts": 0,
        }
        with patch.object(razorpay_client.client.order, "create", return_value=order_payload), \
             patch.object(razorpay_client.client.order, "fetch", return_value=order_payload):
            token = razorpay_client.mint_allow_token(agent_id, amount_paise, receipt)
            created = razorpay_client.create_gated_order(
                agent_id=agent_id,
                amount_paise=amount_paise,
                receipt=receipt,
                allow_token=token,
            )
            assert created["id"] == expected_order_id
            fetched = razorpay_client.fetch_order(created["id"])
            assert fetched["id"] == expected_order_id
            assert fetched["amount"] == amount_paise


def test_verify_order_tampered_signature_rejection():
    """
    Requirement 3 Proof: Confirms that POST /orders/verify independently recomputes
    the HMAC-SHA256 signature and rejects any tampered or forged signature with HTTP 400 Bad Request.
    """
    client = TestClient(app)

    payload = {
        "razorpay_order_id": "order_test_123456",
        "razorpay_payment_id": "pay_test_987654",
        "razorpay_signature": "tampered_bogus_hmac_signature_00000000000000000000000000000000",
        "audit_id": 9999,
    }

    response = client.post("/orders/verify", json=payload)
    assert response.status_code == 400, f"Expected HTTP 400 for tampered signature, got {response.status_code}"
    data = response.json()
    assert "detail" in data
    assert "Invalid Razorpay payment signature" in data["detail"]


def test_verify_order_valid_signature_success():
    """
    Confirms that POST /orders/verify succeeds when passed a valid HMAC signature
    computed using the server's key secret over (order_id + "|" + payment_id).
    """
    import hashlib
    import hmac

    client = TestClient(app)

    order_id = "order_valid_12345"
    payment_id = "pay_valid_67890"
    secret = (settings.razorpay_key_secret or "razorgate_default_signing_secret").encode("utf-8")
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    valid_signature = hmac.new(secret, msg, hashlib.sha256).hexdigest()

    payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": valid_signature,
        "audit_id": 1001,
    }

    mock_order = {
        "id": order_id,
        "entity": "order",
        "amount": 29900,
        "currency": "INR",
        "status": "paid",
    }

    with patch.object(razorpay_client, "fetch_order", return_value=mock_order):
        response = client.post("/orders/verify", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "verified"
        assert data["verified"] is True
        assert data["razorpay_payment_id"] == payment_id
        assert data["razorpay_order_id"] == order_id


def test_scenario_2_reproducibility_five_runs():
    """
    Requirement 6 Proof: Confirms Scenario 2 (Behavioral Anomaly FLAG) reliably
    produces FLAG across 5 consecutive runs when 6 rapid calls are made with a fixed agent_id.
    """
    from backend.gate.behavior import behavior_analyzer

    client = TestClient(app)
    agent_id = "demo_flag_burst_agent"

    for run_idx in range(5):
        # Evict prior window history before starting sequence
        behavior_analyzer.store.evict(agent_id, time.time() + 1000)


        results = []
        for call_i in range(6):
            res = client.post(
                "/gate/check",
                json={
                    "amount": 4900,
                    "currency": "INR",
                    "agent_id": agent_id,
                    "receipt": f"rcpt_burst_{run_idx}_{call_i}",
                    "action": "create_order",
                },
            )
            assert res.status_code == 200
            results.append(res.json())

        # Calls 1..5 must be ALLOW
        for i in range(5):
            assert results[i]["verdict"] == "ALLOW", f"Run {run_idx+1}: Call {i+1} expected ALLOW, got {results[i]['verdict']}"

        # Call 6 MUST be FLAG
        final_call = results[5]
        assert final_call["verdict"] == "FLAG", f"Run {run_idx+1}: Call 6 expected FLAG, got {final_call['verdict']}. Full payload: {final_call}"
        assert final_call["primary_factor"] == "behavior_anomaly"







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

