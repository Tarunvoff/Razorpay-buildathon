import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from backend.control.app import app


async def test_sse_live_delivery():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        print("1. Initiating SSE stream connection...")
        async with client.stream("GET", "/decisions/stream") as sse_stream:
            print("2. SSE Stream HTTP Status:", sse_stream.status_code)
            assert sse_stream.status_code == 200

            # Read initial connection line
            lines_iter = sse_stream.aiter_lines()
            init_line = await lines_iter.__anext__()
            print("3. Initial connection event:", init_line)

            # Trigger /gate/check in background task
            async def trigger():
                await asyncio.sleep(0.1)
                r = await client.post(
                    "/gate/check",
                    json={
                        "amount": 35000,
                        "currency": "INR",
                        "agent_id": "sse_verified_subscriber",
                        "receipt": "rcpt_sse_99",
                        "action": "create_order",
                    },
                )
                print("4. Triggered POST /gate/check -> Verdict:", r.json()["verdict"])

            asyncio.create_task(trigger())

            # Read next live broadcast line from SSE stream
            event_line = await lines_iter.__anext__()
            print("5. Live Pushed SSE Event Line:", event_line)
            assert "sse_verified_subscriber" in event_line
            print("6. SSE live delivery verified end-to-end!")


if __name__ == "__main__":
    asyncio.run(test_sse_live_delivery())
