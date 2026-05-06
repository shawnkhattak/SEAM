from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    service: str


# ---------------------------------------------------------------------------
# Vessel position
# ---------------------------------------------------------------------------

class VesselPosition(BaseModel):
    imo: int
    mmsi: str | None = None
    name: str
    flag: str | None = None
    flag_name: str | None = None
    flag_emoji: str | None = None
    vessel_type: str | None = None
    vessel_type_label: str | None = None
    year_built: str | None = None
    gross_tonnage: float | None = None
    lat: float
    lon: float
    speed_knots: float | None = None
    course_degrees: float | None = None
    heading_degrees: float | None = None
    nav_status: str | None = None
    inferred_status: str
    recorded_at: datetime
    is_shadow_fleet: bool = False
    current_sanctions_status: str = "clean"
    latest_composite_risk: float | None = None


# ---------------------------------------------------------------------------
# Provenance (vessel_particular_fact)
# ---------------------------------------------------------------------------

class ParticularFactResponse(BaseModel):
    field_name: str
    field_value: str | None
    source: str | None
    fetch_time: datetime | None
    confidence: float | None
    valid_from: datetime
    valid_to: datetime | None


# ---------------------------------------------------------------------------
# Company relationship (vessel_company_relationship)
# ---------------------------------------------------------------------------

class CompanyRelationshipResponse(BaseModel):
    company_id: int
    company_name: str
    role: str
    valid_from: datetime
    valid_to: datetime | None
    source: str | None
    confidence: float | None


# ---------------------------------------------------------------------------
# Vessel detail (full, with provenance + relationships)
# ---------------------------------------------------------------------------

class VesselDetail(BaseModel):
    imo: int
    name: str
    mmsi: str | None = None
    call_sign: str | None = None
    flag: str | None = None
    flag_name: str | None = None
    flag_emoji: str | None = None
    vessel_type: str | None = None
    vessel_type_label: str | None = None
    year_built: str | None = None
    gross_tonnage: float | None = None
    deadweight: float | None = None
    length_overall: float | None = None
    beam: float | None = None
    is_shadow_fleet: bool = False
    current_sanctions_status: str = "clean"
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    last_enriched_at: datetime | None = None
    position: VesselPosition | None = None
    movements: list[dict[str, Any]] = []
    particulars: list[ParticularFactResponse] = Field(default_factory=list)
    relationships: list[CompanyRelationshipResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Trail point
# ---------------------------------------------------------------------------

class TrailPoint(BaseModel):
    imo: int
    recorded_at: str
    lat: float
    lon: float
    speed_knots: float | None = None
    heading_degrees: float | None = None
    inferred_status: str


# ---------------------------------------------------------------------------
# Due arrivals / departures
# ---------------------------------------------------------------------------

class DueArrival(BaseModel):
    imo: str | None = None
    name: str | None = None
    flag: str | None = None
    due_to_arrive_time: str | None = None
    location_from: str | None = None
    location_to: str | None = None


class DueDeparture(BaseModel):
    imo: str | None = None
    name: str | None = None
    flag: str | None = None
    due_to_depart_time: str | None = None
    location_from: str | None = None
    location_to: str | None = None


# ---------------------------------------------------------------------------
# Sanctions + Review queue
# ---------------------------------------------------------------------------

class SanctionsMatchResponse(BaseModel):
    id: int
    imo: int
    os_entity_id: str
    match_method: str
    status: str
    confidence: float | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    entity_name: str | None = None
    entity_datasets: list[str] = []


class ReviewQueueItem(BaseModel):
    id: int
    imo: int
    os_entity_id: str
    match_method: str
    confidence: float | None = None
    match_evidence: dict[str, Any] | None = None
    status: str
    reviewer_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

class RiskScoreResponse(BaseModel):
    vessel_imo: int
    scored_at: datetime
    composite: float
    sanctions_score: float
    shadow_fleet_score: float
    age_score: float
    flag_mou_score: float
    congestion_score: float
    weather_score: float
    components: dict[str, Any] | None = None


class RiskLeaderboardItem(BaseModel):
    imo: int
    name: str
    flag: str | None = None
    flag_name: str | None = None
    flag_emoji: str | None = None
    vessel_type: str | None = None
    vessel_type_label: str | None = None
    composite: float
    is_shadow_fleet: bool
    current_sanctions_status: str
    scored_at: datetime


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

class NewsSummaryResponse(BaseModel):
    id: int
    news_id: int
    summary_text: str
    model_used: str
    generated_at_utc: datetime
    tokens_in: int | None = None
    tokens_out: int | None = None


# ---------------------------------------------------------------------------
# NL search
# ---------------------------------------------------------------------------

class SearchFilterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_codes: list[str] | None = None
    vessel_types: list[str] | None = None
    sanctioned_only: bool = False
    shadow_fleet_only: bool = False
    min_risk_score: float | None = None
    max_risk_score: float | None = None
    connected_to_sanctioned_org: bool = False
    new_arrivals_only: bool = False
    min_age_years: float | None = None
    max_age_years: float | None = None
    min_gross_tonnage: float | None = None
    max_gross_tonnage: float | None = None


class NlSearchRequest(BaseModel):
    query: str


class NlSearchResult(BaseModel):
    spec: SearchFilterSpec
    vessels: list[VesselPosition]
    cached: bool = False


# ---------------------------------------------------------------------------
# Enrichment queue (admin)
# ---------------------------------------------------------------------------

class EnrichmentQueueItem(BaseModel):
    imo: int
    priority: int
    enqueued_at: datetime
    last_attempt_at: datetime | None
    next_attempt_at: datetime | None
    attempt_count: int
    last_error: str | None


# ---------------------------------------------------------------------------
# App config (admin — never returns secret values)
# ---------------------------------------------------------------------------

class ConfigKeyResponse(BaseModel):
    key: str
    is_secret: bool
    description: str | None
    updated_at: datetime | None
    updated_by: str | None
    has_value: bool


class ConfigSetRequest(BaseModel):
    value: str
    is_secret: bool = False
    description: str | None = None
