from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app import cache as l1_cache
from app.clients.oceansx import OceansXClient, get_oceansx_client
from app.db import get_db
from app.limiter import limiter
from app.models import RiskScore, Vessel
from app.schemas import DueArrival, DueDeparture, VesselDetail, VesselPosition
from app.services import vessels as vessel_svc
from app.utils.imo import luhn_valid
from app.utils.timezone import utc_now
from app.utils.vessel_labels import display_vessel_name, flag_emoji, flag_name, vessel_type_label

router = APIRouter(prefix="/vessels", tags=["vessels"])
logger = logging.getLogger(__name__)


def _client() -> OceansXClient:
    return get_oceansx_client()


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text_value = str(value).strip()
        if text_value:
            return text_value
    return None


def _first_float(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


@router.get("/positions", response_model=list[VesselPosition])
@limiter.limit("60/minute")
async def list_positions(
    request: Request,
    client: OceansXClient = Depends(_client),
    db: AsyncSession = Depends(get_db),
) -> list[VesselPosition]:
    """Current position snapshot for all visible vessels. Includes sanctions/shadow fleet flags."""
    cache_key = "api:vessels:positions"
    cached = l1_cache.get(cache_key)
    if cached is not None:
        return cached
    positions = await vessel_svc.get_live_positions(client)

    # Merge DB flags + latest risk composite in two queries
    imos = [p["imo"] for p in positions]
    flags: dict[int, dict] = {}
    if imos:
        vessel_result = await db.execute(
            select(Vessel.imo, Vessel.is_shadow_fleet, Vessel.current_sanctions_status)
            .where(Vessel.imo.in_(imos))
        )
        for row in vessel_result.all():
            flags[row.imo] = {
                "is_shadow_fleet": row.is_shadow_fleet,
                "current_sanctions_status": row.current_sanctions_status,
                "latest_composite_risk": None,
            }

        # Latest risk composite per vessel (DISTINCT ON needs a subquery in SA)
        from sqlalchemy import distinct, func
        risk_result = await db.execute(
            select(RiskScore.vessel_imo, RiskScore.composite, RiskScore.scored_at)
            .where(RiskScore.vessel_imo.in_(imos))
            .distinct(RiskScore.vessel_imo)
            .order_by(RiskScore.vessel_imo, RiskScore.scored_at.desc())
        )
        for row in risk_result.all():
            if row.vessel_imo in flags:
                flags[row.vessel_imo]["latest_composite_risk"] = row.composite

    result_list = [
        VesselPosition(
            imo=p["imo"],
            mmsi=p.get("mmsi"),
            name=display_vessel_name(p["name"], p.get("flag")),
            flag=p.get("flag"),
            flag_name=flag_name(p.get("flag")),
            flag_emoji=flag_emoji(p.get("flag")),
            vessel_type=p.get("vessel_type"),
            vessel_type_label=vessel_type_label(p.get("vessel_type")),
            year_built=p.get("year_built"),
            gross_tonnage=p.get("gross_tonnage"),
            lat=p["lat"],
            lon=p["lon"],
            speed_knots=p.get("speed_knots"),
            course_degrees=p.get("course_degrees"),
            heading_degrees=p.get("heading_degrees"),
            inferred_status=p["inferred_status"],
            recorded_at=p["recorded_at"],
            is_shadow_fleet=flags.get(p["imo"], {}).get("is_shadow_fleet", False),
            current_sanctions_status=flags.get(p["imo"], {}).get("current_sanctions_status", "clean"),
            latest_composite_risk=flags.get(p["imo"], {}).get("latest_composite_risk"),
        )
        for p in positions
    ]
    l1_cache.set(cache_key, result_list, ttl_seconds=60)
    return result_list


@router.get("/due-to-arrive", response_model=list[DueArrival])
@limiter.limit("30/minute")
async def due_to_arrive(
    request: Request,
    hours: int = Query(6, ge=1, le=72),
    client: OceansXClient = Depends(_client),
) -> list[DueArrival]:
    items = await client.vessels_due_to_arrive(utc_now(), hours=hours)
    return [
        DueArrival(
            imo=(it.get("vesselParticulars") or {}).get("imoNumber"),
            name=(it.get("vesselParticulars") or {}).get("vesselName"),
            flag=(it.get("vesselParticulars") or {}).get("flag"),
            due_to_arrive_time=it.get("duetoArriveTime"),
            location_from=it.get("locationFrom"),
            location_to=it.get("locationTo"),
        )
        for it in items
    ]


@router.get("/due-to-depart", response_model=list[DueDeparture])
@limiter.limit("30/minute")
async def due_to_depart(
    request: Request,
    hours: int = Query(6, ge=1, le=72),
    client: OceansXClient = Depends(_client),
) -> list[DueDeparture]:
    items = await client.vessels_due_to_depart(utc_now(), hours=hours)
    return [
        DueDeparture(
            imo=(it.get("vesselParticulars") or {}).get("imoNumber"),
            name=(it.get("vesselParticulars") or {}).get("vesselName"),
            flag=(it.get("vesselParticulars") or {}).get("flag"),
            due_to_depart_time=it.get("duetoDepartTime"),
            location_from=it.get("locationFrom"),
            location_to=it.get("locationTo"),
        )
        for it in items
    ]


@router.get("/new-arrivals", response_model=list[VesselDetail])
@limiter.limit("30/minute")
async def new_arrivals(
    request: Request,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    db: AsyncSession = Depends(get_db),
) -> list[VesselDetail]:
    """Vessels first observed in Singapore waters within the last N hours (default 24)."""
    from datetime import timezone, timedelta
    cutoff = utc_now() - timedelta(hours=hours)
    result = await db.execute(
        select(Vessel)
        .where(Vessel.first_observed_at >= cutoff)
        .order_by(Vessel.first_observed_at.desc())
        .limit(100)
    )
    vessels = result.scalars().all()
    return [
        VesselDetail(
            imo=v.imo,
            name=display_vessel_name(v.name, v.flag),
            mmsi=v.mmsi,
            call_sign=v.call_sign,
            flag=v.flag,
            flag_name=flag_name(v.flag),
            flag_emoji=flag_emoji(v.flag),
            vessel_type=v.vessel_type,
            vessel_type_label=vessel_type_label(v.vessel_type),
            year_built=v.year_built,
            gross_tonnage=v.gross_tonnage,
            deadweight=v.deadweight,
            length_overall=v.length_overall,
            beam=v.beam,
            ism_manager=v.ism_manager,
            registered_owner=v.registered_owner,
            operator=v.operator,
            classification_society=v.classification_society,
            is_shadow_fleet=v.is_shadow_fleet,
            current_sanctions_status=v.current_sanctions_status,
            first_observed_at=v.first_observed_at,
            last_observed_at=v.last_observed_at,
            last_enriched_at=v.last_enriched_at,
        )
        for v in vessels
    ]


@router.get("/{imo}", response_model=VesselDetail)
@limiter.limit("30/minute")
async def get_vessel(
    request: Request,
    imo: Annotated[str, Path(pattern=r"^\d{7}$")],
    db: AsyncSession = Depends(get_db),
    client: OceansXClient = Depends(_client),
) -> VesselDetail:
    """Full vessel detail: particulars + last position + recent movements."""
    if not luhn_valid(imo):
        raise HTTPException(status_code=422, detail=f"Invalid IMO number: {imo}")

    cache_key = f"api:vessel:{imo}"
    cached = l1_cache.get(cache_key)
    if cached is not None:
        return cached

    imo_int = int(imo)
    # Fetch from DB first
    result = await db.execute(
        select(Vessel).where(Vessel.imo == imo_int)
    )
    vessel_row = result.scalar_one_or_none()

    # Fetch particulars + movements from API
    particulars = await client.vessel_particulars_by_imo(imo)
    movements = await client.vessel_movements_by_imo(imo)
    if particulars:
        from app.services.vessel_master import update_from_particulars
        await update_from_particulars(db, imo_int, particulars)
        await db.commit()
        if vessel_row:
            await db.refresh(vessel_row)

    # Current position from live snapshot
    positions = await vessel_svc.get_live_positions(client)
    current_pos = next((p for p in positions if p["imo"] == imo_int), None)

    particulars = particulars or {}
    pos = current_pos or {}

    detail = VesselDetail(
        imo=imo_int,
        name=display_vessel_name(_first_text(
            vessel_row.name if vessel_row else None,
            particulars.get("vesselName"),
            pos.get("name"),
            "Unknown",
        ) or "Unknown", _first_text(
            vessel_row.flag if vessel_row else None,
            particulars.get("flag"),
            pos.get("flag"),
        )),
        mmsi=_first_text(
            vessel_row.mmsi if vessel_row else None,
            particulars.get("mmsiNumber"),
            pos.get("mmsi"),
        ),
        call_sign=_first_text(
            vessel_row.call_sign if vessel_row else None,
            particulars.get("callSign"),
            pos.get("call_sign"),
        ),
        flag=_first_text(
            vessel_row.flag if vessel_row else None,
            particulars.get("flag"),
            pos.get("flag"),
        ),
        flag_name=flag_name(_first_text(
            vessel_row.flag if vessel_row else None,
            particulars.get("flag"),
            pos.get("flag"),
        )),
        flag_emoji=flag_emoji(_first_text(
            vessel_row.flag if vessel_row else None,
            particulars.get("flag"),
            pos.get("flag"),
        )),
        vessel_type=_first_text(
            vessel_row.vessel_type if vessel_row else None,
            particulars.get("vesselType"),
            pos.get("vessel_type"),
        ),
        vessel_type_label=vessel_type_label(_first_text(
            vessel_row.vessel_type if vessel_row else None,
            particulars.get("vesselType"),
            pos.get("vessel_type"),
        )),
        year_built=_first_text(
            vessel_row.year_built if vessel_row else None,
            particulars.get("yearBuilt"),
            pos.get("year_built"),
        ),
        gross_tonnage=_first_float(
            vessel_row.gross_tonnage if vessel_row else None,
            particulars.get("grossTonnage"),
            pos.get("gross_tonnage"),
        ),
        deadweight=_first_float(
            vessel_row.deadweight if vessel_row else None,
            particulars.get("deadweight"),
            particulars.get("deadWeight"),
            pos.get("deadweight"),
        ),
        length_overall=_first_float(
            vessel_row.length_overall if vessel_row else None,
            particulars.get("vesselLength"),
            particulars.get("lengthOverall"),
            pos.get("length_overall"),
        ),
        beam=_first_float(
            vessel_row.beam if vessel_row else None,
            particulars.get("vesselBreadth"),
            particulars.get("beam"),
            pos.get("beam"),
        ),
        ism_manager=_first_text(vessel_row.ism_manager if vessel_row else None, particulars.get("ismManager")),
        registered_owner=_first_text(
            vessel_row.registered_owner if vessel_row else None,
            particulars.get("registeredOwnership"),
            particulars.get("registeredOwner"),
        ),
        operator=_first_text(
            vessel_row.operator if vessel_row else None,
            particulars.get("shipManager"),
            particulars.get("operator"),
        ),
        classification_society=_first_text(
            vessel_row.classification_society if vessel_row else None,
            particulars.get("classificationSociety"),
            particulars.get("classSociety"),
        ),
        is_shadow_fleet=vessel_row.is_shadow_fleet if vessel_row else False,
        current_sanctions_status=vessel_row.current_sanctions_status if vessel_row else "clean",
        last_observed_at=vessel_row.last_observed_at if vessel_row else None,
        last_enriched_at=vessel_row.last_enriched_at if vessel_row else None,
        position=VesselPosition(
            imo=current_pos["imo"],
            mmsi=current_pos.get("mmsi"),
            name=display_vessel_name(current_pos["name"], current_pos.get("flag")),
            flag=current_pos.get("flag"),
            flag_name=flag_name(current_pos.get("flag")),
            flag_emoji=flag_emoji(current_pos.get("flag")),
            vessel_type=current_pos.get("vessel_type"),
            vessel_type_label=vessel_type_label(current_pos.get("vessel_type")),
            year_built=current_pos.get("year_built"),
            gross_tonnage=current_pos.get("gross_tonnage"),
            lat=current_pos["lat"],
            lon=current_pos["lon"],
            speed_knots=current_pos.get("speed_knots"),
            course_degrees=current_pos.get("course_degrees"),
            heading_degrees=current_pos.get("heading_degrees"),
            inferred_status=current_pos["inferred_status"],
            recorded_at=current_pos["recorded_at"],
        ) if current_pos else None,
        movements=movements[:5] if movements else [],
    )
    l1_cache.set(cache_key, detail, ttl_seconds=60)
    return detail
