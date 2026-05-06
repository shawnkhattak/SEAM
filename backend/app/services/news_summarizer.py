from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.anthropic_client import HAIKU_MODEL, call_haiku
from app.models import NewsItem, NewsSummary

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a maritime intelligence analyst. "
    "Summarize the following news article in 2–3 concise sentences. "
    "Focus on vessels, ports, sanctions, and compliance implications. "
    "Return only the summary — no preamble, no commentary."
)


async def get_or_create_summary(session: AsyncSession, news_id: int) -> NewsSummary:
    """Return existing summary or generate one via Haiku. Idempotent."""
    existing = await session.scalar(select(NewsSummary).where(NewsSummary.news_id == news_id))
    if existing is not None:
        return existing

    item = await session.get(NewsItem, news_id)
    if item is None:
        raise ValueError(f"NewsItem {news_id} not found")

    user_message = f"{item.title}\n\n{item.body_text or ''}".strip()
    summary_text, tokens_in, tokens_out = await call_haiku(
        system_prompt=_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=256,
        mock_fixture="haiku_summary_response",
    )

    summary = NewsSummary(
        news_id=news_id,
        summary_text=summary_text,
        model_used=HAIKU_MODEL,
        generated_at_utc=datetime.now(timezone.utc),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    session.add(summary)
    await session.flush()
    logger.info(
        "news_summarizer: generated summary news_id=%d tokens_in=%d tokens_out=%d",
        news_id,
        tokens_in,
        tokens_out,
    )
    return summary
