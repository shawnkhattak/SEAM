"""Risk scoring API endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.limiter import limiter
from app.models import RiskScore, Vessel
from app.schemas import RiskLeaderboardItem, RiskScoreResponse
from app.utils.imo import luhn_valid
from app.utils.vessel_labels import display_vessel_name, flag_emoji, flag_name, vessel_type_label

router = APIRouter(prefix="/risk", tags=["risk"])


def _days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


@router.get("/vessel/{imo}", response_model=list[RiskScoreResponse])
@limiter.limit("60/minute")
async def vessel_risk_history(
    request: Request,
    imo: int,
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, ge=1, le=90),
) -> list[RiskScoreResponse]:
    """Latest risk scores for a vessel (most-recent first, up to `days` days of history)."""
    if not luhn_valid(imo):
        raise HTTPException(status_code=422, detail="Invalid IMO number")

    result = await db.execute(
        select(RiskScore)
        .where(RiskScore.vessel_imo == imo)
        .where(RiskScore.scored_at >= _days_ago(days))
        .order_by(RiskScore.scored_at.desc())
        .limit(200)
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No risk scores found for this vessel")

    return [
        RiskScoreResponse(
            vessel_imo=r.vessel_imo,
            scored_at=r.scored_at,
            composite=r.composite,
            sanctions_score=r.sanctions_score,
            shadow_fleet_score=r.shadow_fleet_score,
            age_score=r.age_score,
            flag_mou_score=r.flag_mou_score,
            congestion_score=r.congestion_score,
            weather_score=r.weather_score,
            components=r.components,
        )
        for r in rows
    ]


@router.get("/leaderboard", response_model=list[RiskLeaderboardItem])
@limiter.limit("30/minute")
async def risk_leaderboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
) -> list[RiskLeaderboardItem]:
    """Top vessels by composite risk score (latest score per vessel, active last 24h)."""
    latest_q = (
        select(RiskScore)
        .where(RiskScore.scored_at >= _days_ago(1))
        .distinct(RiskScore.vessel_imo)
        .order_by(RiskScore.vessel_imo, RiskScore.scored_at.desc())
        .subquery()
    )

    LatestScore = aliased(RiskScore, latest_q)

    rows = await db.execute(
        select(
            Vessel.imo,
            Vessel.name,
            Vessel.flag,
            Vessel.vessel_type,
            Vessel.is_shadow_fleet,
            Vessel.current_sanctions_status,
            LatestScore.composite,
            LatestScore.scored_at,
        )
        .join(LatestScore, LatestScore.vessel_imo == Vessel.imo)
        .where(LatestScore.composite >= min_score)
        .order_by(LatestScore.composite.desc())
        .limit(limit)
    )

    return [
        RiskLeaderboardItem(
            imo=row.imo,
            name=display_vessel_name(row.name, row.flag),
            flag=row.flag,
            flag_name=flag_name(row.flag),
            flag_emoji=flag_emoji(row.flag),
            vessel_type=row.vessel_type,
            vessel_type_label=vessel_type_label(row.vessel_type),
            composite=row.composite,
            is_shadow_fleet=row.is_shadow_fleet,
            current_sanctions_status=row.current_sanctions_status,
            scored_at=row.scored_at,
        )
        for row in rows.all()
    ]
