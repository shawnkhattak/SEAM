from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import feedparser

from app.config import get_settings

logger = logging.getLogger(__name__)

_FEED_SLOTS = (1, 2, 3)


def verify_hmac(raw_body: bytes, slot: int, signature_header: str) -> bool:
    """Return True if signature_header matches HMAC-SHA256 of raw_body for the given feed slot.

    Must be called with raw request bytes — not re-serialised JSON — to guarantee
    byte-exact matching regardless of key ordering or whitespace.
    """
    settings = get_settings()
    secret = getattr(settings, f"rss_app_feed_{slot}_hmac", "")
    if not secret:
        logger.warning("rss_app: no HMAC secret configured for slot %d — rejecting", slot)
        return False

    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    # RSS.app sends the signature as "sha256=<hex>" or plain hex
    candidate = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, candidate)


def parse_webhook_payload(raw_body: bytes) -> list[dict[str, Any]]:
    """Extract article dicts from an RSS.app webhook payload.

    Tolerates both the wrapped form ``{"items": [...]}`` and a bare list.
    Each returned dict is guaranteed to have at least: title, url, published.
    """
    import json

    try:
        data = json.loads(raw_body)
    except Exception:
        logger.warning("rss_app: webhook body is not valid JSON")
        return []

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("items") or data.get("entries") or []
    else:
        return []

    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or ""
        url = item.get("url") or item.get("link") or item.get("guid") or ""
        if not title or not url:
            continue
        result.append({
            "title": title.strip(),
            "url": url.strip(),
            "published": item.get("published") or item.get("date_published") or item.get("pubDate") or "",
            "body_text": item.get("content_text") or item.get("content") or item.get("summary") or item.get("description") or "",
        })
    return result


async def poll_feed(slot: int) -> list[dict[str, Any]]:
    """Fetch an RSS feed via feedparser and return article dicts in the same shape as parse_webhook_payload."""
    settings = get_settings()
    url = getattr(settings, f"rss_app_feed_{slot}_url", "")
    if not url:
        logger.debug("rss_app: no URL configured for slot %d — skipping poll", slot)
        return []

    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        logger.warning("rss_app: feedparser error for slot %d: %s", slot, exc)
        return []

    result: list[dict[str, Any]] = []
    for entry in feed.entries:
        title = getattr(entry, "title", "") or ""
        url_val = getattr(entry, "link", "") or ""
        if not title or not url_val:
            continue
        published = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
        body = getattr(entry, "summary", "") or ""
        result.append({
            "title": title.strip(),
            "url": url_val.strip(),
            "published": published,
            "body_text": body,
        })

    logger.info("rss_app: polled slot %d — %d articles", slot, len(result))
    return result
