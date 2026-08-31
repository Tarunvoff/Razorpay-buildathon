"""
Payments-native policy engine for RazorGate.
Combines Apiris per-call risk scoring with session-level behavioral signals.

Decision Hierarchy (First-match-wins):
1. Amount over ceiling -> BLOCK unconditionally (confidence: 1.0 deterministic)
2. Apiris risk_weight >= apiris_risk_block -> BLOCK (confidence: apiris confidence >= 0.90)
3. Apiris risk_weight >= apiris_risk_flag OR behavior anomaly flag -> FLAG
   (Behavior flags can only ever escalate toward FLAG, never trigger BLOCK on their own)
   (Confidence scales dynamically from ~0.70 at the flag boundary up to ~0.95 near the block threshold)
4. Otherwise -> ALLOW
   (confidence: apiris_confidence * (1.0 - risk_weight), 1.00 for clean traffic)
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
import yaml

Verdict = Literal["ALLOW", "BLOCK", "FLAG"]
POLICY_CONFIG_PATH = Path(__file__).parent / "policy.yaml"


@dataclass
class PolicyDecision:
    verdict: Verdict
    confidence: float
    reasons: List[str]
    primary_factor: str
    risk_weight: float
    behavior_flag: bool
    amount_inr: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_policy_config(merchant_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads the policy configuration YAML if present, with defaults.

    If merchant_id is provided and matches an entry in the ``merchants:`` section
    of policy.yaml, per-merchant overrides are merged on top of global defaults.
    Unknown merchant_ids silently fall back to global defaults.
    """
    default_config = {
        "max_order_amount_inr": 50000.0,
        "max_calls_per_agent_per_window": 5,
        "window_seconds": 300.0,
        "amount_deviation_std_threshold": 3.0,
        "apiris_risk_block": 0.80,
        "apiris_risk_flag": 0.40,
    }
    if POLICY_CONFIG_PATH.exists():
        try:
            with open(POLICY_CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                # Apply global keys (non-merchants section)
                global_overrides = {k: v for k, v in loaded.items() if k != "merchants"}
                default_config.update(global_overrides)
                # Apply per-merchant overrides if merchant_id matches
                if merchant_id:
                    merchants = loaded.get("merchants", {}) or {}
                    merchant_cfg = merchants.get(merchant_id, {}) or {}
                    default_config.update(merchant_cfg)
        except Exception:
            pass
    return default_config



def evaluate_policy(
    payment_call: Dict[str, Any],
    apiris_score: Dict[str, Any],
    behavior_signal: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    merchant_id: Optional[str] = None,
) -> PolicyDecision:
    """
    Evaluates payments-native rules against:
    1. Direct payment parameters (amount in paise/INR, currency)
    2. Apiris per-call risk_weight (inversion of C/A/D health scores)
    3. Session/agent behavior signal (frequency and amount deviation)

    Hierarchy is evaluated strictly first-match-wins:
    1. Amount over ceiling -> BLOCK
    2. High Apiris risk (risk_weight >= apiris_risk_block) -> BLOCK
    3. Moderate Apiris risk (risk_weight >= apiris_risk_flag) OR Behavior Flag -> FLAG
    4. Otherwise -> ALLOW

    If merchant_id is provided, per-merchant policy overrides from policy.yaml
    are applied on top of global defaults before evaluation.
    """
    cfg = config or load_policy_config(merchant_id=merchant_id)
    max_order_inr = float(cfg.get("max_order_amount_inr", 50000.0))
    risk_block_thresh = float(cfg.get("apiris_risk_block", 0.80))
    risk_flag_thresh = float(cfg.get("apiris_risk_flag", 0.40))
    freq_limit = int(cfg.get("max_calls_per_agent_per_window", 5))

    # Parse amount in INR: if given in paise (standard Razorpay), convert to INR
    amount_raw = payment_call.get("amount", 0)
    if "amount_inr" in payment_call:
        amount_inr = float(payment_call["amount_inr"])
    else:
        # Standard Razorpay API amounts are in paise (1 INR = 100 paise)
        amount_inr = float(amount_raw) / 100.0

    risk_weight = float(apiris_score.get("risk_weight", 0.0))
    apiris_confidence = float(apiris_score.get("confidence", 1.0))
    behavior_flag = bool(behavior_signal.get("flag")) if behavior_signal else False
    behavior_reasons = behavior_signal.get("reasons", []) if behavior_signal else []

    # 1. First-match: Amount over ceiling -> BLOCK unconditionally
    # Confidence: 1.0 (deterministic policy rule violation, invariant of telemetry)
    if amount_inr > max_order_inr:
        return PolicyDecision(
            verdict="BLOCK",
            confidence=1.0,
            reasons=[
                f"Order amount ₹{amount_inr:,.2f} exceeds policy ceiling of ₹{max_order_inr:,.2f}"
            ],
            primary_factor="amount_exceeded_ceiling",
            risk_weight=risk_weight,
            behavior_flag=behavior_flag,
            amount_inr=amount_inr,
        )

    # 2. Second-match: Apiris risk_weight at or above BLOCK threshold -> BLOCK
    # Confidence: inherits Apiris classification confidence (typically >= 0.90)
    if risk_weight >= risk_block_thresh:
        return PolicyDecision(
            verdict="BLOCK",
            confidence=round(apiris_confidence, 2),
            reasons=[
                f"Apiris risk weight ({risk_weight:.2f}) at or above block threshold ({risk_block_thresh:.2f})"
            ],
            primary_factor="apiris_high_risk",
            risk_weight=risk_weight,
            behavior_flag=behavior_flag,
            amount_inr=amount_inr,
        )

    # 3. Third-match: Moderate risk OR behavior anomaly -> FLAG
    # (Behavior flags only ever escalate toward FLAG, never trigger BLOCK on their own)
    is_moderate_apiris_risk = risk_weight >= risk_flag_thresh
    if is_moderate_apiris_risk or behavior_flag:
        flag_reasons = []
        apiris_flag_conf = 0.70
        if is_moderate_apiris_risk:
            flag_reasons.append(
                f"Apiris risk weight ({risk_weight:.2f}) at or above flag threshold ({risk_flag_thresh:.2f})"
            )
            # Boundary-distance scaling: confidence scales from 0.70 at flag threshold (0.40)
            # up to 0.95 near the block threshold (0.80)
            span = max(0.01, risk_block_thresh - risk_flag_thresh)
            position = max(0.0, min(1.0, (risk_weight - risk_flag_thresh) / span))
            apiris_flag_conf = round(0.70 + 0.25 * position, 2)

        behavior_flag_conf = 0.70
        if behavior_flag:
            flag_reasons.append(
                f"Behavioral anomalies detected: {', '.join(behavior_reasons)}"
            )
            count = behavior_signal.get("session_call_count", freq_limit) if behavior_signal else freq_limit
            excess = max(0, count - freq_limit)
            behavior_flag_conf = round(min(0.95, 0.75 + 0.05 * excess), 2)

        primary_factor = (
            "apiris_and_behavior_risk"
            if (is_moderate_apiris_risk and behavior_flag)
            else "apiris_moderate_risk"
            if is_moderate_apiris_risk
            else "behavior_anomaly"
        )

        final_flag_conf = (
            max(apiris_flag_conf, behavior_flag_conf)
            if (is_moderate_apiris_risk and behavior_flag)
            else apiris_flag_conf
            if is_moderate_apiris_risk
            else behavior_flag_conf
        )

        return PolicyDecision(
            verdict="FLAG",
            confidence=round(final_flag_conf, 2),
            reasons=flag_reasons,
            primary_factor=primary_factor,
            risk_weight=risk_weight,
            behavior_flag=behavior_flag,
            amount_inr=amount_inr,
        )

    # 4. Fourth-match: All checks passed -> ALLOW
    # Confidence: apiris_confidence scaled by safety margin (1.0 - risk_weight)
    allow_confidence = round(max(0.70, apiris_confidence * (1.0 - risk_weight)), 2)
    return PolicyDecision(
        verdict="ALLOW",
        confidence=allow_confidence,
        reasons=["All policy and telemetry safety checks passed"],
        primary_factor="policy_cleared",
        risk_weight=risk_weight,
        behavior_flag=behavior_flag,
        amount_inr=amount_inr,
    )
