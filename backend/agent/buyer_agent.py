"""
Buyer Agent for RazorGate A2A Protocol.

Autonomous AI Buyer Agent with intent, budget constraints, and cryptographic signing.
Communicates strictly via protocol messages (AgentCard, TaskRequest, OfferList, PaymentMandate, Receipt),
enforcing bounded authorizations and anti-hallucination comparative reasoning.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from backend.agent.merchant_agent import MerchantAgent
from backend.agent.protocol import (
    AgentCard,
    Offer,
    OfferList,
    PaymentMandate,
    Receipt,
    TaskRequest,
    sign_payment_mandate,
)


class BuyerAgent:
    """
    Autonomous Buyer Agent participating in the RazorGate A2A Commerce Protocol.
    """

    def __init__(
        self,
        agent_id: str = "buyer_agent_alpha",
        max_budget_paise: int = 500000,  # ₹5,000.00 default budget
        secret_key: str = "razorgate_a2a_shared_secret",
    ):
        self.agent_id = agent_id
        self.max_budget_paise = max_budget_paise
        self.secret_key = secret_key
        self.conversation_transcript: List[Dict[str, Any]] = []

    def log_step(self, step_type: str, data: Any):
        """Records an event in the protocol transcript."""
        self.conversation_transcript.append({
            "step": step_type,
            "timestamp": time.time(),
            "data": data if isinstance(data, (dict, list, str, int, float, bool)) else data.model_dump(),
        })

    def discover_capabilities(self, merchant: MerchantAgent) -> AgentCard:
        """
        Step 1: Capability Discovery.
        Fetches the Merchant's AgentCard to discover supported categories, price bounds,
        and gate disclosures.
        """
        card = merchant.get_agent_card()
        self.log_step("capability_discovery", card)
        return card

    def send_task_request(
        self,
        merchant: MerchantAgent,
        intent: str,
        category: str,
        max_budget_paise: Optional[int] = None,
    ) -> OfferList:
        """
        Step 2: Task Request.
        Sends a structured intent and budget message to the Merchant Agent.
        """
        budget = max_budget_paise if max_budget_paise is not None else self.max_budget_paise
        request = TaskRequest(
            buyer_agent_id=self.agent_id,
            intent=intent,
            category=category,
            max_budget_paise=budget,
        )
        self.log_step("task_request", request)

        offers = merchant.handle_task_request(request)
        self.log_step("received_offers", offers)
        return offers

    def _score_offer_match(self, offer: Offer, intent_lower: str) -> float:
        """
        Scores how well an offer matches the buyer's stated intent.
        Evaluates exact SKU keywords, specs (VRAM, tokens, nodes), descriptions, and performance intent.
        """
        score = 1.0
        name_desc = f"{offer.name} {offer.description} {offer.sku}".lower()
        specs_str = " ".join(f"{k} {v}" for k, v in offer.specs.items()).lower()

        # High-performance / heavy compute intent
        high_perf_keywords = ["h100", "80gb", "training", "fine-tuning", "heavy", "maximum", "top-tier", "high memory", "nvlink", "enterprise"]
        if any(kw in intent_lower for kw in high_perf_keywords):
            if "h100" in offer.sku or "80gb" in specs_str or "enterprise" in offer.category:
                score += 10.0
            elif "a100" in offer.sku or "40gb" in specs_str:
                score += 5.0
            elif "l4" in offer.sku:
                score += 1.0

        # Cost-efficiency / budget intent
        budget_keywords = ["cheap", "budget", "lowest", "cost", "starter", "light", "affordable", "l4", "24gb"]
        if any(kw in intent_lower for kw in budget_keywords):
            if "l4" in offer.sku or "starter" in offer.sku or "79" in str(offer.amount_paise):
                score += 10.0
            elif "a100" in offer.sku:
                score += 4.0

        # Mid-tier / balanced inference intent
        mid_tier_keywords = ["a100", "40gb", "inference", "batch", "balanced", "optimal"]
        if any(kw in intent_lower for kw in mid_tier_keywords):
            if "a100" in offer.sku or "40gb" in specs_str:
                score += 8.0

        # Keyword overlap
        for word in intent_lower.split():
            if len(word) > 2 and (word in name_desc or word in specs_str):
                score += 2.0

        return score

    def evaluate_and_select_offer(
        self,
        offer_list: OfferList,
        intent: Optional[str] = None,
        strategy: str = "intent_match",
        preferred_sku: Optional[str] = None,
    ) -> Tuple[Offer, str]:
        """
        Step 3: Offer Evaluation and Dynamic Comparative Reasoning.
        Strict anti-hallucination constraint: Comparison reasoning may ONLY reference
        SKUs, prices, and specifications present in the received OfferList.
        """
        offers = offer_list.offers
        if not offers:
            raise ValueError("No offers available to evaluate.")

        # If a specific preferred SKU was targeted
        if preferred_sku:
            target = next((o for o in offers if o.sku == preferred_sku), None)
            if target:
                other_skus = [f"{o.sku} (₹{o.amount_paise / 100:.2f})" for o in offers if o.sku != target.sku]
                others_text = f", comparing against {', '.join(other_skus)}" if other_skus else ""
                reasoning = (
                    f"Selected {target.sku} (₹{target.amount_paise / 100:.2f}) matching requested SKU '{target.name}'"
                    f"{others_text}."
                )
                self.log_step("selection_reasoning", {"selected_sku": target.sku, "reasoning": reasoning})
                return target, reasoning

        # Filter within budget ceiling
        within_budget = [o for o in offers if o.amount_paise <= self.max_budget_paise]

        if not within_budget:
            # Over budget fallback (e.g. for testing over-ceiling handling)
            selected = min(offers, key=lambda x: x.amount_paise)
            other_skus = [f"{o.sku} (₹{o.amount_paise / 100:.2f})" for o in offers if o.sku != selected.sku]
            reasoning = (
                f"Selected {selected.sku} (₹{selected.amount_paise / 100:.2f}) as lowest price available among {len(offers)} offers, "
                f"exceeding budget ceiling ₹{self.max_budget_paise / 100:.2f}, compared against [{', '.join(other_skus)}]."
            )
            self.log_step("selection_reasoning", {"selected_sku": selected.sku, "reasoning": reasoning})
            return selected, reasoning

        intent_text = (intent or "").lower()

        # Dynamic intent-driven scoring
        if strategy == "lowest_price" or ("cheap" in intent_text or "budget" in intent_text and "h100" not in intent_text):
            selected = min(within_budget, key=lambda x: x.amount_paise)
            higher_options = [f"{o.sku} (₹{o.amount_paise / 100:.2f})" for o in within_budget if o.sku != selected.sku]
            alt_text = f" over higher-priced alternatives [{', '.join(higher_options)}]" if higher_options else ""
            spec_detail = f" with {selected.specs}" if selected.specs else ""
            reasoning = (
                f"Selected cost-optimized {selected.sku} (₹{selected.amount_paise / 100:.2f}){spec_detail} to minimize spend within budget ₹{self.max_budget_paise / 100:.2f}"
                f"{alt_text}."
            )
        elif strategy == "highest_tier" or ("h100" in intent_text or "80gb" in intent_text or "maximum" in intent_text or "heavy" in intent_text):
            # Pick highest capability / matching top tier within budget
            scored = sorted(within_budget, key=lambda o: (self._score_offer_match(o, intent_text), o.amount_paise), reverse=True)
            selected = scored[0]
            lower_options = [f"{o.sku} (₹{o.amount_paise / 100:.2f})" for o in within_budget if o.sku != selected.sku]
            alt_text = f" prioritizing throughput/specs over lower-tier options [{', '.join(lower_options)}]" if lower_options else ""
            spec_detail = f" featuring {selected.specs.get('gpu', selected.name)} ({selected.specs.get('vram_gb', '')}GB VRAM)" if selected.specs else ""
            reasoning = (
                f"Selected high-performance {selected.sku} (₹{selected.amount_paise / 100:.2f}){spec_detail} within budget ₹{self.max_budget_paise / 100:.2f}"
                f"{alt_text}."
            )
        else:
            # Score each candidate dynamically based on intent matching and capability balance
            scored = sorted(within_budget, key=lambda o: self._score_offer_match(o, intent_text), reverse=True)
            selected = scored[0]
            competing = [f"{o.sku} (₹{o.amount_paise / 100:.2f})" for o in within_budget if o.sku != selected.sku]
            comp_text = f", evaluated against alternatives [{', '.join(competing)}]" if competing else ""
            reasoning = (
                f"Selected {selected.sku} (₹{selected.amount_paise / 100:.2f}) as optimal match for '{intent or 'request'}' "
                f"within budget ₹{self.max_budget_paise / 100:.2f}{comp_text}."
            )

        self.log_step("selection_reasoning", {"selected_sku": selected.sku, "reasoning": reasoning})
        return selected, reasoning

    def issue_mandate(
        self,
        selected_offer: Offer,
        merchant_id: str,
        reasoning: str,
    ) -> PaymentMandate:
        """
        Step 4: Payment Mandate.
        Generates and cryptographically signs a bounded payment mandate.
        The mandate is strictly valid only for (buyer, merchant, sku, amount, timestamp).
        """
        ts, sig = sign_payment_mandate(
            buyer_agent_id=self.agent_id,
            merchant_id=merchant_id,
            sku=selected_offer.sku,
            amount_paise=selected_offer.amount_paise,
            secret_key=self.secret_key,
        )

        mandate = PaymentMandate(
            buyer_agent_id=self.agent_id,
            merchant_id=merchant_id,
            sku=selected_offer.sku,
            amount_paise=selected_offer.amount_paise,
            currency=selected_offer.currency,
            timestamp=float(ts),
            reasoning=reasoning,
            signature=sig,
        )
        self.log_step("payment_mandate", mandate)
        return mandate

    def execute_transaction(
        self,
        merchant: MerchantAgent,
        intent: str,
        category: str,
        max_budget_paise: Optional[int] = None,
        strategy: str = "intent_match",
        preferred_sku: Optional[str] = None,
    ) -> Tuple[Receipt, List[Dict[str, Any]]]:
        """
        Executes the full 6-step A2A commerce lifecycle:
        1. Capability Discovery -> AgentCard
        2. Task Request -> TaskRequest
        3. Offer Negotiation & Comparison -> OfferList -> Selected Offer + Dynamic Reasoning
        4. Signed Mandate Issuance -> PaymentMandate
        5. Gated Execution (Merchant fronts Gate & Razorpay)
        6. Receipt -> Verified outcome & explainable trail
        """
        # 1. Discover
        self.discover_capabilities(merchant)

        # 2. Task Request
        offers = self.send_task_request(
            merchant=merchant,
            intent=intent,
            category=category,
            max_budget_paise=max_budget_paise,
        )

        # 3. Reason & Select dynamically
        selected_offer, reasoning = self.evaluate_and_select_offer(
            offer_list=offers,
            intent=intent,
            strategy=strategy,
            preferred_sku=preferred_sku,
        )

        # 4. Issue Signed Mandate
        mandate = self.issue_mandate(
            selected_offer=selected_offer,
            merchant_id=merchant.merchant_id,
            reasoning=reasoning,
        )

        # 5. Gated Execution by Merchant
        receipt = merchant.process_mandate(mandate)
        self.log_step("receipt", receipt)

        return receipt, self.conversation_transcript
