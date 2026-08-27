import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.audit.db import (
    get_decision_by_id,
    get_recent_decisions,
    init_db,
    link_order_to_decision,
    record_decision,
)
from backend.gate import adapter
from backend.gate.behavior import behavior_analyzer
from backend.gate.policy import load_policy_config
from backend.payments import razorpay_client

# Active SSE subscriber queues for real-time live decision streaming
_sse_subscribers: Set[asyncio.Queue] = set()


async def broadcast_decision_event(event_data: Dict[str, Any]):
    """Broadcasts a decision event to all connected SSE clients."""
    payload = f"data: {json.dumps(event_data)}\n\n"
    for queue in list(_sse_subscribers):
        try:
            queue.put_nowait(payload)
        except Exception:
            _sse_subscribers.discard(queue)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


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
    `amount`: Integer amount in PAISE (Razorpay native currency subunit, e.g. 50000 = ₹500.00).
    `currency`: ISO currency code, default 'INR'.
    """

    amount: int = Field(
        ...,
        description="Amount in paise (Razorpay native subunit, e.g. 50000 = ₹500.00 INR)",
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
    amount_paise: int = Field(..., description="Amount in paise (e.g. 50000 = ₹500.00 INR)")
    receipt: str
    allow_token: str
    currency: str = "INR"
    audit_id: Optional[int] = Field(
        default=None,
        description="Originating audit decision ID for forward-traceability",
    )
    notes: Optional[Dict[str, Any]] = None


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
async def stream_decisions():
    """
    Real-time Server-Sent Events (SSE) stream for live decision feeds and audit monitoring.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _sse_subscribers.add(queue)

    async def event_generator():
        try:
            # Initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'service': 'razorgate'})}\n\n"
            while True:
                try:
                    # Wait for next broadcast event or send keepalive heartbeat every 15s
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield event
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            _sse_subscribers.discard(queue)

    return StreamingResponse(
        event_generator(),
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
async def check_payment(req: PaymentCheckRequest):
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

    # Broadcast live decision event to SSE subscribers
    await broadcast_decision_event({
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


@app.post("/orders")
def create_order(req: CreateOrderRequest):
    """
    Executes real Razorpay Orders API call.
    Strictly gated by server-issued HMAC ALLOW token minted within 30s TTL.
    Links the resulting Razorpay order ID back to the originating audit decision.
    """
    try:
        order_res = razorpay_client.create_gated_order(
            agent_id=req.agent_id,
            amount_paise=req.amount_paise,
            receipt=req.receipt,
            allow_token=req.allow_token,
            currency=req.currency,
            notes=req.notes,
        )

        # Link Razorpay Order ID to audit ledger row if audit_id provided
        if req.audit_id and "id" in order_res:
            link_order_to_decision(audit_id=req.audit_id, razorpay_order_id=order_res["id"])

        return {
            "status": "created",
            "order": order_res,
            "audit_id": req.audit_id,
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Razorpay API Error: {str(e)}")


@app.get("/gate/policy")
def get_policy():
    """Returns current active payments policy rules."""
    return load_policy_config()


@app.get("/gate/behavior/agent/{agent_id}")
def get_agent_behavior(agent_id: str):
    """Returns rolling window behavior telemetry for an agent."""
    events = behavior_analyzer.store.get(agent_id)
    return {
        "agent_id": agent_id,
        "window_events_count": len(events),
        "events": events,
    }
