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
    """Deterministic SHA-256 key over the parsed spec (not the raw query text)."""
    canonical = json.dumps(spec.model_dump(), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Pure translation: SearchFilterSpec → SQLAlchemy Select
# ---------------------------------------------------------------------------

def _sanctioned_org_imos_cte() -> text:
    """
    Recursive CTE that finds all vessel IMOs connected to sanctioned organizations.

    Graph: vessel ↔ organization via vessel_organization_link.
    Cycle detection: visited_imos ARRAY prevents revisiting the same IMO.
    Depth capped at 3 hops to bound query cost.
    """
    return text(
        """
        WITH RECURSIVE connected_to_sanction(imo, visited_imos) AS (
            -- base: vessels directly linked to sanctioned orgs
            SELECT DISTINCT vol.imo, ARRAY[vol.imo]
            FROM vessel_organization_link vol
            JOIN organization_topic ot ON ot.organization_id = vol.organization_id
            WHERE ot.topic LIKE 'sanction%%'
              AND ot.valid_to IS NULL

            UNION ALL

            -- expand: vessels that share any org with an already-connected vessel
            SELECT DISTINCT vol2.imo,
                            c.visited_imos || vol2.imo
            FROM connected_to_sanction c
            JOIN vessel_organization_link vol  ON vol.imo  = c.imo
            JOIN vessel_organization_link vol2 ON vol2.organization_id = vol.organization_id
                                               AND vol2.imo != ALL(c.visited_imos)
            WHERE array_length(c.visited_imos, 1) < 3
        )
        SELECT DISTINCT imo FROM connected_to_sanction
        """
    )


def spec_to_query(spec: SearchFilterSpec) -> Select:
    """Pure function: translate SearchFilterSpec into a SQLAlchemy SELECT on vessel."""
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
        # Subquery: latest composite per vessel
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


# ---------------------------------------------------------------------------
# NL → SearchFilterSpec via Haiku
# ---------------------------------------------------------------------------

async def parse_nl_query(query: str) -> SearchFilterSpec:
    """Call Haiku to translate a natural-language query into a SearchFilterSpec."""
    raw_text, _, _ = await call_haiku(
        system_prompt=_NL_SYSTEM_PROMPT,
        user_message=query,
        max_tokens=256,
        mock_fixture="haiku_nl_parse_response",
    )
    parsed = json.loads(raw_text)
    return SearchFilterSpec(**parsed)


# ---------------------------------------------------------------------------
# Execute search
# ---------------------------------------------------------------------------

async def execute_search(session: AsyncSession, spec: SearchFilterSpec) -> list[Vessel]:
    """Run spec_to_query plus optional CTE for sanctioned-org traversal."""
    if spec.connected_to_sanctioned_org:
        cte_sql = _sanctioned_org_imos_cte()
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
