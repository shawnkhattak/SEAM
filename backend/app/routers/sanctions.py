"""Sanctions API endpoints.

GET  /api/sanctions/vessel/{imo}              — sanctions matches for a vessel
GET  /api/sanctions/review-queue              — admin review queue
POST /api/sanctions/review-queue/{id}/confirm — confirm a match (admin)
POST /api/sanctions/review-queue/{id}/reject  — reject a match (admin)
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import require_admin
from app.db import get_db
from app.limiter import limiter
from app.models import (
    AgentReviewQueue,
    OpenSanctionsEntityRaw,
    SanctionsMatch,
    SanctionsMatchHistory,
)
from app.schemas import ReviewQueueItem, SanctionsMatchResponse
from app.services.audit_log import append_audit_log
from app.utils.timezone import utc_now

router = APIRouter(prefix="/sanctions", tags=["sanctions"])
logger = logging.getLogger(__name__)


def _entity_name(payload: dict[str, Any]) -> str | None:
    props = payload.get("properties", {})
    names = props.get("name", [])
    return names[0] if names else payload.get("caption")


def _entity_datasets(payload: dict[str, Any]) -> list[str]:
    return payload.get("datasets", [])


@router.get("/vessel/{imo}", response_model=list[SanctionsMatchResponse])
@limiter.limit("60/minute")
async def get_vessel_sanctions(
    request: Request,
    imo: Annotated[int, Path(ge=1000000, le=9999999)],
    db: AsyncSession = Depends(get_db),
) -> list[SanctionsMatchResponse]:
    """Return all sanctions matches for a vessel."""
    match_result = await db.execute(
        select(SanctionsMatch)
        .where(SanctionsMatch.imo == imo)
        .order_by(SanctionsMatch.created_at.desc())
    )
    matches = match_result.scalars().all()

    output: list[SanctionsMatchResponse] = []
    for match in matches:
        raw_result = await db.execute(
            select(OpenSanctionsEntityRaw.payload)
            .where(OpenSanctionsEntityRaw.os_entity_id == match.os_entity_id)
            .order_by(OpenSanctionsEntityRaw.ingested_at.desc())
            .limit(1)
        )
        raw_payload = raw_result.scalar_one_or_none() or {}

        output.append(
            SanctionsMatchResponse(
                id=match.id,
                imo=match.imo,
                os_entity_id=match.os_entity_id,
                match_method=match.match_method,
                status=match.status,
                confidence=match.confidence,
                created_at=match.created_at,
                reviewed_at=match.reviewed_at,
                entity_name=_entity_name(raw_payload),
                entity_datasets=_entity_datasets(raw_payload),
            )
        )

    return output


@router.get("/review-queue", response_model=list[ReviewQueueItem])
@limiter.limit("30/minute")
async def get_review_queue(
    request: Request,
    status: str = Query("open", pattern="^(open|confirmed|rejected|all)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[ReviewQueueItem]:
    """Admin: list review queue items."""
    stmt = select(AgentReviewQueue).order_by(AgentReviewQueue.created_at.desc()).limit(limit)
    if status != "all":
        stmt = stmt.where(AgentReviewQueue.status == status)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return [
        ReviewQueueItem(
            id=item.id,
            imo=item.imo,
            os_entity_id=item.os_entity_id,
            match_method=item.match_method,
            confidence=item.confidence,
            match_evidence=item.match_evidence,
            status=item.status,
            reviewer_note=item.reviewer_note,
            created_at=item.created_at,
            resolved_at=item.resolved_at,
        )
        for item in items
    ]


@router.post("/review-queue/{item_id}/confirm", status_code=200)
@limiter.limit("30/minute")
async def confirm_review_item(
    request: Request,
    item_id: Annotated[int, Path(ge=1)],
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, str]:
    """Admin: confirm a review queue item → sanctions_match → confirmed."""
    item_result = await db.execute(
        select(AgentReviewQueue).where(AgentReviewQueue.id == item_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Review queue item not found")
    if item.status != "open":
        raise HTTPException(status_code=409, detail=f"Item already resolved: {item.status}")

    now = utc_now()
    item.status = "confirmed"
    item.resolved_at = now

    match_result = await db.execute(
        select(SanctionsMatch).where(
            SanctionsMatch.imo == item.imo,
            SanctionsMatch.os_entity_id == item.os_entity_id,
        )
    )
    match = match_result.scalar_one_or_none()
    if match is not None:
        old_status = match.status
        match.status = "confirmed"
        match.reviewed_at = now
        db.add(
            SanctionsMatchHistory(
                sanctions_match_id=match.id,
                old_status=old_status,
                new_status="confirmed",
                changed_by="admin",
                changed_at=now,
            )
        )

    await append_audit_log(
        db,
        actor="admin",
        action="sanctions_confirm",
        target_type="review_queue",
        target_id=str(item_id),
        detail={"imo": item.imo, "os_entity_id": item.os_entity_id},
    )
    await db.commit()
    logger.info(
        "review_queue: item=%d confirmed imo=%d entity=%s", item_id, item.imo, item.os_entity_id
    )
    return {"status": "confirmed"}


@router.post("/review-queue/{item_id}/reject", status_code=200)
@limiter.limit("30/minute")
async def reject_review_item(
    request: Request,
    item_id: Annotated[int, Path(ge=1)],
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, str]:
    """Admin: reject a review queue item → sanctions_match → rejected."""
    item_result = await db.execute(
        select(AgentReviewQueue).where(AgentReviewQueue.id == item_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Review queue item not found")
    if item.status != "open":
        raise HTTPException(status_code=409, detail=f"Item already resolved: {item.status}")

    now = utc_now()
    item.status = "rejected"
    item.resolved_at = now

    match_result = await db.execute(
        select(SanctionsMatch).where(
            SanctionsMatch.imo == item.imo,
            SanctionsMatch.os_entity_id == item.os_entity_id,
        )
    )
    match = match_result.scalar_one_or_none()
    if match is not None:
        old_status = match.status
        match.status = "rejected"
        match.reviewed_at = now
        db.add(
            SanctionsMatchHistory(
                sanctions_match_id=match.id,
                old_status=old_status,
                new_status="rejected",
                changed_by="admin",
                changed_at=now,
            )
        )

    await append_audit_log(
        db,
        actor="admin",
        action="sanctions_reject",
        target_type="review_queue",
        target_id=str(item_id),
        detail={"imo": item.imo, "os_entity_id": item.os_entity_id},
    )
    await db.commit()
    logger.info(
        "review_queue: item=%d rejected imo=%d entity=%s", item_id, item.imo, item.os_entity_id
    )
    return {"status": "rejected"}
