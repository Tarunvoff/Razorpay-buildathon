import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.audit.db import get_recent_decisions, init_db, log_decision
from backend.audit.explainer import explainer
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
    agent_id: Optional[str] = "default_agent"
    mock_response: Optional[Dict[str, Any]] = None
    timing_ms: Optional[float] = 50.0


@app.get("/health")
def health():
    return {"status": "ok", "service": "razorgate-control"}


@app.get("/decisions")
def list_decisions(limit: int = 50):
    return get_recent_decisions(limit=limit)


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
    Evaluates an agent payment call through Apiris scoring and RazorGate policy.
    """
    call_dict = req.model_dump()
    result = adapter.check(call_dict)

    # Record behavior session event
    agent_id = req.agent_id or req.session_id or "default_agent"
    behavior_signal = behavior_analyzer.record_and_evaluate(
        agent_id=agent_id,
        amount_paise=req.amount,
    )

    # Log to audit DB
    log_decision(
        request=call_dict,
        verdict=result["verdict"],
        confidence=result.get("confidence", 1.0),
        explanation=result.get("explanation", ""),
    )

    return {
        **result,
        "behavior_signal": behavior_signal,
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
