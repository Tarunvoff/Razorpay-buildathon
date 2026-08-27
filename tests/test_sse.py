import asyncio
import json
import pytest
import httpx
from backend.control.app import app, _sse_subscribers, broadcast_decision_event


@pytest.mark.asyncio
async def test_sse_stream_receives_broadcast_events():
    """
    Direct verification of subscriber queue receiving broadcast events and SSE format.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _sse_subscribers.add(queue)

    try:
        # Broadcast decision event
        event_payload = {
            "type": "decision",
            "audit_id": 42,
            "agent_id": "sse_test_agent_direct",
            "verdict": "ALLOW",
            "amount_paise": 25000,
            "amount_inr": 250.0,
            "primary_factor": "policy_cleared",
            "summary": "Transaction APPROVED",
            "confidence": 1.0,
        }
        await broadcast_decision_event(event_payload)

        # Confirm queue received the formatted SSE string
        raw_sse = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert raw_sse.startswith("data: ")
        assert raw_sse.endswith("\n\n")

        # Parse JSON payload from SSE format
        body = json.loads(raw_sse.replace("data: ", "").strip())
        assert body["type"] == "decision"
        assert body["agent_id"] == "sse_test_agent_direct"
        assert body["verdict"] == "ALLOW"
        assert body["amount_inr"] == 250.0
    finally:
        _sse_subscribers.discard(queue)
