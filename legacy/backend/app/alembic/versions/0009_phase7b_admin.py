"""Phase 7b: outbound_request_log, data_source_status, dependency_audit_log, data_source_attribution

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_source_status",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(100), nullable=False, unique=True),
        sa.Column("last_success_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_payload_sha1", sa.String(40), nullable=True),
    )

    op.create_table(
        "outbound_request_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("requested_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_outbound_request_log_requested_at", "outbound_request_log", ["requested_at"])
    op.create_index("ix_outbound_request_log_source", "outbound_request_log", ["source_name"])

    op.create_table(
        "dependency_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audited_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ecosystem", sa.String(20), nullable=False),
        sa.Column("vulnerabilities", JSONB(), nullable=True),
        sa.Column("high_critical_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_output", sa.Text(), nullable=True),
    )
    op.create_index("ix_dependency_audit_log_audited_at", "dependency_audit_log", ["audited_at"])

    op.create_table(
        "data_source_attribution",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_text", sa.String(300), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("license_summary", sa.String(200), nullable=True),
        sa.Column("attribution_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("non_commercial_only", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_table("data_source_attribution")
    op.drop_index("ix_dependency_audit_log_audited_at", "dependency_audit_log")
    op.drop_table("dependency_audit_log")
    op.drop_index("ix_outbound_request_log_source", "outbound_request_log")
    op.drop_index("ix_outbound_request_log_requested_at", "outbound_request_log")
    op.drop_table("outbound_request_log")
    op.drop_table("data_source_status")
