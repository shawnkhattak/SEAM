from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache as l1_cache
from app.clients.oceansx import OceansXClient, get_oceansx_client
from app.db import get_db
from app.limiter import limiter
from app.models import Company, RiskScore, Vessel, VesselCompanyRelationship, VesselParticularFact
from app.schemas import (
    CompanyRelationshipResponse,
    DueArrival,
    DueDeparture,
    ParticularFactResponse,
    VesselDetail,
    VesselPosition,
)
from app.services import vessels as vessel_svc
from app.services.enrichment_queue import enqueue
from app.utils.imo import luhn_valid
from app.utils.timezone import utc_now
from app.utils.vessel_labels import display_vessel_name, flag_emoji, flag_name, vessel_type_label

router = APIRouter(prefix="/vessels", tags=["vessels"])
log = logging.getLogger(__name__)


def _client() -> OceansXClient:
    return get_oceansx_client()


def _first_text(*values: Any) -> str | None:
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _first_float(*values: Any) -> float | None:
    for v in values:
        if v is None or v == "":
            continue
        try:
            return float(v)
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
    """Current position snapshot for all visible vessels."""
    cache_key = "api:vessels:positions"
    cached = l1_cache.get(cache_key)
    if cached is not None:
        return cached

    positions = await vessel_svc.get_live_positions(client)
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
    from datetime import timedelta
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
            is_shadow_fleet=v.is_shadow_fleet,
            current_sanctions_status=v.current_sanctions_status,
            first_observed_at=v.first_observed_at,
            last_observed_at=v.last_observed_at,
            last_enriched_at=v.last_enriched_at,
        )
        for v in vessels
    ]


@router.get("/{imo}/provenance", response_model=list[ParticularFactResponse])
@limiter.limit("30/minute")
async def get_vessel_provenance(
    request: Request,
    imo: Annotated[str, Path(pattern=r"^\d{7}$")],
    db: AsyncSession = Depends(get_db),
    include_closed: bool = Query(False),
) -> list[ParticularFactResponse]:
    """Return the full field-level provenance history for a vessel."""
    if not luhn_valid(imo):
        raise HTTPException(status_code=422, detail=f"Invalid IMO number: {imo}")

    query = select(VesselParticularFact).where(VesselParticularFact.imo == int(imo))
    if not include_closed:
        query = query.where(VesselParticularFact.valid_to.is_(None))
    query = query.order_by(VesselParticularFact.field_name, VesselParticularFact.valid_from.desc())

    rows = (await db.execute(query)).scalars().all()
    return [
        ParticularFactResponse(
            field_name=r.field_name,
            field_value=r.field_value,
            source=r.source,
            fetch_time=r.fetch_time,
            confidence=r.confidence,
            valid_from=r.valid_from,
            valid_to=r.valid_to,
        )
        for r in rows
    ]


@router.get("/{imo}/relationships", response_model=list[CompanyRelationshipResponse])
@limiter.limit("30/minute")
async def get_vessel_relationships(
    request: Request,
    imo: Annotated[str, Path(pattern=r"^\d{7}$")],
    db: AsyncSession = Depends(get_db),
    include_closed: bool = Query(False),
) -> list[CompanyRelationshipResponse]:
    """Return company relationships for a vessel."""
    if not luhn_valid(imo):
        raise HTTPException(status_code=422, detail=f"Invalid IMO number: {imo}")

    query = (
        select(VesselCompanyRelationship, Company.name)
        .join(Company, VesselCompanyRelationship.company_id == Company.id)
        .where(VesselCompanyRelationship.imo == int(imo))
    )
    if not include_closed:
        query = query.where(VesselCompanyRelationship.valid_to.is_(None))
    query = query.order_by(VesselCompanyRelationship.role, VesselCompanyRelationship.valid_from.desc())

    rows = (await db.execute(query)).all()
    return [
        CompanyRelationshipResponse(
            company_id=rel.company_id,
            company_name=name,
            role=rel.role,
            valid_from=rel.valid_from,
            valid_to=rel.valid_to,
            source=rel.source,
            confidence=rel.confidence,
        )
        for rel, name in rows
    ]


@router.get("/{imo}", response_model=VesselDetail)
@limiter.limit("30/minute")
async def get_vessel(
    request: Request,
    imo: Annotated[str, Path(pattern=r"^\d{7}$")],
    db: AsyncSession = Depends(get_db),
    client: OceansXClient = Depends(_client),
) -> VesselDetail:
    """Full vessel detail with provenance and company relationships.

    On first access, enqueues the vessel for particulars enrichment.
    If particulars are already cached, merges them inline.
    """
    if not luhn_valid(imo):
        raise HTTPException(status_code=422, detail=f"Invalid IMO number: {imo}")

    cache_key = f"api:vessel:{imo}"
    cached = l1_cache.get(cache_key)
    if cached is not None:
        return cached

    imo_int = int(imo)
    vessel_row = await db.scalar(select(Vessel).where(Vessel.imo == imo_int))

    # Fetch particulars from API (also triggers enrichment write)
    particulars = await client.vessel_particulars_by_imo(imo)
    movements = await client.vessel_movements_by_imo(imo)

    if particulars:
        from app.services.vessel_master import update_from_particulars
        await update_from_particulars(db, imo_int, particulars)
        await db.commit()
        if vessel_row:
            await db.refresh(vessel_row)
    else:
        # No particulars yet — enqueue for background enrichment
        await enqueue(db, imo_int, priority=10)
        await db.commit()

    # Current position from live snapshot
    positions = await vessel_svc.get_live_positions(client)
    current_pos = next((p for p in positions if p["imo"] == imo_int), None)

    particulars = particulars or {}
    pos = current_pos or {}

    # Load open provenance facts
    fact_rows = (await db.execute(
        select(VesselParticularFact)
        .where(VesselParticularFact.imo == imo_int, VesselParticularFact.valid_to.is_(None))
        .order_by(VesselParticularFact.field_name)
    )).scalars().all()
    prov = [
        ParticularFactResponse(
            field_name=r.field_name,
            field_value=r.field_value,
            source=r.source,
            fetch_time=r.fetch_time,
            confidence=r.confidence,
            valid_from=r.valid_from,
            valid_to=r.valid_to,
        )
        for r in fact_rows
    ]

    # Load open company relationships
    rel_rows = (await db.execute(
        select(VesselCompanyRelationship, Company.name)
        .join(Company, VesselCompanyRelationship.company_id == Company.id)
        .where(VesselCompanyRelationship.imo == imo_int, VesselCompanyRelationship.valid_to.is_(None))
        .order_by(VesselCompanyRelationship.role)
    )).all()
    rels = [
        CompanyRelationshipResponse(
            company_id=rel.company_id,
            company_name=name,
            role=rel.role,
            valid_from=rel.valid_from,
            valid_to=rel.valid_to,
            source=rel.source,
            confidence=rel.confidence,
        )
        for rel, name in rel_rows
    ]

    v = vessel_row
    flag = _first_text(v.flag if v else None, particulars.get("flag"), pos.get("flag"))
    name = display_vessel_name(
        _first_text(v.name if v else None, particulars.get("vesselName"), pos.get("name"), "Unknown") or "Unknown",
        flag,
    )

    detail = VesselDetail(
        imo=imo_int,
        name=name,
        mmsi=_first_text(v.mmsi if v else None, particulars.get("mmsiNumber"), pos.get("mmsi")),
        call_sign=_first_text(v.call_sign if v else None, particulars.get("callSign"), pos.get("call_sign")),
        flag=flag,
        flag_name=flag_name(flag),
        flag_emoji=flag_emoji(flag),
        vessel_type=_first_text(v.vessel_type if v else None, particulars.get("vesselType"), pos.get("vessel_type")),
        vessel_type_label=vessel_type_label(_first_text(v.vessel_type if v else None, particulars.get("vesselType"))),
        year_built=_first_text(v.year_built if v else None, particulars.get("yearBuilt"), pos.get("year_built")),
        gross_tonnage=_first_float(v.gross_tonnage if v else None, particulars.get("grossTonnage")),
        deadweight=_first_float(v.deadweight if v else None, particulars.get("deadweight"), particulars.get("deadWeight")),
        length_overall=_first_float(v.length_overall if v else None, particulars.get("vesselLength"), particulars.get("lengthOverall")),
        beam=_first_float(v.beam if v else None, particulars.get("vesselBreadth"), particulars.get("beam")),
        is_shadow_fleet=v.is_shadow_fleet if v else False,
        current_sanctions_status=v.current_sanctions_status if v else "clean",
        first_observed_at=v.first_observed_at if v else None,
        last_observed_at=v.last_observed_at if v else None,
        last_enriched_at=v.last_enriched_at if v else None,
        movements=movements[:5] if movements else [],
        particulars=prov,
        relationships=rels,
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
    )
    l1_cache.set(cache_key, detail, ttl_seconds=60)
    return detail
