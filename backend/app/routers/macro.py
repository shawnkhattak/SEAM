from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.clients.oceansx import OceansXClient, get_oceansx_client
from app.limiter import limiter
from app.services import macro as macro_svc

router = APIRouter(prefix="/macro", tags=["macro"])

_CACHE_1H = "public, max-age=3600"


def _client() -> OceansXClient:
    return get_oceansx_client()


def _json(data: Any) -> JSONResponse:
    return JSONResponse(content=data, headers={"Cache-Control": _CACHE_1H})


@router.get("/cargo/throughput")
@limiter.limit("30/minute")
async def cargo_throughput(
    request: Request,
    months: int = Query(12, ge=1, le=60),
    client: OceansXClient = Depends(_client),
) -> JSONResponse:
    data = await macro_svc.get_cargo_throughput(client, months)
    return _json(data)


@router.get("/container/throughput")
@limiter.limit("30/minute")
async def container_throughput(
    request: Request,
    months: int = Query(12, ge=1, le=60),
    client: OceansXClient = Depends(_client),
) -> JSONResponse:
    data = await macro_svc.get_container_throughput(client, months)
    return _json(data)


@router.get("/bunkers/sales")
@limiter.limit("30/minute")
async def bunkers_sales(
    request: Request,
    months: int = Query(12, ge=1, le=60),
    client: OceansXClient = Depends(_client),
) -> JSONResponse:
    data = await macro_svc.get_bunkers_sales(client, months)
    return _json(data)


@router.get("/shipping/tonnage")
@limiter.limit("30/minute")
async def shipping_tonnage(
    request: Request,
    months: int = Query(12, ge=1, le=60),
    client: OceansXClient = Depends(_client),
) -> JSONResponse:
    data = await macro_svc.get_shipping_tonnage(client, months)
    return _json(data)


@router.get("/vessel-calls")
@limiter.limit("30/minute")
async def vessel_calls(
    request: Request,
    months: int = Query(12, ge=1, le=60),
    client: OceansXClient = Depends(_client),
) -> JSONResponse:
    data = await macro_svc.get_vessel_call_volume(client, months)
    return _json(data)
