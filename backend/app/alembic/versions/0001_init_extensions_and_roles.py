"""init extensions and roles

Revision ID: 0001
Revises:
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis CASCADE")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'seam_app') THEN
                CREATE ROLE seam_app LOGIN PASSWORD 'changeme_app';
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'seam_promote') THEN
                CREATE ROLE seam_promote LOGIN PASSWORD 'changeme_promote';
            END IF;
        END
        $$
    """)


def downgrade() -> None:
    pass
