"""phase 4 sanctions: opensanctions_entity_raw, sanctions tables, agent_review_queue, mou_inspection

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opensanctions_entity_raw",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("os_entity_id", sa.String(100), nullable=False),
        sa.Column("schema_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("dataset", sa.String(100)),
        sa.Column("ingested_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("file_date", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("os_entity_id", "ingested_at", name="uq_os_raw_entity_ingested"),
    )
    op.create_index("ix_os_raw_entity_id", "opensanctions_entity_raw", ["os_entity_id"])
    op.create_index("ix_os_raw_schema_type", "opensanctions_entity_raw", ["schema_type"])

    op.create_table(
        "sanctions_source",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("dataset_name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200)),
        sa.Column("last_downloaded_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("file_date", sa.TIMESTAMP(timezone=True)),
        sa.Column("entity_count", sa.Integer),
    )

    op.create_table(
        "sanctions_listing",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("os_entity_id", sa.String(100), nullable=False),
        sa.Column(
            "sanctions_source_id",
            sa.Integer,
            sa.ForeignKey("sanctions_source.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("listing_date", sa.TIMESTAMP(timezone=True)),
        sa.Column("first_seen_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("imo", "sanctions_source_id", name="uq_sanctions_listing_imo_source"),
    )
    op.create_index("ix_sanctions_listing_imo", "sanctions_listing", ["imo"])

    op.create_table(
        "sanctions_match",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("os_entity_id", sa.String(100), nullable=False),
        sa.Column("match_method", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("confidence", sa.Float),
        sa.Column("reviewer_note", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "match_method IN ('imo_exact', 'name_flag_fuzzy', 'name_fuzzy', 'org_link')",
            name="ck_sanctions_match_method",
        ),
        sa.CheckConstraint(
            "status IN ('auto_confirmed', 'pending', 'confirmed', 'rejected')",
            name="ck_sanctions_match_status",
        ),
        sa.CheckConstraint(
            "NOT (status = 'auto_confirmed' AND match_method != 'imo_exact')",
            name="ck_sanctions_match_auto_confirm_imo_only",
        ),
        sa.UniqueConstraint("imo", "os_entity_id", name="uq_sanctions_match_imo_entity"),
    )
    op.create_index("ix_sanctions_match_imo", "sanctions_match", ["imo"])

    op.create_table(
        "sanctions_match_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "sanctions_match_id",
            sa.Integer,
            sa.ForeignKey("sanctions_match.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_status", sa.String(20)),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("changed_by", sa.String(100)),
        sa.Column("note", sa.Text),
        sa.Column("changed_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_smh_match_id", "sanctions_match_history", ["sanctions_match_id"])

    op.create_table(
        "agent_review_queue",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("os_entity_id", sa.String(100), nullable=False),
        sa.Column("match_method", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("match_evidence", sa.dialects.postgresql.JSONB),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("reviewer_note", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status IN ('open', 'confirmed', 'rejected')",
            name="ck_arq_status",
        ),
    )
    op.create_index("ix_arq_imo", "agent_review_queue", ["imo"])

    op.create_table(
        "mou_inspection",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("mou_region", sa.String(30), nullable=False, server_default="tokyo"),
        sa.Column("inspection_date", sa.TIMESTAMP(timezone=True)),
        sa.Column("port_of_inspection", sa.String(200)),
        sa.Column("detained", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deficiency_count", sa.Integer),
        sa.Column("source_ref", sa.String(200)),
        sa.Column("ingested_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_mou_inspection_imo", "mou_inspection", ["imo"])


def downgrade() -> None:
    op.drop_index("ix_mou_inspection_imo", table_name="mou_inspection")
    op.drop_table("mou_inspection")
    op.drop_index("ix_arq_imo", table_name="agent_review_queue")
    op.drop_table("agent_review_queue")
    op.drop_index("ix_smh_match_id", table_name="sanctions_match_history")
    op.drop_table("sanctions_match_history")
    op.drop_index("ix_sanctions_match_imo", table_name="sanctions_match")
    op.drop_table("sanctions_match")
    op.drop_index("ix_sanctions_listing_imo", table_name="sanctions_listing")
    op.drop_table("sanctions_listing")
    op.drop_table("sanctions_source")
    op.drop_index("ix_os_raw_schema_type", table_name="opensanctions_entity_raw")
    op.drop_index("ix_os_raw_entity_id", table_name="opensanctions_entity_raw")
    op.drop_table("opensanctions_entity_raw")
