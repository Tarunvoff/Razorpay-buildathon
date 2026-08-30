"""
Buyer Agent for RazorGate A2A Protocol.

Autonomous AI Buyer Agent powered by Claude API tool-use loops.
Communicates strictly via protocol messages (AgentCard, TaskRequest, OfferList, PaymentMandate, Receipt),
enforcing bounded authorizations and anti-hallucination comparative reasoning.
"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import anthropic
from backend.config import settings
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


BUYER_SYSTEM_PROMPT = """You are an autonomous AI Buyer Agent participating in the RazorGate A2A Commerce Protocol.
Your goal is to evaluate available merchant offers for a requested purchase intent and budget constraint, perform rigorous comparative reasoning, and execute a bounded transaction through RazorGate's security gate.

HARD CONSTRAINTS & ANTI-HALLUCINATION RULES:
1. You MUST first inspect returned catalog offers before making any selection.
2. ANTI-HALLUCINATION HARD RULE: In your comparative reasoning, you may ONLY cite SKU names, prices, or specifications that appear directly in the search_catalog tool result. Never invent or hallucinate SKUs, prices, or specs not present in the returned offers.
3. Compare the candidate offers on specs (VRAM, GPU architecture, throughput, unit) and pricing relative to budget.
4. Select the single best-matching offer, explain why in your own words, and invoke check_gate with that SKU and amount_paise.
5. Branch strictly on the check_gate verdict:
   - If ALLOW: call create_order with the allow_token and audit_id.
   - If BLOCK: stop execution immediately, do NOT call create_order, and state clearly that RazorGate's policy ceiling blocked the transaction safely.
   - If FLAG: document the anomaly flag and proceed according to policy.
"""


class BuyerAgent:
    """
    Autonomous Buyer Agent participating in the RazorGate A2A Commerce Protocol.
    Uses Claude API tool-use for comparative reasoning and transaction execution.
    """

    def __init__(
        self,
        agent_id: str = "buyer_agent_alpha",
        max_budget_paise: int = 500000,  # ₹5,000.00 default budget
        secret_key: str = "razorgate_a2a_shared_secret",
        api_key: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.max_budget_paise = max_budget_paise
        self.secret_key = secret_key
        self.api_key = api_key or settings.api_key
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
    ) -> Tuple[Optional[Offer], str]:
        """
        Step 3: Offer Evaluation and Dynamic Comparative Reasoning.
        Uses Claude API when available (temperature=0.2), or structured fallback.
        Strict anti-hallucination constraint: Comparison reasoning may ONLY reference
        SKUs, prices, and specifications present in the received OfferList.
        """
        offers = offer_list.offers
        if not offers:
            reasoning = f"No matching merchant offers found for intent '{intent or 'request'}' in the catalog."
            self.log_step("selection_reasoning", {"selected_sku": None, "reasoning": reasoning})
            return None, reasoning


        # Try Real Claude API Tool / Completion call if API key present
        if self.api_key:
            try:
                client = anthropic.Anthropic(api_key=self.api_key, timeout=5.0)
                offers_summary = [
                    {
                        "sku": o.sku,
                        "name": o.name,
                        "amount_paise": o.amount_paise,
                        "amount_inr": f"₹{o.amount_paise / 100:.2f}",
                        "specs": o.specs,
                        "description": o.description,
                    }
                    for o in offers
                ]

                prompt_user = (
                    f"User Intent: '{intent or 'general request'}'\n"
                    f"Max Budget: ₹{self.max_budget_paise / 100:.2f} ({self.max_budget_paise} paise)\n"
                    f"Preferred SKU Target: {preferred_sku or 'None'}\n"
                    f"Candidate Offers Received:\n{json.dumps(offers_summary, indent=2)}\n\n"
                    f"Perform comparative reasoning over these exact candidate offers. State which offer is selected and why. "
                    f"You MUST format your response as JSON: {{\"selected_sku\": \"<sku>\", \"reasoning\": \"<detailed comparative reasoning>\"}}"
                )

                response = client.messages.create(
                    model="claude-3-5-sonnet-20001022",
                    max_tokens=400,
                    temperature=0.2,
                    system=BUYER_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt_user}],
                )

                text = response.content[0].text
                # Try to parse JSON from Claude response
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    parsed = json.loads(text[start : end + 1])
                    selected_sku = parsed.get("selected_sku")
                    llm_reasoning = parsed.get("reasoning", text)
                    target = next((o for o in offers if o.sku == selected_sku), None)
                    if target:
                        self.log_step("selection_reasoning", {"selected_sku": target.sku, "reasoning": llm_reasoning})
                        return target, llm_reasoning
            except Exception as e:
                # Log API error and proceed with deterministic fallback
                pass

        # Deterministic comparative reasoning fallback (strictly anti-hallucinatory)
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

        within_budget = [o for o in offers if o.amount_paise <= self.max_budget_paise]
        if not within_budget:
            selected = min(offers, key=lambda x: x.amount_paise)
            other_skus = [f"{o.sku} (₹{o.amount_paise / 100:.2f})" for o in offers if o.sku != selected.sku]
            reasoning = (
                f"Selected {selected.sku} (₹{selected.amount_paise / 100:.2f}) as lowest price available among {len(offers)} offers, "
                f"exceeding budget ceiling ₹{self.max_budget_paise / 100:.2f}, compared against [{', '.join(other_skus)}]."
            )
            self.log_step("selection_reasoning", {"selected_sku": selected.sku, "reasoning": reasoning})
            return selected, reasoning

        intent_text = (intent or "").lower()
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

        if selected_offer is None:
            no_match_receipt = Receipt(
                mandate_id=f"mandate_no_match_{int(time.time())}",
                buyer_agent_id=self.agent_id,
                merchant_id=merchant.merchant_id,
                sku="none",
                amount_paise=0,
                amount_inr=0.0,
                currency="INR",
                verdict="NO_MATCH",
                primary_factor="no_catalog_match",
                summary=f"No matching merchant offers found for intent '{intent}' in the marketplace catalog.",
                confidence=1.0,
                audit_id=None,
                order=None,
                evidence={"intent": intent, "category": category},
                timestamp=time.time(),
            )
            self.log_step("receipt", no_match_receipt)
            return no_match_receipt, self.conversation_transcript

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


    def explain_outcome(self, receipt: Receipt) -> str:
        """
        Translates the structured protocol Receipt into a clear, natural-language,
        user-facing explanation of the outcome.
        Uses Claude API when available to generate fresh natural language explanation.
        """
        if self.api_key:
            try:
                client = anthropic.Anthropic(api_key=self.api_key)
                prompt_user = (
                    f"Receipt Summary:\n"
                    f"Verdict: {receipt.verdict}\n"
                    f"Primary Factor: {receipt.primary_factor}\n"
                    f"SKU: {receipt.sku}\n"
                    f"Amount: ₹{receipt.amount_inr:,.2f}\n"
                    f"Summary: {receipt.summary}\n"
                    f"Audit Decision ID: {receipt.audit_id}\n\n"
                    f"Provide a concise 1-2 sentence user-facing explanation of this outcome from the perspective of an autonomous AI Buyer Agent. "
                    f"If evidence contains 'token_refreshed': true, mention that the token expired due to latency but was successfully refreshed before final execution. "
                    f"If verdict is BLOCK due to amount_exceeded_ceiling, state clearly that you found the matching option but RazorGate security policy ceiling (₹50,000.00) safely blocked execution, so no payment was made."
                )
                response = client.messages.create(
                    model="claude-3-5-sonnet-20001022",
                    max_tokens=200,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt_user}],
                )
                return response.content[0].text.strip()
            except Exception:
                pass

        refresh_note = ""
        if receipt.evidence and receipt.evidence.get("token_refreshed"):
            refresh_note = " (Note: The transaction took longer than expected due to reasoning latency, but I successfully refreshed the expired security token before execution.)"

        if receipt.verdict == "ALLOW":
            order_id = receipt.order.get("id", "created") if receipt.order else "order_created"
            return (
                f"Successfully authorized and placed order for '{receipt.sku}' at ₹{receipt.amount_inr:,.2f}. "
                f"Razorpay Order ID: {order_id} (Audit Decision #{receipt.audit_id}).{refresh_note}"
            )
        elif receipt.verdict == "BLOCK" and receipt.primary_factor == "amount_exceeded_ceiling":
            return (
                f"I found a matching option ('{receipt.sku}' at ₹{receipt.amount_inr:,.2f}), "
                f"but RazorGate's deterministic security gate blocked the transaction because the amount exceeds the ₹50,000.00 policy ceiling. "
                f"I stopped execution safely — no payment was made and no Razorpay order was created (Audit Decision #{receipt.audit_id})."
            )
        elif receipt.verdict == "BLOCK":
            return (
                f"Transaction for '{receipt.sku}' at ₹{receipt.amount_inr:,.2f} was blocked by RazorGate security policy "
                f"({receipt.primary_factor}: {receipt.summary}). No payment was processed."
            )
        elif receipt.verdict == "FLAG":
            return (
                f"Transaction for '{receipt.sku}' at ₹{receipt.amount_inr:,.2f} was flagged for behavioral anomaly "
                f"({receipt.primary_factor}). Requires stepped-up authorization from a human before proceeding."
            )
        return receipt.summary
