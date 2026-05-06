"""OpenSanctions FtM ingestion and projection service.

Two-step design (advisor constraint):
  1. Raw insert: every entity stored in opensanctions_entity_raw independent of projection.
  2. Projection: parse raw payload into Company / VesselTopic rows; can be re-run.

Only 'Vessel' and 'Company'/'Organization' schemas are projected. Others stored raw only.

SEAM note: Organization/OrganizationAlias/OrganizationTopic from legacy → Company/CompanyAlias/
CompanyIdentifier. OS entity IDs and topics stored as CompanyIdentifier rows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Company,
    CompanyAlias,
    CompanyIdentifier,
    OpenSanctionsEntityRaw,
    VesselTopic,
)
from app.utils.timezone import utc_now

logger = logging.getLogger(__name__)

_VESSEL_SCHEMAS = {"Vessel", "Ship"}
_ORG_SCHEMAS = {"Company", "Organization", "LegalEntity"}


def _extract_first(props: dict[str, Any], key: str) -> str | None:
    values = props.get(key, [])
    return values[0].strip() if values else None


def _extract_all(props: dict[str, Any], key: str) -> list[str]:
    return [v.strip() for v in props.get(key, []) if v.strip()]


def _parse_file_date(entity: dict[str, Any]) -> datetime | None:
    raw = entity.get("last_seen") or entity.get("last_change")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


async def _upsert_raw(
    session: AsyncSession,
    entity: dict[str, Any],
    file_date: datetime | None,
) -> int:
    now = utc_now()
    os_entity_id = entity.get("id", "")
    schema_type = entity.get("schema", "Unknown")
    dataset = (entity.get("datasets") or [""])[0]

    stmt = (
        pg_insert(OpenSanctionsEntityRaw)
        .values(
            os_entity_id=os_entity_id,
            schema_type=schema_type,
            payload=entity,
            dataset=dataset,
            ingested_at=now,
            file_date=file_date,
        )
        .on_conflict_do_update(
            constraint="uq_os_raw_entity_ingested",
            set_={"payload": entity, "schema_type": schema_type},
        )
        .returning(OpenSanctionsEntityRaw.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def _project_company(
    session: AsyncSession,
    entity: dict[str, Any],
) -> Company | None:
    """Upsert a Company row from an org-type OS entity.

    OS entity ID is stored as CompanyIdentifier(identifier_type='os_entity_id').
    Aliases stored as CompanyAlias. Topics stored as CompanyIdentifier(identifier_type='topic').
    """
    os_entity_id = entity.get("id", "")
    if not os_entity_id:
        return None
    props = entity.get("properties", {})
    name = _extract_first(props, "name")
    if not name:
        return None

    now = utc_now()

    # Look up existing company by OS entity ID
    existing_id_row = await session.execute(
        select(CompanyIdentifier.company_id).where(
            CompanyIdentifier.identifier_type == "os_entity_id",
            CompanyIdentifier.identifier_value == os_entity_id,
        )
    )
    company_id = existing_id_row.scalar_one_or_none()

    if company_id is None:
        company = Company(
            name=name,
            country=_extract_first(props, "country"),
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(company)
        await session.flush()
        company_id = company.id

        # Store OS entity ID
        session.add(
            CompanyIdentifier(
                company_id=company_id,
                identifier_type="os_entity_id",
                identifier_value=os_entity_id,
            )
        )
        await session.flush()
    else:
        # Update last_seen
        company = await session.get(Company, company_id)
        if company:
            company.last_seen_at = now

    # Upsert aliases (all names beyond the first)
    all_names = _extract_all(props, "name")
    for alias in all_names[1:]:
        await session.execute(
            pg_insert(CompanyAlias)
            .values(company_id=company_id, alias=alias)
            .on_conflict_do_nothing()
        )

    # Upsert topics as CompanyIdentifier rows
    topics = _extract_all(props, "topics")
    for topic in topics:
        await session.execute(
            pg_insert(CompanyIdentifier)
            .values(company_id=company_id, identifier_type="topic", identifier_value=topic)
            .on_conflict_do_nothing()
        )

    # Store registration number if present
    reg_num = _extract_first(props, "registrationNumber")
    if reg_num:
        await session.execute(
            pg_insert(CompanyIdentifier)
            .values(company_id=company_id, identifier_type="registration_number", identifier_value=reg_num)
            .on_conflict_do_nothing()
        )

    result = await session.execute(select(Company).where(Company.id == company_id))
    return result.scalar_one_or_none()


async def _project_vessel_topics(
    session: AsyncSession,
    entity: dict[str, Any],
) -> int:
    """Write VesselTopic rows for a vessel entity. Returns count written."""
    props = entity.get("properties", {})
    imo_strings = _extract_all(props, "imoNumber")
    if not imo_strings:
        return 0

    topics = _extract_all(props, "topics")
    if not topics:
        return 0

    os_entity_id = entity.get("id", "")
    now = utc_now()
    written = 0
    for imo_raw in imo_strings:
        try:
            imo = int(imo_raw.strip())
        except ValueError:
            continue
        for topic in topics:
            existing = await session.execute(
                select(VesselTopic.id).where(
                    VesselTopic.imo == imo,
                    VesselTopic.topic == topic,
                    VesselTopic.os_entity_id == os_entity_id,
                    VesselTopic.valid_to.is_(None),
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(
                VesselTopic(
                    imo=imo,
                    topic=topic,
                    os_entity_id=os_entity_id,
                    valid_from=now,
                    valid_to=None,
                )
            )
            written += 1

    await session.flush()
    return written


async def ingest_entity(
    session: AsyncSession,
    entity: dict[str, Any],
) -> dict[str, Any]:
    """Ingest a single FtM entity: raw insert then projection."""
    os_entity_id = entity.get("id", "")
    schema_type = entity.get("schema", "Unknown")
    file_date = _parse_file_date(entity)

    raw_id = await _upsert_raw(session, entity, file_date)

    projected = False
    if schema_type in _VESSEL_SCHEMAS:
        count = await _project_vessel_topics(session, entity)
        projected = count > 0
    elif schema_type in _ORG_SCHEMAS:
        company = await _project_company(session, entity)
        projected = company is not None

    return {
        "os_entity_id": os_entity_id,
        "schema_type": schema_type,
        "raw_id": raw_id,
        "projected": projected,
    }


async def ingest_batch(
    session: AsyncSession,
    entities: list[dict[str, Any]],
) -> dict[str, int]:
    """Ingest a list of FtM entities. Returns summary counts."""
    total = len(entities)
    vessels = 0
    orgs = 0
    other = 0
    errors = 0

    for entity in entities:
        schema_type = entity.get("schema", "Unknown")
        try:
            await ingest_entity(session, entity)
            if schema_type in _VESSEL_SCHEMAS:
                vessels += 1
            elif schema_type in _ORG_SCHEMAS:
                orgs += 1
            else:
                other += 1
        except Exception as exc:
            errors += 1
            logger.warning(
                "opensanctions: ingest error entity=%s schema=%s: %s",
                entity.get("id", "?"),
                schema_type,
                exc,
            )

    await session.flush()
    logger.info(
        "opensanctions: ingested %d/%d entities (vessels=%d companies=%d other=%d errors=%d)",
        total - errors, total, vessels, orgs, other, errors,
    )
    return {"total": total, "vessels": vessels, "orgs": orgs, "other": other, "errors": errors}
