"""Phase 1: full vessel + position + provenance + enrichment queue + company model

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # app_config — must exist before anything reads from it
    # -----------------------------------------------------------------
    op.create_table(
        "app_config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value_encrypted", sa.Text, nullable=True),
        sa.Column("value_plain", sa.Text, nullable=True),
        sa.Column("is_secret", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
    )

    # -----------------------------------------------------------------
    # vessel master
    # -----------------------------------------------------------------
    op.create_table(
        "vessel",
        sa.Column("imo", sa.BigInteger, primary_key=True),
        sa.Column("mmsi", sa.String(20), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("call_sign", sa.String(20), nullable=True),
        sa.Column("flag", sa.String(5), nullable=True),
        sa.Column("vessel_type", sa.String(50), nullable=True),
        sa.Column("year_built", sa.String(4), nullable=True),
        sa.Column("gross_tonnage", sa.Float, nullable=True),
        sa.Column("deadweight", sa.Float, nullable=True),
        sa.Column("length_overall", sa.Float, nullable=True),
        sa.Column("beam", sa.Float, nullable=True),
        sa.Column("draft_max", sa.Float, nullable=True),
        sa.Column("is_shadow_fleet", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("current_sanctions_status", sa.String(20), nullable=False, server_default="clean"),
        sa.Column("first_observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_enriched_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("latest_risk_score_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_manual_review_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("imo BETWEEN 1000000 AND 9999999", name="ck_vessel_imo_range"),
    )
    op.create_index("ix_vessel_mmsi", "vessel", ["mmsi"])
    op.create_index("ix_vessel_flag", "vessel", ["flag"])
    op.create_index("ix_vessel_vessel_type", "vessel", ["vessel_type"])
    op.create_index("ix_vessel_last_observed_at", "vessel", ["last_observed_at"])
    op.create_index(
        "ix_vessel_shadow_fleet",
        "vessel",
        ["is_shadow_fleet"],
        postgresql_where=sa.text("is_shadow_fleet = true"),
    )

    # -----------------------------------------------------------------
    # vessel_particular_fact — field-level provenance
    # -----------------------------------------------------------------
    op.create_table(
        "vessel_particular_fact",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_value", sa.Text, nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("fetch_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_vpf_imo", "vessel_particular_fact", ["imo"])
    op.create_index(
        "ix_vpf_imo_field_open",
        "vessel_particular_fact",
        ["imo", "field_name"],
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.create_index(
        "ix_vpf_imo_field_from",
        "vessel_particular_fact",
        ["imo", "field_name", "valid_from"],
    )

    # -----------------------------------------------------------------
    # vessel_enrichment_queue
    # -----------------------------------------------------------------
    op.create_table(
        "vessel_enrichment_queue",
        sa.Column("imo", sa.BigInteger, primary_key=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("enqueued_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("locked_until", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_veq_ready",
        "vessel_enrichment_queue",
        ["next_attempt_at", "priority"],
        postgresql_where=sa.text("locked_until IS NULL OR locked_until < NOW()"),
    )

    # -----------------------------------------------------------------
    # vessel_topic
    # -----------------------------------------------------------------
    op.create_table(
        "vessel_topic",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("os_entity_id", sa.String(100), nullable=True),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_vessel_topic_imo", "vessel_topic", ["imo"])
    op.create_index("ix_vessel_topic_imo_topic", "vessel_topic", ["imo", "topic"])

    # -----------------------------------------------------------------
    # position_live + position_archive (TimescaleDB hypertables created below)
    # -----------------------------------------------------------------
    op.create_table(
        "position_live",
        sa.Column("imo", sa.BigInteger, primary_key=True),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), primary_key=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("speed_knots", sa.Float, nullable=True),
        sa.Column("course_degrees", sa.Float, nullable=True),
        sa.Column("heading_degrees", sa.Float, nullable=True),
        sa.Column("nav_status", sa.String(50), nullable=True),
        sa.Column("draft_meters", sa.Float, nullable=True),
        sa.Column("inferred_status", sa.String(20), nullable=False),
        sa.Column("terminal_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("imo", "recorded_at", name="uq_pos_live_imo_recorded_at"),
    )

    op.create_table(
        "position_archive",
        sa.Column("imo", sa.BigInteger, primary_key=True),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), primary_key=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("speed_knots", sa.Float, nullable=True),
        sa.Column("course_degrees", sa.Float, nullable=True),
        sa.Column("heading_degrees", sa.Float, nullable=True),
        sa.Column("nav_status", sa.String(50), nullable=True),
        sa.Column("draft_meters", sa.Float, nullable=True),
        sa.Column("inferred_status", sa.String(20), nullable=False),
        sa.Column("terminal_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("imo", "recorded_at", name="uq_pos_archive_imo_recorded_at"),
    )

    # Convert to TimescaleDB hypertables (14-day + 365-day retention chunks)
    op.execute(
        "SELECT create_hypertable('position_live', 'recorded_at', "
        "chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT add_retention_policy('position_live', INTERVAL '14 days', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('position_archive', 'recorded_at', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT add_retention_policy('position_archive', INTERVAL '365 days', if_not_exists => TRUE)"
    )

    # -----------------------------------------------------------------
    # company + company_alias + company_identifier + vessel_company_relationship
    # -----------------------------------------------------------------
    op.create_table(
        "company",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("country", sa.String(5), nullable=True),
        sa.Column("first_seen_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_company_name", "company", ["name"])

    op.create_table(
        "company_alias",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("company.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(300), nullable=False),
    )
    op.create_index("ix_company_alias_company_id", "company_alias", ["company_id"])
    op.create_index(
        "ix_company_alias_lower",
        "company_alias",
        ["alias"],
        postgresql_ops={"alias": "text_pattern_ops"},
    )

    op.create_table(
        "company_identifier",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("company.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identifier_type", sa.String(50), nullable=False),
        sa.Column("identifier_value", sa.String(200), nullable=False),
        sa.CheckConstraint(
            "identifier_type IN ('os_entity_id', 'registration_number', 'lei', 'mmsi', 'topic')",
            name="ck_company_identifier_type",
        ),
        sa.UniqueConstraint("company_id", "identifier_type", "identifier_value", name="uq_company_identifier"),
    )
    op.create_index(
        "ix_company_identifier_type_value",
        "company_identifier",
        ["identifier_type", "identifier_value"],
    )

    op.create_table(
        "vessel_company_relationship",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.CheckConstraint(
            "role IN ('registered_owner', 'operator', 'ism_manager', 'classification_society', 'bareboat_charterer')",
            name="ck_vcr_role",
        ),
    )
    op.create_index("ix_vcr_imo", "vessel_company_relationship", ["imo"])
    op.create_index("ix_vcr_company_id", "vessel_company_relationship", ["company_id"])
    op.create_index(
        "ix_vcr_imo_role_open",
        "vessel_company_relationship",
        ["imo", "role"],
        postgresql_where=sa.text("valid_to IS NULL"),
    )

    # -----------------------------------------------------------------
    # audit_log (needed by config_service from Phase 1)
    # -----------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("detail", postgresql.JSONB, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_actor_action", "audit_log", ["actor", "action"])

    # -----------------------------------------------------------------
    # Grant table-level permissions to seam_app role
    # -----------------------------------------------------------------
    tables = [
        "app_config", "vessel", "vessel_particular_fact", "vessel_enrichment_queue",
        "vessel_topic", "position_live", "position_archive",
        "company", "company_alias", "company_identifier", "vessel_company_relationship",
        "audit_log",
    ]
    for tbl in tables:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO seam_app")
        op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO seam_app")


def downgrade() -> None:
    for tbl in [
        "audit_log",
        "vessel_company_relationship", "company_identifier", "company_alias", "company",
        "position_archive", "position_live",
        "vessel_topic", "vessel_enrichment_queue", "vessel_particular_fact",
        "vessel", "app_config",
    ]:
        op.drop_table(tbl)
