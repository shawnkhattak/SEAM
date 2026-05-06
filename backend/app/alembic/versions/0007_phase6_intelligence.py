"""phase6_intelligence — tokens_in/tokens_out on news_summary

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_summary", sa.Column("tokens_in", sa.Integer(), nullable=True))
    op.add_column("news_summary", sa.Column("tokens_out", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("news_summary", "tokens_out")
    op.drop_column("news_summary", "tokens_in")
