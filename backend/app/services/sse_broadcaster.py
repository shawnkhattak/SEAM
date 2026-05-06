from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Singleton broadcaster that fans out events to all connected SSE clients.

    Usage:
      - scheduler job calls await broadcaster.publish("positions_updated", {...})
      - SSE route yields from broadcaster.subscribe()
    """

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[str | None]] = []

    async def publish(self, event: str, data: Any = None) -> None:
        payload = json.dumps({"event": event, "data": data or {}})
        message = f"event: {event}\ndata: {payload}\n\n"
        dead: list[asyncio.Queue[str | None]] = []
        for q in self._queues:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._queues.remove(q)
        logger.debug("sse: published %s to %d clients", event, len(self._queues))

    async def subscribe(self) -> AsyncIterator[str]:
        """Yield SSE-formatted messages. Yields keepalive every 15s if no events."""
        q: asyncio.Queue[str | None] = asyncio.Queue(maxsize=50)
        self._queues.append(q)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    if msg is None:
                        break
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self._queues.remove(q)

    def disconnect_all(self) -> None:
        for q in self._queues:
            q.put_nowait(None)
        self._queues.clear()


# Module-level singleton
position_broadcaster = SSEBroadcaster()
