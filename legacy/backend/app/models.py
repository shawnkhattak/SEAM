from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Shared metadata — imported by alembic/env.py for autogenerate
class Base(DeclarativeBase):
    pass

metadata = Base.metadata


# ---------------------------------------------------------------------------
# Phase 1: Vessel Master + Position tables
# ---------------------------------------------------------------------------

class Vessel(Base):
    """One row per IMO. Updated on every position poll. SCD2 history in sibling tables."""

    __tablename__ = "vessel"
    __table_args__ = (
        CheckConstraint("imo BETWEEN 1000000 AND 9999999", name="ck_vessel_imo_range"),
        Index("ix_vessel_last_observed_at", "last_observed_at"),
        Index(
            "ix_vessel_shadow_fleet",
            "is_shadow_fleet",
            postgresql_where="is_shadow_fleet = true",
        ),
    )

    imo: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mmsi: Mapped[str | None] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    call_sign: Mapped[str | None] = mapped_column(String(20))
    flag: Mapped[str | None] = mapped_column(String(5), index=True)
    vessel_type: Mapped[str | None] = mapped_column(String(50), index=True)
    year_built: Mapped[str | None] = mapped_column(String(4))
    gross_tonnage: Mapped[float | None] = mapped_column(Float)
    deadweight: Mapped[float | None] = mapped_column(Float)
    length_overall: Mapped[float | None] = mapped_column(Float)
    beam: Mapped[float | None] = mapped_column(Float)
    draft_max: Mapped[float | None] = mapped_column(Float)
    ism_manager: Mapped[str | None] = mapped_column(String(200))
    registered_owner: Mapped[str | None] = mapped_column(String(200))
    operator: Mapped[str | None] = mapped_column(String(200))
    classification_society: Mapped[str | None] = mapped_column(String(100))
    # Phase 4: sanctions / shadow fleet flags (False by default)
    is_shadow_fleet: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    current_sanctions_status: Mapped[str] = mapped_column(
        String(20), default="clean", server_default="clean"
    )
    first_observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    last_observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    last_enriched_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    latest_risk_score_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_manual_review_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class VesselNameHistory(Base):
    """SCD2: every name a vessel has carried."""

    __tablename__ = "vessel_name_history"
    __table_args__ = (Index("ix_vnh_imo_valid_from", "imo", "valid_from"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    source: Mapped[str] = mapped_column(String(50))


class VesselFlagHistory(Base):
    """SCD2: every flag state a vessel has flown."""

    __tablename__ = "vessel_flag_history"
    __table_args__ = (Index("ix_vfh_imo_valid_from", "imo", "valid_from"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, index=True)
    flag: Mapped[str] = mapped_column(String(5))
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    source: Mapped[str] = mapped_column(String(50))


class VesselOwnerHistory(Base):
    """SCD2: registered owner."""

    __tablename__ = "vessel_owner_history"
    __table_args__ = (Index("ix_voh_imo_valid_from", "imo", "valid_from"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, index=True)
    owner: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    source: Mapped[str] = mapped_column(String(50))


class VesselOperatorHistory(Base):
    """SCD2: operator / manager."""

    __tablename__ = "vessel_operator_history"
    __table_args__ = (Index("ix_voph_imo_valid_from", "imo", "valid_from"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, index=True)
    operator: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    source: Mapped[str] = mapped_column(String(50))


class VesselClassHistory(Base):
    """SCD2: classification society."""

    __tablename__ = "vessel_class_history"
    __table_args__ = (Index("ix_vch_imo_valid_from", "imo", "valid_from"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, index=True)
    classification_society: Mapped[str] = mapped_column(String(100))
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    source: Mapped[str] = mapped_column(String(50))


class VesselTopic(Base):
    """OpenSanctions topic tags (SCD2). Phase 4a renames source_dataset → os_entity_id."""

    __tablename__ = "vessel_topic"
    __table_args__ = (
        Index("ix_vessel_topic_imo_topic", "imo", "topic"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, index=True)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    os_entity_id: Mapped[str | None] = mapped_column(String(100))
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class PositionLive(Base):
    """Rolling hot table — every position poll row. TimescaleDB hypertable."""

    __tablename__ = "position_live"
    __table_args__ = (
        # Composite PK required by TimescaleDB (time col must be in unique constraints)
        UniqueConstraint("imo", "recorded_at", name="uq_pos_live_imo_recorded_at"),
    )

    # TimescaleDB hypertables need the time column in the PK
    imo: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    speed_knots: Mapped[float | None] = mapped_column(Float)
    course_degrees: Mapped[float | None] = mapped_column(Float)
    heading_degrees: Mapped[float | None] = mapped_column(Float)
    nav_status: Mapped[str | None] = mapped_column(String(50))
    draft_meters: Mapped[float | None] = mapped_column(Float)
    inferred_status: Mapped[str] = mapped_column(String(20))
    # terminal_id FK added in Phase 2 when terminal table exists
    terminal_id: Mapped[int | None] = mapped_column(Integer)


class PositionArchive(Base):
    """Dedup'd long-term archive. TimescaleDB hypertable. Source for 24h timeline."""

    __tablename__ = "position_archive"
    __table_args__ = (
        UniqueConstraint("imo", "recorded_at", name="uq_pos_archive_imo_recorded_at"),
    )

    imo: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    speed_knots: Mapped[float | None] = mapped_column(Float)
    course_degrees: Mapped[float | None] = mapped_column(Float)
    heading_degrees: Mapped[float | None] = mapped_column(Float)
    nav_status: Mapped[str | None] = mapped_column(String(50))
    draft_meters: Mapped[float | None] = mapped_column(Float)
    inferred_status: Mapped[str] = mapped_column(String(20))
    terminal_id: Mapped[int | None] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Phase 2: Port, PortAlias, Terminal (with FK to Port), TerminalGeom (PostGIS)
# ---------------------------------------------------------------------------

class Port(Base):
    """MPA canonical port — one row per port code."""

    __tablename__ = "port"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    locode: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(5))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)


class PortAlias(Base):
    """Alternative names / short codes for ports."""

    __tablename__ = "port_alias"
    __table_args__ = (Index("ix_port_alias_alias", "alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    port_id: Mapped[int] = mapped_column(Integer, ForeignKey("port.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), nullable=False)


class Terminal(Base):
    """Named berth / terminal within a port."""

    __tablename__ = "terminal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    port_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("port.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_code: Mapped[str | None] = mapped_column(String(20))


class TerminalGeom(Base):
    """PostGIS polygon geometry for a terminal — separate table so the main Terminal row is light."""

    __tablename__ = "terminal_geom"
    __table_args__ = (Index("ix_terminal_geom_gist", "geom", postgresql_using="gist"),)

    terminal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("terminal.id", ondelete="CASCADE"), primary_key=True
    )
    geom: Mapped[object] = mapped_column(
        Geography(geometry_type="POLYGON", srid=4326), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    buffered: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


# ---------------------------------------------------------------------------
# Phase 3: News feeds and entity-aware articles
# ---------------------------------------------------------------------------

class NewsFeed(Base):
    """RSS.app feed registry — one row per configured feed slot."""

    __tablename__ = "news_feed"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feed_slot: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class NewsItem(Base):
    """One article ingested from an RSS feed or webhook."""

    __tablename__ = "news_item"
    __table_args__ = (
        CheckConstraint(
            "extraction_status IN ('pending', 'done', 'error')",
            name="ck_news_item_extraction_status",
        ),
        Index("ix_news_item_published_at", "published_at_utc", postgresql_ops={"published_at_utc": "DESC"}),
        Index("ix_news_item_extraction_status", "extraction_status", "published_at_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feed_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("news_feed.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text)
    published_at_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ingested_at_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    extraction_status: Mapped[str] = mapped_column(
        String(30), default="pending", server_default="pending", nullable=False
    )


class NewsEntityMention(Base):
    """An entity (vessel or port) identified in a news article."""

    __tablename__ = "news_entity_mention"
    __table_args__ = (
        Index("ix_news_entity_mention_lookup", "entity_type", "entity_ref_id", "news_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news_item.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_text: Mapped[str] = mapped_column(String(300), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)


class NewsSummary(Base):
    """AI-generated summary for a news article. Populated in Phase 6."""

    __tablename__ = "news_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news_item.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_at_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Phase 4: OpenSanctions, sanctions matching, shadow fleet
# ---------------------------------------------------------------------------

class OpenSanctionsEntityRaw(Base):
    """Raw FtM payload — authoritative source. Projection can be re-run from here."""

    __tablename__ = "opensanctions_entity_raw"
    __table_args__ = (
        UniqueConstraint("os_entity_id", "ingested_at", name="uq_os_raw_entity_ingested"),
        Index("ix_os_raw_entity_id", "os_entity_id"),
        Index("ix_os_raw_schema_type", "schema_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    os_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dataset: Mapped[str | None] = mapped_column(String(100))
    ingested_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    file_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class Organization(Base):
    """Projected company/organization entity from OpenSanctions."""

    __tablename__ = "organization"
    __table_args__ = (
        Index("ix_organization_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    os_entity_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    country: Mapped[str | None] = mapped_column(String(5))
    registration_number: Mapped[str | None] = mapped_column(String(100))
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class OrganizationAlias(Base):
    """Alternate name spellings for an organization."""

    __tablename__ = "organization_alias"
    __table_args__ = (
        Index("ix_organization_alias_org_id", "organization_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(300), nullable=False)


class OrganizationTopic(Base):
    """Topic tags for an organization (sanction, debarment, etc.)."""

    __tablename__ = "organization_topic"
    __table_args__ = (
        Index("ix_organization_topic_org_id", "organization_id", "topic"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class VesselOrganizationLink(Base):
    """Vessel <-> organization relationship (owner, manager, operator)."""

    __tablename__ = "vessel_organization_link"
    __table_args__ = (
        Index("ix_vessel_org_link_imo", "imo", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class SanctionsSource(Base):
    """Registry of OpenSanctions datasets loaded."""

    __tablename__ = "sanctions_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    last_downloaded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    file_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    entity_count: Mapped[int | None] = mapped_column(Integer)


class SanctionsListing(Base):
    """Projected vessel-level sanctions entry (one row per vessel per dataset)."""

    __tablename__ = "sanctions_listing"
    __table_args__ = (
        UniqueConstraint("imo", "sanctions_source_id", name="uq_sanctions_listing_imo_source"),
        Index("ix_sanctions_listing_imo", "imo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    os_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sanctions_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sanctions_source.id", ondelete="CASCADE"), nullable=False
    )
    listing_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class SanctionsMatch(Base):
    """Match result between a vessel and an OpenSanctions entity.

    ADR-0005: status='auto_confirmed' is only permitted when match_method='imo_exact'.
    This is enforced at the database level by ck_sanctions_match_auto_confirm_imo_only.
    """

    __tablename__ = "sanctions_match"
    __table_args__ = (
        CheckConstraint(
            "match_method IN ('imo_exact', 'name_flag_fuzzy', 'name_fuzzy', 'org_link')",
            name="ck_sanctions_match_method",
        ),
        CheckConstraint(
            "status IN ('auto_confirmed', 'pending', 'confirmed', 'rejected')",
            name="ck_sanctions_match_status",
        ),
        CheckConstraint(
            "NOT (status = 'auto_confirmed' AND match_method != 'imo_exact')",
            name="ck_sanctions_match_auto_confirm_imo_only",
        ),
        UniqueConstraint("imo", "os_entity_id", name="uq_sanctions_match_imo_entity"),
        Index("ix_sanctions_match_imo", "imo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    os_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    match_method: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    confidence: Mapped[float | None] = mapped_column(Float)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class SanctionsMatchHistory(Base):
    """Audit trail for every sanctions_match status transition."""

    __tablename__ = "sanctions_match_history"
    __table_args__ = (
        Index("ix_smh_match_id", "sanctions_match_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sanctions_match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sanctions_match.id", ondelete="CASCADE"), nullable=False
    )
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class AgentReviewQueue(Base):
    """Human review queue for non-IMO sanctions matches (ADR-0005)."""

    __tablename__ = "agent_review_queue"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'confirmed', 'rejected')",
            name="ck_arq_status",
        ),
        Index("ix_arq_imo", "imo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    os_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    match_method: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    match_evidence: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class MouInspection(Base):
    """Tokyo MoU Port State Control inspection / detention record."""

    __tablename__ = "mou_inspection"
    __table_args__ = (
        Index("ix_mou_inspection_imo", "imo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mou_region: Mapped[str] = mapped_column(String(30), nullable=False, default="tokyo", server_default="tokyo")
    inspection_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    port_of_inspection: Mapped[str | None] = mapped_column(String(200))
    detained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    deficiency_count: Mapped[int | None] = mapped_column(Integer)
    source_ref: Mapped[str | None] = mapped_column(String(200))
    ingested_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Phase 5: Weather, anchorage dwell, risk scoring, flag performance
# ---------------------------------------------------------------------------

class WeatherObservation(Base):
    """Hourly Open-Meteo Marine reading for Singapore anchorage (1.265°N 103.82°E)."""

    __tablename__ = "weather_observation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    wave_height_m: Mapped[float | None] = mapped_column(Float)
    wave_direction_deg: Mapped[float | None] = mapped_column(Float)
    wave_period_s: Mapped[float | None] = mapped_column(Float)
    wind_wave_height_m: Mapped[float | None] = mapped_column(Float)
    wind_wave_direction_deg: Mapped[float | None] = mapped_column(Float)
    wind_wave_period_s: Mapped[float | None] = mapped_column(Float)
    swell_wave_height_m: Mapped[float | None] = mapped_column(Float)
    swell_wave_direction_deg: Mapped[float | None] = mapped_column(Float)
    swell_wave_period_s: Mapped[float | None] = mapped_column(Float)
    ocean_current_velocity_ms: Mapped[float | None] = mapped_column(Float)
    ocean_current_direction_deg: Mapped[float | None] = mapped_column(Float)
    sea_surface_temperature_c: Mapped[float | None] = mapped_column(Float)


class AnchorageDwell(Base):
    """Per-vessel dwell event inside a terminal polygon. Open ended_at = still present."""

    __tablename__ = "anchorage_dwell"
    __table_args__ = (
        Index("ix_anchorage_dwell_vessel_imo", "vessel_imo"),
        Index(
            "ix_anchorage_dwell_terminal_active",
            "terminal_id",
            "started_at",
            postgresql_where="ended_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vessel_imo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    terminal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class RiskScore(Base):
    """Hourly composite risk snapshot. TimescaleDB hypertable partitioned by scored_at."""

    __tablename__ = "risk_score"
    __table_args__ = (
        Index("ix_risk_score_vessel_scored", "vessel_imo", "scored_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vessel_imo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    composite: Mapped[float] = mapped_column(Float, nullable=False)
    sanctions_score: Mapped[float] = mapped_column(Float, nullable=False)
    shadow_fleet_score: Mapped[float] = mapped_column(Float, nullable=False)
    age_score: Mapped[float] = mapped_column(Float, nullable=False)
    flag_mou_score: Mapped[float] = mapped_column(Float, nullable=False)
    congestion_score: Mapped[float] = mapped_column(Float, nullable=False)
    weather_score: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[dict | None] = mapped_column(JSONB)


class FlagPerformanceYear(Base):
    """Annual MoU flag band rating. Seeded from fixture; queried by latest year per flag."""

    __tablename__ = "flag_performance_year"
    __table_args__ = (
        CheckConstraint("mou IN ('tokyo', 'paris', 'black_sea', 'abuja')", name="ck_fpy_mou"),
        CheckConstraint("performance_band IN ('white', 'grey', 'black')", name="ck_fpy_band"),
        UniqueConstraint("flag_code", "mou", "year", name="uq_fpy_flag_mou_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flag_code: Mapped[str] = mapped_column(String(3), nullable=False)
    mou: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_band: Mapped[str] = mapped_column(String(10), nullable=False)


# ---------------------------------------------------------------------------
# Phase 7: Audit log, project journal, glossary
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """Append-only log of admin actions. Never deleted."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_occurred_at", "occurred_at"),
        Index("ix_audit_log_actor_action", "actor", "action"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info", server_default="info")


class JournalPhase(Base):
    """One row per implementation phase, indexed from docs/journey/ markdown files."""

    __tablename__ = "journal_phase"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    summary_md: Mapped[str | None] = mapped_column(Text)
    markdown_file_path: Mapped[str | None] = mapped_column(String(300))
    indexed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class JournalAdr(Base):
    """One row per Architecture Decision Record, indexed from docs/adr/ markdown files."""

    __tablename__ = "journal_adr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adr_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="accepted", server_default="accepted")
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    summary_md: Mapped[str | None] = mapped_column(Text)
    markdown_file_path: Mapped[str | None] = mapped_column(String(300))
    superseded_by_adr_number: Mapped[int | None] = mapped_column(Integer)
    indexed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class JournalEvent(Base):
    """Timestamped narrative events in the project journal."""

    __tablename__ = "journal_event"
    __table_args__ = (Index("ix_journal_event_occurred_at", "occurred_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body_md: Mapped[str | None] = mapped_column(Text)


class GlossaryTerm(Base):
    """Plain-English definitions indexed from docs/glossary.md."""

    __tablename__ = "glossary_term"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(100))
    plain_definition: Mapped[str | None] = mapped_column(Text)
    why_it_matters_in_project: Mapped[str | None] = mapped_column(Text)
    markdown_file_path: Mapped[str | None] = mapped_column(String(300))
    indexed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Phase 7b: Admin/ops tables
# ---------------------------------------------------------------------------

class DataSourceStatus(Base):
    """Health status tracker for each external data source polled by the scheduler."""

    __tablename__ = "data_source_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    last_success_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_payload_sha1: Mapped[str | None] = mapped_column(String(40))


class OutboundRequestLog(Base):
    """Append-only log of every HTTP request made to external APIs."""

    __tablename__ = "outbound_request_log"
    __table_args__ = (
        Index("ix_outbound_request_log_requested_at", "requested_at"),
        Index("ix_outbound_request_log_source", "source_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requested_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)


class DependencyAuditLog(Base):
    """One row per pip-audit / npm-audit run, storing vulnerability counts and raw output."""

    __tablename__ = "dependency_audit_log"
    __table_args__ = (Index("ix_dependency_audit_log_audited_at", "audited_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audited_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(20), nullable=False)
    vulnerabilities: Mapped[dict | None] = mapped_column(JSONB)
    high_critical_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    raw_output: Mapped[str | None] = mapped_column(Text)


class DataSourceAttribution(Base):
    """Data source licence and attribution metadata, served by /api/about."""

    __tablename__ = "data_source_attribution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_text: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500))
    license_summary: Mapped[str | None] = mapped_column(String(200))
    attribution_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    non_commercial_only: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
