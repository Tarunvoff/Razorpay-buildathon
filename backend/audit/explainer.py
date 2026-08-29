"""
Natural-language decision record generator for RazorGate.
Produces structured, deterministic, template-rendered explanation records
without any runtime LLM dependency.
"""

from typing import Any, Dict, List, Optional


def build_explanation(
    verdict: str,
    primary_factor: str,
    amount_inr: float,
    confidence: float,
    policy_reasons: Optional[List[str]] = None,
    apiris_score: Optional[Dict[str, Any]] = None,
    behavior_signal: Optional[Dict[str, Any]] = None,
    currency: str = "INR",
    payment_call: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Template-rendered decision explanation generator.

    Constructs a plain-English, auditable summary and structured evidence payload
    over the exact fields exposed by PolicyDecision and Apiris telemetry.
    """
    policy_reasons = policy_reasons or []
    apiris_score = apiris_score or {}
    behavior_signal = behavior_signal or {}

    amount_fmt = f"₹{amount_inr:,.2f}"

    # 1. Deterministic template rendering for summary based on primary_factor
    if primary_factor == "amount_exceeded_ceiling":
        summary = (
            f"Transaction of {amount_fmt} BLOCKED: Exceeds policy amount ceiling. "
            f"Rule reasons: {'; '.join(policy_reasons)}."
        )
    elif primary_factor == "apiris_high_risk":
        rw = apiris_score.get("risk_weight", 1.0)
        action = apiris_score.get("action", "unknown")
        summary = (
            f"Transaction of {amount_fmt} BLOCKED: High telemetry risk detected by Apiris "
            f"(risk_weight: {rw:.2f}, action: {action})."
        )
    elif primary_factor == "apiris_and_behavior_risk":
        rw = apiris_score.get("risk_weight", 0.0)
        b_reasons = ", ".join(behavior_signal.get("reasons", []))
        summary = (
            f"Transaction of {amount_fmt} FLAGGED for verification: Both moderate telemetry risk "
            f"(risk_weight: {rw:.2f}) and behavioral anomalies ({b_reasons}) detected."
        )
    elif primary_factor == "behavior_anomaly":
        b_reasons = ", ".join(behavior_signal.get("reasons", []))
        call_count = behavior_signal.get("session_call_count", 1)
        summary = (
            f"Transaction of {amount_fmt} FLAGGED for verification: Behavioral anomaly triggered "
            f"({b_reasons}, {call_count} calls in rolling window)."
        )
    elif primary_factor == "apiris_moderate_risk":
        rw = apiris_score.get("risk_weight", 0.0)
        summary = (
            f"Transaction of {amount_fmt} FLAGGED for verification: Moderate API telemetry risk "
            f"(risk_weight: {rw:.2f})."
        )
    else:  # policy_cleared / ALLOW
        summary = (
            f"Transaction of {amount_fmt} APPROVED: All policy and telemetry safety checks passed."
        )

    # 2. Structured evidence payload
    evidence = {
        "apiris": {
            "action": apiris_score.get("action", "pass_through"),
            "risk_weight": apiris_score.get("risk_weight", 0.0),
            "risk_weights": apiris_score.get("risk_weights", {}),
            "health_scores": apiris_score.get("health_scores", {}),
            "justification": apiris_score.get("justification", ""),
        },
        "behavior": {
            "flag": behavior_signal.get("flag", False),
            "reasons": behavior_signal.get("reasons", []),
            "session_call_count": behavior_signal.get("session_call_count", 0),
            "frequency": behavior_signal.get("frequency", 0),
            "amount_deviation_zscore": behavior_signal.get("amount_deviation_zscore", 0.0),
            "window_mean_amount": behavior_signal.get("window_mean_amount", 0.0),
            "window_std_amount": behavior_signal.get("window_std_amount", 0.0),
        },
        "policy": {
            "verdict": verdict,
            "primary_factor": primary_factor,
            "reasons": policy_reasons,
            "amount_inr": amount_inr,
        },
        "request": payment_call or {},
    }

    return {
        "verdict": verdict,
        "primary_factor": primary_factor,
        "confidence": confidence,
        "summary": summary,
        "amount_inr": amount_inr,
        "currency": currency,
        "evidence": evidence,
    }


class DecisionExplainer:
    """Wrapper class providing backwards-compatible explainer interface."""

    @staticmethod
    def explain(
        verdict: str,
        payment_call: Dict[str, Any],
        apiris_score: Optional[Dict[str, Any]] = None,
        behavior_signal: Optional[Dict[str, Any]] = None,
        rules_triggered: Optional[List[str]] = None,
    ) -> str:
        amount_raw = payment_call.get("amount", 0)
        amount_inr = payment_call.get("amount_inr", amount_raw / 100.0)
        record = build_explanation(
            verdict=verdict,
            primary_factor="policy_evaluation",
            amount_inr=amount_inr,
            confidence=1.0,
            policy_reasons=rules_triggered,
            apiris_score=apiris_score,
            behavior_signal=behavior_signal,
        )
        return record["summary"]


explainer = DecisionExplainer()
