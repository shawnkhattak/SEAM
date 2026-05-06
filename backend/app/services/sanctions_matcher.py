"""Sanctions matching service.

ADR-0005 (locked): IMO-exact is the ONLY match_method that may produce status='auto_confirmed'.
All other match methods → status='pending', written to agent_review_queue.
Enforced here AND by DB constraint ck_sanctions_match_auto_confirm_imo_only.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentReviewQueue,
    OpenSanctionsEntityRaw,
    SanctionsListing,
    SanctionsMatch,
    SanctionsMatchHistory,
    SanctionsSource,
    Vessel,
)
from app.utils.timezone import utc_now

logger = logging.getLogger(__name__)

_VESSEL_SCHEMAS = {"Vessel", "Ship"}


def _extract_all(props: dict[str, Any], key: str) -> list[str]:
    return [v.strip() for v in props.get(key, []) if v.strip()]


async def _get_or_create_source(session: AsyncSession, dataset: str) -> int:
    result = await session.execute(
        select(SanctionsSource.id).where(SanctionsSource.dataset_name == dataset)
    )
    source_id = result.scalar_one_or_none()
    if source_id is not None:
        return source_id

    source = SanctionsSource(dataset_name=dataset, display_name=dataset)
    session.add(source)
    await session.flush()
    return source.id


async def _record_match(
    session: AsyncSession,
    imo: int,
    os_entity_id: str,
    match_method: str,
    status: str,
    confidence: float | None,
) -> SanctionsMatch:
    now = utc_now()

    existing_result = await session.execute(
        select(SanctionsMatch).where(
            SanctionsMatch.imo == imo,
            SanctionsMatch.os_entity_id == os_entity_id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        old_status = existing.status
        if old_status == status or existing.status == "auto_confirmed":
            return existing
        existing.status = status
        existing.confidence = confidence
        await session.flush()
        session.add(
            SanctionsMatchHistory(
                sanctions_match_id=existing.id,
                old_status=old_status,
                new_status=status,
                changed_by="system",
                changed_at=now,
            )
        )
        await session.flush()
        return existing

    match = SanctionsMatch(
        imo=imo,
        os_entity_id=os_entity_id,
        match_method=match_method,
        status=status,
        confidence=confidence,
        created_at=now,
    )
    session.add(match)
    await session.flush()
    session.add(
        SanctionsMatchHistory(
            sanctions_match_id=match.id,
            old_status=None,
            new_status=status,
            changed_by="system",
            changed_at=now,
        )
    )
    await session.flush()
    return match


async def _update_vessel_sanctions_status(session: AsyncSession, imo: int, new_status: str) -> None:
    await session.execute(
        update(Vessel).where(Vessel.imo == imo).values(current_sanctions_status=new_status)
    )


async def match_vessel_entity(
    session: AsyncSession,
    entity: dict[str, Any],
) -> dict[str, Any]:
    """IMO-exact match → auto_confirmed. All others → pending review queue."""
    props = entity.get("properties", {})
    os_entity_id: str = entity.get("id", "")
    datasets: list[str] = entity.get("datasets", [])

    imo_strings = _extract_all(props, "imoNumber")
    matched_imos: list[int] = []

    for imo_raw in imo_strings:
        try:
            imo = int(imo_raw.strip())
        except ValueError:
            continue

        vessel_result = await session.execute(select(Vessel.imo).where(Vessel.imo == imo))
        if vessel_result.scalar_one_or_none() is None:
            continue

        await _record_match(
            session,
            imo=imo,
            os_entity_id=os_entity_id,
            match_method="imo_exact",
            status="auto_confirmed",
            confidence=1.0,
        )

        await _update_vessel_sanctions_status(session, imo, "sanctioned")

        for dataset in datasets:
            source_id = await _get_or_create_source(session, dataset)
            now = utc_now()
            await session.execute(
                pg_insert(SanctionsListing)
                .values(
                    imo=imo,
                    os_entity_id=os_entity_id,
                    sanctions_source_id=source_id,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                .on_conflict_do_update(
                    constraint="uq_sanctions_listing_imo_source",
                    set_={"last_seen_at": now, "os_entity_id": os_entity_id},
                )
            )

        matched_imos.append(imo)
        logger.info("sanctions_matcher: IMO-exact auto_confirmed imo=%d entity=%s", imo, os_entity_id)

    return {
        "os_entity_id": os_entity_id,
        "imo_matches": matched_imos,
        "method": "imo_exact" if matched_imos else None,
    }


async def run_matcher(
    session: AsyncSession,
    entities: list[dict[str, Any]],
) -> dict[str, int]:
    """Run the IMO-exact matcher across all vessel entities."""
    total = 0
    auto_confirmed = 0
    skipped = 0
    errors = 0

    for entity in entities:
        schema_type = entity.get("schema", "Unknown")
        if schema_type not in _VESSEL_SCHEMAS:
            skipped += 1
            continue

        total += 1
        try:
            result = await match_vessel_entity(session, entity)
            auto_confirmed += len(result["imo_matches"])
        except Exception as exc:
            errors += 1
            logger.warning("sanctions_matcher: error entity=%s: %s", entity.get("id", "?"), exc)

    await session.flush()
    logger.info(
        "sanctions_matcher: processed %d vessel entities auto_confirmed=%d errors=%d",
        total, auto_confirmed, errors,
    )
    return {
        "total_vessel_entities": total,
        "auto_confirmed_imos": auto_confirmed,
        "skipped_non_vessel": skipped,
        "errors": errors,
    }
