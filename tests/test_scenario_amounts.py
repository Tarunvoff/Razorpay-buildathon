import pytest
import asyncio
from backend.control.app import ask_buyer_agent, AskAgentRequest

def test_back_to_back_scenario_amounts():
    """
    Test that back-to-back scenarios with different pricing goals
    create Razorpay orders whose amount field matches their own selected SKU price.
    Prevents state-bleed / amount mismatch regressions between consecutive runs.
    """
    # 1. Run Free-Form Intent for cheap object storage (Starter 100GB SKU = ₹199.00 / 19900 paise)
    req1 = AskAgentRequest(intent="cheap object storage for side project", max_budget_inr=5000.0)
    res1 = asyncio.run(ask_buyer_agent(req1))
    
    receipt1 = res1["receipt"]
    verdict1 = getattr(receipt1, "verdict", None) or receipt1.get("verdict")
    amount_paise1 = getattr(receipt1, "amount_paise", None) or receipt1.get("amount_paise")
    amount_inr1 = getattr(receipt1, "amount_inr", None) or receipt1.get("amount_inr")
    order1 = getattr(receipt1, "order", None) or receipt1.get("order")

    assert verdict1 == "ALLOW"
    assert amount_paise1 == 19900
    assert amount_inr1 == 199.0
    assert order1 is not None
    order1_amount = getattr(order1, "amount", None) or (order1.get("amount") if isinstance(order1, dict) else None)
    assert order1_amount == 19900
    
    # 2. Run Free-Form Intent for high-end GPU compute (H100 GPU SKU = ₹299.00 / 29900 paise)
    req2 = AskAgentRequest(intent="NVIDIA H100 SXM 80GB GPU instance for fine tuning", max_budget_inr=5000.0)
    res2 = asyncio.run(ask_buyer_agent(req2))
    
    receipt2 = res2["receipt"]
    verdict2 = getattr(receipt2, "verdict", None) or receipt2.get("verdict")
    amount_paise2 = getattr(receipt2, "amount_paise", None) or receipt2.get("amount_paise")
    amount_inr2 = getattr(receipt2, "amount_inr", None) or receipt2.get("amount_inr")
    order2 = getattr(receipt2, "order", None) or receipt2.get("order")

    assert verdict2 == "ALLOW"
    assert amount_paise2 == 29900
    assert amount_inr2 == 299.0
    assert order2 is not None
    order2_amount = getattr(order2, "amount", None) or (order2.get("amount") if isinstance(order2, dict) else None)
    assert order2_amount == 29900

    print("\n[SUCCESS] Both back-to-back scenarios created exact matching Razorpay orders without state-bleed:")
    print(f"  Run 1 (Storage): Gate = INR {amount_inr1:.2f}, Razorpay Order Amount = {order1_amount} paise")
    print(f"  Run 2 (GPU):     Gate = INR {amount_inr2:.2f}, Razorpay Order Amount = {order2_amount} paise")


if __name__ == "__main__":
    test_back_to_back_scenario_amounts()

