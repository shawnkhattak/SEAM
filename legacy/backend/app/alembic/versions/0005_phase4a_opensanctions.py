"""phase 4a: opensanctions ingestion, sanctions matching, shadow fleet, admin queue

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-01

Phase 4a (data plumbing only, no UI):
- opensanctions_entity_raw: raw FtM payloads, authoritative source of truth
- organization / organization_alias / organization_topic: projected company entities
- vessel_organization_link: vessel <-> company relationships
- vessel_topic: vessel-level topic tags (sanction, mare.shadow, etc.)
- sanctions_source / sanctions_listing: projected vessel sanctions
- sanctions_match / sanctions_match_history: match results + audit trail
- staging_opensanctions_ingest / staging_sanctions_match: Ops Swarm boundary
- agent_review_queue: human review queue for non-IMO matches
- mou_inspection: Tokyo MoU detention records
- ALTER vessel ADD CONSTRAINT ck_vessel_sanctions_status
- GRANT staging_* tables to oceansx_ops
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
    # ------------------------------------------------------------------
    # opensanctions_entity_raw
    # Raw FtM payload. Inserted independently of projection so projection
    # can be re-run from this table at any time.
    # ------------------------------------------------------------------
    op.create_table(
        "opensanctions_entity_raw",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("os_entity_id", sa.String(100), nullable=False),
        sa.Column("schema_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("dataset", sa.String(100)),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "file_date",
            sa.TIMESTAMP(timezone=True),
        ),
        sa.UniqueConstraint("os_entity_id", "ingested_at", name="uq_os_raw_entity_ingested"),
    )
    op.create_index("ix_os_raw_entity_id", "opensanctions_entity_raw", ["os_entity_id"])
    op.create_index("ix_os_raw_schema_type", "opensanctions_entity_raw", ["schema_type"])

    # ------------------------------------------------------------------
    # organization
    # Projected company/organization entities from OpenSanctions.
    # ------------------------------------------------------------------
    op.create_table(
        "organization",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("os_entity_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("country", sa.String(5)),
        sa.Column("registration_number", sa.String(100)),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_organization_os_entity_id", "organization", ["os_entity_id"])
    op.create_index("ix_organization_name", "organization", ["name"])

    # ------------------------------------------------------------------
    # organization_alias
    # All name variants for an organization (primary name stored in
    # organization.name; aliases include alternate spellings, abbreviations).
    # ------------------------------------------------------------------
    op.create_table(
        "organization_alias",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(300), nullable=False),
    )
    op.create_index(
        "ix_organization_alias_org_id", "organization_alias", ["organization_id"]
    )

    # ------------------------------------------------------------------
    # organization_topic
    # Topic tags (sanction, debarment, etc.) per organization.
    # ------------------------------------------------------------------
    op.create_table(
        "organization_topic",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index(
        "ix_organization_topic_org_id", "organization_topic", ["organization_id", "topic"]
    )

    # ------------------------------------------------------------------
    # vessel_organization_link
    # Many-to-many: vessel <-> organization (owner, manager, operator roles).
    # ------------------------------------------------------------------
    op.create_table(
        "vessel_organization_link",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index(
        "ix_vessel_org_link_imo", "vessel_organization_link", ["imo", "role"]
    )

    # ------------------------------------------------------------------
    # vessel_topic — table created as stub in 0002; Phase 4a alters it:
    #   - rename source_dataset → os_entity_id (was empty)
    #   - widen topic column from VARCHAR(50) → VARCHAR(100)
    #   - add ix_vessel_topic_imo_topic (non-partial, for general lookups)
    #   - add ix_vessel_topic_shadow (partial for shadow fleet derivation)
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE vessel_topic RENAME COLUMN source_dataset TO os_entity_id"
    )
    op.execute(
        "ALTER TABLE vessel_topic ALTER COLUMN topic TYPE VARCHAR(100)"
    )
    op.execute(
        "ALTER TABLE vessel_topic ALTER COLUMN os_entity_id DROP NOT NULL"
    )
    op.create_index(
        "ix_vessel_topic_imo_topic", "vessel_topic", ["imo", "topic"]
    )
    op.create_index(
        "ix_vessel_topic_shadow",
        "vessel_topic",
        ["imo"],
        postgresql_where=sa.text("topic = 'mare.shadow' AND valid_to IS NULL"),
    )

    # ------------------------------------------------------------------
    # sanctions_source
    # Which OpenSanctions datasets are loaded (e.g. us_ofac_sdn, ru_nsd_sdn).
    # ------------------------------------------------------------------
    op.create_table(
        "sanctions_source",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("dataset_name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200)),
        sa.Column(
            "last_downloaded_at",
            sa.TIMESTAMP(timezone=True),
        ),
        sa.Column(
            "file_date",
            sa.TIMESTAMP(timezone=True),
        ),
        sa.Column("entity_count", sa.Integer),
    )

    # ------------------------------------------------------------------
    # sanctions_listing
    # Projected vessel-level sanctions entries (one row per vessel per dataset).
    # ------------------------------------------------------------------
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
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("imo", "sanctions_source_id", name="uq_sanctions_listing_imo_source"),
    )
    op.create_index("ix_sanctions_listing_imo", "sanctions_listing", ["imo"])

    # ------------------------------------------------------------------
    # sanctions_match
    # One row per (vessel, opensanctions entity) match attempt.
    # match_method values: 'imo_exact', 'name_flag_fuzzy', 'name_fuzzy', 'org_link'
    # status values: 'auto_confirmed', 'pending', 'confirmed', 'rejected'
    # ADR-0005: only 'imo_exact' may ever produce status='auto_confirmed'.
    # ------------------------------------------------------------------
    op.create_table(
        "sanctions_match",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("os_entity_id", sa.String(100), nullable=False),
        sa.Column(
            "match_method",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("confidence", sa.Float),
        sa.Column("reviewer_note", sa.Text),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
            # ADR-0005: IMO-exact-only auto-confirm — hardcoded, never relax
            "NOT (status = 'auto_confirmed' AND match_method != 'imo_exact')",
            name="ck_sanctions_match_auto_confirm_imo_only",
        ),
        sa.UniqueConstraint("imo", "os_entity_id", name="uq_sanctions_match_imo_entity"),
    )
    op.create_index("ix_sanctions_match_imo", "sanctions_match", ["imo"])
    op.create_index(
        "ix_sanctions_match_pending",
        "sanctions_match",
        ["status"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # ------------------------------------------------------------------
    # sanctions_match_history
    # Audit trail: every status transition for every match row.
    # ------------------------------------------------------------------
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
        sa.Column(
            "changed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_smh_match_id", "sanctions_match_history", ["sanctions_match_id"]
    )

    # ------------------------------------------------------------------
    # staging_opensanctions_ingest
    # Ops Swarm writes here; oceansx_promote role moves to production.
    # ------------------------------------------------------------------
    op.create_table(
        "staging_opensanctions_ingest",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("os_entity_id", sa.String(100), nullable=False),
        sa.Column("schema_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("dataset", sa.String(100)),
        sa.Column("file_date", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "staged_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="staged"),
        sa.CheckConstraint(
            "status IN ('staged', 'promoted', 'rejected')",
            name="ck_staging_os_status",
        ),
    )
    op.create_index(
        "ix_staging_os_status", "staging_opensanctions_ingest", ["status"]
    )

    # ------------------------------------------------------------------
    # staging_sanctions_match
    # Ops Swarm proposed matches waiting for oceansx_promote approval.
    # ------------------------------------------------------------------
    op.create_table(
        "staging_sanctions_match",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("imo", sa.BigInteger, nullable=False),
        sa.Column("os_entity_id", sa.String(100), nullable=False),
        sa.Column("match_method", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column(
            "staged_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="staged"),
        sa.CheckConstraint(
            "status IN ('staged', 'promoted', 'rejected')",
            name="ck_staging_sm_status",
        ),
    )
    op.create_index("ix_staging_sm_imo", "staging_sanctions_match", ["imo"])

    # ------------------------------------------------------------------
    # agent_review_queue
    # Human review queue: non-IMO matches that cannot auto-confirm.
    # ------------------------------------------------------------------
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
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status IN ('open', 'confirmed', 'rejected')",
            name="ck_arq_status",
        ),
    )
    op.create_index(
        "ix_arq_status_open",
        "agent_review_queue",
        ["created_at"],
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_index("ix_arq_imo", "agent_review_queue", ["imo"])

    # ------------------------------------------------------------------
    # mou_inspection
    # Tokyo MoU Port State Control detention records.
    # ------------------------------------------------------------------
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
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_mou_inspection_imo", "mou_inspection", ["imo"])
    op.create_index(
        "ix_mou_inspection_detained",
        "mou_inspection",
        ["imo"],
        postgresql_where=sa.text("detained = true"),
    )

    # ------------------------------------------------------------------
    # ADD CHECK constraint to vessel.current_sanctions_status
    # Missing from 0002 (no CHECK was specified there).
    # ------------------------------------------------------------------
    op.create_check_constraint(
        "ck_vessel_sanctions_status",
        "vessel",
        "current_sanctions_status IN ('clean', 'sanctioned', 'pending', 'prev_sanctioned')",
    )

    # ------------------------------------------------------------------
    # GRANT staging_* tables to oceansx_ops (INSERT only — ADR-0007)
    # ------------------------------------------------------------------
    op.execute(
        "GRANT INSERT ON staging_opensanctions_ingest TO oceansx_ops"
    )
    op.execute(
        "GRANT INSERT ON staging_sanctions_match TO oceansx_ops"
    )
    # oceansx_app needs full access for the scheduler and promotion flow
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON opensanctions_entity_raw TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON organization TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON organization_alias TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON organization_topic TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON vessel_organization_link TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON vessel_topic TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON sanctions_source TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON sanctions_listing TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON sanctions_match TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON sanctions_match_history TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON staging_opensanctions_ingest TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON staging_sanctions_match TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON agent_review_queue TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON mou_inspection TO oceansx_app"
    )
    op.execute(
        "GRANT SELECT ON opensanctions_entity_raw TO oceansx_readonly"
    )
    op.execute(
        "GRANT SELECT ON organization TO oceansx_readonly"
    )
    op.execute(
        "GRANT SELECT ON sanctions_match TO oceansx_readonly"
    )
    op.execute(
        "GRANT SELECT ON agent_review_queue TO oceansx_readonly"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mou_inspection CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_review_queue CASCADE")
    op.execute("DROP TABLE IF EXISTS staging_sanctions_match CASCADE")
    op.execute("DROP TABLE IF EXISTS staging_opensanctions_ingest CASCADE")
    op.execute("DROP TABLE IF EXISTS sanctions_match_history CASCADE")
    op.execute("DROP TABLE IF EXISTS sanctions_match CASCADE")
    op.execute("DROP TABLE IF EXISTS sanctions_listing CASCADE")
    op.execute("DROP TABLE IF EXISTS sanctions_source CASCADE")
    # vessel_topic was created in 0002; just reverse the Phase 4a alterations
    op.execute("DROP INDEX IF EXISTS ix_vessel_topic_shadow")
    op.execute("DROP INDEX IF EXISTS ix_vessel_topic_imo_topic")
    op.execute("ALTER TABLE vessel_topic ALTER COLUMN topic TYPE VARCHAR(50)")
    op.execute("ALTER TABLE vessel_topic ALTER COLUMN os_entity_id SET NOT NULL")
    op.execute("ALTER TABLE vessel_topic RENAME COLUMN os_entity_id TO source_dataset")
    op.execute("DROP TABLE IF EXISTS vessel_organization_link CASCADE")
    op.execute("DROP TABLE IF EXISTS organization_topic CASCADE")
    op.execute("DROP TABLE IF EXISTS organization_alias CASCADE")
    op.execute("DROP TABLE IF EXISTS organization CASCADE")
    op.execute("DROP TABLE IF EXISTS opensanctions_entity_raw CASCADE")
    op.drop_constraint("ck_vessel_sanctions_status", "vessel", type_="check")
