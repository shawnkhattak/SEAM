"""Admin force-action endpoints, DB explorer, and stats. All require an admin token."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import require_admin
from app.db import get_db
from app.limiter import limiter
from app.services.audit_log import append_audit_log

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

_PAGE_SIZE = 50

# Tables the DB explorer is allowed to expose. Keep this aligned with
# app.models.__tablename__ values so the explorer never advertises dead tables.
_ALLOWED_TABLES = {
    "agent_review_queue",
    "anchorage_dwell",
    "audit_log",
    "data_source_attribution",
    "data_source_status",
    "dependency_audit_log",
    "flag_performance_year",
    "glossary_term",
    "journal_adr",
    "journal_event",
    "journal_phase",
    "mou_inspection",
    "news_entity_mention",
    "news_feed",
    "news_item",
    "news_summary",
    "opensanctions_entity_raw",
    "organization",
    "organization_alias",
    "organization_topic",
    "outbound_request_log",
    "port",
    "port_alias",
    "position_archive",
    "position_live",
    "risk_score",
    "sanctions_listing",
    "sanctions_match",
    "sanctions_match_history",
    "sanctions_source",
    "terminal",
    "terminal_geom",
    "vessel",
    "vessel_class_history",
    "vessel_flag_history",
    "vessel_name_history",
    "vessel_operator_history",
    "vessel_organization_link",
    "vessel_owner_history",
    "vessel_topic",
    "weather_observation",
}


async def _existing_allowed_tables(db: AsyncSession) -> set[str]:
    result = await db.execute(
        text(
            "SELECT tablename "
            "FROM pg_catalog.pg_tables "
            "WHERE schemaname = ANY(current_schemas(false))"
        )
    )
    existing = {row.tablename for row in result}
    return _ALLOWED_TABLES & existing


@router.post("/force-poll", status_code=200)
@limiter.limit("5/minute")
async def force_poll(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, str]:
    """Trigger an immediate position poll outside the 15-minute scheduler cadence."""
    from app.clients.oceansx import get_oceansx_client
    from app.services import vessels as vessel_svc
    from app.services import vessel_master as vm_svc
    from app.services.history import maybe_write_position_archive, update_position_terminal, write_position_live
    from app.services.sse_broadcaster import position_broadcaster
    from app import cache as l1_cache

    client = get_oceansx_client()
    positions = await vessel_svc.get_live_positions(client)

    written_live = 0
    written_archive = 0
    for pos in positions:
        await vm_svc.upsert_vessel(db, pos)
        await vm_svc.record_scd2_changes(db, pos["imo"], pos["name"], pos.get("flag"))
        await write_position_live(db, pos)
        terminal_id = await update_position_terminal(db, pos["imo"], pos["recorded_at"], pos["lat"], pos["lon"])
        archived = await maybe_write_position_archive(db, pos, terminal_id=terminal_id)
        if archived:
            written_archive += 1
        written_live += 1

    l1_cache.delete("api:vessels:positions")
    await position_broadcaster.publish("positions_updated", {"count": len(positions), "archived": written_archive})

    await append_audit_log(
        db,
        actor="admin",
        action="force_poll",
        detail={"positions": len(positions), "live": written_live, "archive": written_archive},
    )
    await db.commit()
    logger.info("admin/force-poll: %d positions, %d live, %d archive", len(positions), written_live, written_archive)
    return {"status": "ok", "positions": str(len(positions))}


@router.post("/force-risk-score", status_code=200)
@limiter.limit("5/minute")
async def force_risk_score(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, str]:
    """Trigger an immediate composite risk scoring run."""
    from app.services.risk_scorer import run_hourly_scoring

    summary = await run_hourly_scoring(db)
    await append_audit_log(db, actor="admin", action="force_risk_score", detail={"summary": str(summary)})
    await db.commit()
    logger.info("admin/force-risk-score: %s", summary)
    return {"status": "ok", "summary": str(summary)}


@router.post("/force-weather", status_code=200)
@limiter.limit("5/minute")
async def force_weather(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, str]:
    """Trigger an immediate Open-Meteo weather pull."""
    from app.services.weather import pull_and_store_weather

    summary = await pull_and_store_weather(db)
    await append_audit_log(db, actor="admin", action="force_weather", detail={"summary": str(summary)})
    await db.commit()
    logger.info("admin/force-weather: %s", summary)
    return {"status": "ok", "summary": str(summary)}


@router.post("/force-news", status_code=200)
@limiter.limit("5/minute")
async def force_news(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, str]:
    """Trigger an immediate RSS feed poll across all 3 slots."""
    from app.clients.rss_app import poll_feed
    from app.services.entity_extraction import extract_entities_for_item
    from app.services.news import get_or_create_feed, ingest_article

    _SLOT_NAMES = {1: "Maritime Feed 1", 2: "Maritime Feed 2", 3: "Maritime Feed 3"}
    total_accepted = 0

    for slot in (1, 2, 3):
        articles = await poll_feed(slot)
        if not articles:
            continue
        feed_id = await get_or_create_feed(db, slot=slot, name=_SLOT_NAMES[slot])
        for article in articles:
            item = await ingest_article(db, article, feed_id=feed_id)
            if item is not None:
                await extract_entities_for_item(db, news_id=item.id, title=item.title, body_text=item.body_text)
                item.extraction_status = "done"
                total_accepted += 1

    await append_audit_log(db, actor="admin", action="force_news", detail={"accepted": total_accepted})
    await db.commit()
    logger.info("admin/force-news: %d articles accepted", total_accepted)
    return {"status": "ok", "accepted": str(total_accepted)}


@router.post("/force-opensanctions", status_code=200)
@limiter.limit("5/minute")
async def force_opensanctions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, str]:
    """Trigger an immediate OpenSanctions bulk ingest + IMO-exact matching."""
    from app.clients.opensanctions import fetch_maritime_entities
    from app.services.opensanctions_ingest import ingest_batch
    from app.services.sanctions_matcher import run_matcher

    entities = await fetch_maritime_entities()
    if not entities:
        return {"status": "ok", "note": "no entities returned"}

    ingest_summary = await ingest_batch(db, entities)
    match_summary = await run_matcher(db, entities)
    await append_audit_log(
        db,
        actor="admin",
        action="force_opensanctions",
        detail={"ingest": str(ingest_summary), "match": str(match_summary)},
    )
    await db.commit()
    logger.info("admin/force-opensanctions: ingest=%s match=%s", ingest_summary, match_summary)
    return {"status": "ok", "ingest": str(ingest_summary), "match": str(match_summary)}


@router.post("/force-journal-index", status_code=200)
@limiter.limit("5/minute")
async def force_journal_index(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, str]:
    """Trigger an immediate journal + glossary index run."""
    from app.services.journal_indexer import run_journal_indexer

    summary = await run_journal_indexer(db)
    await append_audit_log(db, actor="admin", action="force_journal_index", detail=summary)
    await db.commit()
    logger.info("admin/force-journal-index: %s", summary)
    return {"status": "ok", **{k: str(v) for k, v in summary.items()}}


# ---------------------------------------------------------------------------
# DB Explorer
# ---------------------------------------------------------------------------

@router.get("/db", status_code=200)
@limiter.limit("30/minute")
async def list_explorer_tables(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[str]:
    """Return the list of tables available for DB exploration."""
    return sorted(await _existing_allowed_tables(db))


@router.get("/db/{table}", status_code=200)
@limiter.limit("30/minute")
async def explore_table(
    table: str,
    request: Request,
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, Any]:
    """Return up to 50 rows from *table* with total row count."""
    if table not in await _existing_allowed_tables(db):
        raise HTTPException(status_code=404, detail=f"Table '{table}' not in allowed list")

    offset = (page - 1) * _PAGE_SIZE

    total_result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
    total = total_result.scalar_one()

    rows_result = await db.execute(
        text(f"SELECT * FROM {table} ORDER BY 1 LIMIT :limit OFFSET :offset"),  # noqa: S608
        {"limit": _PAGE_SIZE, "offset": offset},
    )
    columns = list(rows_result.keys())
    rows = [dict(zip(columns, row)) for row in rows_result.fetchall()]

    return {
        "table": table,
        "page": page,
        "page_size": _PAGE_SIZE,
        "total": total,
        "columns": columns,
        "rows": rows,
    }


@router.get("/db/{table}/{pk}", status_code=200)
@limiter.limit("30/minute")
async def explore_row(
    table: str,
    pk: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, Any]:
    """Return a single row from *table* by primary key (assumed column 'id')."""
    if table not in await _existing_allowed_tables(db):
        raise HTTPException(status_code=404, detail=f"Table '{table}' not in allowed list")

    result = await db.execute(
        text(f"SELECT * FROM {table} WHERE id = :pk"),  # noqa: S608
        {"pk": pk},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")

    columns = list(result.keys())
    return dict(zip(columns, row))


# ---------------------------------------------------------------------------
# Stats endpoints
# ---------------------------------------------------------------------------

@router.get("/stats/sources", status_code=200)
@limiter.limit("30/minute")
async def stats_sources(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Health of each polled data source."""
    from app.services.data_source_status import get_all_statuses
    rows = await get_all_statuses(db)
    return [
        {
            "source_name": r.source_name,
            "last_success_at": r.last_success_at,
            "last_attempt_at": r.last_attempt_at,
            "last_error": r.last_error,
            "consecutive_failures": r.consecutive_failures,
        }
        for r in rows
    ]


@router.get("/stats/vessel-types", status_code=200)
@limiter.limit("30/minute")
async def stats_vessel_types(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Distribution of vessels by vessel_type."""
    from app.models import Vessel
    from app.utils.vessel_labels import vessel_type_label
    result = await db.execute(
        select(Vessel.vessel_type, func.count().label("count"))
        .group_by(Vessel.vessel_type)
        .order_by(func.count().desc())
    )
    return [
        {
            "vessel_type": row.vessel_type or "Unknown",
            "vessel_type_label": vessel_type_label(row.vessel_type) or "Unknown",
            "count": row.count,
        }
        for row in result
    ]


@router.get("/stats/risk-histogram", status_code=200)
@limiter.limit("30/minute")
async def stats_risk_histogram(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Histogram of composite risk scores in 0.1-width buckets."""
    result = await db.execute(
        text(
            "SELECT ROUND(composite::numeric, 1) AS bucket, COUNT(*) AS count "
            "FROM risk_score "
            "WHERE scored_at > NOW() - INTERVAL '24 hours' "
            "GROUP BY bucket ORDER BY bucket"
        )
    )
    return [{"bucket": float(row.bucket), "count": row.count} for row in result]


@router.get("/stats/top-risk", status_code=200)
@limiter.limit("30/minute")
async def stats_top_risk(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Top 20 highest-scoring vessels from the most recent scoring run."""
    result = await db.execute(
        text(
            "SELECT rs.vessel_imo AS imo, v.name, rs.composite AS composite_score "
            "FROM risk_score rs "
            "JOIN vessel v ON v.imo = rs.vessel_imo "
            "WHERE rs.scored_at = (SELECT MAX(scored_at) FROM risk_score) "
            "ORDER BY rs.composite DESC LIMIT 20"
        )
    )
    return [{"imo": row.imo, "name": row.name, "score": float(row.composite_score)} for row in result]


@router.get("/stats/sanctions-overview", status_code=200)
@limiter.limit("30/minute")
async def stats_sanctions_overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict[str, Any]:
    """Counts of sanctioned vessels, shadow fleet vessels, and review queue size."""
    result = await db.execute(
        text(
            "SELECT "
            "  (SELECT COUNT(*) FROM vessel WHERE current_sanctions_status != 'clean') AS sanctioned, "
            "  (SELECT COUNT(*) FROM vessel WHERE is_shadow_fleet = true) AS shadow_fleet, "
            "  (SELECT COUNT(*) FROM agent_review_queue WHERE status = 'open') AS pending_reviews"
        )
    )
    row = result.fetchone()
    return {
        "sanctioned": row.sanctioned,
        "shadow_fleet": row.shadow_fleet,
        "pending_reviews": row.pending_reviews,
    }


@router.get("/stats/news-entities", status_code=200)
@limiter.limit("30/minute")
async def stats_news_entities(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Top 20 entity mentions across all news items in the last 7 days."""
    result = await db.execute(
        text(
            "SELECT ne.matched_text AS entity_text, ne.entity_type, COUNT(*) AS mentions "
            "FROM news_entity_mention ne "
            "JOIN news_item ni ON ni.id = ne.news_id "
            "WHERE ni.published_at_utc > NOW() - INTERVAL '7 days' "
            "GROUP BY ne.matched_text, ne.entity_type "
            "ORDER BY mentions DESC LIMIT 20"
        )
    )
    return [
        {"entity_text": row.entity_text, "entity_type": row.entity_type, "mentions": row.mentions}
        for row in result
    ]


@router.get("/stats/audit-log", status_code=200)
@limiter.limit("30/minute")
async def stats_audit_log(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Last 50 audit log entries, newest first."""
    from app.models import AuditLog
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(50)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "occurred_at": r.occurred_at,
            "actor": r.actor,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "detail": r.detail,
            "severity": r.severity,
        }
        for r in rows
    ]


@router.get("/stats/dependency-audit", status_code=200)
@limiter.limit("30/minute")
async def stats_dependency_audit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Last 10 dependency audit runs per ecosystem."""
    from app.models import DependencyAuditLog
    result = await db.execute(
        select(DependencyAuditLog)
        .order_by(DependencyAuditLog.audited_at.desc())
        .limit(10)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "audited_at": r.audited_at,
            "ecosystem": r.ecosystem,
            "high_critical_count": r.high_critical_count,
            "total_count": r.total_count,
        }
        for r in rows
    ]
