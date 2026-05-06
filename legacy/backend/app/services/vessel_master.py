from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Vessel,
    VesselClassHistory,
    VesselFlagHistory,
    VesselNameHistory,
    VesselOperatorHistory,
    VesselOwnerHistory,
)
from app.utils.timezone import utc_now

logger = logging.getLogger(__name__)


def _text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text_value = str(value).strip()
        if text_value:
            return text_value
    return None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def upsert_vessel(session: AsyncSession, pos: dict[str, Any]) -> None:
    """Insert or update the vessel master row from a normalized position dict.
    Records SCD2 name and flag changes when they differ from the current record.
    """
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


async def record_scd2_changes(
    session: AsyncSession, imo: int, new_name: str, new_flag: str | None
) -> None:
    """Open a new SCD2 record when the vessel's name or flag changes."""
    now = utc_now()

    # Check current open name record
    result = await session.execute(
        select(VesselNameHistory)
        .where(VesselNameHistory.imo == imo, VesselNameHistory.valid_to.is_(None))
        .order_by(VesselNameHistory.valid_from.desc())
        .limit(1)
    )
    current_name = result.scalar_one_or_none()
    if current_name is None:
        session.add(VesselNameHistory(imo=imo, name=new_name, valid_from=now, source="mpa_poll"))
    elif current_name.name != new_name:
        current_name.valid_to = now
        session.add(VesselNameHistory(imo=imo, name=new_name, valid_from=now, source="mpa_poll"))
        logger.info("vessel %d name changed: %r → %r", imo, current_name.name, new_name)

    if new_flag:
        result = await session.execute(
            select(VesselFlagHistory)
            .where(VesselFlagHistory.imo == imo, VesselFlagHistory.valid_to.is_(None))
            .order_by(VesselFlagHistory.valid_from.desc())
            .limit(1)
        )
        current_flag = result.scalar_one_or_none()
        if current_flag is None:
            session.add(VesselFlagHistory(imo=imo, flag=new_flag, valid_from=now, source="mpa_poll"))
        elif current_flag.flag != new_flag:
            current_flag.valid_to = now
            session.add(VesselFlagHistory(imo=imo, flag=new_flag, valid_from=now, source="mpa_poll"))
            logger.info("vessel %d flag changed: %r → %r", imo, current_flag.flag, new_flag)


async def update_from_particulars(
    session: AsyncSession, imo: int, particulars: dict[str, Any]
) -> None:
    """Apply enrichment data from the particulars API to the vessel master row."""
    now = utc_now()
    owner = _text(particulars.get("registeredOwnership"), particulars.get("registeredOwner"))
    operator = _text(particulars.get("shipManager"), particulars.get("operator"))
    classification_society = _text(particulars.get("classificationSociety"), particulars.get("classSociety"))
    values = {
        "last_enriched_at": now,
        "mmsi": _text(particulars.get("mmsiNumber")),
        "call_sign": _text(particulars.get("callSign")),
        "flag": _text(particulars.get("flag")),
        "vessel_type": _text(particulars.get("vesselType")),
        "year_built": _text(particulars.get("yearBuilt")),
        "gross_tonnage": _float(particulars.get("grossTonnage")),
        "deadweight": _float(particulars.get("deadweight") or particulars.get("deadWeight")),
        "length_overall": _float(particulars.get("vesselLength") or particulars.get("lengthOverall")),
        "beam": _float(particulars.get("vesselBreadth") or particulars.get("beam")),
        "draft_max": _float(particulars.get("vesselDepth")),
        "ism_manager": _text(particulars.get("ismManager")),
        "registered_owner": owner,
        "operator": operator,
        "classification_society": classification_society,
    }
    values = {key: value for key, value in values.items() if value is not None or key == "last_enriched_at"}

    await session.execute(
        update(Vessel)
        .where(Vessel.imo == imo)
        .values(**values)
    )

    # SCD2 owner and operator (populated from particulars, not positions)
    if owner:
        result = await session.execute(
            select(VesselOwnerHistory)
            .where(VesselOwnerHistory.imo == imo, VesselOwnerHistory.valid_to.is_(None))
            .limit(1)
        )
        current = result.scalar_one_or_none()
        if current is None:
            session.add(VesselOwnerHistory(imo=imo, owner=owner, valid_from=now, source="mpa_particulars"))
        elif current.owner != owner:
            current.valid_to = now
            session.add(VesselOwnerHistory(imo=imo, owner=owner, valid_from=now, source="mpa_particulars"))

    if operator:
        result = await session.execute(
            select(VesselOperatorHistory)
            .where(VesselOperatorHistory.imo == imo, VesselOperatorHistory.valid_to.is_(None))
            .limit(1)
        )
        current = result.scalar_one_or_none()
        if current is None:
            session.add(VesselOperatorHistory(imo=imo, operator=operator, valid_from=now, source="mpa_particulars"))
        elif current.operator != operator:
            current.valid_to = now
            session.add(VesselOperatorHistory(imo=imo, operator=operator, valid_from=now, source="mpa_particulars"))

    if classification_society:
        result = await session.execute(
            select(VesselClassHistory)
            .where(VesselClassHistory.imo == imo, VesselClassHistory.valid_to.is_(None))
            .limit(1)
        )
        current = result.scalar_one_or_none()
        if current is None:
            session.add(VesselClassHistory(
                imo=imo,
                classification_society=classification_society,
                valid_from=now,
                source="mpa_particulars",
            ))
        elif current.classification_society != classification_society:
            current.valid_to = now
            session.add(VesselClassHistory(
                imo=imo,
                classification_society=classification_society,
                valid_from=now,
                source="mpa_particulars",
            ))
