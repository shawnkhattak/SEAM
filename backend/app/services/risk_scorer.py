"""Deterministic composite risk scoring.

Formula (ADR-0026):
  IF sanctions_score > 0 OR shadow_fleet_score > 0:
      composite = max(sanctions_score, shadow_fleet_score)
  ELSE:
      composite = flag_mou_score * 0.40 + age_score * 0.30
                  + congestion_score * 0.20 + weather_score * 0.10

weather_score and congestion_score are hardcoded 0.0 — formulas deferred.
Scoring scope: vessels with last_observed_at >= now() - 24 hours.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FlagPerformanceYear, MouInspection, RiskScore, Vessel

logger = logging.getLogger(__name__)

WEATHER_SCORE: float = 0.0
CONGESTION_SCORE: float = 0.0

_SANCTIONS_SCORE_MAP = {
    "sanctioned": 100.0,
    "pending": 50.0,
    "prev_sanctioned": 25.0,
    "clean": 0.0,
}


def _sanctions_score(current_sanctions_status: str) -> float:
    return _SANCTIONS_SCORE_MAP.get(current_sanctions_status, 0.0)


def _shadow_fleet_score(is_shadow_fleet: bool) -> float:
    return 100.0 if is_shadow_fleet else 0.0


def _age_score(year_built: str | None, reference_year: int) -> float:
    """Linear ramp: 0 at ≤10 years old, 100 at ≥25 years old. 0 if year_built unknown."""
    if year_built is None:
        return 0.0
    try:
        built = int(year_built)
    except (ValueError, TypeError):
        return 0.0
    age = reference_year - built
    if age <= 10:
        return 0.0
    if age >= 25:
        return 100.0
    return (age - 10) / 15.0 * 100.0


def _composite(
    sanctions: float,
    shadow: float,
    flag_mou: float,
    age: float,
    congestion: float = CONGESTION_SCORE,
    weather: float = WEATHER_SCORE,
) -> float:
    if sanctions > 0 or shadow > 0:
        return max(sanctions, shadow)
    return (
        flag_mou * 0.40
        + age * 0.30
        + congestion * 0.20
        + weather * 0.10
    )


async def _flag_mou_score(
    session: AsyncSession,
    flag_code: str | None,
    imo: int,
) -> float:
    """0=white, 50=grey, 100=black. Override 100 if detained in last 24 months.
    Unknown flag → grey (50) per ADR-0026."""
    band = "grey"

    if flag_code:
        row = await session.execute(
            select(FlagPerformanceYear.performance_band)
            .where(FlagPerformanceYear.flag_code == flag_code)
            .where(FlagPerformanceYear.mou == "tokyo")
            .order_by(FlagPerformanceYear.year.desc())
            .limit(1)
        )
        result = row.scalar_one_or_none()
        if result is not None:
            band = result

    score_map = {"white": 0.0, "grey": 50.0, "black": 100.0}
    base = score_map.get(band, 50.0)

    detention_row = await session.execute(
        select(MouInspection.id)
        .where(MouInspection.imo == imo)
        .where(MouInspection.detained.is_(True))
        .where(
            MouInspection.inspection_date
            >= text("now() - interval '24 months'")
        )
        .limit(1)
    )
    if detention_row.scalar_one_or_none() is not None:
        return 100.0

    return base


async def score_vessel(session: AsyncSession, vessel: Vessel) -> RiskScore:
    """Compute and persist one RiskScore row for a single vessel."""
    now = datetime.now(timezone.utc)
    ref_year = now.year

    s_score = _sanctions_score(vessel.current_sanctions_status)
    sh_score = _shadow_fleet_score(vessel.is_shadow_fleet)
    a_score = _age_score(vessel.year_built, ref_year)
    fm_score = await _flag_mou_score(session, vessel.flag, vessel.imo)

    comp = _composite(s_score, sh_score, fm_score, a_score)

    rs = RiskScore(
        vessel_imo=vessel.imo,
        scored_at=now,
        composite=round(comp, 2),
        sanctions_score=s_score,
        shadow_fleet_score=sh_score,
        age_score=round(a_score, 2),
        flag_mou_score=fm_score,
        congestion_score=CONGESTION_SCORE,
        weather_score=WEATHER_SCORE,
        components={
            "sanctions_status": vessel.current_sanctions_status,
            "is_shadow_fleet": vessel.is_shadow_fleet,
            "year_built": vessel.year_built,
            "flag": vessel.flag,
        },
    )
    session.add(rs)

    vessel.latest_risk_score_at = now
    return rs


async def run_hourly_scoring(session: AsyncSession) -> dict:
    """Score all vessels active in the last 24 hours. Returns summary counts."""
    result = await session.execute(
        select(Vessel).where(
            Vessel.last_observed_at >= text("now() - interval '24 hours'")
        )
    )
    vessels = result.scalars().all()

    scored = 0
    errors = 0
    for vessel in vessels:
        try:
            await score_vessel(session, vessel)
            scored += 1
        except Exception:
            logger.exception("risk scoring failed for imo=%s", vessel.imo)
            errors += 1

    return {"scored": scored, "errors": errors, "total": len(vessels)}
