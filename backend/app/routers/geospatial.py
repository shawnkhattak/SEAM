from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import JSONResponse

from app.clients.oceansx import OceansXClient, get_oceansx_client
from app.limiter import limiter
from app.services.geospatial import VALID_LAYERS, get_layer

router = APIRouter(prefix="/geo", tags=["geospatial"])

_CACHE_24H = "public, max-age=86400"


def _client() -> OceansXClient:
    return get_oceansx_client()


@router.get("/layers")
async def list_layers(request: Request) -> JSONResponse:
    """Available geospatial layer names."""
    return JSONResponse(content=sorted(VALID_LAYERS), headers={"Cache-Control": _CACHE_24H})


@router.get("/layer/{layer_name}")
@limiter.limit("30/minute")
async def get_geospatial_layer(
    request: Request,
    layer_name: str = Path(description="Geospatial layer name"),
    client: OceansXClient = Depends(_client),
) -> JSONResponse:
    """Return a named GeoJSON layer (coastline, dangers, ports, etc.)."""
    if layer_name not in VALID_LAYERS:
        raise HTTPException(status_code=404, detail=f"Unknown layer: {layer_name!r}")
    data = await get_layer(client, layer_name)
    return JSONResponse(content=data, headers={"Cache-Control": _CACHE_24H})
