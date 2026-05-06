from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PositionArchive, PositionLive
from app.utils.timezone import utc_now

logger = logging.getLogger(__name__)

# Archive dedup thresholds (ADR-0018)
_DEDUP_DISTANCE_M = 100.0
_DEDUP_HEADING_DEG = 5.0
_DEDUP_SPEED_KN = 0.5


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def write_position_live(session: AsyncSession, pos: dict[str, Any]) -> None:
    """Upsert a position row into position_live."""
    stmt = insert(PositionLive).values(
        imo=pos["imo"],
        recorded_at=pos["recorded_at"],
        lat=pos["lat"],
        lon=pos["lon"],
        speed_knots=pos.get("speed_knots"),
        course_degrees=pos.get("course_degrees"),
        heading_degrees=pos.get("heading_degrees"),
        nav_status=pos.get("nav_status"),
        draft_meters=pos.get("draft_meters"),
        inferred_status=pos["inferred_status"],
        terminal_id=None,
    ).on_conflict_do_nothing(constraint="uq_pos_live_imo_recorded_at")
    await session.execute(stmt)


async def maybe_write_position_archive(session: AsyncSession, pos: dict[str, Any], terminal_id: int | None = None) -> bool:
    """Write to position_archive only if the vessel moved enough since the last archive row.

    Dedup rule (locked decision #18): skip if within 100 m AND |Δheading| < 5° AND |Δspeed| < 0.5 kn.
    Returns True if a row was written, False if skipped.
    """
    imo = pos["imo"]

    # Fetch the most recent archive row for this vessel
    result = await session.execute(
        select(PositionArchive)
        .where(PositionArchive.imo == imo)
        .order_by(PositionArchive.recorded_at.desc())
        .limit(1)
    )
    prev = result.scalar_one_or_none()

    if prev is not None:
        dist = _haversine_m(prev.lat, prev.lon, pos["lat"], pos["lon"])
        dheading = abs((pos.get("heading_degrees") or 0.0) - (prev.heading_degrees or 0.0))
        dspeed = abs((pos.get("speed_knots") or 0.0) - (prev.speed_knots or 0.0))
        if dist < _DEDUP_DISTANCE_M and dheading < _DEDUP_HEADING_DEG and dspeed < _DEDUP_SPEED_KN:
            return False

    stmt = insert(PositionArchive).values(
        imo=imo,
        recorded_at=pos["recorded_at"],
        lat=pos["lat"],
        lon=pos["lon"],
        speed_knots=pos.get("speed_knots"),
        course_degrees=pos.get("course_degrees"),
        heading_degrees=pos.get("heading_degrees"),
        nav_status=pos.get("nav_status"),
        draft_meters=pos.get("draft_meters"),
        inferred_status=pos["inferred_status"],
        terminal_id=terminal_id,
    ).on_conflict_do_nothing(constraint="uq_pos_archive_imo_recorded_at")
    await session.execute(stmt)
    return True


async def get_vessel_trail(
    session: AsyncSession, imo: int, since: datetime | None = None
) -> list[dict[str, Any]]:
    """Return archive positions for a vessel in the last 24h (or since a given time)."""
    if since is None:
        since = utc_now() - timedelta(hours=24)

    result = await session.execute(
        select(PositionArchive)
        .where(PositionArchive.imo == imo, PositionArchive.recorded_at >= since)
        .order_by(PositionArchive.recorded_at.asc())
        .limit(1440)  # max 1440 points per §8.4
    )
    rows = result.scalars().all()
    return [
        {
            "imo": r.imo,
            "recorded_at": r.recorded_at.isoformat(),
            "lat": r.lat,
            "lon": r.lon,
            "speed_knots": r.speed_knots,
            "heading_degrees": r.heading_degrees,
            "inferred_status": r.inferred_status,
        }
        for r in rows
    ]


async def get_all_recent_positions(session: AsyncSession) -> list[dict[str, Any]]:
    """Most recent position_live row per vessel — used for the initial map load."""
    result = await session.execute(
        text(
            "SELECT DISTINCT ON (imo) imo, recorded_at, lat, lon, "
            "speed_knots, course_degrees, heading_degrees, nav_status, "
            "draft_meters, inferred_status "
            "FROM position_live "
            "ORDER BY imo, recorded_at DESC"
        )
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]


async def update_position_terminal(
    session: AsyncSession, imo: int, recorded_at: datetime, lat: float, lon: float
) -> int | None:
    """Set terminal_id on a position_live row using an ST_Within containment check.

    Returns the matched terminal_id, or None if outside all terminal polygons.
    Only updates rows where terminal_id IS NULL to avoid re-querying for unchanged rows.
    """
    from app.services.ports import find_terminal_for_position

    terminal_id = await find_terminal_for_position(session, lat, lon)
    if terminal_id is not None:
        await session.execute(
            text(
                "UPDATE position_live SET terminal_id = :tid "
                "WHERE imo = :imo AND recorded_at = :ra AND terminal_id IS NULL"
            ),
            {"tid": terminal_id, "imo": imo, "ra": recorded_at},
        )
    return terminal_id
