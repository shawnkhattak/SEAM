from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache as l1_cache
from app.db import get_db
from app.limiter import limiter
from app.schemas import NlSearchRequest, NlSearchResult, VesselPosition
from app.services.nl_search import execute_search, parse_nl_query, spec_cache_key
from app.utils.vessel_labels import display_vessel_name, flag_emoji, flag_name, vessel_type_label

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)

_NL_CACHE_TTL = 600  # 10 minutes
_NL_TIMEOUT_S = 5.0  # asyncio timeout for LLM parse


@router.post("/nl", response_model=NlSearchResult)
@limiter.limit("10/minute")
async def nl_search(
    request: Request,
    body: NlSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> NlSearchResult:
    """Natural-language vessel search. Translates the query into a structured filter via Haiku,
    then executes the filter against the vessel table. Results cached 10 minutes per parsed spec."""
    # Parse NL query → SearchFilterSpec (rate-limited by the decorator above)
    try:
        spec = await asyncio.wait_for(parse_nl_query(body.query), timeout=_NL_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="NL parse timed out — try a simpler query")
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("nl_search: parse error query=%r: %s", body.query, exc)
        raise HTTPException(status_code=422, detail=f"Could not parse query: {exc}") from exc

    cache_key = f"api:search:nl:{spec_cache_key(spec)}"
    cached_result = l1_cache.get(cache_key)
    if cached_result is not None:
        logger.debug("nl_search: cache hit key=%s", cache_key[:16])
        return NlSearchResult(spec=spec, vessels=cached_result, cached=True)

    vessels = await execute_search(db, spec)

    result_vessels: list[VesselPosition] = []
    for v in vessels:
        result_vessels.append(
            VesselPosition(
                imo=v.imo,
                name=display_vessel_name(v.name, v.flag),
                flag=v.flag,
                flag_name=flag_name(v.flag),
                flag_emoji=flag_emoji(v.flag),
                vessel_type=v.vessel_type,
                vessel_type_label=vessel_type_label(v.vessel_type),
                year_built=v.year_built,
                gross_tonnage=v.gross_tonnage,
                lat=0.0,
                lon=0.0,
                inferred_status="unknown",
                recorded_at=v.last_observed_at or v.first_observed_at,
                is_shadow_fleet=v.is_shadow_fleet,
                current_sanctions_status=v.current_sanctions_status,
            )
        )

    l1_cache.set(cache_key, result_vessels, ttl_seconds=_NL_CACHE_TTL)
    logger.info(
        "nl_search: query=%r spec=%s vessels=%d",
        body.query,
        spec.model_dump(exclude_defaults=True),
        len(result_vessels),
    )
    return NlSearchResult(spec=spec, vessels=result_vessels, cached=False)
