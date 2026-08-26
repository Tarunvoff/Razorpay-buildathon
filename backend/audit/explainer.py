"""
Natural-language decision record generator for RazorGate.
Adapted from cadlens's explainer architecture, tailored to payments-native
risk factors, Apiris per-call scoring, and behavioral drift metrics.
"""

from typing import Any, Dict, List, Optional


class DecisionExplainer:
    """
    Generates human-readable, auditable natural-language explanations
    for RazorGate decisions (ALLOW, BLOCK, FLAG).
    """

    @staticmethod
    def explain(
        verdict: str,
        payment_call: Dict[str, Any],
        apiris_score: Optional[Dict[str, Any]] = None,
        behavior_signal: Optional[Dict[str, Any]] = None,
        rules_triggered: Optional[List[str]] = None,
    ) -> str:
        """
        Produces an explainable summary of the gate decision.
        """
        amount_paise = payment_call.get("amount", 0)
        currency = payment_call.get("currency", "INR")
        amount_fmt = f"{amount_paise / 100:.2f} {currency}"
        action = payment_call.get("action", "payment call")

        rules_str = ", ".join(rules_triggered) if rules_triggered else "none"
        parts = []

        if verdict == "ALLOW":
            parts.append(f"Approved {action} of {amount_fmt}.")
            if apiris_score:
                parts.append(
                    f"Apiris scoring confirmed normal telemetry (integrity: {apiris_score.get('D_score', 1.0):.2f})."
                )
            if behavior_signal and not behavior_signal.get("drift_detected"):
                parts.append("Session velocity and failure rate within safe bounds.")

        elif verdict == "BLOCK":
            parts.append(f"Blocked {action} of {amount_fmt}.")
            if rules_triggered:
                parts.append(f"Triggered safety policy rules: {rules_str}.")
            if behavior_signal and behavior_signal.get("brownout_detected"):
                parts.append("Elevated consecutive failure rate detected in session.")

        elif verdict == "FLAG":
            parts.append(f"Flagged {action} of {amount_fmt} for agent verification.")
            if rules_triggered:
                parts.append(f"Triggered threshold warning: {rules_str}.")
            if apiris_score and apiris_score.get("integrityRate", 0) > 0.5:
                parts.append("Statistical anomaly detected in API telemetry.")
        else:
            parts.append(f"Decision: {verdict} for {action} of {amount_fmt}.")

        return " ".join(parts)


# Default explainer instance
explainer = DecisionExplainer()
