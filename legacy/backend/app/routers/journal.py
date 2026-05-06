"""Public read-only journal endpoints — phases, ADRs, glossary."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.limiter import limiter
from app.models import GlossaryTerm, JournalAdr, JournalPhase

router = APIRouter(prefix="/journal", tags=["journal"])
logger = logging.getLogger(__name__)


@router.get("/phases", response_model=list[dict[str, Any]])
@limiter.limit("60/minute")
async def list_phases(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await db.execute(select(JournalPhase).order_by(JournalPhase.phase_number))
    rows = result.scalars().all()
    return [
        {
            "phase_number": r.phase_number,
            "title": r.title,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "summary_md": r.summary_md,
            "markdown_file_path": r.markdown_file_path,
            "indexed_at": r.indexed_at,
        }
        for r in rows
    ]


@router.get("/adrs", response_model=list[dict[str, Any]])
@limiter.limit("60/minute")
async def list_adrs(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await db.execute(select(JournalAdr).order_by(JournalAdr.adr_number))
    rows = result.scalars().all()
    return [
        {
            "adr_number": r.adr_number,
            "title": r.title,
            "status": r.status,
            "decided_at": r.decided_at,
            "summary_md": r.summary_md,
            "markdown_file_path": r.markdown_file_path,
            "superseded_by_adr_number": r.superseded_by_adr_number,
            "indexed_at": r.indexed_at,
        }
        for r in rows
    ]


@router.get("/glossary", response_model=list[dict[str, Any]])
@limiter.limit("60/minute")
async def list_glossary(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await db.execute(select(GlossaryTerm).order_by(GlossaryTerm.term))
    rows = result.scalars().all()
    return [
        {
            "term": r.term,
            "category": r.category,
            "plain_definition": r.plain_definition,
            "why_it_matters_in_project": r.why_it_matters_in_project,
            "markdown_file_path": r.markdown_file_path,
            "indexed_at": r.indexed_at,
        }
        for r in rows
    ]
