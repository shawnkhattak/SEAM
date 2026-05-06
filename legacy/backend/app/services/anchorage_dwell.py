"""Anchorage dwell tracking.

At :10 each hour, compares current vessel positions against terminal polygons.
- Vessel inside a terminal with no open dwell → open new dwell (started_at = now)
- Vessel outside every terminal with an open dwell → close it (ended_at = now)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnchorageDwell

logger = logging.getLogger(__name__)


async def compute_dwell(session: AsyncSession) -> dict:
    """Open dwell events for newly-arrived vessels; close those that have left."""
    now = datetime.now(timezone.utc)
    opened = 0
    closed = 0

    # -----------------------------------------------------------------
    # Vessels currently inside a terminal polygon (PostGIS ST_Within)
    # Returns (imo, terminal_id) pairs using the latest position per IMO
    # -----------------------------------------------------------------
    inside_q = text("""
        WITH latest AS (
            SELECT DISTINCT ON (pl.imo)
                pl.imo,
                ST_SetSRID(ST_MakePoint(pl.lon, pl.lat), 4326) AS geom
            FROM position_live pl
            WHERE pl.recorded_at >= now() - interval '30 minutes'
            ORDER BY pl.imo, pl.recorded_at DESC
        )
        SELECT l.imo, tg.terminal_id
        FROM latest l
        JOIN terminal_geom tg
          ON ST_Within(l.geom::geometry, tg.geom::geometry)
    """)
    inside_rows = (await session.execute(inside_q)).fetchall()
    inside: dict[int, int] = {row.imo: row.terminal_id for row in inside_rows}

    # -----------------------------------------------------------------
    # Fetch all currently-open dwell events
    # -----------------------------------------------------------------
    open_rows = await session.execute(
        select(AnchorageDwell).where(AnchorageDwell.ended_at.is_(None))
    )
    open_dwells: list[AnchorageDwell] = open_rows.scalars().all()
    open_by_imo: dict[int, AnchorageDwell] = {d.vessel_imo: d for d in open_dwells}

    # -----------------------------------------------------------------
    # Close dwells for vessels no longer inside any terminal
    # -----------------------------------------------------------------
    for imo, dwell in open_by_imo.items():
        if imo not in inside:
            dwell.ended_at = now
            closed += 1

    # -----------------------------------------------------------------
    # Open dwell events for vessels newly inside a terminal
    # -----------------------------------------------------------------
    for imo, terminal_id in inside.items():
        if imo not in open_by_imo:
            session.add(AnchorageDwell(
                vessel_imo=imo,
                terminal_id=terminal_id,
                started_at=now,
                ended_at=None,
            ))
            opened += 1

    return {"opened": opened, "closed": closed}
