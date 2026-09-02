"""
DecisionBroadcaster — Real-time SSE event fanout abstraction for RazorGate.

Protocol mirrors the existing DecisionStore pattern in backend/audit/db.py.

Implementations:
  InMemoryBroadcaster  — Single-process asyncio.Queue fanout (dev/test default)
  RedisBroadcaster     — Cross-process Redis pub/sub (live default when REDIS_URL is set)

Factory:
  get_broadcaster()    — Returns RedisBroadcaster if REDIS_URL configured, else InMemory.
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, Protocol, Set

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "razorgate:decisions"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class DecisionBroadcaster(Protocol):
    """Abstract broadcaster interface — matches DecisionStore pattern."""

    async def publish(self, event: Dict[str, Any]) -> None:
        """Publish a decision event to all subscribers."""
        ...

    def subscribe_iter(self) -> "AsyncIterator[str]":
        """Return an async iterator yielding SSE-formatted strings."""
        ...

    async def close(self) -> None:
        """Release resources (connections, etc.)."""
        ...


# ---------------------------------------------------------------------------
# InMemoryBroadcaster — single-process, zero-dependency
# ---------------------------------------------------------------------------

class InMemoryBroadcaster:
    """
    asyncio.Queue-based in-process broadcaster.
    Works within a single uvicorn process.
    Used in tests and as dev fallback when REDIS_URL is not configured.
    """

    def __init__(self) -> None:
        self._queues: Set[asyncio.Queue] = set()

    async def publish(self, event: Dict[str, Any]) -> None:
        payload = f"data: {json.dumps(event)}\n\n"
        for q in list(self._queues):
            try:
                q.put_nowait(payload)
            except Exception:
                self._queues.discard(q)

    async def subscribe_iter(self) -> AsyncIterator[str]:  # type: ignore[override]
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.add(queue)
        try:
            yield f"data: {json.dumps({'type': 'connected', 'service': 'razorgate', 'mode': 'in_memory'})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield event
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            self._queues.discard(queue)

    async def close(self) -> None:
        self._queues.clear()

    @property
    def subscriber_count(self) -> int:
        return len(self._queues)


# ---------------------------------------------------------------------------
# RedisBroadcaster — cross-process pub/sub
# ---------------------------------------------------------------------------

class RedisBroadcaster:
    """
    Redis pub/sub broadcaster using redis-py async client.
    Enables cross-process SSE fanout: any process that publishes to the same
    Redis channel will be received by all subscribers across all processes.

    Requires: REDIS_URL in environment (e.g. redis://localhost:6379/0 or
              rediss://... for TLS, e.g. Upstash).
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._publish_client = None

    async def _get_publish_client(self):
        if self._publish_client is None:
            import redis.asyncio as aioredis
            self._publish_client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        return self._publish_client

    async def publish(self, event: Dict[str, Any]) -> None:
        try:
            client = await self._get_publish_client()
            await client.publish(REDIS_CHANNEL, json.dumps(event))
        except Exception as exc:
            logger.warning("RedisBroadcaster.publish failed: %s", exc)

    async def subscribe_iter(self) -> AsyncIterator[str]:  # type: ignore[override]
        import redis.asyncio as aioredis
        client = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        pubsub = client.pubsub()
        await pubsub.subscribe(REDIS_CHANNEL)
        try:
            yield f"data: {json.dumps({'type': 'connected', 'service': 'razorgate', 'mode': 'redis'})}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0),
                        timeout=16.0,
                    )
                    if message and message.get("type") == "message":
                        raw = message.get("data", "")
                        try:
                            json.loads(raw)
                            yield f"data: {raw}\n\n"
                        except (json.JSONDecodeError, TypeError):
                            pass
                    else:
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            try:
                await pubsub.unsubscribe(REDIS_CHANNEL)
                await pubsub.close()
                await client.aclose()
            except Exception:
                pass

    async def close(self) -> None:
        if self._publish_client:
            try:
                await self._publish_client.aclose()
            except Exception:
                pass
            self._publish_client = None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_broadcaster():
    """
    Returns the appropriate broadcaster based on REDIS_URL configuration.

    - If REDIS_URL is set -> RedisBroadcaster (cross-process)
    - Otherwise          -> InMemoryBroadcaster (single-process, zero-dependency)
    """
    try:
        from backend.config import settings
        redis_url = getattr(settings, "redis_url", None)
    except Exception:
        redis_url = None

    if redis_url:
        logger.info("DecisionBroadcaster: using RedisBroadcaster at %s", redis_url)
        return RedisBroadcaster(redis_url)
    else:
        logger.info("DecisionBroadcaster: REDIS_URL not set — using InMemoryBroadcaster")
        return InMemoryBroadcaster()
