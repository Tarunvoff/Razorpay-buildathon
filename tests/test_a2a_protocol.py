"""
RazorGate Agent-to-Agent (A2A) Protocol Test Suite.

Verifies the 6-step A2A commerce lifecycle, cryptographic mandate verification,
anti-hallucination comparative reasoning, and policy ceiling enforcement.
"""

import time
from unittest.mock import MagicMock, patch

from backend.agent.buyer_agent import BuyerAgent
from backend.agent.catalog import DEFAULT_CATALOG
from backend.agent.merchant_agent import MerchantAgent
from backend.agent.protocol import (
    AgentCard,
    Offer,
    OfferList,
    PaymentMandate,
    Receipt,
    TaskRequest,
    sign_payment_mandate,
    verify_payment_mandate,
)
from backend.audit.db import init_db
from backend.config import settings
from backend.gate.policy import load_policy_config
from backend.payments import razorpay_client


def test_a2a_full_protocol_roundtrip_happy_path():
    """
    Test 1: Full Protocol Round-Trip (Happy Path).
    1. Buyer discovers Merchant AgentCard (with GateDisclosure).
    2. Buyer sends TaskRequest for AI compute.
    3. Merchant returns ranked OfferList with gate_disclosure attached.
    4. Buyer performs comparative reasoning and issues signed PaymentMandate.
    5. Merchant verifies mandate, executes gate check -> ALLOW, creates real Razorpay order.
    6. Merchant returns Receipt with verdict, explanation, and real order.
    7. Validates order fetch-back from Razorpay.
    """
    init_db()
    merchant = MerchantAgent(
        merchant_id="merchant_razorgate_test",
        secret_key="shared_test_secret_key",
    )
    buyer = BuyerAgent(
        agent_id=f"buyer_happy_{int(time.time())}",
        max_budget_paise=50000,  # ₹500.00
        secret_key="shared_test_secret_key",
    )

    is_live_key = settings.razorpay_key_id.startswith("rzp_test_") and "dummy" not in settings.razorpay_key_id

    if is_live_key:
        # Live Razorpay API Execution
        receipt, transcript = buyer.execute_transaction(
            merchant=merchant,
            intent="GPU compute for model inference",
            category="ai_compute",
            strategy="intent_match",
        )

        assert receipt.verdict == "ALLOW"
        assert receipt.primary_factor == "policy_cleared"
        assert receipt.order is not None
        assert "id" in receipt.order
        order_id = receipt.order["id"]
        assert order_id.startswith("order_")

        # Fetch back from Razorpay to prove genuine order existence
        fetched_order = razorpay_client.fetch_order(order_id)
        assert fetched_order["id"] == order_id
        assert fetched_order["amount"] == receipt.amount_paise
        assert fetched_order["status"] == "created"
    else:
        # Deterministic Mock Execution
        mock_order_id = f"order_a2a_{int(time.time())}"
        order_mock_payload = {
            "id": mock_order_id,
            "entity": "order",
            "amount": 14900,
            "amount_paid": 0,
            "amount_due": 14900,
            "currency": "INR",
            "receipt": "rcpt_test",
            "status": "created",
            "attempts": 0,
        }

        with patch.object(razorpay_client.client.order, "create", return_value=order_mock_payload), \
             patch.object(razorpay_client.client.order, "fetch", return_value=order_mock_payload):

            receipt, transcript = buyer.execute_transaction(
                merchant=merchant,
                intent="GPU compute for model inference",
                category="ai_compute",
                strategy="intent_match",
            )

            assert receipt.verdict == "ALLOW"
            assert receipt.primary_factor == "policy_cleared"
            assert receipt.order is not None
            assert receipt.order["id"] == mock_order_id

            fetched_order = razorpay_client.fetch_order(mock_order_id)
            assert fetched_order["id"] == mock_order_id

    # Verify transcript contains all 6 steps in order
    step_names = [entry["step"] for entry in transcript]
    assert step_names == [
        "capability_discovery",
        "task_request",
        "received_offers",
        "selection_reasoning",
        "payment_mandate",
        "receipt",
    ]


def test_a2a_tampered_mandate_rejected_before_orders():
    """
    Test 2: Tampered Mandate Rejection (Amount Tampering & Same-Amount SKU Substitution).
    Proves that:
      (a) Altering amount invalidates HMAC signature.
      (b) Substituting a different SKU at the SAME signed amount invalidates HMAC signature.
    Both must be rejected with BLOCK before touching the gate check or Razorpay /orders.
    """
    init_db()
    merchant = MerchantAgent(
        merchant_id="merchant_tamper_test",
        secret_key="secret_legit_key",
    )
    buyer = BuyerAgent(
        agent_id="buyer_tamper_test",
        max_budget_paise=50000,
        secret_key="secret_legit_key",
    )

    # 1. Buyer signs valid mandate for A100 (₹149.00 / 14,900 paise)
    ts, valid_sig = sign_payment_mandate(
        buyer_agent_id="buyer_tamper_test",
        merchant_id="merchant_tamper_test",
        sku="compute-gpu-a100-1hr",
        amount_paise=14900,
        secret_key="secret_legit_key",
    )

    # Case A: Amount Tampering (14900 -> 29900)
    tampered_amount_mandate = PaymentMandate(
        buyer_agent_id="buyer_tamper_test",
        merchant_id="merchant_tamper_test",
        sku="compute-gpu-a100-1hr",
        amount_paise=29900,  # Altered!
        currency="INR",
        timestamp=float(ts),
        reasoning="Attempting tampered amount mandate",
        signature=valid_sig,
    )

    with patch("backend.payments.razorpay_client.create_gated_order") as mock_create:
        receipt_a = merchant.process_mandate(tampered_amount_mandate)
        assert receipt_a.verdict == "BLOCK"
        assert receipt_a.primary_factor == "invalid_mandate_signature"
        assert "BLOCKED: Cryptographic signature verification failed" in receipt_a.summary
        assert receipt_a.order is None
        mock_create.assert_not_called()

    # Case B: SKU Substitution at SAME Amount (compute-gpu-a100-1hr -> compute-gpu-l4-1hr at 14900 paise)
    tampered_sku_mandate = PaymentMandate(
        buyer_agent_id="buyer_tamper_test",
        merchant_id="merchant_tamper_test",
        sku="compute-gpu-l4-1hr",  # Altered SKU!
        amount_paise=14900,        # Same signed amount
        currency="INR",
        timestamp=float(ts),
        reasoning="Attempting substituted SKU mandate with same amount",
        signature=valid_sig,
    )

    with patch("backend.payments.razorpay_client.create_gated_order") as mock_create:
        receipt_b = merchant.process_mandate(tampered_sku_mandate)
        assert receipt_b.verdict == "BLOCK"
        assert receipt_b.primary_factor == "invalid_mandate_signature"
        assert "BLOCKED: Cryptographic signature verification failed" in receipt_b.summary
        assert receipt_b.order is None
        mock_create.assert_not_called()


def test_a2a_best_match_is_not_first_offer():
    """
    Test 3: Best-Match-Isn't-First-Offer (Genuine Non-Positional Comparative Reasoning).
    Proves that the Buyer Agent evaluates candidate offers based on intent and constraints:
      (a) When intent requests lowest-cost / light accelerator, selects L4 (3rd offer / cheapest).
      (b) When intent requests maximum memory 80GB H100, selects H100 (1st offer / most expensive).
    Asserts both choices and reasonings dynamically adapt and reference the competing options.
    """
    merchant = MerchantAgent(merchant_id="merchant_catalog_test")

    # Scenario A: Cost-effective intent -> selects cheapest option (3rd offer: L4 at ₹79.00)
    buyer_budget = BuyerAgent(
        agent_id="buyer_cost_test",
        max_budget_paise=50000,  # ₹500.00
    )
    offers_budget = buyer_budget.send_task_request(
        merchant=merchant,
        intent="lowest cost affordable GPU for audio processing",
        category="ai_compute",
        max_budget_paise=50000,
    )

    assert len(offers_budget.offers) >= 3
    first_offer = offers_budget.offers[0]  # H100 at ₹299.00

    selected_cheap, reasoning_cheap = buyer_budget.evaluate_and_select_offer(
        offer_list=offers_budget,
        intent="lowest cost affordable GPU for audio processing",
    )

    # Must NOT be first offer (H100) or middle offer (A100)
    assert selected_cheap.sku == "compute-gpu-l4-1hr"
    assert selected_cheap.sku != first_offer.sku
    assert selected_cheap.amount_paise == 7900
    assert "compute-gpu-l4-1hr" in reasoning_cheap
    assert "₹79.00" in reasoning_cheap
    assert "compute-gpu-h100-1hr" in reasoning_cheap or "higher-priced" in reasoning_cheap

    # Scenario B: High-end intent -> selects most expensive option (1st offer: H100 at ₹299.00)
    buyer_perf = BuyerAgent(
        agent_id="buyer_perf_test",
        max_budget_paise=50000,  # ₹500.00
    )
    offers_perf = buyer_perf.send_task_request(
        merchant=merchant,
        intent="NVIDIA H100 80GB maximum memory for LLM fine-tuning",
        category="ai_compute",
        max_budget_paise=50000,
    )

    selected_perf, reasoning_perf = buyer_perf.evaluate_and_select_offer(
        offer_list=offers_perf,
        intent="NVIDIA H100 80GB maximum memory for LLM fine-tuning",
    )

    assert selected_perf.sku == "compute-gpu-h100-1hr"
    assert selected_perf.amount_paise == 29900
    assert "compute-gpu-h100-1hr" in reasoning_perf
    assert "₹299.00" in reasoning_perf
    assert "lower-tier" in reasoning_perf or "compute-gpu-a100-1hr" in reasoning_perf or "80gb" in reasoning_perf.lower()


def test_a2a_agent_card_reads_canonical_policy_ceiling():
    """
    Item 3 Verification:
    Asserts that AgentCard and GateDisclosure dynamically read the policy ceiling
    from policy.yaml directly (single source of truth).
    """
    canonical_ceiling = load_policy_config()["max_order_amount_inr"]
    merchant = MerchantAgent()
    card = merchant.get_agent_card()

    assert card.gate_disclosure.max_order_ceiling_inr == canonical_ceiling
    assert card.gate_disclosure.max_order_ceiling_inr == 50000.0


def test_a2a_over_ceiling_blocked_with_explanation():
    """
    Test 4: Over-Ceiling Mandate Block with Explanation.
    Buyer requests and issues mandate for an enterprise service costing ₹65,000.00
    (6,500,000 paise), which exceeds RazorGate's max_order_amount_inr ceiling of ₹50,000.00.
    Merchant submits to /gate/check -> evaluates to BLOCK -> returns structured Receipt.
    Buyer handles gracefully without crashing and surfaces explanation.
    """
    init_db()
    merchant = MerchantAgent(
        merchant_id="merchant_ceiling_test",
        secret_key="shared_ceiling_key",
    )
    buyer = BuyerAgent(
        agent_id="buyer_ceiling_test",
        max_budget_paise=10000000,  # ₹100,000.00
        secret_key="shared_ceiling_key",
    )

    receipt, transcript = buyer.execute_transaction(
        merchant=merchant,
        intent="enterprise support dedicated team",
        category="enterprise_services",
        preferred_sku="enterprise-support-tier1",
    )

    # 1. Assert BLOCK verdict due to ceiling
    assert receipt.verdict == "BLOCK"
    assert receipt.primary_factor == "amount_exceeded_ceiling"
    assert receipt.order is None
    assert receipt.confidence == 1.0

    # 2. Assert explanatory summary explains the ceiling breach
    assert "BLOCKED: Exceeds policy amount ceiling" in receipt.summary
    assert "₹65,000.00" in receipt.summary

    # 3. Assert Buyer transcript captured the receipt cleanly without exception
    receipt_entry = transcript[-1]
    assert receipt_entry["step"] == "receipt"
    assert receipt_entry["data"]["verdict"] == "BLOCK"
    assert receipt_entry["data"]["primary_factor"] == "amount_exceeded_ceiling"
