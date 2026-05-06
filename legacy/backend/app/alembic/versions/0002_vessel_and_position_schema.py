"""vessel and position schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-30

Phase 1: Vessel master (SCD2), position_live and position_archive TimescaleDB hypertables.
Terminal table stub (Phase 2 adds PostGIS geometry column).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # vessel master
    # ------------------------------------------------------------------
    op.create_table(
        "vessel",
        sa.Column("imo", sa.BigInteger, primary_key=True),
        sa.Column("mmsi", sa.String(20)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("call_sign", sa.String(20)),
        sa.Column("flag", sa.String(5)),
        sa.Column("vessel_type", sa.String(50)),
        sa.Column("year_built", sa.String(4)),
        sa.Column("gross_tonnage", sa.Float),
        sa.Column("deadweight", sa.Float),
        sa.Column("length_overall", sa.Float),
        sa.Column("beam", sa.Float),
        sa.Column("draft_max", sa.Float),
        sa.Column("ism_manager", sa.String(200)),
        sa.Column("registered_owner", sa.String(200)),
        sa.Column("operator", sa.String(200)),
        sa.Column("classification_society", sa.String(100)),
        sa.Column("is_shadow_fleet", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("current_sanctions_status", sa.String(20), nullable=False, server_default="clean"),
        sa.Column("first_observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_enriched_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("latest_risk_score_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_manual_review_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("imo BETWEEN 1000000 AND 9999999", name="ck_vessel_imo_range"),
    )
    op.create_index("ix_vessel_last_observed_at", "vessel", ["last_observed_at"])
    op.create_index("ix_vessel_flag", "vessel", ["flag"])
    op.create_index("ix_vessel_type", "vessel", ["vessel_type"])
    op.create_index("ix_vessel_mmsi", "vessel", ["mmsi"])
    op.execute(
        "CREATE INDEX ix_vessel_shadow_fleet ON vessel (is_shadow_fleet) "
        "WHERE is_shadow_fleet = true"
    )

    # ------------------------------------------------------------------
    # SCD2 history tables
    # ------------------------------------------------------------------
    for table, col, coltype in [
        ("vessel_name_history", "name", sa.String(200)),
        ("vessel_flag_history", "flag", sa.String(5)),
        ("vessel_owner_history", "owner", sa.String(200)),
        ("vessel_operator_history", "operator", sa.String(200)),
        ("vessel_class_history", "classification_society", sa.String(100)),
    ]:
        op.create_table(
            table,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("imo", sa.BigInteger, nullable=False, index=True),
            sa.Column(col, coltype, nullable=False),
            sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
            sa.Column("source", sa.String(50), nullable=False),
        )
        op.create_index(f"ix_{table}_imo_valid_from", table, ["imo", "valid_from"])

    # vessel_topic (Phase 4 populates; create now for schema completeness)
    op.create_table(
        "vessel_topic",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False, index=True),
        sa.Column("topic", sa.String(50), nullable=False),
        sa.Column("source_dataset", sa.String(100), nullable=False),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
    )
    op.execute(
        "CREATE INDEX ix_vessel_topic_current ON vessel_topic (imo, topic) "
        "WHERE valid_to IS NULL"
    )

    # ------------------------------------------------------------------
    # Terminal stub (Phase 2 adds PostGIS geometry column)
    # ------------------------------------------------------------------
    op.create_table(
        "terminal",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("port_id", sa.Integer),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("short_code", sa.String(20)),
    )

    # ------------------------------------------------------------------
    # position_live — TimescaleDB hypertable, 1-day chunks, 14-day retention
    # ------------------------------------------------------------------
    op.create_table(
        "position_live",
        sa.Column("imo", sa.BigInteger, nullable=False, primary_key=True),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False, primary_key=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("speed_knots", sa.Float),
        sa.Column("course_degrees", sa.Float),
        sa.Column("heading_degrees", sa.Float),
        sa.Column("nav_status", sa.String(50)),
        sa.Column("draft_meters", sa.Float),
        sa.Column("inferred_status", sa.String(20), nullable=False),
        sa.Column("terminal_id", sa.Integer),
    )
    op.create_index("ix_pos_live_imo_recorded_at", "position_live", ["imo", "recorded_at"])

    # Convert to hypertable (no-op if TimescaleDB not installed)
    op.execute(
        "DO $$ BEGIN "
        "  PERFORM create_hypertable('position_live', 'recorded_at', "
        "    chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE); "
        "  PERFORM add_retention_policy('position_live', INTERVAL '14 days', if_not_exists => TRUE); "
        "EXCEPTION WHEN OTHERS THEN NULL; END $$"
    )

    # ------------------------------------------------------------------
    # position_archive — TimescaleDB hypertable, 1-month chunks, 365-day retention
    # ------------------------------------------------------------------
    op.create_table(
        "position_archive",
        sa.Column("imo", sa.BigInteger, nullable=False, primary_key=True),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False, primary_key=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("speed_knots", sa.Float),
        sa.Column("course_degrees", sa.Float),
        sa.Column("heading_degrees", sa.Float),
        sa.Column("nav_status", sa.String(50)),
        sa.Column("draft_meters", sa.Float),
        sa.Column("inferred_status", sa.String(20), nullable=False),
        sa.Column("terminal_id", sa.Integer),
    )
    op.create_index("ix_pos_archive_imo_recorded_at", "position_archive", ["imo", "recorded_at"])

    op.execute(
        "DO $$ BEGIN "
        "  PERFORM create_hypertable('position_archive', 'recorded_at', "
        "    chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE); "
        "  PERFORM add_retention_policy('position_archive', INTERVAL '365 days', if_not_exists => TRUE); "
        "  ALTER TABLE position_archive SET ("
        "    timescaledb.compress, "
        "    timescaledb.compress_orderby = 'recorded_at DESC', "
        "    timescaledb.compress_segmentby = 'imo'"
        "  ); "
        "  PERFORM add_compression_policy('position_archive', INTERVAL '7 days', if_not_exists => TRUE); "
        "EXCEPTION WHEN OTHERS THEN NULL; END $$"
    )


def downgrade() -> None:
    # TimescaleDB hypertables and their policies must be dropped before the table
    for table in ("position_archive", "position_live"):
        op.execute(f"SELECT remove_retention_policy('{table}', if_not_exists => TRUE)")
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    for table in (
        "vessel_topic",
        "vessel_class_history",
        "vessel_operator_history",
        "vessel_owner_history",
        "vessel_flag_history",
        "vessel_name_history",
        "terminal",
        "vessel",
    ):
        op.drop_table(table)
