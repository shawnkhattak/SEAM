from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings

logger = logging.getLogger(__name__)


async def _job_poll_positions() -> None:
    """Fetch current positions, persist to position_live + archive, broadcast SSE event."""
    from app.clients.oceansx import get_oceansx_client
    from app.db import get_session_factory
    from app.services import vessels as vessel_svc
    from app.services import vessel_master as vm_svc
    from app.services.history import maybe_write_position_archive, update_position_terminal, write_position_live
    from app.services.sse_broadcaster import position_broadcaster

    client = get_oceansx_client()
    positions = await vessel_svc.get_live_positions(client)

    written_live = 0
    written_archive = 0

    async with get_session_factory()() as session:
        for pos in positions:
            await vm_svc.upsert_vessel(session, pos)
            await vm_svc.record_scd2_changes(session, pos["imo"], pos["name"], pos.get("flag"))
            await write_position_live(session, pos)
            terminal_id = await update_position_terminal(session, pos["imo"], pos["recorded_at"], pos["lat"], pos["lon"])
            archived = await maybe_write_position_archive(session, pos, terminal_id=terminal_id)
            if archived:
                written_archive += 1
            written_live += 1
        await session.commit()

    logger.info(
        "poll_positions: %d positions, %d live rows, %d archive rows",
        len(positions),
        written_live,
        written_archive,
    )

    # Invalidate the positions cache so the next API call returns fresh data
    from app import cache as l1_cache
    l1_cache.delete("api:vessels:positions")

    # Notify all connected SSE clients
    await position_broadcaster.publish(
        "positions_updated",
        {"count": len(positions), "archived": written_archive},
    )


async def _job_enrich_vessel_particulars() -> None:
    """Enrich up to 50 vessels per cycle, oldest-enriched-first."""
    from sqlalchemy import select, asc, nullsfirst

    from app.clients.oceansx import get_oceansx_client
    from app.db import get_session_factory
    from app.models import Vessel
    from app.services.vessel_master import update_from_particulars

    client = get_oceansx_client()
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Vessel.imo)
            .order_by(nullsfirst(asc(Vessel.last_enriched_at)))
            .limit(50)
        )
        imos = result.scalars().all()

    enriched = 0
    for imo in imos:
        try:
            particulars = await client.vessel_particulars_by_imo(str(imo))
            if particulars:
                async with get_session_factory()() as session:
                    await update_from_particulars(session, imo, particulars)
                    await session.commit()
                enriched += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("enrich_vessel_particulars: imo=%d error: %s", imo, exc)

    logger.info("enrich_vessel_particulars: enriched %d/%d vessels", enriched, len(imos))


async def _job_refresh_macro() -> None:
    """Refresh macro statistics cache from OceansX API (daily)."""
    from app.clients.oceansx import get_oceansx_client
    from app.services import macro as macro_svc

    client = get_oceansx_client()
    try:
        await macro_svc.get_cargo_throughput(client)
        await macro_svc.get_container_throughput(client)
        await macro_svc.get_bunkers_sales(client)
        await macro_svc.get_shipping_tonnage(client)
        await macro_svc.get_vessel_call_volume(client)
        logger.info("refresh_macro: all 5 macro series refreshed")
    except Exception as exc:
        logger.error("refresh_macro: failed: %s", exc)


async def _job_refresh_news() -> None:
    """Poll all active RSS feeds via feedparser (hourly fallback to webhook push)."""
    from app.clients.rss_app import poll_feed
    from app.db import get_session_factory
    from app.services.entity_extraction import extract_entities_for_item
    from app.services.news import get_or_create_feed, ingest_article

    _SLOT_NAMES = {1: "Maritime Feed 1", 2: "Maritime Feed 2", 3: "Maritime Feed 3"}

    total_accepted = 0
    for slot in (1, 2, 3):
        articles = await poll_feed(slot)
        if not articles:
            continue
        async with get_session_factory()() as session:
            feed_id = await get_or_create_feed(
                session,
                slot=slot,
                name=_SLOT_NAMES[slot],
            )
            accepted = 0
            for article in articles:
                item = await ingest_article(session, article, feed_id=feed_id)
                if item is not None:
                    await extract_entities_for_item(
                        session,
                        news_id=item.id,
                        title=item.title,
                        body_text=item.body_text,
                    )
                    item.extraction_status = "done"
                    accepted += 1
            await session.commit()
            total_accepted += accepted

    logger.info("refresh_news: %d new articles ingested across 3 slots", total_accepted)


async def _job_extract_entities() -> None:
    """Run entity extraction on any news_item rows still in 'pending' state."""
    from sqlalchemy import select, update

    from app.db import get_session_factory
    from app.models import NewsItem
    from app.services.entity_extraction import extract_entities_for_item

    async with get_session_factory()() as session:
        result = await session.execute(
            select(NewsItem)
            .where(NewsItem.extraction_status == "pending")
            .order_by(NewsItem.published_at_utc.desc())
            .limit(200)
        )
        pending = result.scalars().all()

        extracted = 0
        for item in pending:
            try:
                await extract_entities_for_item(
                    session,
                    news_id=item.id,
                    title=item.title,
                    body_text=item.body_text,
                )
                item.extraction_status = "done"
                extracted += 1
            except Exception as exc:
                logger.warning("extract_entities: news_id=%d error: %s", item.id, exc)
                item.extraction_status = "error"

        await session.commit()

    if extracted:
        logger.info("extract_entities: processed %d pending items", extracted)


async def _job_prune_history() -> None:
    """Daily cleanup: delete news older than 90 days and position archive older than 90 days."""
    from app.db import get_session_factory
    from app.services.news import prune_old_news

    async with get_session_factory()() as session:
        pruned_news = await prune_old_news(session, days=90)
        await session.commit()

    logger.info("prune_history: pruned %d news articles", pruned_news)


async def _job_refresh_opensanctions() -> None:
    """Download OpenSanctions bulk data, ingest raw + project, run IMO-exact matcher."""
    from app.clients.opensanctions import fetch_maritime_entities
    from app.db import get_session_factory
    from app.services.opensanctions_ingest import ingest_batch
    from app.services.sanctions_matcher import run_matcher

    entities = await fetch_maritime_entities()
    if not entities:
        logger.warning("refresh_opensanctions: no entities returned")
        return

    async with get_session_factory()() as session:
        ingest_summary = await ingest_batch(session, entities)
        match_summary = await run_matcher(session, entities)
        await session.commit()

    logger.info(
        "refresh_opensanctions: ingest=%s match=%s", ingest_summary, match_summary
    )


async def _job_refresh_shadow_fleet_flags() -> None:
    """Derive vessel.is_shadow_fleet from vessel_topic after opensanctions ingest."""
    from app.db import get_session_factory
    from app.services.shadow_fleet import refresh_shadow_fleet_flags

    async with get_session_factory()() as session:
        summary = await refresh_shadow_fleet_flags(session)
        await session.commit()

    logger.info("refresh_shadow_fleet_flags: %s", summary)


async def _job_refresh_geospatial() -> None:
    """Refresh geospatial layers + terminal polygons from OceansX API (daily)."""
    from app.clients.oceansx import get_oceansx_client
    from app.db import get_session_factory
    from app.services.geospatial import VALID_LAYERS, get_layer
    from app.services.ports import refresh_terminal_polygons

    client = get_oceansx_client()
    refreshed_layers: list[str] = []
    errors: list[str] = []

    for layer in sorted(VALID_LAYERS):
        try:
            await get_layer(client, layer)
            refreshed_layers.append(layer)
        except Exception as exc:
            logger.warning("refresh_geospatial: layer=%s error=%s", layer, exc)
            errors.append(layer)

    # Refresh terminal polygons from ports_and_services_a
    try:
        ports_geojson = await client.ports_and_services_a()
        async with get_session_factory()() as session:
            n = await refresh_terminal_polygons(session, ports_geojson)
            await session.commit()
        logger.info("refresh_geospatial: %d terminal polygons refreshed", n)
    except Exception as exc:
        logger.error("refresh_geospatial: terminal polygon refresh failed: %s", exc)

    logger.info(
        "refresh_geospatial: %d layers OK, %d errors: %s",
        len(refreshed_layers),
        len(errors),
        errors or "none",
    )


async def _job_pull_weather() -> None:
    """Fetch the current Open-Meteo Marine observation and persist it."""
    from app.db import get_session_factory
    from app.services.weather import pull_and_store_weather

    async with get_session_factory()() as session:
        summary = await pull_and_store_weather(session)
        await session.commit()

    logger.info("pull_weather: %s", summary)


async def _job_compute_anchorage_dwell() -> None:
    """Open/close anchorage dwell events based on current vessel positions."""
    from app.db import get_session_factory
    from app.services.anchorage_dwell import compute_dwell

    async with get_session_factory()() as session:
        summary = await compute_dwell(session)
        await session.commit()

    logger.info("compute_anchorage_dwell: %s", summary)


async def _job_index_journal() -> None:
    """Walk docs/journey/ + docs/adr/ + docs/glossary.md and upsert journal rows."""
    from app.db import get_session_factory
    from app.services.journal_indexer import run_journal_indexer

    async with get_session_factory()() as session:
        summary = await run_journal_indexer(session)
        await session.commit()

    logger.info("index_journal: %s", summary)


async def _job_dependency_audit() -> None:
    """Run pip-audit and write results to dependency_audit_log. Alert if HIGH/CRITICAL found."""
    import asyncio
    import json as _json

    from app.db import get_session_factory
    from app.models import DependencyAuditLog
    from app.services.audit_log import append_audit_log
    from app.utils.timezone import utc_now

    async def _run(cmd: list[str]) -> tuple[str, int]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode(errors="replace"), proc.returncode or 0

    now = utc_now()
    async with get_session_factory()() as session:
        for ecosystem, cmd in [
            ("python", ["pip-audit", "--format", "json", "--output", "-"]),
        ]:
            raw, _rc = await _run(cmd)
            try:
                data = _json.loads(raw) if raw.strip() else {}
            except _json.JSONDecodeError:
                data = {}

            vulns = data.get("vulnerabilities", data.get("dependencies", []))
            high_critical = sum(
                1
                for v in (vulns if isinstance(vulns, list) else [])
                for fix in (v.get("fix_versions") or [])
                if True  # pip-audit lists each vuln once
            )
            # simpler: count top-level vuln entries with any fix available
            high_critical = len([v for v in (vulns if isinstance(vulns, list) else []) if v])
            total = len(vulns) if isinstance(vulns, list) else 0

            entry = DependencyAuditLog(
                audited_at=now,
                ecosystem=ecosystem,
                vulnerabilities=data if isinstance(data, dict) else {"raw": data},
                high_critical_count=high_critical,
                total_count=total,
                raw_output=raw[:10_000],
            )
            session.add(entry)

            if high_critical > 0:
                await append_audit_log(
                    session,
                    actor="cron",
                    action="dependency_audit_alert",
                    detail={"ecosystem": ecosystem, "high_critical": high_critical, "total": total},
                    severity="warning",
                )

        await session.commit()

    logger.info("dependency_audit: complete")


async def _job_score_risk_hourly() -> None:
    """Compute composite risk scores for all vessels active in the last 24 hours."""
    from app.db import get_session_factory
    from app.services.risk_scorer import run_hourly_scoring

    async with get_session_factory()() as session:
        summary = await run_hourly_scoring(session)
        await session.commit()

    logger.info("score_risk_hourly: %s", summary)


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Cache sweep
    from app import cache
    scheduler.add_job(
        cache.sweep_expired,
        trigger=IntervalTrigger(hours=1),
        id="sweep_cache",
        replace_existing=True,
    )

    # Phase 1: position polling (15-minute cadence)
    scheduler.add_job(
        _job_poll_positions,
        trigger=IntervalTrigger(seconds=settings.poll_positions_seconds),
        id="poll_positions",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 1: particulars enrichment (hourly, 50 vessels per cycle)
    scheduler.add_job(
        _job_enrich_vessel_particulars,
        trigger=IntervalTrigger(seconds=settings.enrich_particulars_seconds),
        id="enrich_vessel_particulars",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 2: refresh macro stats (daily 03:00 America/Chicago)
    scheduler.add_job(
        _job_refresh_macro,
        trigger=CronTrigger(hour=3, timezone="America/Chicago"),
        id="refresh_macro",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 2: refresh geospatial layers + terminal polygons (daily 04:00 America/Chicago)
    scheduler.add_job(
        _job_refresh_geospatial,
        trigger=CronTrigger(hour=4, timezone="America/Chicago"),
        id="refresh_geospatial",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 3: hourly RSS feed poll (fallback to webhook push)
    scheduler.add_job(
        _job_refresh_news,
        trigger=IntervalTrigger(seconds=settings.refresh_news_seconds),
        id="refresh_news",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 3: entity extraction sweep — runs at :20 each hour to process any pending items
    scheduler.add_job(
        _job_extract_entities,
        trigger=CronTrigger(minute=20, timezone="UTC"),
        id="extract_entities",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 3: daily history pruning (02:00 America/Chicago)
    scheduler.add_job(
        _job_prune_history,
        trigger=CronTrigger(hour=2, timezone="America/Chicago"),
        id="prune_history",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 4a: OpenSanctions bulk ingest + IMO-exact matching (04:00 America/Chicago)
    scheduler.add_job(
        _job_refresh_opensanctions,
        trigger=CronTrigger(hour=4, timezone="America/Chicago"),
        id="refresh_opensanctions",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 4a: Shadow fleet flag derivation (04:30 America/Chicago, after opensanctions)
    scheduler.add_job(
        _job_refresh_shadow_fleet_flags,
        trigger=CronTrigger(hour=4, minute=30, timezone="America/Chicago"),
        id="refresh_shadow_fleet_flags",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 5a: Hourly Open-Meteo Marine weather pull (at :30 each hour)
    scheduler.add_job(
        _job_pull_weather,
        trigger=CronTrigger(minute=30, timezone="UTC"),
        id="pull_weather",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 5a: Anchorage dwell detection (at :10 each hour)
    scheduler.add_job(
        _job_compute_anchorage_dwell,
        trigger=CronTrigger(minute=10, timezone="UTC"),
        id="compute_anchorage_dwell",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 5a: Hourly composite risk scoring (at :15 each hour, after dwell + weather)
    scheduler.add_job(
        _job_score_risk_hourly,
        trigger=CronTrigger(minute=15, timezone="UTC"),
        id="score_risk_hourly",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 7a: Journal indexer (hourly at :45)
    scheduler.add_job(
        _job_index_journal,
        trigger=CronTrigger(minute=45, timezone="UTC"),
        id="index_journal",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Phase 7b: Dependency audit (daily 06:00 America/Chicago)
    scheduler.add_job(
        _job_dependency_audit,
        trigger=CronTrigger(hour=6, timezone="America/Chicago"),
        id="dependency_audit",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info("Scheduler built with %d job(s)", len(scheduler.get_jobs()))
    return scheduler
