"""vessel_master — upserts vessel rows and tracks field-level provenance.

Key changes from legacy:
  - Scalar fields → vessel_particular_fact (closes old open row, inserts new)
  - Company-type fields → company + vessel_company_relationship (SCD2 via role)
  - Null distinction: explicit API null writes a null fact; omitted field = skip
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Company,
    CompanyAlias,
    VesselCompanyRelationship,
    Vessel,
    VesselParticularFact,
)
from app.utils.timezone import utc_now

log = logging.getLogger(__name__)

# Scalar particulars that use vessel_particular_fact
_SCALAR_FIELDS = {
    "mmsi": "mmsiNumber",
    "call_sign": "callSign",
    "flag": "flag",
    "vessel_type": "vesselType",
    "year_built": "yearBuilt",
    "gross_tonnage": "grossTonnage",
    "deadweight": "deadweight",
    "length_overall": "vesselLength",
    "beam": "vesselBreadth",
    "draft_max": "vesselDepth",
    "net_tonnage": "netTonnage",
}

# Company-type particulars that use vessel_company_relationship
_COMPANY_ROLES = {
    "registered_owner": ["registeredOwnership", "registeredOwner"],
    "operator": ["shipManager", "operator"],
    "ism_manager": ["ismManager"],
    "classification_society": ["classificationSociety", "classSociety"],
}


def _text(*values: Any) -> str | None:
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _float_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return None


async def upsert_vessel(session: AsyncSession, pos: dict[str, Any]) -> None:
    """Insert or update vessel master row from a normalized position dict."""
    imo = pos["imo"]
    now = utc_now()

    stmt = insert(Vessel).values(
        imo=imo,
        mmsi=pos.get("mmsi"),
        name=pos["name"],
        call_sign=pos.get("call_sign"),
        flag=pos.get("flag"),
        vessel_type=pos.get("vessel_type"),
        year_built=pos.get("year_built"),
        gross_tonnage=pos.get("gross_tonnage"),
        deadweight=pos.get("deadweight"),
        length_overall=pos.get("length_overall"),
        beam=pos.get("beam"),
        is_shadow_fleet=False,
        current_sanctions_status="clean",
        first_observed_at=now,
        last_observed_at=now,
    ).on_conflict_do_update(
        index_elements=["imo"],
        set_={
            "mmsi": pos.get("mmsi"),
            "name": pos["name"],
            "flag": pos.get("flag"),
            "vessel_type": pos.get("vessel_type"),
            "year_built": pos.get("year_built"),
            "gross_tonnage": pos.get("gross_tonnage"),
            "deadweight": pos.get("deadweight"),
            "length_overall": pos.get("length_overall"),
            "beam": pos.get("beam"),
            "last_observed_at": now,
        },
    )
    await session.execute(stmt)


async def _write_scalar_fact(
    session: AsyncSession,
    imo: int,
    field_name: str,
    field_value: str | None,
    source: str,
    now: Any,
) -> None:
    """Close any open fact for (imo, field_name) and insert a new one if value changed."""
    open_row = await session.scalar(
        select(VesselParticularFact)
        .where(
            VesselParticularFact.imo == imo,
            VesselParticularFact.field_name == field_name,
            VesselParticularFact.valid_to.is_(None),
        )
        .limit(1)
    )

    if open_row is not None and open_row.field_value == field_value:
        return  # nothing changed

    if open_row is not None:
        open_row.valid_to = now

    session.add(
        VesselParticularFact(
            imo=imo,
            field_name=field_name,
            field_value=field_value,
            source=source,
            fetch_time=now,
            confidence=1.0,
            valid_from=now,
            valid_to=None,
        )
    )


async def _resolve_or_create_company(
    session: AsyncSession, name: str, now: Any
) -> int:
    """Return company.id for the given name, creating it if needed."""
    existing = await session.scalar(
        select(Company).where(Company.name == name).limit(1)
    )
    if existing:
        existing.last_seen_at = now
        return existing.id

    # Try alias match
    alias_row = await session.scalar(
        select(CompanyAlias).where(CompanyAlias.alias == name).limit(1)
    )
    if alias_row:
        company = await session.get(Company, alias_row.company_id)
        if company:
            company.last_seen_at = now
            return company.id

    # Create new company
    company = Company(name=name, first_seen_at=now, last_seen_at=now)
    session.add(company)
    await session.flush()
    return company.id


async def _write_company_relationship(
    session: AsyncSession,
    imo: int,
    role: str,
    company_name: str,
    source: str,
    now: Any,
) -> None:
    """Close the open relationship for this role and open a new one if company changed."""
    company_id = await _resolve_or_create_company(session, company_name, now)

    open_rel = await session.scalar(
        select(VesselCompanyRelationship)
        .where(
            VesselCompanyRelationship.imo == imo,
            VesselCompanyRelationship.role == role,
            VesselCompanyRelationship.valid_to.is_(None),
        )
        .limit(1)
    )

    if open_rel is not None and open_rel.company_id == company_id:
        return  # same company, nothing to do

    if open_rel is not None:
        open_rel.valid_to = now
        log.info("vessel %d role %s: company changed → %r", imo, role, company_name)

    session.add(
        VesselCompanyRelationship(
            imo=imo,
            company_id=company_id,
            role=role,
            valid_from=now,
            valid_to=None,
            source=source,
            confidence=1.0,
        )
    )


async def update_from_particulars(
    session: AsyncSession, imo: int, particulars: dict[str, Any]
) -> None:
    """Apply enrichment data from particulars API.

    For scalar fields: writes vessel_particular_fact rows.
    For company fields: resolves/creates company, writes vessel_company_relationship.
    Explicit API null → writes null fact. Omitted field → skip (no row written).
    """
    now = utc_now()
    source = "mpa_particulars"

    # Update vessel master last_enriched_at
    await session.execute(
        update(Vessel).where(Vessel.imo == imo).values(last_enriched_at=now)
    )

    # Scalar fields
    for field_name, api_key in _SCALAR_FIELDS.items():
        if api_key not in particulars:
            continue  # field omitted — skip
        raw_value = particulars[api_key]
        if field_name in ("gross_tonnage", "deadweight", "length_overall", "beam", "draft_max", "net_tonnage"):
            value = _float_str(raw_value)
        else:
            value = _text(raw_value) if raw_value is not None else None

        await _write_scalar_fact(session, imo, field_name, value, source, now)

    # Company-type fields
    for role, api_keys in _COMPANY_ROLES.items():
        name = None
        for k in api_keys:
            if k in particulars:
                name = _text(particulars[k])
                break
        if name is None:
            continue  # omitted
        await _write_company_relationship(session, imo, role, name, source, now)
