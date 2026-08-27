"""
RazorGate Agent-to-Agent (A2A) Commerce Protocol Schemas.

Defines the message models and cryptographic signature structures
for two-agent commerce (Buyer Agent <-> Merchant Agent) fronting RazorGate.
Inspired by the AP2 / ACP / x402 pattern space.
"""

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GateDisclosure(BaseModel):
    """
    Explicit disclosure advertised by the Merchant Agent.
    States that every transaction is evaluated in real-time by RazorGate
    deterministic security policies and is subject to ALLOW / FLAG / BLOCK gating.
    """
    gating_enforced: bool = True
    gating_policy: str = "RazorGate Deterministic Policy v1.0"
    contract: str = (
        "All transactions are evaluated in real-time by RazorGate deterministic security policies; "
        "subject to ALLOW/FLAG/BLOCK gating before payment execution."
    )
    supported_verdicts: List[str] = Field(default_factory=lambda: ["ALLOW", "FLAG", "BLOCK"])
    max_order_ceiling_inr: float = 50000.0


class AgentCard(BaseModel):
    """
    Merchant capability discovery object (A2A Agent Card).
    Advertises merchant identity, categories sold, price bounds,
    and the explicit gate disclosure capability.
    """
    merchant_id: str
    merchant_name: str
    description: str
    protocol_version: str = "razorgate-a2a-v1"
    categories: List[str]
    price_range_paise: Dict[str, int] = Field(
        default_factory=lambda: {"min": 5000, "max": 5000000}
    )
    supported_currencies: List[str] = Field(default_factory=lambda: ["INR"])
    gate_disclosure: GateDisclosure = Field(default_factory=GateDisclosure)


class TaskRequest(BaseModel):
    """
    Structured intent message sent by the Buyer Agent to request offers.
    Replaces unstructured free-text chat with a typed negotiation request.
    """
    request_id: str = Field(default_factory=lambda: f"req_{int(time.time() * 1000)}")
    buyer_agent_id: str
    intent: str
    category: str
    max_budget_paise: int
    currency: str = "INR"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Offer(BaseModel):
    """
    An individual product or service offer returned by the Merchant Agent.
    Includes SKU, pricing, description, and the gate_disclosure field.
    """
    sku: str
    name: str
    description: str
    category: str
    amount_paise: int
    currency: str = "INR"
    unit: str = "unit"
    in_stock: bool = True
    gate_disclosure: str = (
        "Subject to real-time risk gating; may result in ALLOW/FLAG/BLOCK before execution."
    )
    specs: Dict[str, Any] = Field(default_factory=dict)


class OfferList(BaseModel):
    """
    Collection of candidate offers returned by the Merchant Agent for a TaskRequest.
    """
    request_id: str
    merchant_id: str
    offers: List[Offer] = Field(default_factory=list)
    gate_disclosure: GateDisclosure = Field(default_factory=GateDisclosure)
    timestamp: float = Field(default_factory=time.time)


class PaymentMandate(BaseModel):
    """
    Signed, bounded payment mandate issued by the Buyer Agent.
    Authorizes strictly the specific SKU, amount, and merchant.
    Analogous to AP2 mandate concept, secured via cryptographic HMAC signature.
    """
    mandate_id: str = Field(default_factory=lambda: f"mnd_{int(time.time() * 1000)}")
    buyer_agent_id: str
    merchant_id: str
    sku: str
    amount_paise: int
    currency: str = "INR"
    timestamp: float = Field(default_factory=time.time)
    reasoning: str = Field(
        ...,
        description="One-line comparative reasoning strictly referencing returned offers",
    )
    receipt_ref: str = Field(default_factory=lambda: f"rcpt_{int(time.time())}")
    signature: str = Field(
        ...,
        description="HMAC-SHA256 signature binding buyer, merchant, sku, amount, timestamp",
    )


class Receipt(BaseModel):
    """
    Structured outcome returned by Merchant Agent to Buyer Agent after gated execution.
    Contains decision verdict, primary factor, human-readable summary, evidence trail,
    audit ID, and (on ALLOW) the real Razorpay order entity.
    """
    receipt_id: str = Field(default_factory=lambda: f"rcpt_a2a_{int(time.time() * 1000)}")
    mandate_id: str
    buyer_agent_id: str
    merchant_id: str
    sku: str
    amount_paise: int
    amount_inr: float
    currency: str = "INR"
    verdict: str  # ALLOW, BLOCK, FLAG
    primary_factor: str
    summary: str
    confidence: float
    audit_id: Optional[int] = None
    order: Optional[Dict[str, Any]] = None  # Razorpay Order object if ALLOW
    evidence: Optional[Dict[str, Any]] = None
    timestamp: float = Field(default_factory=time.time)
    error: Optional[str] = None


def compute_mandate_payload(
    buyer_agent_id: str,
    merchant_id: str,
    sku: str,
    amount_paise: int,
    timestamp: int,
) -> str:
    """Canonical string representation for signing a PaymentMandate."""
    return f"{buyer_agent_id}:{merchant_id}:{sku}:{amount_paise}:{timestamp}"


def sign_payment_mandate(
    buyer_agent_id: str,
    merchant_id: str,
    sku: str,
    amount_paise: int,
    timestamp: Optional[float] = None,
    secret_key: str = "razorgate_a2a_shared_secret",
) -> tuple[int, str]:
    """
    Computes an HMAC-SHA256 signature for a payment mandate.
    Returns (ts_integer, signature_hex).
    """
    ts = int(timestamp if timestamp is not None else time.time())
    payload = compute_mandate_payload(buyer_agent_id, merchant_id, sku, amount_paise, ts).encode("utf-8")
    sig = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return ts, sig


def verify_payment_mandate(
    mandate: PaymentMandate,
    secret_key: str = "razorgate_a2a_shared_secret",
    max_age_seconds: float = 60.0,
    current_time: Optional[float] = None,
) -> bool:
    """
    Verifies that a payment mandate:
    1. Was minted within the valid time window.
    2. Matches the expected HMAC-SHA256 signature over its fields.
    """
    if not mandate.signature:
        return False

    now = current_time if current_time is not None else time.time()
    ts = int(mandate.timestamp)

    # Time window check (with 5s future clock skew tolerance)
    if (now - ts) > max_age_seconds or ts > (now + 5.0):
        return False

    payload = compute_mandate_payload(
        mandate.buyer_agent_id,
        mandate.merchant_id,
        mandate.sku,
        mandate.amount_paise,
        ts,
    ).encode("utf-8")
    expected_sig = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mandate.signature, expected_sig)
