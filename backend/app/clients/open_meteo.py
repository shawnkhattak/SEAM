"""Open-Meteo Marine API client.

Single polling point: 1.265°N 103.82°E (Singapore anchorage).
12 marine variables per ADR-0024 / architecture §Open-Meteo Marine Polling.
Mock mode reads app/mocks/weather_response.json.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
_LAT = 1.265
_LON = 103.82
_VARIABLES = [
    "wave_height",
    "wave_direction",
    "wave_period",
    "wind_wave_height",
    "wind_wave_direction",
    "wind_wave_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
    "ocean_current_velocity",
    "ocean_current_direction",
    "sea_surface_temperature",
]
_MOCK_PATH = Path(__file__).parent.parent / "mocks" / "weather_response.json"


def _parse_response(data: dict) -> dict | None:
    """Return the most-recent hourly observation row as a flat dict, or None."""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return None

    now = datetime.now(timezone.utc)
    # Find the index of the latest hour that is at or before now
    best_idx: int | None = None
    for i, t_str in enumerate(times):
        try:
            t = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if t <= now:
            best_idx = i
        else:
            break

    if best_idx is None:
        best_idx = 0

    t_str = times[best_idx]
    recorded_at = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)

    def _val(key: str) -> float | None:
        vals = hourly.get(key, [])
        if best_idx < len(vals):
            v = vals[best_idx]
            return float(v) if v is not None else None
        return None

    return {
        "recorded_at": recorded_at,
        "wave_height_m": _val("wave_height"),
        "wave_direction_deg": _val("wave_direction"),
        "wave_period_s": _val("wave_period"),
        "wind_wave_height_m": _val("wind_wave_height"),
        "wind_wave_direction_deg": _val("wind_wave_direction"),
        "wind_wave_period_s": _val("wind_wave_period"),
        "swell_wave_height_m": _val("swell_wave_height"),
        "swell_wave_direction_deg": _val("swell_wave_direction"),
        "swell_wave_period_s": _val("swell_wave_period"),
        "ocean_current_velocity_ms": _val("ocean_current_velocity"),
        "ocean_current_direction_deg": _val("ocean_current_direction"),
        "sea_surface_temperature_c": _val("sea_surface_temperature"),
    }


async def fetch_current_observation() -> dict | None:
    """Fetch the latest hourly marine observation. Returns a flat row dict or None."""
    if get_settings().opensanctions_mock_mode:
        data = json.loads(_MOCK_PATH.read_text())
        return _parse_response(data)

    params = {
        "latitude": _LAT,
        "longitude": _LON,
        "hourly": ",".join(_VARIABLES),
        "timezone": "UTC",
        "forecast_days": 1,
        "past_days": 1,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(_MARINE_URL, params=params)
        resp.raise_for_status()
        return _parse_response(resp.json())
