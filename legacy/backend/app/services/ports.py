from __future__ import annotations

import logging
from typing import Any

from shapely.geometry import shape
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Port, PortAlias, Terminal

logger = logging.getLogger(__name__)

_FALLBACK_RADIUS_M = 1000.0


def _geojson_to_polygon_wkt(geom_dict: dict[str, Any]) -> str | None:
    """Convert a GeoJSON geometry dict to WKT. Returns None if not a Polygon."""
    if not geom_dict:
        return None
    try:
        geom = shape(geom_dict)
        if geom.geom_type != "Polygon":
            return None
        return geom.wkt
    except Exception:
        return None


async def _upsert_terminal_geom(
    session: AsyncSession,
    terminal_id: int,
    wkt: str,
    source: str,
    buffered: bool,
) -> None:
    """Insert or replace terminal_geom row using a PostGIS geography WKT."""
    if buffered:
        # wkt is a POINT — buffer it to 1 km circle polygon
        sql = (
            "INSERT INTO terminal_geom (terminal_id, geom, source, buffered) "
            "VALUES (:tid, ST_Buffer(ST_GeographyFromText(:wkt), :radius), :src, :buf) "
            "ON CONFLICT (terminal_id) DO UPDATE "
            "SET geom = EXCLUDED.geom, source = EXCLUDED.source, buffered = EXCLUDED.buffered"
        )
        await session.execute(
            text(sql),
            {"tid": terminal_id, "wkt": wkt, "radius": _FALLBACK_RADIUS_M, "src": source, "buf": buffered},
        )
    else:
        sql = (
            "INSERT INTO terminal_geom (terminal_id, geom, source, buffered) "
            "VALUES (:tid, ST_GeographyFromText(:wkt), :src, :buf) "
            "ON CONFLICT (terminal_id) DO UPDATE "
            "SET geom = EXCLUDED.geom, source = EXCLUDED.source, buffered = EXCLUDED.buffered"
        )
        await session.execute(
            text(sql),
            {"tid": terminal_id, "wkt": wkt, "src": source, "buf": buffered},
        )


async def refresh_terminal_polygons(session: AsyncSession, geojson: dict[str, Any]) -> int:
    """Parse ports_and_services_a GeoJSON, upsert Port + Terminal + TerminalGeom rows.

    Returns the number of terminals with geometry written.
    """
    features = geojson.get("features", [])
    processed = 0

    for feature in features:
        props = feature.get("properties") or {}
        geom_dict = feature.get("geometry") or {}
        name = props.get("name") or props.get("terminalName") or ""
        locode = props.get("locode") or props.get("portCode") or name[:10]
        country = props.get("country") or "SG"
        terminal_code = props.get("terminalCode") or props.get("terminalShortCode")

        if not name:
            continue

        # Upsert Port
        port_stmt = (
            insert(Port)
            .values(locode=locode, name=name, country_code=country)
            .on_conflict_do_update(
                index_elements=["locode"],
                set_={"name": name, "country_code": country},
            )
            .returning(Port.id)
        )
        port_result = await session.execute(port_stmt)
        port_id = port_result.scalar_one()

        # Upsert Terminal
        terminal_stmt = (
            insert(Terminal)
            .values(port_id=port_id, name=name, short_code=terminal_code)
            .on_conflict_do_nothing()
            .returning(Terminal.id)
        )
        terminal_result = await session.execute(terminal_stmt)
        terminal_id = terminal_result.scalar_one_or_none()

        if terminal_id is None:
            existing = await session.execute(
                select(Terminal.id).where(Terminal.name == name, Terminal.port_id == port_id)
            )
            terminal_id = existing.scalar_one_or_none()

        if terminal_id is None:
            logger.warning("ports: could not resolve terminal_id for %s", name)
            continue

        # Determine geometry
        wkt = _geojson_to_polygon_wkt(geom_dict)
        buffered = False

        if wkt is None:
            lat = props.get("lat") or props.get("latitude")
            lon = props.get("lon") or props.get("longitude")
            if lat is not None and lon is not None:
                wkt = f"POINT({lon} {lat})"
                buffered = True
            else:
                logger.debug("ports: no polygon or centroid for %s — skipping geom", name)
                continue

        await _upsert_terminal_geom(session, terminal_id, wkt, "ports_and_services_a", buffered)
        processed += 1

    logger.info("ports: refresh_terminal_polygons processed %d terminals", processed)
    return processed


async def find_terminal_for_position(session: AsyncSession, lat: float, lon: float) -> int | None:
    """Return the terminal_id whose polygon contains (lat, lon), or None."""
    result = await session.execute(
        text(
            "SELECT tg.terminal_id "
            "FROM terminal_geom tg "
            "WHERE ST_Within("
            "  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geometry, "
            "  tg.geom::geometry"
            ") "
            "LIMIT 1"
        ),
        {"lat": lat, "lon": lon},
    )
    row = result.fetchone()
    return row[0] if row else None
