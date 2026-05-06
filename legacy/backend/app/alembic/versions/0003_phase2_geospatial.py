"""phase 2 geospatial: port, port_alias, terminal_geom, terminal FK, position terminal FKs

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-01

Phase 2: PostGIS terminal polygons, port catalogue, position.terminal_id FK enforcement.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # port — canonical MPA port catalogue
    # ------------------------------------------------------------------
    op.create_table(
        "port",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("locode", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(5)),
        sa.Column("lat", sa.Float),
        sa.Column("lon", sa.Float),
        sa.UniqueConstraint("locode", name="uq_port_locode"),
    )

    # ------------------------------------------------------------------
    # port_alias — alternative names / codes
    # ------------------------------------------------------------------
    op.create_table(
        "port_alias",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("port_id", sa.Integer, nullable=False),
        sa.Column("alias", sa.String(200), nullable=False),
        sa.ForeignKeyConstraint(["port_id"], ["port.id"], ondelete="CASCADE", name="fk_port_alias_port_id"),
    )
    op.create_index("ix_port_alias_alias", "port_alias", ["alias"])

    # ------------------------------------------------------------------
    # terminal — add FK from existing port_id column to port.id
    # (Column already exists as plain Integer from migration 0002)
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_terminal_port_id",
        "terminal",
        "port",
        ["port_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # terminal_geom — PostGIS polygon, GiST indexed
    # ------------------------------------------------------------------
    op.create_table(
        "terminal_geom",
        sa.Column("terminal_id", sa.Integer, primary_key=True),
        sa.Column("geom", Geography(geometry_type="POLYGON", srid=4326), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("buffered", sa.Boolean, nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(
            ["terminal_id"], ["terminal.id"], ondelete="CASCADE", name="fk_terminal_geom_terminal_id"
        ),
    )
    op.execute("CREATE INDEX ix_terminal_geom_gist ON terminal_geom USING gist (geom)")

    # ------------------------------------------------------------------
    # position_live / position_archive — enforce FK on existing terminal_id column
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_pos_live_terminal_id",
        "position_live",
        "terminal",
        ["terminal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_pos_archive_terminal_id",
        "position_archive",
        "terminal",
        ["terminal_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_pos_archive_terminal_id", "position_archive", type_="foreignkey")
    op.drop_constraint("fk_pos_live_terminal_id", "position_live", type_="foreignkey")
    op.execute("DROP INDEX IF EXISTS ix_terminal_geom_gist")
    op.drop_table("terminal_geom")
    op.drop_constraint("fk_terminal_port_id", "terminal", type_="foreignkey")
    op.drop_index("ix_port_alias_alias", table_name="port_alias")
    op.drop_table("port_alias")
    op.drop_table("port")
