from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    service: str


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Vessel position (used by live-tracking endpoints)
# ---------------------------------------------------------------------------

class VesselPositionResponse(BaseModel):
    imo: str
    mmsi: str | None = None
    name: str | None = None
    lat: float
    lon: float
    speed: float | None = None
    heading: float | None = None
    course: float | None = None
    nav_status: str | None = None
    vessel_type: str | None = None
    flag: str | None = None
    timestamp: datetime


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

class VesselDetailResponse(BaseModel):
    imo: str
    mmsi: str | None = None
    name: str | None = None
    flag: str | None = None
    vessel_type: str | None = None
    gross_tonnage: float | None = None
    deadweight: float | None = None
    year_built: int | None = None
    length: float | None = None
    beam: float | None = None
    draught: float | None = None
    call_sign: str | None = None
    is_shadow_fleet: bool = False
    current_sanctions_status: str | None = None
    risk_score: float | None = None
    last_position: VesselPositionResponse | None = None
    particulars: list[ParticularFactResponse] = Field(default_factory=list)
    relationships: list[CompanyRelationshipResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Enrichment queue
# ---------------------------------------------------------------------------

class EnrichmentQueueItem(BaseModel):
    imo: str
    priority: int
    enqueued_at: datetime
    last_attempt_at: datetime | None
    next_attempt_at: datetime | None
    attempt_count: int
    last_error: str | None
