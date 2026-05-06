from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewsEntityMention, NewsFeed, NewsItem
from app.utils.timezone import clamp_future, utc_now

logger = logging.getLogger(__name__)


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _parse_published(raw: str) -> datetime:
    """Parse a published timestamp string to UTC datetime. Falls back to now on failure."""
    if not raw:
        return utc_now()
    try:
        # RFC 2822 (RSS default)
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        # ISO 8601
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    logger.debug("news: could not parse published date %r — using now", raw)
    return utc_now()


async def ingest_article(
    session: AsyncSession,
    article: dict[str, Any],
    feed_id: int | None = None,
) -> NewsItem | None:
    """Insert a single article into news_item if the URL has not been seen before.

    Returns the NewsItem if inserted, None if it was a duplicate.
    """
    url = article.get("url", "").strip()
    title = article.get("title", "").strip()
    if not url or not title:
        return None

    url_hash = _hash_url(url)

    # Dedup check
    existing = await session.execute(
        select(NewsItem.id).where(NewsItem.url_hash == url_hash).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return None

    published_raw = article.get("published", "")
    published_dt = _parse_published(published_raw)
    published_dt, was_clamped = clamp_future(published_dt)
    if was_clamped:
        logger.debug("news: clamped future-dated article: %s", url)

    now = utc_now()
    item = NewsItem(
        feed_id=feed_id,
        title=title,
        url=url,
        url_hash=url_hash,
        body_text=article.get("body_text") or None,
        published_at_utc=published_dt,
        ingested_at_utc=now,
        extraction_status="pending",
    )
    session.add(item)
    await session.flush()  # populate item.id before returning
    return item


async def get_or_create_feed(session: AsyncSession, slot: int, name: str, url: str | None = None) -> int:
    """Return feed_id for the given slot, inserting a row if needed."""
    result = await session.execute(
        select(NewsFeed.id).where(NewsFeed.feed_slot == slot)
    )
    feed_id = result.scalar_one_or_none()
    if feed_id is not None:
        return feed_id

    feed = NewsFeed(feed_slot=slot, name=name, url=url, active=True)
    session.add(feed)
    await session.flush()
    return feed.id


async def get_recent_news(
    session: AsyncSession,
    limit: int = 50,
    entity_type: str | None = None,
    entity_ref_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return recent news items, optionally filtered to a specific entity."""
    from sqlalchemy import desc

    if entity_type and entity_ref_id is not None:
        # Filtered by entity
        stmt = (
            select(NewsItem)
            .join(NewsEntityMention, NewsEntityMention.news_id == NewsItem.id)
            .where(
                NewsEntityMention.entity_type == entity_type,
                NewsEntityMention.entity_ref_id == entity_ref_id,
            )
            .order_by(desc(NewsItem.published_at_utc))
            .limit(limit)
        )
    else:
        stmt = (
            select(NewsItem)
            .order_by(desc(NewsItem.published_at_utc))
            .limit(limit)
        )

    result = await session.execute(stmt)
    items = result.scalars().all()

    output: list[dict[str, Any]] = []
    for item in items:
        # Load entity mentions
        mention_result = await session.execute(
            select(NewsEntityMention).where(NewsEntityMention.news_id == item.id)
        )
        mentions = mention_result.scalars().all()
        output.append({
            "id": item.id,
            "title": item.title,
            "url": item.url,
            "published_at_utc": item.published_at_utc.isoformat(),
            "ingested_at_utc": item.ingested_at_utc.isoformat(),
            "extraction_status": item.extraction_status,
            "body_text": item.body_text,
            "entities": [
                {
                    "entity_type": m.entity_type,
                    "entity_ref_id": m.entity_ref_id,
                    "matched_text": m.matched_text,
                }
                for m in mentions
            ],
        })

    return output


async def prune_old_news(session: AsyncSession, days: int = 90) -> int:
    """Delete news_item rows older than `days` days. Returns count deleted."""
    from datetime import timedelta
    cutoff = utc_now() - timedelta(days=days)
    result = await session.execute(
        delete(NewsItem).where(NewsItem.published_at_utc < cutoff)
    )
    count = result.rowcount
    if count:
        logger.info("news: pruned %d articles older than %d days", count, days)
    return count
