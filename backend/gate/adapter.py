import json
import time
from typing import Any, Dict, Literal, Optional, TypedDict

import apiris
from apiris.config import ApirisConfig
from apiris.decision_engine import DecisionEngine
from apiris.evaluator import ObservationEvaluator

Verdict = Literal["ALLOW", "BLOCK", "FLAG"]


class GateResult(TypedDict):
    verdict: Verdict
    confidence: float
    explanation: str
    apiris_score: Dict[str, Any]


def create_apiris_engine(config: Optional[ApirisConfig] = None) -> tuple[ObservationEvaluator, DecisionEngine]:
    """Factory creating configured Apiris ObservationEvaluator and DecisionEngine instances."""
    cfg = config or ApirisConfig(
        enable_ai=True,
        integrity_threshold=0.0,
        availability_threshold=0.5,
        latency_budget_ms=1000,
        mode="enforce",
    )
    return ObservationEvaluator(cfg), DecisionEngine(cfg)


def score_payment_call(payment_call: dict, evaluator: Optional[ObservationEvaluator] = None, engine: Optional[DecisionEngine] = None) -> dict:
    """
    Scores a Razorpay payment call through Apiris ObservationEvaluator
    and DecisionEngine.

    CRITICAL SIGN CONVENTION:
    Apiris C_score, A_score, and D_score are HEALTH scores [0.0 - 1.0]:
      - 1.0 = optimal health, zero anomalies/defects detected.
      - Dropping toward 0.0 = defects/anomalies detected (latency surge, 500 error,
        data leakage, schema corruption).
    To avoid downstream sign confusion in policy evaluation, we explicitly compute:
      risk_weight = 1.0 - health_score
      - Near-1.0 health produces near-0.0 risk_weight (safe).
      - Near-0.0 health produces near-1.0 risk_weight (high risk).
    """
    if evaluator is None or engine is None:
        evaluator, engine = create_apiris_engine()

    amount = payment_call.get("amount", 50000)
    currency = payment_call.get("currency", "INR")
    receipt = payment_call.get("receipt", f"rcpt_{int(time.time())}")
    method = payment_call.get("method", "POST")
    url = payment_call.get("url", "https://api.razorpay.com/v1/orders")
    order_id = payment_call.get("order_id", f"order_{int(time.time())}")

    # High-fidelity request signature
    request_body = {
        "amount": amount,
        "currency": currency,
        "receipt": receipt,
        "notes": payment_call.get("notes", {"source": "buyer_agent"}),
    }
    request_data = {
        "method": method,
        "url": url,
        "headers": {
            "content-type": "application/json",
            "user-agent": "RazorGate/1.0",
            "x-razorpay-session-id": payment_call.get("session_id", "default_session"),
        },
        "body": json.dumps(request_body),
    }

    # High-fidelity response telemetry: use custom response if supplied,
    # otherwise construct a clean, realistic Razorpay Order entity response
    mock_resp = payment_call.get("mock_response")
    if mock_resp:
        response_status = mock_resp.get("status", 200)
        response_headers = mock_resp.get("headers", {"content-type": "application/json"})
        response_body = mock_resp.get("body", "{}")
        if isinstance(response_body, dict):
            response_body = json.dumps(response_body)
    else:
        response_status = 200
        response_headers = {
            "content-type": "application/json",
            "x-ratelimit-limit": "100",
            "x-ratelimit-remaining": "98",
            "x-ratelimit-reset": str(int(time.time()) + 60),
        }
        response_body = json.dumps({
            "id": order_id,
            "entity": "order",
            "amount": amount,
            "amount_paid": 0,
            "amount_due": amount,
            "currency": currency,
            "receipt": receipt,
            "status": "created",
            "attempts": 0,
            "created_at": int(time.time()),
        })

    error = payment_call.get("error")
    timing_ms = payment_call.get("timing_ms", 120.0)
    seq = payment_call.get("seq", 1)
    session_id = payment_call.get("session_id", "default_session")

    runtime_context = {
        "timing_ms": timing_ms,
        "duration_ms": timing_ms,
        "soft_timeout_ms": 2000,
        "seq": seq,
        "run_id": session_id,
    }

    # 1. Run observation evaluation (schema hashing, drift detection, security scans)
    observation = evaluator.evaluate(
        api="razorpay",
        request=request_data,
        response={
            "status": response_status,
            "headers": response_headers,
            "body": response_body,
        },
        error=error,
        runtime_context=runtime_context,
    )

    # 2. Run multi-objective decision engine
    try:
        parsed_body = json.loads(response_body)
    except Exception:
        parsed_body = {}

    decision_output = engine.evaluate(
        observation=observation,
        response_text=response_body,
        parsed=parsed_body,
        response_headers=response_headers,
        response_status=response_status,
    )
    return decision_output


def check(payment_call: dict) -> GateResult:
    """
    Evaluates the payment call through Apiris intelligence.
    Extracts raw apiris action and calculates explicit inverted risk_weights.
    Real payments-native policy enforcement (ALLOW/BLOCK/FLAG) combining Apiris + behavior
    signal is wired in policy.py in Phase 4.
    """
    apiris_eval = score_payment_call(payment_call)
    decision = apiris_eval.get("decision", {})
    scores = decision.get("scores", {})
    action = decision.get("action", "pass_through")

    c_score = float(scores.get("C_score", 1.0))
    a_score = float(scores.get("A_score", 1.0))
    d_score = float(scores.get("D_score", 1.0))
    confidence = float(decision.get("confidence", 1.0))
    justification = str(decision.get("justification", "Scores within acceptable bounds"))

    # Explicit risk weight inversion: risk_weight = 1.0 - health_score
    risk_c = round(max(0.0, min(1.0, 1.0 - c_score)), 4)
    risk_a = round(max(0.0, min(1.0, 1.0 - a_score)), 4)
    risk_d = round(max(0.0, min(1.0, 1.0 - d_score)), 4)
    composite_risk_weight = round(max(risk_c, risk_a, risk_d), 4)

    apiris_summary: Dict[str, Any] = {
        "action": action,
        "risk_weight": composite_risk_weight,
        "risk_weights": {
            "confidentiality": risk_c,
            "availability": risk_a,
            "integrity": risk_d,
        },
        "health_scores": {
            "C_score": c_score,
            "A_score": a_score,
            "D_score": d_score,
        },
        "integrityRate": scores.get("integrityRate", 0.0),
        "confidence": confidence,
        "justification": justification,
    }

    return {
        "verdict": "ALLOW",
        "confidence": confidence,
        "explanation": f"apiris evaluation: action={action}, risk_weight={composite_risk_weight:.2f} (health: A={a_score:.2f}, D={d_score:.2f}, C={c_score:.2f})",
        "apiris_score": apiris_summary,
    }
