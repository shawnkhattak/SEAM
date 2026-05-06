"""Weather ingestion service — stores Open-Meteo Marine observations."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.open_meteo import fetch_current_observation
from app.models import WeatherObservation

logger = logging.getLogger(__name__)


async def pull_and_store_weather(session: AsyncSession) -> dict:
    """Fetch the current marine observation and upsert into weather_observation."""
    obs = await fetch_current_observation()
    if obs is None:
        logger.warning("open_meteo returned no observation")
        return {"stored": 0}

    existing = await session.execute(
        select(WeatherObservation.id)
        .where(WeatherObservation.recorded_at == obs["recorded_at"])
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return {"stored": 0, "skipped": 1}

    row = WeatherObservation(**obs)
    session.add(row)
    return {"stored": 1}
