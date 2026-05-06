"""phase7a_hardening — audit_log, journal tables, glossary_term

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_actor_action", "audit_log", ["actor", "action"])

    op.create_table(
        "journal_phase",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phase_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("summary_md", sa.Text(), nullable=True),
        sa.Column("markdown_file_path", sa.String(300), nullable=True),
        sa.Column("indexed_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "journal_adr",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("adr_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="accepted"),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("summary_md", sa.Text(), nullable=True),
        sa.Column("markdown_file_path", sa.String(300), nullable=True),
        sa.Column("superseded_by_adr_number", sa.Integer(), nullable=True),
        sa.Column("indexed_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "journal_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=True),
    )
    op.create_index("ix_journal_event_occurred_at", "journal_event", ["occurred_at"])

    op.create_table(
        "glossary_term",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("term", sa.String(200), nullable=False, unique=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("plain_definition", sa.Text(), nullable=True),
        sa.Column("why_it_matters_in_project", sa.Text(), nullable=True),
        sa.Column("markdown_file_path", sa.String(300), nullable=True),
        sa.Column("indexed_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "audit_log, journal_phase, journal_adr, journal_event, glossary_term "
        "TO seam_app"
    )
    op.execute(
        "GRANT SELECT ON "
        "journal_phase, journal_adr, glossary_term "
        "TO seam_readonly"
    )


def downgrade() -> None:
    op.drop_table("glossary_term")
    op.drop_index("ix_journal_event_occurred_at", "journal_event")
    op.drop_table("journal_event")
    op.drop_table("journal_adr")
    op.drop_table("journal_phase")
    op.drop_index("ix_audit_log_actor_action", "audit_log")
    op.drop_index("ix_audit_log_occurred_at", "audit_log")
    op.drop_table("audit_log")
