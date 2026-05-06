"""Public /api/about endpoint — data source attribution + build info."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.limiter import limiter
from app.models import DataSourceAttribution

router = APIRouter(prefix="/about", tags=["about"])
logger = logging.getLogger(__name__)

_SEED_ATTRIBUTIONS = [
    {
        "source_name": "oceansx",
        "display_text": "OceansX Maritime Intelligence Platform",
        "url": "https://www.oceansx.io",
        "license_summary": "Commercial API — subscription required",
        "attribution_required": False,
        "non_commercial_only": False,
    },
    {
        "source_name": "opensanctions",
        "display_text": "OpenSanctions Global Sanctions Database",
        "url": "https://www.opensanctions.org",
        "license_summary": "CC BY-NC 4.0 (non-commercial use)",
        "attribution_required": True,
        "non_commercial_only": True,
    },
    {
        "source_name": "open_meteo",
        "display_text": "Open-Meteo Marine Weather API",
        "url": "https://open-meteo.com",
        "license_summary": "CC BY 4.0 — attribution required",
        "attribution_required": True,
        "non_commercial_only": False,
    },
    {
        "source_name": "rss_app",
        "display_text": "RSS.app Maritime News Aggregation",
        "url": "https://rss.app",
        "license_summary": "Commercial API — subscription required",
        "attribution_required": False,
        "non_commercial_only": False,
    },
]


async def seed_attributions(session: AsyncSession) -> int:
    """Upsert default attribution rows. Returns count inserted/updated."""
    upserted = 0
    for item in _SEED_ATTRIBUTIONS:
        result = await session.execute(
            select(DataSourceAttribution).where(
                DataSourceAttribution.source_name == item["source_name"]
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = DataSourceAttribution(**item)
            session.add(row)
            upserted += 1
        else:
            for k, v in item.items():
                setattr(row, k, v)
            upserted += 1
    return upserted


@router.get("", response_model=dict[str, Any])
@limiter.limit("60/minute")
async def get_about(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return build metadata and all data source attribution records."""
    settings = get_settings()
    result = await db.execute(
        select(DataSourceAttribution).order_by(DataSourceAttribution.source_name)
    )
    rows = result.scalars().all()

    attributions = [
        {
            "source_name": r.source_name,
            "display_text": r.display_text,
            "url": r.url,
            "license_summary": r.license_summary,
            "attribution_required": r.attribution_required,
            "non_commercial_only": r.non_commercial_only,
        }
        for r in rows
    ]

    env = "production" if settings.oceansx_mock_mode == "never" else "development"
    return {
        "app_name": "OceansX Visualizer V2",
        "version": "2.0.0",
        "environment": env,
        "data_sources": attributions,
    }
