"""phase5a_weather_risk

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-02
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # weather_observation — single-point hourly Open-Meteo Marine poll
    # ------------------------------------------------------------------
    op.create_table(
        "weather_observation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("wave_height_m", sa.Float(), nullable=True),
        sa.Column("wave_direction_deg", sa.Float(), nullable=True),
        sa.Column("wave_period_s", sa.Float(), nullable=True),
        sa.Column("wind_wave_height_m", sa.Float(), nullable=True),
        sa.Column("wind_wave_direction_deg", sa.Float(), nullable=True),
        sa.Column("wind_wave_period_s", sa.Float(), nullable=True),
        sa.Column("swell_wave_height_m", sa.Float(), nullable=True),
        sa.Column("swell_wave_direction_deg", sa.Float(), nullable=True),
        sa.Column("swell_wave_period_s", sa.Float(), nullable=True),
        sa.Column("ocean_current_velocity_ms", sa.Float(), nullable=True),
        sa.Column("ocean_current_direction_deg", sa.Float(), nullable=True),
        sa.Column("sea_surface_temperature_c", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", "recorded_at"),
    )
    op.execute(
        "DO $$ BEGIN "
        "  PERFORM create_hypertable('weather_observation', 'recorded_at', "
        "    chunk_time_interval => INTERVAL '7 days'); "
        "  PERFORM add_retention_policy('weather_observation', INTERVAL '365 days'); "
        "EXCEPTION WHEN OTHERS THEN NULL; END $$"
    )

    # ------------------------------------------------------------------
    # anchorage_dwell — per-vessel dwell event inside a terminal polygon
    # ------------------------------------------------------------------
    op.create_table(
        "anchorage_dwell",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vessel_imo", sa.BigInteger(), nullable=False),
        sa.Column("terminal_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["vessel_imo"], ["vessel.imo"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["terminal_id"], ["terminal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anchorage_dwell_vessel_imo", "anchorage_dwell", ["vessel_imo"])
    op.create_index(
        "ix_anchorage_dwell_terminal_active",
        "anchorage_dwell",
        ["terminal_id", "started_at"],
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    # ------------------------------------------------------------------
    # risk_score — hourly composite snapshot, TimescaleDB hypertable
    # ------------------------------------------------------------------
    op.create_table(
        "risk_score",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vessel_imo", sa.BigInteger(), nullable=False),
        sa.Column("scored_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("composite", sa.Float(), nullable=False),
        sa.Column("sanctions_score", sa.Float(), nullable=False),
        sa.Column("shadow_fleet_score", sa.Float(), nullable=False),
        sa.Column("age_score", sa.Float(), nullable=False),
        sa.Column("flag_mou_score", sa.Float(), nullable=False),
        sa.Column("congestion_score", sa.Float(), nullable=False),
        sa.Column("weather_score", sa.Float(), nullable=False),
        sa.Column("components", JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["vessel_imo"], ["vessel.imo"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", "scored_at"),
    )
    op.execute(
        "DO $$ BEGIN "
        "  PERFORM create_hypertable('risk_score', 'scored_at', "
        "    chunk_time_interval => INTERVAL '7 days'); "
        "  PERFORM add_retention_policy('risk_score', INTERVAL '365 days'); "
        "EXCEPTION WHEN OTHERS THEN NULL; END $$"
    )
    op.create_index("ix_risk_score_vessel_scored", "risk_score", ["vessel_imo", "scored_at"])

    # ------------------------------------------------------------------
    # flag_performance_year — annual MoU flag band (seeded from fixture)
    # ------------------------------------------------------------------
    op.create_table(
        "flag_performance_year",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flag_code", sa.String(3), nullable=False),
        sa.Column("mou", sa.String(50), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("performance_band", sa.String(10), nullable=False),
        sa.CheckConstraint(
            "mou IN ('tokyo', 'paris', 'black_sea', 'abuja')",
            name="ck_fpy_mou",
        ),
        sa.CheckConstraint(
            "performance_band IN ('white', 'grey', 'black')",
            name="ck_fpy_band",
        ),
        sa.UniqueConstraint("flag_code", "mou", "year", name="uq_fpy_flag_mou_year"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Grants
    # ------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "weather_observation, anchorage_dwell, risk_score, flag_performance_year "
        "TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT ON "
        "weather_observation, risk_score, flag_performance_year "
        "TO oceansx_readonly"
    )


def downgrade() -> None:
    op.drop_table("flag_performance_year")
    op.drop_table("risk_score")
    op.drop_table("anchorage_dwell")
    op.drop_table("weather_observation")
