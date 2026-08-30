import os
import json
from backend.agent.buyer_agent import BuyerAgent
from backend.agent.merchant_agent import MerchantAgent

def run_freeform():
    merchant = MerchantAgent()
    buyer = BuyerAgent(agent_id="test_buyer", max_budget_paise=50000) # Rs 500
    
    # Intentionally asking for "cheap object storage" which should not match the H100 catalog
    receipt, transcript = buyer.execute_transaction(
        merchant=merchant,
        intent="I want cheap object storage for my backups",
        category="cloud_infrastructure",
        max_budget_paise=100000
    )
    
    with open(r"C:\Users\TARUN\.gemini\antigravity-ide\brain\849d26d8-5fb0-48af-a687-b2278807202d\artifacts\cheap_storage_transcript.json", "w") as f:
        json.dump(transcript, f, indent=2)

    with open(r"C:\Users\TARUN\.gemini\antigravity-ide\brain\849d26d8-5fb0-48af-a687-b2278807202d\artifacts\cheap_storage_receipt.json", "w") as f:
        json.dump(receipt.model_dump(), f, indent=2)
        
    print(buyer.explain_outcome(receipt))

if __name__ == "__main__":
    os.makedirs(r"C:\Users\TARUN\.gemini\antigravity-ide\brain\849d26d8-5fb0-48af-a687-b2278807202d\artifacts", exist_ok=True)
    run_freeform()
