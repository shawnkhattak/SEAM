from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.limiter import limiter
from app.services.sse_broadcaster import position_broadcaster

router = APIRouter(prefix="/sse", tags=["sse"])
logger = logging.getLogger(__name__)


@router.get("/positions")
@limiter.limit("10/minute")
async def sse_positions(request: Request) -> StreamingResponse:
    """Server-Sent Events stream for position updates.

    The frontend subscribes once on mount. After each successful poll_positions
    job the broadcaster emits a 'positions_updated' event, triggering a
    React Query cache invalidation and re-fetch.

    Reconnect: client auto-reconnects (EventSource spec); keepalive every 15s.
    """
    logger.debug("sse: new positions subscriber from %s", request.client)

    async def event_stream() -> AsyncIterator[str]:
        # Send an initial 'connected' event so the client knows the stream is live
        yield "event: connected\ndata: {}\n\n"
        async for message in position_broadcaster.subscribe():
            if await request.is_disconnected():
                break
            yield message

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
