"""Shadow fleet flag derivation.

Reads vessel_topic WHERE topic = 'mare.shadow' AND valid_to IS NULL,
then sets vessel.is_shadow_fleet accordingly (True/False).
Run nightly after opensanctions ingest.
"""

from __future__ import annotations

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vessel, VesselTopic

logger = logging.getLogger(__name__)


async def refresh_shadow_fleet_flags(session: AsyncSession) -> dict[str, int]:
    """Sync vessel.is_shadow_fleet from vessel_topic.

    Any vessel with an active 'mare.shadow' topic tag → is_shadow_fleet=True.
    All others → is_shadow_fleet=False.
    Returns counts of vessels set True and False.
    """
    # IMOs currently tagged as shadow fleet
    result = await session.execute(
        select(VesselTopic.imo).where(
            VesselTopic.topic == "mare.shadow",
            VesselTopic.valid_to.is_(None),
        )
    )
    shadow_imos: set[int] = {row[0] for row in result.all()}

    set_true = 0
    set_false = 0

    if shadow_imos:
        res = await session.execute(
            update(Vessel)
            .where(Vessel.imo.in_(shadow_imos))
            .values(is_shadow_fleet=True)
        )
        set_true = res.rowcount

    # Clear flag for vessels no longer tagged
    res = await session.execute(
        update(Vessel)
        .where(Vessel.imo.not_in(shadow_imos) if shadow_imos else True)
        .where(Vessel.is_shadow_fleet.is_(True))
        .values(is_shadow_fleet=False)
    )
    set_false = res.rowcount

    await session.flush()
    logger.info(
        "shadow_fleet: set is_shadow_fleet=True for %d vessels, False for %d",
        set_true, set_false,
    )
    return {"set_true": set_true, "set_false": set_false}
