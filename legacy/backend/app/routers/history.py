from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.limiter import limiter
from app.schemas import TrailPoint
from app.services.history import get_vessel_trail
from app.utils.imo import luhn_valid
from app.utils.timezone import utc_now

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/trail/{imo}", response_model=list[TrailPoint])
@limiter.limit("30/minute")
async def vessel_trail(
    request: Request,
    imo: Annotated[str, Path(pattern=r"^\d{7}$")],
    db: AsyncSession = Depends(get_db),
) -> list[TrailPoint]:
    """24-hour position trail for the timeline scrubber (up to 1440 points)."""
    if not luhn_valid(imo):
        raise HTTPException(status_code=422, detail=f"Invalid IMO: {imo}")

    since = utc_now() - timedelta(hours=24)
    rows = await get_vessel_trail(db, int(imo), since=since)
    return [TrailPoint(**r) for r in rows]
