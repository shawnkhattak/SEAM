"""init extensions and roles

Revision ID: 0001
Revises:
Create Date: 2026-04-30

Enables TimescaleDB, PostGIS, and pg_trgm extensions.
Grants schema usage to application roles.
No table DDL — that starts in Phase 1 migrations.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions (require superuser; already run by init-db.sql on first start,
    # but CREATE EXTENSION IF NOT EXISTS is idempotent so safe to repeat).
    # TimescaleDB is optional — not available in all dev environments.
    op.execute(
        "DO $$ BEGIN "
        "  CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE; "
        "EXCEPTION WHEN OTHERS THEN NULL; END $$"
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis CASCADE")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Grant schema usage to application roles (idempotent).
    for role in ("oceansx_app", "oceansx_ops", "oceansx_promote", "oceansx_readonly"):
        op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")

    # Default privileges: oceansx_app gets read/write on all future tables.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO oceansx_app"
    )
    # oceansx_ops gets SELECT on all future tables (staging INSERT granted per-table in Phase 4).
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT ON TABLES TO oceansx_ops"
    )
    # oceansx_promote gets full access.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO oceansx_promote"
    )
    # oceansx_readonly gets SELECT only.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT ON TABLES TO oceansx_readonly"
    )
    # Sequences
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO oceansx_app, oceansx_ops, oceansx_promote"
    )


def downgrade() -> None:
    # Cannot revoke extensions safely in production; downgrade is a no-op.
    pass
