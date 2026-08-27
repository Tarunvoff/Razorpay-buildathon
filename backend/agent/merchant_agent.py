"""
Merchant Agent for RazorGate A2A Protocol.

Fronts the merchant's catalog, RazorGate deterministic gate engine,
and Razorpay payments backend. Advertises capabilities via AgentCard,
handles structured TaskRequests, verifies signed PaymentMandates,
and executes gated Razorpay orders on behalf of AI buyer agents.
"""

import time
from typing import Any, Dict, List, Optional

from backend.agent.catalog import DEFAULT_CATALOG, search_catalog
from backend.agent.protocol import (
    AgentCard,
    GateDisclosure,
    Offer,
    OfferList,
    PaymentMandate,
    Receipt,
    TaskRequest,
    verify_payment_mandate,
)
from backend.gate import adapter
from backend.payments import razorpay_client
from backend.audit.db import link_order_to_decision, record_decision


class MerchantAgent:
    """
    Merchant Agent in the RazorGate A2A Commerce Protocol.
    """

    def __init__(
        self,
        merchant_id: str = "merchant_razorgate_cloud",
        merchant_name: str = "RazorGate Cloud & AI Compute Services",
        secret_key: str = "razorgate_a2a_shared_secret",
        catalog: Optional[List[Dict[str, Any]]] = None,
    ):
        self.merchant_id = merchant_id
        self.merchant_name = merchant_name
        self.secret_key = secret_key
        self.catalog = catalog if catalog is not None else DEFAULT_CATALOG

    def get_agent_card(self) -> AgentCard:
        """
        Capability Discovery (Step 1):
        Returns the Merchant's AgentCard advertising categories, price bounds,
        and explicit gate disclosure (ALLOW/FLAG/BLOCK deterministic security contract).
        """
        categories = list({item["category"] for item in self.catalog})
        prices = [item["amount_paise"] for item in self.catalog]
        min_p = min(prices) if prices else 1000
        max_p = max(prices) if prices else 10000000

        return AgentCard(
            merchant_id=self.merchant_id,
            merchant_name=self.merchant_name,
            description="Enterprise AI compute, high-throughput model endpoints, and cloud infrastructure.",
            protocol_version="razorgate-a2a-v1",
            categories=categories,
            price_range_paise={"min": min_p, "max": max_p},
            supported_currencies=["INR"],
            gate_disclosure=GateDisclosure(),
        )

    def handle_task_request(self, request: TaskRequest) -> OfferList:
        """
        Task Request & Offer Negotiation (Steps 2 & 3):
        Processes a structured intent & budget request and returns 2-4 candidate offers
        with transparent pricing and attached gate disclosures.
        """
        matching_offers = search_catalog(
            query=request.intent,
            category=request.category,
            max_budget_paise=request.max_budget_paise,
            catalog=self.catalog,
        )

        return OfferList(
            request_id=request.request_id,
            merchant_id=self.merchant_id,
            offers=matching_offers,
            gate_disclosure=GateDisclosure(),
            timestamp=time.time(),
        )

    def process_mandate(self, mandate: PaymentMandate) -> Receipt:
        """
        Mandate Processing & Gated Execution (Steps 4, 5, 6):
        1. Verifies cryptographic HMAC signature on the Buyer's bounded mandate.
           Rejects tampered / forged mandates immediately BEFORE touching gate or payments.
        2. Submits payment check to RazorGate's gate engine (/gate/check / adapter.check).
        3. On ALLOW: executes gated Razorpay order creation (/orders / razorpay_client.create_gated_order)
           using the server-issued ALLOW token.
        4. On BLOCK or FLAG: halts downstream execution cleanly.
        5. Returns a structured Receipt with full explanation trail and audit traceability.
        """
        # Step 4a: Cryptographic validation of Buyer Agent's signed mandate
        is_valid_sig = verify_payment_mandate(
            mandate=mandate,
            secret_key=self.secret_key,
        )

        if not is_valid_sig:
            return Receipt(
                mandate_id=mandate.mandate_id,
                buyer_agent_id=mandate.buyer_agent_id,
                merchant_id=self.merchant_id,
                sku=mandate.sku,
                amount_paise=mandate.amount_paise,
                amount_inr=mandate.amount_paise / 100.0,
                currency=mandate.currency,
                verdict="BLOCK",
                primary_factor="invalid_mandate_signature",
                summary="BLOCKED: Cryptographic signature verification failed on payment mandate.",
                confidence=1.0,
                audit_id=None,
                order=None,
                evidence={
                    "mandate_id": mandate.mandate_id,
                    "signature": mandate.signature,
                    "reason": "HMAC signature mismatch or timestamp expired.",
                },
                error="Invalid or tampered payment mandate signature.",
            )

        # Step 5: Evaluate through RazorGate deterministic gate engine
        payment_call = {
            "amount": mandate.amount_paise,
            "currency": mandate.currency,
            "merchant_id": self.merchant_id,
            "agent_id": mandate.buyer_agent_id,
            "receipt": mandate.receipt_ref,
            "action": "create_order",
            "notes": {
                "sku": mandate.sku,
                "mandate_id": mandate.mandate_id,
                "reasoning": mandate.reasoning,
                "protocol": "razorgate-a2a-v1",
            },
        }

        gate_result = adapter.check(payment_call)
        verdict = gate_result.get("verdict", "BLOCK")
        confidence = gate_result.get("confidence", 1.0)
        primary_factor = gate_result.get("primary_factor", "unknown")
        summary = gate_result.get("summary", "")
        allow_token = gate_result.get("allow_token")
        explanation_record = gate_result.get("explanation_record", {})
        amount_inr = mandate.amount_paise / 100.0

        # Persist decision to SQLite audit ledger
        row_id = record_decision(
            agent_id=mandate.buyer_agent_id,
            amount_paise=mandate.amount_paise,
            amount_inr=amount_inr,
            verdict=verdict,
            confidence=confidence,
            primary_factor=primary_factor,
            summary=summary,
            evidence=explanation_record.get("evidence", {}),
        )

        razorpay_order: Optional[Dict[str, Any]] = None
        exec_error: Optional[str] = None

        # Step 6: Gated execution if verdict is ALLOW
        if verdict == "ALLOW" and allow_token:
            try:
                razorpay_order = razorpay_client.create_gated_order(
                    agent_id=mandate.buyer_agent_id,
                    amount_paise=mandate.amount_paise,
                    receipt=mandate.receipt_ref,
                    allow_token=allow_token,
                    currency=mandate.currency,
                    notes={
                        "sku": mandate.sku,
                        "mandate_id": mandate.mandate_id,
                        "audit_id": row_id,
                        "merchant_id": self.merchant_id,
                    },
                )
                # Link Razorpay Order ID to audit ledger row
                if "id" in razorpay_order:
                    link_order_to_decision(audit_id=row_id, razorpay_order_id=razorpay_order["id"])
            except Exception as e:
                exec_error = str(e)
                summary = f"Gate ALLOWed but order execution failed: {str(e)}"

        return Receipt(
            mandate_id=mandate.mandate_id,
            buyer_agent_id=mandate.buyer_agent_id,
            merchant_id=self.merchant_id,
            sku=mandate.sku,
            amount_paise=mandate.amount_paise,
            amount_inr=amount_inr,
            currency=mandate.currency,
            verdict=verdict,
            primary_factor=primary_factor,
            summary=summary,
            confidence=confidence,
            audit_id=row_id,
            order=razorpay_order,
            evidence=explanation_record.get("evidence", {}),
            timestamp=time.time(),
            error=exec_error,
        )
