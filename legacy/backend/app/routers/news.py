from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.rss_app import parse_webhook_payload, verify_hmac
from app.db import get_db
from app.limiter import limiter
from app.schemas import NewsSummaryResponse
from app.services.entity_extraction import extract_entities_for_item
from app.services.news import get_or_create_feed, get_recent_news, ingest_article
from app.services.news_summarizer import get_or_create_summary

router = APIRouter(prefix="/news", tags=["news"])
logger = logging.getLogger(__name__)

_SLOT_NAMES = {1: "Maritime Feed 1", 2: "Maritime Feed 2", 3: "Maritime Feed 3"}


@router.post("/ingest/{feed_slot}", status_code=202)
async def webhook_ingest(
    request: Request,
    feed_slot: Annotated[int, Path(ge=1, le=3)],
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive an RSS.app webhook push for a feed slot.

    The HMAC-SHA256 signature must be present in X-Hub-Signature-256 or X-RSS-Signature.
    Verification runs against the raw request bytes — not re-serialised JSON.
    """
    raw_body = await request.body()
    signature = (
        request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-RSS-Signature")
        or ""
    )

    if not verify_hmac(raw_body, feed_slot, signature):
        raise HTTPException(status_code=401, detail="HMAC verification failed")

    articles = parse_webhook_payload(raw_body)
    if not articles:
        return {"accepted": 0, "duplicate": 0}

    feed_id = await get_or_create_feed(
        session,
        slot=feed_slot,
        name=_SLOT_NAMES.get(feed_slot, f"Feed {feed_slot}"),
    )

    accepted = 0
    duplicate = 0
    for article in articles:
        item = await ingest_article(session, article, feed_id=feed_id)
        if item is None:
            duplicate += 1
        else:
            await extract_entities_for_item(
                session,
                news_id=item.id,
                title=item.title,
                body_text=item.body_text,
            )
            item.extraction_status = "done"
            accepted += 1

    await session.commit()
    logger.info("news/ingest: slot=%d accepted=%d duplicate=%d", feed_slot, accepted, duplicate)
    return {"accepted": accepted, "duplicate": duplicate}


@router.post("/{news_id}/summarize", response_model=NewsSummaryResponse)
@limiter.limit("20/minute")
async def summarize_item(
    request: Request,
    news_id: Annotated[int, Path(ge=1)],
    session: AsyncSession = Depends(get_db),
) -> NewsSummaryResponse:
    """Generate or return a cached AI summary for a news article."""
    from fastapi import HTTPException

    try:
        summary = await get_or_create_summary(session, news_id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return NewsSummaryResponse(
        id=summary.id,
        news_id=summary.news_id,
        summary_text=summary.summary_text,
        model_used=summary.model_used,
        generated_at_utc=summary.generated_at_utc,
        tokens_in=summary.tokens_in,
        tokens_out=summary.tokens_out,
    )


@router.get("/items")
@limiter.limit("60/minute")
async def list_news_items(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    entity_type: Annotated[str | None, Query()] = None,
    entity_ref_id: Annotated[int | None, Query()] = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return recent news articles, optionally filtered to a specific entity."""
    return await get_recent_news(
        session,
        limit=limit,
        entity_type=entity_type,
        entity_ref_id=entity_ref_id,
    )
