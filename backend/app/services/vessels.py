from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.clients.oceansx import OceansXClient
from app.utils.imo import luhn_valid
from app.utils.timezone import clamp_future, utc_now

logger = logging.getLogger(__name__)

# MPA OceansX publishes timestamps in Singapore local time (UTC+8).
_SG_TZ = timezone(timedelta(hours=8))

# Singapore Strait bounding box for status inference.
_SG_BBOX = (1.10, 103.55, 1.50, 104.10)


def parse_mpa_timestamp(s: str | None) -> datetime:
    """Convert MPA's 'YYYY-MM-DD HH:MM:SS' (Singapore time) to UTC, clamped."""
    if not s:
        return utc_now()
    try:
        naive = datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
        sg_aware = naive.replace(tzinfo=_SG_TZ)
        utc_ts = sg_aware.astimezone(timezone.utc)
        clamped, was_clamped = clamp_future(utc_ts)
        if was_clamped:
            logger.debug("parse_mpa_timestamp: clamped future timestamp %s", s)
        return clamped
    except ValueError:
        return utc_now()


def _infer_status(lat: float, lon: float, speed: float) -> str:
    in_bbox = (
        _SG_BBOX[0] <= lat <= _SG_BBOX[2] and _SG_BBOX[1] <= lon <= _SG_BBOX[3]
    )
    if in_bbox and speed < 1.0:
        return "arrived"
    if in_bbox and speed >= 1.0:
        return "departing"
    if 103.40 < lon < 104.50 and 1.00 < lat < 1.60:
        return "incoming"
    return "departed"


def normalize_position(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an upstream snapshot record to a canonical V2 position dict."""
    vp = raw.get("vesselParticulars") or {}
    imo_str = (vp.get("imoNumber") or "").strip()
    if not imo_str or not luhn_valid(imo_str):
        return None

    lat = raw.get("latitudeDegrees")
    lon = raw.get("longitudeDegrees")
    if lat is None or lon is None:
        return None

    lat, lon = float(lat), float(lon)
    speed = float(raw.get("speed") or 0.0)
    course = float(raw.get("course") or 0.0)
    heading = float(raw.get("heading") or course)
    recorded_at = parse_mpa_timestamp(raw.get("timeStamp"))

    return {
        "imo": int(imo_str),
        "mmsi": vp.get("mmsiNumber"),
        "name": (vp.get("vesselName") or "Unknown").strip(),
        "call_sign": vp.get("callSign"),
        "flag": vp.get("flag"),
        "vessel_type": vp.get("vesselType"),
        "year_built": str(vp.get("yearBuilt")) if vp.get("yearBuilt") else None,
        "gross_tonnage": float(vp["grossTonnage"]) if vp.get("grossTonnage") else None,
        "deadweight": float(vp["deadweight"]) if vp.get("deadweight") else None,
        "length_overall": float(vp["vesselLength"]) if vp.get("vesselLength") else None,
        "beam": float(vp["vesselBreadth"]) if vp.get("vesselBreadth") else None,
        "lat": lat,
        "lon": lon,
        "speed_knots": speed,
        "course_degrees": course,
        "heading_degrees": heading,
        "nav_status": None,
        "draft_meters": None,
        "inferred_status": _infer_status(lat, lon, speed),
        "recorded_at": recorded_at,
    }


async def get_live_positions(client: OceansXClient) -> list[dict[str, Any]]:
    """Fetch and normalize the current position snapshot from MPA."""
    raw_list = await client.vessel_positions_snapshot()
    positions: list[dict[str, Any]] = []
    rejected = 0
    for raw in raw_list:
        norm = normalize_position(raw)
        if norm is not None:
            positions.append(norm)
        else:
            rejected += 1
    if rejected:
        logger.debug("get_live_positions: rejected %d invalid records", rejected)
    return positions


def enrich_from_particulars(position: dict[str, Any], particulars: dict[str, Any]) -> dict[str, Any]:
    """Merge particulars API response into a position dict (for vessel detail view)."""
    return {
        **position,
        "ism_manager": particulars.get("ismManager"),
        "registered_owner": particulars.get("registeredOwnership"),
        "operator": particulars.get("shipManager"),
        "classification_society": particulars.get("classificationSociety"),
        "net_tonnage": float(particulars["netTonnage"]) if particulars.get("netTonnage") else None,
        "depth": float(particulars["vesselDepth"]) if particulars.get("vesselDepth") else None,
    }
