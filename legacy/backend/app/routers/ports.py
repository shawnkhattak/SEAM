from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.limiter import limiter
from app.models import Port, PortAlias, Terminal

router = APIRouter(prefix="/ports", tags=["ports"])

_CACHE_1H = "public, max-age=3600"


@router.get("/terminals")
@limiter.limit("30/minute")
async def list_terminals(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """All terminals with their port locode and name."""
    result = await db.execute(
        select(Terminal.id, Terminal.name, Terminal.short_code, Terminal.port_id, Port.locode, Port.name.label("port_name"))
        .join(Port, Terminal.port_id == Port.id, isouter=True)
        .order_by(Port.locode, Terminal.name)
    )
    rows = result.mappings().all()
    data = [dict(r) for r in rows]
    return JSONResponse(content=data, headers={"Cache-Control": _CACHE_1H})
