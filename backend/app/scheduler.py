"""APScheduler job definitions for SEAM.

Key differences from legacy:
  - Enrichment queue: IntervalTrigger(seconds=60) replaces hourly 50-vessel loop.
    dequeue_batch() uses SELECT FOR UPDATE SKIP LOCKED with per-minute rate limit.
  - All API keys read from ConfigCache (not Settings).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 1 jobs
# ---------------------------------------------------------------------------

async def _job_poll_positions() -> None:
    """Fetch current positions, persist to position_live + archive, broadcast SSE."""
    from app.clients.oceansx import get_oceansx_client
    from app.db import get_session_factory
    from app.services import vessels as vessel_svc
    from app.services import vessel_master as vm_svc
    from app.services.enrichment_queue import enqueue_many
    from app.services.history import maybe_write_position_archive, write_position_live
    from app.services.sse_broadcaster import position_broadcaster

    client = get_oceansx_client()
    positions = await vessel_svc.get_live_positions(client)

    written_live = 0
    written_archive = 0
    new_imos: list[int] = []

    async with get_session_factory()() as session:
        for pos in positions:
            is_new = await vm_svc.upsert_vessel(session, pos)
            await write_position_live(session, pos)
            archived = await maybe_write_position_archive(session, pos)
            if archived:
                written_archive += 1
            written_live += 1
            if is_new:
                new_imos.append(pos["imo"])

        # Enqueue new vessels for enrichment at elevated priority
        if new_imos:
            await enqueue_many(session, new_imos, priority=5)

        await session.commit()

    log.info(
        "poll_positions: %d positions, %d live, %d archive, %d new enqueued",
        len(positions), written_live, written_archive, len(new_imos),
    )

    from app import cache as l1_cache
    l1_cache.delete("api:vessels:positions")

    await position_broadcaster.publish(
        "positions_updated",
        {"count": len(positions), "archived": written_archive},
    )


async def _job_enrich_particulars() -> None:
    """Dequeue up to max_enrich_per_minute vessels and fetch their particulars."""
    import httpx

    from app.clients.oceansx import get_oceansx_client
    from app.db import get_session_factory
    from app.services.enrichment_queue import dequeue_batch, mark_failure, mark_success
    from app.services.vessel_master import update_from_particulars

    settings = get_settings()
    client = get_oceansx_client()

    async with get_session_factory()() as session:
        imos = await dequeue_batch(session, max_count=settings.max_enrich_per_minute)
        await session.commit()

    if not imos:
        return

    enriched = 0
    for imo in imos:
        try:
            particulars = await client.vessel_particulars_by_imo(str(imo))
            async with get_session_factory()() as session:
                if particulars:
                    await update_from_particulars(session, imo, particulars)
                await mark_success(session, imo)
                await session.commit()
            enriched += 1
        except httpx.HTTPStatusError as exc:
            is_rl = exc.response.status_code == 429
            async with get_session_factory()() as session:
                await mark_failure(session, imo, str(exc), is_rate_limit=is_rl)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            async with get_session_factory()() as session:
                await mark_failure(session, imo, str(exc)[:200])
                await session.commit()

    log.info("enrich_particulars: %d/%d enriched", enriched, len(imos))


# ---------------------------------------------------------------------------
# Remaining jobs — ported unchanged from legacy
# ---------------------------------------------------------------------------

async def _job_refresh_macro() -> None:
    from app.clients.oceansx import get_oceansx_client
    from app.services import macro as macro_svc
    client = get_oceansx_client()
    try:
        await macro_svc.get_cargo_throughput(client)
        await macro_svc.get_container_throughput(client)
        await macro_svc.get_bunkers_sales(client)
        await macro_svc.get_shipping_tonnage(client)
        await macro_svc.get_vessel_call_volume(client)
        log.info("refresh_macro: all 5 macro series refreshed")
    except Exception as exc:
        log.error("refresh_macro: failed: %s", exc)


async def _job_refresh_news() -> None:
    from app.clients.rss_app import poll_feed
    from app.db import get_session_factory
    from app.services.entity_extraction import extract_entities_for_item
    from app.services.news import get_or_create_feed, ingest_article

    _SLOT_NAMES = {1: "Maritime Feed 1", 2: "Maritime Feed 2", 3: "Maritime Feed 3"}
    total = 0
    for slot in (1, 2, 3):
        articles = await poll_feed(slot)
        if not articles:
            continue
        async with get_session_factory()() as session:
            feed_id = await get_or_create_feed(session, slot=slot, name=_SLOT_NAMES[slot])
            for article in articles:
                item = await ingest_article(session, article, feed_id=feed_id)
                if item:
                    await extract_entities_for_item(session, news_id=item.id, title=item.title, body_text=item.body_text)
                    item.extraction_status = "done"
                    total += 1
            await session.commit()
    log.info("refresh_news: %d new articles", total)


async def _job_extract_entities() -> None:
    from app.db import get_session_factory
    from app.models import NewsItem
    from app.services.entity_extraction import extract_entities_for_item
    from sqlalchemy import select

    async with get_session_factory()() as session:
        pending = (await session.execute(
            select(NewsItem).where(NewsItem.extraction_status == "pending")
            .order_by(NewsItem.published_at_utc.desc()).limit(200)
        )).scalars().all()
        for item in pending:
            try:
                await extract_entities_for_item(session, news_id=item.id, title=item.title, body_text=item.body_text)
                item.extraction_status = "done"
            except Exception as exc:
                log.warning("extract_entities: news_id=%d error: %s", item.id, exc)
                item.extraction_status = "error"
        await session.commit()


async def _job_prune_history() -> None:
    from app.db import get_session_factory
    from app.services.news import prune_old_news

    async with get_session_factory()() as session:
        pruned = await prune_old_news(session, days=90)
        await session.commit()
    log.info("prune_history: pruned %d news articles", pruned)


async def _job_refresh_opensanctions() -> None:
    from app.clients.opensanctions import fetch_maritime_entities
    from app.db import get_session_factory
    from app.services.opensanctions_ingest import ingest_batch
    from app.services.sanctions_matcher import run_matcher

    entities = await fetch_maritime_entities()
    if not entities:
        log.warning("refresh_opensanctions: no entities returned")
        return
    async with get_session_factory()() as session:
        ingest_summary = await ingest_batch(session, entities)
        match_summary = await run_matcher(session, entities)
        await session.commit()
    log.info("refresh_opensanctions: ingest=%s match=%s", ingest_summary, match_summary)


async def _job_refresh_shadow_fleet_flags() -> None:
    from app.db import get_session_factory
    from app.services.shadow_fleet import refresh_shadow_fleet_flags

    async with get_session_factory()() as session:
        summary = await refresh_shadow_fleet_flags(session)
        await session.commit()
    log.info("refresh_shadow_fleet_flags: %s", summary)


async def _job_refresh_geospatial() -> None:
    from app.clients.oceansx import get_oceansx_client
    from app.db import get_session_factory
    from app.services.geospatial import VALID_LAYERS, get_layer
    from app.services.ports import refresh_terminal_polygons

    client = get_oceansx_client()
    errors = []
    for layer in sorted(VALID_LAYERS):
        try:
            await get_layer(client, layer)
        except Exception as exc:
            log.warning("refresh_geospatial: layer=%s error=%s", layer, exc)
            errors.append(layer)
    try:
        ports_geojson = await client.ports_and_services_a()
        async with get_session_factory()() as session:
            n = await refresh_terminal_polygons(session, ports_geojson)
            await session.commit()
        log.info("refresh_geospatial: %d terminal polygons refreshed", n)
    except Exception as exc:
        log.error("refresh_geospatial: terminal refresh failed: %s", exc)
    log.info("refresh_geospatial: errors: %s", errors or "none")


async def _job_pull_weather() -> None:
    from app.db import get_session_factory
    from app.services.weather import pull_and_store_weather

    async with get_session_factory()() as session:
        summary = await pull_and_store_weather(session)
        await session.commit()
    log.info("pull_weather: %s", summary)


async def _job_compute_anchorage_dwell() -> None:
    from app.db import get_session_factory
    from app.services.anchorage_dwell import compute_dwell

    async with get_session_factory()() as session:
        summary = await compute_dwell(session)
        await session.commit()
    log.info("compute_anchorage_dwell: %s", summary)


async def _job_score_risk_hourly() -> None:
    from app.db import get_session_factory
    from app.services.risk_scorer import run_hourly_scoring

    async with get_session_factory()() as session:
        summary = await run_hourly_scoring(session)
        await session.commit()
    log.info("score_risk_hourly: %s", summary)


async def _job_index_journal() -> None:
    from app.db import get_session_factory
    from app.services.journal_indexer import run_journal_indexer

    async with get_session_factory()() as session:
        summary = await run_journal_indexer(session)
        await session.commit()
    log.info("index_journal: %s", summary)


async def _job_dependency_audit() -> None:
    import asyncio
    import json as _json

    from app.db import get_session_factory
    from app.models import DependencyAuditLog
    from app.services.audit_log import append_audit_log
    from app.utils.timezone import utc_now

    async def _run(cmd):
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        return stdout.decode(errors="replace"), proc.returncode or 0

    now = utc_now()
    async with get_session_factory()() as session:
        for ecosystem, cmd in [("python", ["pip-audit", "--format", "json", "--output", "-"])]:
            raw, _ = await _run(cmd)
            try:
                data = _json.loads(raw) if raw.strip() else {}
            except _json.JSONDecodeError:
                data = {}
            vulns = data.get("vulnerabilities", data.get("dependencies", []))
            total = len(vulns) if isinstance(vulns, list) else 0
            session.add(DependencyAuditLog(
                audited_at=now, ecosystem=ecosystem,
                vulnerabilities=data if isinstance(data, dict) else {},
                high_critical_count=total, total_count=total, raw_output=raw[:10_000],
            ))
            if total > 0:
                await append_audit_log(session, actor="cron", action="dependency_audit_alert",
                                       detail={"ecosystem": ecosystem, "total": total}, severity="warning")
        await session.commit()
    log.info("dependency_audit: complete")


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------

def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")

    from app import cache
    scheduler.add_job(cache.sweep_expired, IntervalTrigger(hours=1), id="sweep_cache", replace_existing=True)

    scheduler.add_job(
        _job_poll_positions,
        IntervalTrigger(seconds=settings.poll_positions_seconds),
        id="poll_positions", replace_existing=True, max_instances=1, coalesce=True,
    )

    # Per-minute enrichment queue worker (replaces legacy hourly 50-vessel batch)
    scheduler.add_job(
        _job_enrich_particulars,
        IntervalTrigger(seconds=settings.enrich_particulars_seconds),
        id="enrich_particulars", replace_existing=True, max_instances=1, coalesce=True,
    )

    scheduler.add_job(_job_refresh_macro, CronTrigger(hour=3, timezone="America/Chicago"), id="refresh_macro", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_refresh_geospatial, CronTrigger(hour=4, timezone="America/Chicago"), id="refresh_geospatial", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_refresh_news, IntervalTrigger(seconds=settings.refresh_news_seconds), id="refresh_news", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_extract_entities, CronTrigger(minute=20, timezone="UTC"), id="extract_entities", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_prune_history, CronTrigger(hour=2, timezone="America/Chicago"), id="prune_history", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_refresh_opensanctions, CronTrigger(hour=4, timezone="America/Chicago"), id="refresh_opensanctions", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_refresh_shadow_fleet_flags, CronTrigger(hour=4, minute=30, timezone="America/Chicago"), id="refresh_shadow_fleet_flags", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_pull_weather, CronTrigger(minute=30, timezone="UTC"), id="pull_weather", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_compute_anchorage_dwell, CronTrigger(minute=10, timezone="UTC"), id="compute_anchorage_dwell", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_score_risk_hourly, CronTrigger(minute=15, timezone="UTC"), id="score_risk_hourly", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_index_journal, CronTrigger(minute=45, timezone="UTC"), id="index_journal", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(_job_dependency_audit, CronTrigger(hour=6, timezone="America/Chicago"), id="dependency_audit", replace_existing=True, max_instances=1, coalesce=True)

    log.info("Scheduler built with %d job(s)", len(scheduler.get_jobs()))
    return scheduler
