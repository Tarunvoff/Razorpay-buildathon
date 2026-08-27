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

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.audit.db import (
    get_decision_by_id,
    get_recent_decisions,
    init_db,
    record_decision,
)
from backend.gate import adapter
from backend.gate.behavior import behavior_analyzer
from backend.gate.policy import load_policy_config


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
    amount: int
    currency: str = "INR"
    merchant_id: Optional[str] = None
    order_id: Optional[str] = None
    action: str = "create_order"
    session_id: Optional[str] = "default_session"
    agent_id: Optional[str] = None
    mock_response: Optional[Dict[str, Any]] = None
    mock_behavior_signal: Optional[Dict[str, Any]] = None
    timing_ms: Optional[float] = 50.0


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


@app.get("/decisions/{decision_id}")
def get_decision(decision_id: int):
    """
    Retrieves a single decision record by ID.
    """
    record = get_decision_by_id(decision_id=decision_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Decision with ID {decision_id} not found")
    return record


@app.get("/decisions/stream")
async def stream_decisions():
    async def event_generator():
        while True:
            # Heartbeat event to verify end-to-end SSE connection
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/gate/check")
def check_payment(req: PaymentCheckRequest):
    """
    Evaluates an agent payment call through Apiris scoring and RazorGate policy,
    and persists the decision record to the SQLite audit ledger.
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

    return {
        **result,
        "audit_id": row_id,
    }


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
