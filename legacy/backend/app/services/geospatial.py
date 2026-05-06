from __future__ import annotations

from typing import Any

from app.clients.oceansx import OceansXClient

_GEO_LAYERS = {
    "coastline_a": "coastline_a",
    "coastline_l": "coastline_l",
    "dangers_a": "dangers_a",
    "dangers_l": "dangers_l",
    "dangers_p": "dangers_p",
    "aids_to_navigation_p": "aids_to_navigation_p",
    "ports_and_services_a": "ports_and_services_a",
    "ports_and_services_l": "ports_and_services_l",
    "ports_and_services_p": "ports_and_services_p",
    "offshore_installations_a": "offshore_installations_a",
    "offshore_installations_l": "offshore_installations_l",
}

VALID_LAYERS = frozenset(_GEO_LAYERS)


async def get_layer(client: OceansXClient, layer: str) -> dict[str, Any]:
    """Fetch a named geospatial layer from the OceansX API."""
    if layer not in VALID_LAYERS:
        raise ValueError(f"Unknown geospatial layer: {layer!r}")
    method = getattr(client, layer)
    return await method()
