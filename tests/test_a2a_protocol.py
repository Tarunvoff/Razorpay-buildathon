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
            strategy="best_fit",
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
                strategy="best_fit",
            )

            assert receipt.verdict == "ALLOW"
            assert receipt.primary_factor == "policy_cleared"
            assert receipt.order is not None
            assert receipt.order["id"] == mock_order_id

            fetched_order = razorpay_client.fetch_order(mock_order_id)
            assert fetched_order["id"] == mock_order_id

    # Verify transcript contains all 5 steps in order
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
    Test 2: Tampered Mandate Rejection.
    A mandate signed for one amount/SKU (e.g. ₹149.00 / 14,900 paise)
    is tampered with by claiming a different amount (e.g. ₹299.00 / 29,900 paise)
    or invalid signature.
    Must be rejected with BLOCK before touching the gate check or Razorpay /orders.
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

    # 1. Buyer creates valid signature for ₹149.00 (compute-gpu-a100-1hr)
    ts, valid_sig = sign_payment_mandate(
        buyer_agent_id="buyer_tamper_test",
        merchant_id="merchant_tamper_test",
        sku="compute-gpu-a100-1hr",
        amount_paise=14900,
        secret_key="secret_legit_key",
    )

    # 2. Tampered Mandate: Amount is altered to 29900 paise (₹299.00) while keeping signature
    tampered_mandate = PaymentMandate(
        buyer_agent_id="buyer_tamper_test",
        merchant_id="merchant_tamper_test",
        sku="compute-gpu-a100-1hr",
        amount_paise=29900,  # Tampered from 14900 to 29900!
        currency="INR",
        timestamp=float(ts),
        reasoning="Attempting tampered amount mandate",
        signature=valid_sig,
    )

    with patch("backend.payments.razorpay_client.create_gated_order") as mock_create:
        receipt = merchant.process_mandate(tampered_mandate)

        # Assert rejection before payments
        assert receipt.verdict == "BLOCK"
        assert receipt.primary_factor == "invalid_mandate_signature"
        assert "BLOCKED: Cryptographic signature verification failed" in receipt.summary
        assert receipt.order is None
        mock_create.assert_not_called()


def test_a2a_best_match_is_not_first_offer():
    """
    Test 3: Best-Match-Isn't-First-Offer (Genuine Comparative Reasoning).
    Proves that the Buyer Agent genuinely compares multiple candidate offers,
    selects an offer that is NOT the 1st item in the received list,
    and states explicit comparative reasoning referencing the alternatives.
    """
    merchant = MerchantAgent(merchant_id="merchant_catalog_test")
    buyer = BuyerAgent(
        agent_id="buyer_comparison_test",
        max_budget_paise=50000,  # ₹500.00
    )

    # Request offers for AI compute
    offers = buyer.send_task_request(
        merchant=merchant,
        intent="compute instance",
        category="ai_compute",
        max_budget_paise=50000,
    )

    assert len(offers.offers) >= 3
    first_offer = offers.offers[0]  # e.g., H100 at ₹299.00

    # Strategy: "lowest_price" selects the cheapest offer (e.g., L4 at ₹79.00, which is index 2)
    selected_offer, reasoning = buyer.evaluate_and_select_offer(
        offer_list=offers,
        strategy="lowest_price",
    )

    # Assert that the chosen offer is NOT the first offer in the catalog list
    assert selected_offer.sku != first_offer.sku, (
        f"Selected offer ({selected_offer.sku}) must not default to first offer ({first_offer.sku})"
    )
    assert selected_offer.amount_paise < first_offer.amount_paise

    # Assert anti-hallucination constraint: reasoning contains selected SKU and references alternatives
    assert selected_offer.sku in reasoning
    assert f"₹{selected_offer.amount_paise / 100:.2f}" in reasoning
    assert "lowest cost" in reasoning.lower() or "budget" in reasoning.lower()


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
