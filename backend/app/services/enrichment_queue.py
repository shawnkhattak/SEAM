"""Enrichment queue service — dequeue vessels for per-minute particulars enrichment.

Design:
  - One row per IMO in vessel_enrichment_queue.
  - dequeue_batch() uses SELECT ... FOR UPDATE SKIP LOCKED to safely fan out.
  - mark_success() removes the row (vessel stays enriched until re-enqueued on next poll).
  - mark_failure() implements exponential backoff:
      - 429 rate-limit: next_attempt_at = now + 300s (fixed)
      - 5xx errors: next_attempt_at = now + min(3600s, 60 * 2^attempt_count)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VesselEnrichmentQueue
from app.utils.timezone import utc_now

log = logging.getLogger(__name__)

_LOCK_DURATION_S = 120  # hold a lock for 2 minutes while enriching
_RATE_LIMIT_BACKOFF_S = 300
_MAX_BACKOFF_S = 3600


def _backoff_seconds(attempt_count: int) -> int:
    return min(_MAX_BACKOFF_S, 60 * (2 ** attempt_count))


async def enqueue(
    session: AsyncSession,
    imo: int,
    *,
    priority: int = 0,
) -> None:
    """Add a vessel to the enrichment queue, ignoring if already present."""
    now = utc_now()
    stmt = insert(VesselEnrichmentQueue).values(
        imo=imo,
        priority=priority,
        enqueued_at=now,
        next_attempt_at=now,
        attempt_count=0,
    ).on_conflict_do_nothing(index_elements=["imo"])
    await session.execute(stmt)


async def enqueue_many(session: AsyncSession, imos: list[int], *, priority: int = 0) -> int:
    """Enqueue a batch of IMOs. Returns count of newly enqueued."""
    if not imos:
        return 0
    now = utc_now()
    rows = [
        {
            "imo": imo,
            "priority": priority,
            "enqueued_at": now,
            "next_attempt_at": now,
            "attempt_count": 0,
        }
        for imo in imos
    ]
    result = await session.execute(
        insert(VesselEnrichmentQueue)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["imo"])
    )
    return result.rowcount


async def dequeue_batch(
    session: AsyncSession,
    max_count: int = 10,
) -> list[int]:
    """Claim up to max_count ready vessels and lock them.

    Returns a list of IMOs. Caller must call mark_success() or mark_failure()
    for each IMO when done.
    """
    now = utc_now()
    lock_until = now + timedelta(seconds=_LOCK_DURATION_S)

    result = await session.execute(
        select(VesselEnrichmentQueue.imo)
        .where(
            VesselEnrichmentQueue.next_attempt_at <= now,
            (VesselEnrichmentQueue.locked_until.is_(None))
            | (VesselEnrichmentQueue.locked_until < now),
        )
        .order_by(
            VesselEnrichmentQueue.priority.desc(),
            VesselEnrichmentQueue.next_attempt_at.asc(),
        )
        .limit(max_count)
        .with_for_update(skip_locked=True)
    )
    imos = [row[0] for row in result.all()]

    if imos:
        await session.execute(
            update(VesselEnrichmentQueue)
            .where(VesselEnrichmentQueue.imo.in_(imos))
            .values(
                locked_until=lock_until,
                last_attempt_at=now,
                attempt_count=VesselEnrichmentQueue.attempt_count + 1,
            )
        )

    return imos


async def mark_success(session: AsyncSession, imo: int) -> None:
    """Remove vessel from the queue after successful enrichment."""
    await session.execute(
        delete(VesselEnrichmentQueue).where(VesselEnrichmentQueue.imo == imo)
    )


async def mark_failure(
    session: AsyncSession,
    imo: int,
    error: str,
    *,
    is_rate_limit: bool = False,
) -> None:
    """Record failure and schedule retry with backoff."""
    row = await session.scalar(
        select(VesselEnrichmentQueue).where(VesselEnrichmentQueue.imo == imo)
    )
    if row is None:
        return

    now = utc_now()
    if is_rate_limit:
        backoff = _RATE_LIMIT_BACKOFF_S
    else:
        backoff = _backoff_seconds(row.attempt_count)

    next_attempt = now + timedelta(seconds=backoff)
    await session.execute(
        update(VesselEnrichmentQueue)
        .where(VesselEnrichmentQueue.imo == imo)
        .values(
            locked_until=None,
            next_attempt_at=next_attempt,
            last_error=error,
        )
    )
    log.warning("enrichment: imo=%d failed (%s), retry in %ds", imo, error[:80], backoff)


async def queue_stats(session: AsyncSession) -> dict[str, Any]:
    """Return summary stats for the admin dashboard."""
    from sqlalchemy import func
    total = await session.scalar(select(func.count()).select_from(VesselEnrichmentQueue))
    now = utc_now()
    ready = await session.scalar(
        select(func.count())
        .select_from(VesselEnrichmentQueue)
        .where(
            VesselEnrichmentQueue.next_attempt_at <= now,
            (VesselEnrichmentQueue.locked_until.is_(None))
            | (VesselEnrichmentQueue.locked_until < now),
        )
    )
    locked = await session.scalar(
        select(func.count())
        .select_from(VesselEnrichmentQueue)
        .where(VesselEnrichmentQueue.locked_until >= now)
    )
    return {"total": total or 0, "ready": ready or 0, "locked": locked or 0}
