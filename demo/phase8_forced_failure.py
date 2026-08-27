"""
Phase 8: Deliberate, Reproducible Forced-Failure Demonstration.

Demonstrates a Buyer Agent requesting an enterprise tier service that
exceeds RazorGate's deterministic policy ceiling (₹50,000).

Runs the full 6-step A2A protocol live to rejection, verifies that:
1. The transaction is BLOCKED with primary_factor: 'amount_exceeded_ceiling'.
2. Downstream Razorpay /orders is NEVER touched.
3. The Buyer Agent handles the rejection gracefully in natural language.
4. No partial side effects exist.
"""

import json
import sys
import time
from pathlib import Path

# Ensure UTF-8 output encoding on all platforms
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.agent.buyer_agent import BuyerAgent
from backend.agent.merchant_agent import MerchantAgent
from backend.audit.db import get_decision_by_id, init_db
from backend.gate.policy import load_policy_config


def run_forced_failure_demo(silent: bool = False) -> dict:
    """
    Executes a single end-to-end forced-failure protocol run.
    Returns summary metrics for verification.
    """
    init_db()
    policy_cfg = load_policy_config()
    ceiling_inr = policy_cfg.get("max_order_amount_inr", 50000.0)

    # 1. Instantiate agents
    merchant = MerchantAgent(
        merchant_id="merchant_razorgate_cloud",
        merchant_name="RazorGate Cloud & AI Compute Services",
        secret_key="razorgate_demo_secret",
    )
    buyer = BuyerAgent(
        agent_id=f"buyer_enterprise_exec_{int(time.time() * 1000) % 100000}",
        max_budget_paise=10000000,  # ₹100,000.00 authorized by corporate card
        secret_key="razorgate_demo_secret",
    )

    if not silent:
        print("\n" + "=" * 70)
        print("  RAZORGATE A2A COMMERCE — PHASE 8 FORCED-FAILURE DEMO")
        print("=" * 70)
        print(f"[*] Configured Policy Ceiling: ₹{ceiling_inr:,.2f} INR")
        print(f"[*] Buyer Agent ID:           {buyer.agent_id}")
        print(f"[*] Buyer Authorized Budget:  ₹{buyer.max_budget_paise / 100:,.2f} INR")
        print("-" * 70)

    # 2. Natural, realistic enterprise intent
    intent = "Enterprise 24/7 dedicated support & quarterly architecture review for mission-critical deployment"
    category = "enterprise_services"

    if not silent:
        print(f"[Step 1-4] Buyer expressing intent: '{intent}'...")

    receipt, transcript = buyer.execute_transaction(
        merchant=merchant,
        intent=intent,
        category=category,
        preferred_sku="enterprise-support-tier1",
    )

    if not silent:
        # Print negotiation and mandate details
        mandate_step = next((s for s in transcript if s["step"] == "payment_mandate"), None)
        if mandate_step:
            mandate_data = mandate_step["data"]
            print(f"[Step 4] Signed Payment Mandate Issued:")
            print(f"         - SKU:       {mandate_data.get('sku')}")
            print(f"         - Amount:    ₹{mandate_data.get('amount_paise', 0) / 100:,.2f} INR")
            print(f"         - Reasoning: {mandate_data.get('reasoning')}")
            print(f"         - Signature: {mandate_data.get('signature')[:16]}... (HMAC-SHA256)")

        print("\n[Step 5] Merchant submitted mandate to RazorGate Gate Engine...")
        print(f"         - Verdict:        {receipt.verdict}")
        print(f"         - Primary Factor: {receipt.primary_factor}")
        print(f"         - Confidence:     {receipt.confidence * 100:.0f}%")
        print(f"         - Audit ID:       #{receipt.audit_id}")
        print(f"         - Summary:        {receipt.summary}")

    # 3. Buyer Agent Natural Language Graceful Explanation
    agent_statement = buyer.explain_outcome(receipt)

    if not silent:
        print("\n[Step 6] Buyer Agent Final User-Facing Response:")
        print(f"  \"{agent_statement}\"")
        print("-" * 70)

    # 4. Verify no partial side effects in SQLite audit DB
    audit_row = get_decision_by_id(receipt.audit_id) if receipt.audit_id else None
    razorpay_order_id = audit_row.get("razorpay_order_id") if audit_row else None
    orders_reached = receipt.order is not None or razorpay_order_id is not None

    if not silent:
        print("[*] Side-Effect Invariant Check:")
        print(f"    - Audit Record Saved:       {'YES' if audit_row else 'NO'} (#{receipt.audit_id})")
        print(f"    - Razorpay Order Created:   {'YES (VIOLATION)' if orders_reached else 'NO (ZERO SIDE EFFECTS)'}")
        print("=" * 70 + "\n")

    return {
        "agent_id": buyer.agent_id,
        "sku": receipt.sku,
        "amount_inr": receipt.amount_inr,
        "verdict": receipt.verdict,
        "primary_factor": receipt.primary_factor,
        "audit_id": receipt.audit_id,
        "agent_statement": agent_statement,
        "orders_reached": orders_reached,
        "razorpay_order": receipt.order,
    }


if __name__ == "__main__":
    run_forced_failure_demo()
