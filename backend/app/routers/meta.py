from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import HealthResponse

router = APIRouter(tags=["meta"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Liveness + readiness check. Pings Postgres and returns version."""
    try:
        result = await db.execute(text("SELECT version()"))
        row = result.scalar_one()
        db_status = "ok"
        logger.debug("health check db=%s", row[:50])
    except Exception as exc:
        logger.error("health check db error: %s", exc)
        db_status = f"error: {exc}"

    return HealthResponse(status="ok", db=db_status)


@router.get("/about")
async def about() -> dict:
    """Data source attribution and license summaries."""
    return {
        "sources": [
            {
                "name": "MPA OceansX",
                "description": "Vessel positions and particulars",
                "url": "https://oceans-x.mpa.gov.sg",
                "license": "Per MPA Singapore terms",
                "attribution_required": True,
            },
            {
                "name": "OpenSanctions",
                "description": "Sanctioned vessels, organizations, and MoU detention records",
                "url": "https://opensanctions.org",
                "license": "CC-BY 4.0 (non-commercial)",
                "attribution_required": True,
            },
            {
                "name": "Open-Meteo Marine",
                "description": "Wave, wind, swell, current, and sea surface temperature data",
                "url": "https://open-meteo.com",
                "license": "CC-BY 4.0 (non-commercial)",
                "attribution_required": True,
            },
            {
                "name": "RSS.app",
                "description": "Curated maritime news feeds",
                "url": "https://rss.app",
                "license": "Per RSS.app terms; per-article attribution to original publisher",
                "attribution_required": True,
            },
        ],
        "license_posture": "Strictly non-commercial. All data sources used under free non-commercial terms.",
    }
