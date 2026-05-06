"""phase 3 news: news_feed, news_item, news_entity_mention, news_summary

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-01

Phase 3: RSS.app feed registry, article ingestion, entity-aware mentions, AI summary stub.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # news_feed — RSS.app feed registry (one row per slot)
    # ------------------------------------------------------------------
    op.create_table(
        "news_feed",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("feed_slot", sa.Integer, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("url", sa.String(500)),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint("feed_slot", name="uq_news_feed_slot"),
    )

    # ------------------------------------------------------------------
    # news_item — individual articles
    # ------------------------------------------------------------------
    op.create_table(
        "news_item",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("feed_id", sa.Integer, sa.ForeignKey("news_feed.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("body_text", sa.Text),
        sa.Column("published_at_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ingested_at_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("extraction_status", sa.String(30), nullable=False, server_default="pending"),
        sa.UniqueConstraint("url_hash", name="uq_news_item_url_hash"),
        sa.CheckConstraint(
            "extraction_status IN ('pending', 'done', 'error')",
            name="ck_news_item_extraction_status",
        ),
    )
    # Mandatory indexes (advisor-specified)
    op.create_index(
        "ix_news_item_published_at",
        "news_item",
        [sa.text("published_at_utc DESC")],
    )
    op.create_index(
        "ix_news_item_extraction_status",
        "news_item",
        ["extraction_status", "published_at_utc"],
    )

    # ------------------------------------------------------------------
    # news_entity_mention — entities found inside an article
    # ------------------------------------------------------------------
    op.create_table(
        "news_entity_mention",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "news_id",
            sa.Integer,
            sa.ForeignKey("news_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_ref_id", sa.Integer, nullable=False),
        sa.Column("matched_text", sa.String(300), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
    )
    op.create_index("ix_news_entity_mention_news_id", "news_entity_mention", ["news_id"])
    op.create_index(
        "ix_news_entity_mention_lookup",
        "news_entity_mention",
        ["entity_type", "entity_ref_id", "news_id"],
    )

    # ------------------------------------------------------------------
    # news_summary — AI-generated summaries (populated in Phase 6)
    # ------------------------------------------------------------------
    op.create_table(
        "news_summary",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "news_id",
            sa.Integer,
            sa.ForeignKey("news_item.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("summary_text", sa.Text, nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("generated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("news_summary")
    op.drop_index("ix_news_entity_mention_lookup", table_name="news_entity_mention")
    op.drop_index("ix_news_entity_mention_news_id", table_name="news_entity_mention")
    op.drop_table("news_entity_mention")
    op.drop_index("ix_news_item_extraction_status", table_name="news_item")
    op.drop_index("ix_news_item_published_at", table_name="news_item")
    op.drop_table("news_item")
    op.drop_table("news_feed")
