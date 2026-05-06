from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, CompanyAlias, NewsEntityMention, Port, PortAlias, Vessel

logger = logging.getLogger(__name__)

_MIN_TERM_LEN = 4


def _build_pattern(term: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)


async def _load_dictionary(session: AsyncSession) -> list[tuple[re.Pattern[str], str, int]]:
    """Return list of (pattern, entity_type, entity_ref_id) for all known vessels, ports, companies."""
    entries: list[tuple[re.Pattern[str], str, int]] = []

    result = await session.execute(select(Vessel.imo, Vessel.name))
    for imo, name in result:
        if len(name) >= _MIN_TERM_LEN:
            entries.append((_build_pattern(name), "vessel", imo))

    port_result = await session.execute(select(Port.id, Port.name))
    for port_id, name in port_result:
        if len(name) >= _MIN_TERM_LEN:
            entries.append((_build_pattern(name), "port", port_id))

    alias_result = await session.execute(select(PortAlias.port_id, PortAlias.alias))
    for port_id, alias in alias_result:
        if len(alias) >= _MIN_TERM_LEN:
            entries.append((_build_pattern(alias), "port", port_id))

    company_result = await session.execute(select(Company.id, Company.name))
    for company_id, name in company_result:
        if len(name) >= _MIN_TERM_LEN:
            entries.append((_build_pattern(name), "company", company_id))

    company_alias_result = await session.execute(select(CompanyAlias.company_id, CompanyAlias.alias))
    for company_id, alias in company_alias_result:
        if len(alias) >= _MIN_TERM_LEN:
            entries.append((_build_pattern(alias), "company", company_id))

    return entries


def _search_text(text: str, dictionary: list[tuple[re.Pattern[str], str, int]]) -> list[dict[str, Any]]:
    """Return deduplicated mention dicts for all dictionary terms found in text."""
    seen: set[tuple[str, int]] = set()
    mentions: list[dict[str, Any]] = []

    for pattern, entity_type, entity_ref_id in dictionary:
        match = pattern.search(text)
        if match:
            key = (entity_type, entity_ref_id)
            if key not in seen:
                seen.add(key)
                mentions.append({
                    "entity_type": entity_type,
                    "entity_ref_id": entity_ref_id,
                    "matched_text": match.group(0),
                    "confidence": 1.0,
                })

    return mentions


async def extract_entities_for_item(
    session: AsyncSession,
    news_id: int,
    title: str,
    body_text: str | None,
) -> int:
    """Run dictionary extraction against title + body, write NewsEntityMention rows.

    Returns the number of mentions written.
    """
    combined = title + " " + (body_text or "")
    dictionary = await _load_dictionary(session)
    mentions = _search_text(combined, dictionary)

    for m in mentions:
        session.add(NewsEntityMention(
            news_id=news_id,
            entity_type=m["entity_type"],
            entity_ref_id=m["entity_ref_id"],
            matched_text=m["matched_text"],
            confidence=m["confidence"],
        ))

    if mentions:
        logger.debug("entity_extraction: news_id=%d found %d mentions", news_id, len(mentions))

    return len(mentions)
