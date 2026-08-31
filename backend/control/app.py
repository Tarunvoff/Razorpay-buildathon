import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import hashlib
import hmac
import time
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.audit.db import (
    get_decision_by_id,
    get_recent_decisions,
    init_db,
    is_webhook_processed,
    link_order_to_decision,
    record_decision,
    record_webhook_processed,
    update_decision_webhook_status,
)
from backend.broadcaster import get_broadcaster
from backend.config import settings
from backend.gate import adapter
from backend.gate.behavior import behavior_analyzer
from backend.gate.policy import load_policy_config
from backend.payments import razorpay_client

# Module-level fallback broadcaster â€” used by tests (TestClient without lifespan)
# and as a safety net if app.state.broadcaster is somehow not set.
from backend.broadcaster import InMemoryBroadcaster as _InMemoryBroadcaster
_default_broadcaster = _InMemoryBroadcaster()


def _get_broadcaster(request):
    """Returns the broadcaster from app.state, falling back to the module-level default."""
    try:
        return request.app.state.broadcaster
    except AttributeError:
        return _default_broadcaster


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    broadcaster = get_broadcaster()
    app.state.broadcaster = broadcaster
    print(f"\n==================================================")
    print(f"[RazorGate Startup] SSE Broadcaster active: {broadcaster.__class__.__name__}")
    print(f"==================================================\n")
    try:
        yield
    finally:
        await broadcaster.close()



app = FastAPI(
    title="RazorGate Control Plane",
    description="Deterministic trust, scoring, and policy gating layer for agentic Razorpay payments",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PaymentCheckRequest(BaseModel):
    """
    Public payment check request payload.

    UNIT CONVENTION:
    `amount`: Integer amount in PAISE (Razorpay native currency subunit, e.g. 50000 = â‚¹500.00).
    `currency`: ISO currency code, default 'INR'.
    """

    amount: int = Field(
        ...,
        description="Amount in paise (Razorpay native subunit, e.g. 50000 = â‚¹500.00 INR)",
    )
    currency: str = Field(default="INR", description="ISO currency code")
    merchant_id: Optional[str] = None
    order_id: Optional[str] = None
    receipt: Optional[str] = None
    action: str = "create_order"
    session_id: Optional[str] = "default_session"
    agent_id: Optional[str] = None
    mock_response: Optional[Dict[str, Any]] = None
    mock_behavior_signal: Optional[Dict[str, Any]] = None
    timing_ms: Optional[float] = 50.0


class CreateOrderRequest(BaseModel):
    """
    Gated Razorpay order creation request.
    Requires server-issued ALLOW token minted by RazorGate gate check.
    """

    agent_id: str
    amount_paise: int = Field(..., description="Amount in paise (e.g. 50000 = â‚¹500.00 INR)")
    receipt: str
    allow_token: str
    merchant_id: Optional[str] = "merchant_default"
    sku: Optional[str] = "sku_default"
    currency: str = "INR"
    audit_id: Optional[int] = Field(
        default=None,
        description="Originating audit decision ID for forward-traceability",
    )
    notes: Optional[Dict[str, Any]] = None


class RefreshTokenRequest(BaseModel):
    audit_id: int
    agent_id: str
    amount_paise: int
    receipt: str


class VerifyOrderRequest(BaseModel):
    """
    Razorpay payment signature verification request payload.
    Re-verifies HMAC-SHA256 signature server-side before declaring payment authorization complete.
    """

    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    audit_id: Optional[int] = Field(
        default=None,
        description="Originating audit decision ID for forward-traceability",
    )



@app.get("/health")
def health():
    return {"status": "ok", "service": "razorgate-control"}


@app.get("/decisions")
def list_decisions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    agent_id: Optional[str] = Query(default=None),
):
    """
    Returns paginated historical decision records from the SQLite audit ledger.
    """
    return get_recent_decisions(limit=limit, offset=offset, agent_id=agent_id)


@app.get("/decisions/stream")
async def stream_decisions(request: Request):
    """
    Real-time Server-Sent Events (SSE) stream for live decision feeds and audit monitoring.
    Backed by InMemoryBroadcaster (default) or RedisBroadcaster (when REDIS_URL is set),
    enabling cross-process fanout across multiple uvicorn workers.
    """
    broadcaster = _get_broadcaster(request)

    return StreamingResponse(
        broadcaster.subscribe_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/decisions/{decision_id}")
def get_decision(decision_id: int):
    """
    Retrieves a single decision record by ID.
    """
    record = get_decision_by_id(decision_id=decision_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Decision with ID {decision_id} not found")
    return record


@app.post("/gate/check")
async def check_payment(request: Request, req: PaymentCheckRequest):
    """
    Evaluates an agent payment call through Apiris scoring and RazorGate policy,
    persists the decision record to the SQLite audit ledger, broadcasts live SSE,
    and returns an ALLOW token if approved.
    """
    call_dict = req.model_dump()
    agent_id = req.agent_id or req.session_id or "default_agent"
    call_dict["agent_id"] = agent_id

    result = adapter.check(call_dict)

    # Persist decision row to SQLite audit ledger
    explanation_record = result.get("explanation_record", {})
    amount_inr = (
        explanation_record.get("amount_inr")
        or result.get("decision", {}).get("amount_inr")
        or (req.amount / 100.0)
    )
    primary_factor = result.get("primary_factor") or result.get("decision", {}).get(
        "primary_factor", "policy_cleared"
    )
    summary = result.get("summary") or result.get("explanation", "")
    confidence = result.get("confidence", 1.0)
    verdict = result.get("verdict", "ALLOW")

    evidence = explanation_record.get("evidence") or {
        "apiris_score": result.get("apiris_score", {}),
        "behavior_signal": result.get("behavior_signal", {}),
        "decision": result.get("decision", {}),
        "policy": {
            "verdict": verdict,
            "primary_factor": primary_factor,
            "reasons": result.get("decision", {}).get("reasons", []),
            "amount_inr": amount_inr,
        },
        "request": call_dict,
    }

    row_id = record_decision(
        agent_id=agent_id,
        amount_paise=req.amount,
        amount_inr=amount_inr,
        verdict=verdict,
        confidence=confidence,
        primary_factor=primary_factor,
        summary=summary,
        evidence=evidence,
    )

    response_payload = {
        **result,
        "audit_id": row_id,
    }

    # Broadcast live decision event via broadcaster (InMemory or Redis)
    await _get_broadcaster(request).publish({
        "type": "decision",
        "audit_id": row_id,
        "agent_id": agent_id,
        "verdict": verdict,
        "amount_paise": req.amount,
        "amount_inr": amount_inr,
        "primary_factor": primary_factor,
        "summary": summary,
        "confidence": confidence,
        "allow_token": result.get("allow_token"),
    })

    return response_payload


@app.post("/gate/refresh-token")
def refresh_token(req: RefreshTokenRequest):
    """
    Re-evaluates a previously ALLOWed decision that has expired due to TTL.
    Mints a fresh token without changing the original request parameters.
    """
    record = get_decision_by_id(req.audit_id)
    if not record or record.get("agent_id") != req.agent_id or record.get("amount_paise") != req.amount_paise:
        raise HTTPException(status_code=400, detail="Invalid refresh request: context mismatch")
    
    evidence = record.get("evidence", {})
    original_request = evidence.get("request")
    if not original_request:
        raise HTTPException(status_code=400, detail="Original request context missing")
        
    # Re-evaluate with current state (e.g., behavior metrics, policy ceilings)
    gate_result = adapter.check(original_request)
    if gate_result.get("verdict") != "ALLOW":
        raise HTTPException(status_code=403, detail=f"Refresh denied. New verdict: {gate_result.get('verdict')}")
        
    return {
        "allow_token": gate_result.get("allow_token"),
        "audit_id": gate_result.get("audit_id"),
        "status": "refreshed"
    }


@app.post("/orders")
def create_order(req: CreateOrderRequest):
    """
    Executes real Razorpay Orders API call.
    Strictly gated by server-issued HMAC ALLOW token minted within 30s TTL.
    Links the resulting Razorpay order ID back to the originating audit decision.
    """
    try:
        # Software-Level Idempotency & Replay Protection Guard
        # Serves as a fast-path defense-in-depth layer on top of Razorpay's API guarantee.
        # Resolves audit decision ID -> existing Razorpay order ID to prevent duplicate order generation
        # on retried agent mandate submissions, returning the existing order object deterministically.
        merchant_id = req.merchant_id or "merchant_default"
        sku = req.sku or (req.notes.get("sku") if req.notes else None) or "sku_default"
        if req.audit_id:
            record = get_decision_by_id(req.audit_id)
            if record:
                if record.get("razorpay_order_id"):
                    # Fetch existing order instead of creating a duplicate
                    existing_order = razorpay_client.fetch_order(record["razorpay_order_id"])
                    return {
                        "status": "created",
                        "order": existing_order,
                        "audit_id": req.audit_id,
                        "key_id": settings.razorpay_key_id,
                        "idempotency_hit": True
                    }
                evidence = record.get("evidence", {})
                orig_req = evidence.get("request", {})
                if orig_req:
                    if merchant_id == "merchant_default" and orig_req.get("merchant_id"):
                        merchant_id = orig_req["merchant_id"]
                    if sku == "sku_default":
                        sku = orig_req.get("sku") or (orig_req.get("notes") or {}).get("sku") or sku

        order_res = razorpay_client.create_gated_order(
            agent_id=req.agent_id,
            amount_paise=req.amount_paise,
            receipt=req.receipt,
            allow_token=req.allow_token,
            merchant_id=merchant_id,
            sku=sku,
            currency=req.currency,
            notes=req.notes,
            idempotency_key=str(req.audit_id) if req.audit_id else None,
        )

        # Link Razorpay Order ID to audit ledger row if audit_id provided
        if req.audit_id and "id" in order_res:
            link_order_to_decision(audit_id=req.audit_id, razorpay_order_id=order_res["id"])

        return {
            "status": "created",
            "order": order_res,
            "audit_id": req.audit_id,
            "key_id": settings.razorpay_key_id,
        }
    except razorpay_client.TokenExpiredError:
        raise HTTPException(status_code=403, detail="token_expired")
    except razorpay_client.TokenInvalidError:
        raise HTTPException(status_code=403, detail="token_invalid")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Razorpay API Error: {str(e)}")


@app.post("/orders/verify")
async def verify_order_signature(request: Request, req: VerifyOrderRequest):
    """
    Server-side HMAC-SHA256 signature verification for Razorpay payment callback.
    Independently recomputes HMAC signature and verifies against razorpay_signature.
    Only marks transaction as ALLOW-and-paid if signature is valid.
    """
    is_valid = razorpay_client.verify_payment_signature(
        razorpay_order_id=req.razorpay_order_id,
        razorpay_payment_id=req.razorpay_payment_id,
        razorpay_signature=req.razorpay_signature,
    )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay payment signature. Tampering detected.",
        )

    # Fetch official order object from Razorpay SDK to return full side-by-side verification
    try:
        order_details = razorpay_client.fetch_order(req.razorpay_order_id)
    except Exception:
        order_details = {"id": req.razorpay_order_id, "status": "paid"}

    # Update SQLite audit decision ledger if audit_id provided
    if req.audit_id:
        link_order_to_decision(audit_id=req.audit_id, razorpay_order_id=req.razorpay_order_id)

    response_data = {
        "status": "verified",
        "verified": True,
        "razorpay_payment_id": req.razorpay_payment_id,
        "razorpay_order_id": req.razorpay_order_id,
        "audit_id": req.audit_id,
        "order": order_details,
    }

    # Broadcast payment_verified SSE event via broadcaster
    await _get_broadcaster(request).publish({
        "type": "payment_verified",
        "audit_id": req.audit_id,
        "razorpay_order_id": req.razorpay_order_id,
        "razorpay_payment_id": req.razorpay_payment_id,
        "status": "verified",
    })

    return response_data


@app.post("/webhooks/razorpay")
async def handle_razorpay_webhook(request: Request):
    """
    Razorpay Webhook Listener.
    Verifies X-Razorpay-Signature header against raw request body using razorpay_webhook_secret.
    Rejects tampered / unverified payloads with HTTP 400 immediately before parsing.
    Handles 'payment.captured' and 'payment.failed' events idempotently.
    Updates the audit ledger to mark decisions confirmed-paid asynchronously.
    """
    raw_body = await request.body()
    x_signature = request.headers.get("X-Razorpay-Signature") or ""

    secret = (settings.razorpay_webhook_secret or "razorgate_webhook_secret_dev").encode("utf-8")
    expected_sig = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

    if not x_signature or not hmac.compare_digest(expected_sig, x_signature):
        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay webhook signature. Tampering detected.",
        )

    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event", "unknown")
    event_id = payload.get("event_id") or f"evt_{int(time.time() * 1000)}"

    # Idempotency check: skip processing if duplicate event ID
    if is_webhook_processed(event_id):
        return {
            "status": "already_processed",
            "event_id": event_id,
            "event": event,
            "idempotency_hit": True,
        }

    # Record event ID for idempotency tracking
    record_webhook_processed(event_id, event)

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_order_id = payment_entity.get("order_id") or payment_entity.get("id")
    razorpay_payment_id = payment_entity.get("id")

    if event == "payment.captured":
        status_label = "confirmed_paid"
        audit_id = update_decision_webhook_status(razorpay_order_id, status_label) if razorpay_order_id else None

        await _get_broadcaster(request).publish({
            "type": "webhook_payment_captured",
            "event_id": event_id,
            "event": event,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "status": status_label,
            "audit_id": audit_id,
        })

        return {
            "status": "processed",
            "event_id": event_id,
            "event": event,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "audit_id": audit_id,
            "payment_status": status_label,
        }
    elif event == "payment.failed":
        status_label = "payment_failed"
        audit_id = update_decision_webhook_status(razorpay_order_id, status_label) if razorpay_order_id else None

        await _get_broadcaster(request).publish({
            "type": "webhook_payment_failed",
            "event_id": event_id,
            "event": event,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "status": status_label,
            "audit_id": audit_id,
        })

        return {
            "status": "processed",
            "event_id": event_id,
            "event": event,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "audit_id": audit_id,
            "payment_status": status_label,
        }

    return {
        "status": "ignored",
        "event_id": event_id,
        "event": event,
    }



@app.get("/gate/policy")
def get_policy(merchant_id: Optional[str] = Query(default=None, description="Merchant ID to inspect effective policy for")):
    """Returns current active payments policy rules, optionally merged with per-merchant overrides."""
    return load_policy_config(merchant_id=merchant_id)


@app.get("/gate/behavior/agent/{agent_id}")
def get_agent_behavior(agent_id: str):
    """Returns rolling window behavior telemetry for an agent."""
    events = behavior_analyzer.store.get(agent_id)
    return {
        "agent_id": agent_id,
        "window_events_count": len(events),
        "events": events,
    }


class RunScenarioRequest(BaseModel):
    scenario: str = Field(
        default="clean_allow",
        description="Demo scenario: 'clean_allow', 'behavior_flag', or 'forced_failure_block'",
    )
    custom_budget_paise: Optional[int] = None


class AskAgentRequest(BaseModel):
    intent: str = Field(..., description="Free-form buyer intent typed by judge/user")
    category: Optional[str] = Field(default="all", description="Category filter")
    max_budget_inr: Optional[float] = Field(default=5000.0, description="Max budget ceiling in INR")


@app.post("/agent/ask")
@app.post("/demo/ask")
async def ask_buyer_agent(request: Request, req: AskAgentRequest):

    """
    Executes an open-ended free-form AI Buyer Agent transaction:
    1. Runs real Claude API tool-use loop / comparative reasoning against the expanded marketplace catalog.
    2. Executes real 6-step A2A protocol handshake.
    3. Evaluates through RazorGate deterministic security gate.
    4. If verdict is ALLOW, creates real Razorpay order.
    5. Returns full transcript, receipt, explanation, and decision audit record.
    """
    import time
    from backend.agent.buyer_agent import BuyerAgent
    from backend.agent.merchant_agent import MerchantAgent

    timestamp_suffix = int(time.time() * 1000) % 100000
    merchant = MerchantAgent(
        merchant_id="merchant_razorgate_cloud",
        merchant_name="RazorGate Cloud & AI Compute Services",
        secret_key="razorgate_demo_secret",
    )

    budget_paise = int((req.max_budget_inr or 5000.0) * 100)
    buyer = BuyerAgent(
        agent_id=f"buyer_custom_{timestamp_suffix}",
        max_budget_paise=budget_paise,
        secret_key="razorgate_demo_secret",
    )

    receipt, transcript = buyer.execute_transaction(
        merchant=merchant,
        intent=req.intent,
        category=req.category or "all",
        max_budget_paise=budget_paise,
    )

    explanation = buyer.explain_outcome(receipt)

    # Broadcast event via broadcaster (InMemory or Redis)
    await _get_broadcaster(request).publish({
        "type": "decision",
        "audit_id": receipt.audit_id,
        "agent_id": buyer.agent_id,
        "verdict": receipt.verdict,
        "amount_paise": receipt.amount_paise,
        "amount_inr": receipt.amount_inr,
        "primary_factor": receipt.primary_factor,
        "summary": receipt.summary,
        "confidence": receipt.confidence,
        "allow_token": receipt.evidence.get("allow_token") if receipt.evidence else None,
        "razorpay_order_id": receipt.order.get("id") if receipt.order else None,
    })

    return {
        "scenario": "custom_freeform",
        "intent": req.intent,
        "receipt": receipt,
        "transcript": transcript,
        "explanation": explanation,
        "key_id": settings.razorpay_key_id,
    }



@app.post("/demo/run-scenario")
async def run_scenario(request: Request, req: RunScenarioRequest):
    """
    Executes a real end-to-end A2A protocol transaction scenario:
    1. 'clean_allow': NVIDIA H100 GPU compute (â‚¹299.00) -> ALLOW -> Real Razorpay Order.
    2. 'behavior_flag': High-frequency session burst -> FLAG -> Safe completion.
    3. 'forced_failure_block': Enterprise support (â‚¹65,000 > â‚¹50,000 ceiling) -> Deterministic BLOCK -> Zero orders.
    """
    import time
    from backend.agent.buyer_agent import BuyerAgent
    from backend.agent.merchant_agent import MerchantAgent

    timestamp_suffix = int(time.time() * 1000) % 100000
    merchant = MerchantAgent(
        merchant_id="merchant_razorgate_cloud",
        merchant_name="RazorGate Cloud & AI Compute Services",
        secret_key="razorgate_demo_secret",
    )

    if req.scenario == "forced_failure_block":
        buyer = BuyerAgent(
            agent_id=f"buyer_enterprise_exec_{timestamp_suffix}",
            max_budget_paise=req.custom_budget_paise or 10000000,
            secret_key="razorgate_demo_secret",
        )
        receipt, transcript = buyer.execute_transaction(
            merchant=merchant,
            intent="Enterprise 24/7 dedicated support & quarterly architecture review for mission-critical deployment",
            category="enterprise_services",
            preferred_sku="enterprise-support-tier1",
        )
    elif req.scenario == "behavior_flag":
        agent_id = "demo_flag_burst_agent"
        # Evict prior window history for clean burst evaluation
        behavior_analyzer.store.evict(agent_id, time.time() + 1000)
        # Seed 5 rapid burst calls in rolling window
        now = time.time()
        for i in range(5):
            behavior_analyzer.store.append(agent_id, now - (30 - i * 2), 4900)
        buyer = BuyerAgent(
            agent_id=agent_id,
            max_budget_paise=req.custom_budget_paise or 500000,
            secret_key="razorgate_demo_secret",
        )

        receipt, transcript = buyer.execute_transaction(
            merchant=merchant,
            intent="Rapid API token quota refill for live automated batch evaluation",
            category="api_credits",
            preferred_sku="api-tier-starter-100k",
        )
    else:  # clean_allow
        buyer = BuyerAgent(
            agent_id=f"buyer_h100_cluster_{timestamp_suffix}",
            max_budget_paise=req.custom_budget_paise or 1000000,
            secret_key="razorgate_demo_secret",
        )
        receipt, transcript = buyer.execute_transaction(
            merchant=merchant,
            intent="High-throughput GPU compute instance with NVLink interconnect for 80GB model inference",
            category="ai_compute",
            preferred_sku="compute-gpu-h100-1hr",
        )

    explanation = buyer.explain_outcome(receipt)

    # Broadcast event via broadcaster (InMemory or Redis)
    await _get_broadcaster(request).publish({
        "type": "decision",
        "audit_id": receipt.audit_id,
        "agent_id": buyer.agent_id,
        "verdict": receipt.verdict,
        "amount_paise": receipt.amount_paise,
        "amount_inr": receipt.amount_inr,
        "primary_factor": receipt.primary_factor,
        "summary": receipt.summary,
        "confidence": receipt.confidence,
        "allow_token": receipt.evidence.get("allow_token") if receipt.evidence else None,
        "razorpay_order_id": receipt.order.get("id") if receipt.order else None,
    })

    return {
        "scenario": req.scenario,
        "agent_id": buyer.agent_id,
        "receipt": receipt.model_dump(),
        "transcript": transcript,
        "explanation": explanation,
        "verdict": receipt.verdict,
        "primary_factor": receipt.primary_factor,
        "confidence": receipt.confidence,
        "amount_inr": receipt.amount_inr,
        "audit_id": receipt.audit_id,
        "order": receipt.order,
    }


@app.get("/metrics/summary")
def get_metrics_summary():
    """
    Returns aggregated audit ledger statistics and published Apiris performance specs.
    """
    from backend.audit.db import get_db_connection

    init_db()
    conn = get_db_connection()
    total_decisions = conn.execute("SELECT COUNT(*) as cnt FROM decisions").fetchone()["cnt"]
    allow_count = conn.execute("SELECT COUNT(*) as cnt FROM decisions WHERE verdict = 'ALLOW'").fetchone()["cnt"]
    flag_count = conn.execute("SELECT COUNT(*) as cnt FROM decisions WHERE verdict = 'FLAG'").fetchone()["cnt"]
    block_count = conn.execute("SELECT COUNT(*) as cnt FROM decisions WHERE verdict = 'BLOCK'").fetchone()["cnt"]
    conn.close()

    return {
        "ledger": {
            "total_decisions": total_decisions,
            "allow_count": allow_count,
            "flag_count": flag_count,
            "block_count": block_count,
        },
        "apiris_specs": {
            "version": "1.1.1",
            "p50_latency_ms": 0.061,
            "p95_latency_ms": 0.137,
            "throughput_rps_core": 14500,
            "memory_footprint_mb": 24,
            "cve_count": 65,
            "vendor_count": 47,
            "telemetry_sent": 0,
            "air_gapped": True,
        },
        "policy_ceiling_inr": 50000.0,
        "token_ttl_seconds": 30,
    }


