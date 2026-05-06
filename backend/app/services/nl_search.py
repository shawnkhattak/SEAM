"""Natural-language vessel search service.

NL query → Haiku → SearchFilterSpec → SQL → list[Vessel].
CTE for sanctioned-org traversal uses vessel_company_relationship (SEAM model).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.anthropic_client import call_haiku
from app.models import RiskScore, Vessel
from app.schemas import SearchFilterSpec

logger = logging.getLogger(__name__)

_NL_SYSTEM_PROMPT = """\
Translate the user's maritime vessel search query into a structured JSON filter.
Return ONLY valid JSON — no explanation, no markdown, no code fences.

Schema (all fields required, use null when not specified):
{
  "flag_codes": ["XX"] or null,
  "vessel_types": ["tanker"] or null,
  "sanctioned_only": true or false,
  "shadow_fleet_only": true or false,
  "min_risk_score": 0-100 or null,
  "max_risk_score": 0-100 or null,
  "connected_to_sanctioned_org": true or false,
  "new_arrivals_only": true or false,
  "min_age_years": number or null,
  "max_age_years": number or null,
  "min_gross_tonnage": number or null,
  "max_gross_tonnage": number or null
}

flag_codes must be ISO 3166-1 alpha-2 (e.g. "IR", "PA", "SG").
vessel_types should be lowercase keywords (e.g. "tanker", "bulk carrier", "container").
"high risk" means min_risk_score >= 50; "critical risk" means min_risk_score >= 75.
"new arrivals" means new_arrivals_only = true.
"""


def spec_cache_key(spec: SearchFilterSpec) -> str:
    canonical = json.dumps(spec.model_dump(), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _sanctioned_company_imos_cte() -> text:
    """
    CTE: vessel IMOs connected to companies with sanctions topics.
    Uses vessel_company_relationship + company_identifier (SEAM model).
    Depth capped at 3 hops to bound query cost.
    """
    return text(
        """
        WITH RECURSIVE connected_to_sanction(imo, visited_imos) AS (
            SELECT DISTINCT vcr.imo, ARRAY[vcr.imo]
            FROM vessel_company_relationship vcr
            JOIN company_identifier ci ON ci.company_id = vcr.company_id
            WHERE ci.identifier_type = 'topic'
              AND ci.identifier_value LIKE 'sanction%%'
              AND vcr.valid_to IS NULL

            UNION ALL

            SELECT DISTINCT vcr2.imo,
                            c.visited_imos || vcr2.imo
            FROM connected_to_sanction c
            JOIN vessel_company_relationship vcr  ON vcr.imo  = c.imo
                                                 AND vcr.valid_to IS NULL
            JOIN vessel_company_relationship vcr2 ON vcr2.company_id = vcr.company_id
                                                 AND vcr2.valid_to IS NULL
                                                 AND vcr2.imo != ALL(c.visited_imos)
            WHERE array_length(c.visited_imos, 1) < 3
        )
        SELECT DISTINCT imo FROM connected_to_sanction
        """
    )


def spec_to_query(spec: SearchFilterSpec) -> Select:
    """Translate SearchFilterSpec into a SQLAlchemy SELECT on vessel."""
    q: Select = select(Vessel)

    if spec.flag_codes:
        upper = [c.upper() for c in spec.flag_codes]
        q = q.where(Vessel.flag.in_(upper))

    if spec.vessel_types:
        conditions = [
            func.lower(Vessel.vessel_type).contains(t.lower()) for t in spec.vessel_types
        ]
        q = q.where(or_(*conditions))

    if spec.sanctioned_only:
        q = q.where(Vessel.current_sanctions_status != "clean")

    if spec.shadow_fleet_only:
        q = q.where(Vessel.is_shadow_fleet.is_(True))

    if spec.min_risk_score is not None or spec.max_risk_score is not None:
        latest_risk = (
            select(RiskScore.vessel_imo, RiskScore.composite)
            .distinct(RiskScore.vessel_imo)
            .order_by(RiskScore.vessel_imo, RiskScore.scored_at.desc())
            .subquery("latest_risk")
        )
        q = q.join(latest_risk, Vessel.imo == latest_risk.c.vessel_imo)
        if spec.min_risk_score is not None:
            q = q.where(latest_risk.c.composite >= spec.min_risk_score)
        if spec.max_risk_score is not None:
            q = q.where(latest_risk.c.composite <= spec.max_risk_score)

    if spec.new_arrivals_only:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        q = q.where(Vessel.first_observed_at >= cutoff)

    if spec.min_age_years is not None or spec.max_age_years is not None:
        current_year = datetime.now(timezone.utc).year
        if spec.max_age_years is not None:
            min_year = current_year - int(spec.max_age_years)
            q = q.where(Vessel.year_built >= str(min_year))
        if spec.min_age_years is not None:
            max_year = current_year - int(spec.min_age_years)
            q = q.where(Vessel.year_built <= str(max_year))

    if spec.min_gross_tonnage is not None:
        q = q.where(Vessel.gross_tonnage >= spec.min_gross_tonnage)

    if spec.max_gross_tonnage is not None:
        q = q.where(Vessel.gross_tonnage <= spec.max_gross_tonnage)

    return q


async def parse_nl_query(query: str) -> SearchFilterSpec:
    raw_text, _, _ = await call_haiku(
        system_prompt=_NL_SYSTEM_PROMPT,
        user_message=query,
        max_tokens=256,
        mock_fixture="haiku_nl_parse_response",
    )
    parsed = json.loads(raw_text)
    return SearchFilterSpec(**parsed)


async def execute_search(session: AsyncSession, spec: SearchFilterSpec) -> list[Vessel]:
    if spec.connected_to_sanctioned_org:
        cte_sql = _sanctioned_company_imos_cte()
        cte_result = await session.execute(cte_sql)
        connected_imos = [row[0] for row in cte_result.all()]
        if not connected_imos:
            return []
        q = spec_to_query(spec).where(Vessel.imo.in_(connected_imos))
    else:
        q = spec_to_query(spec)

    q = q.limit(200)
    result = await session.execute(q)
    return list(result.scalars().all())
