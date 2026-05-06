# Phase 7: Hardening, Admin, SEAM UI & Documentation

**Status:** Complete
**Started:** 2026-05-02
**Completed:** 2026-05-02

---

## What Was Built

Phase 7 is the operational hardening layer — no new data features, but the infrastructure that makes the system trustworthy enough to hand off. The work split into three sub-phases.

**Phase 7a — Audit, Journal, Admin Force Actions**

- Migration `0008` adds five tables: `audit_log`, `journal_phase`, `journal_adr`, `journal_event`, `glossary_term`.
- `app/services/audit_log.py` — append-only `append_audit_log()` function; never commits (caller owns the transaction boundary).
- `app/services/journal_indexer.py` — walks `docs/journey/`, `docs/adr/`, and `docs/glossary.md` and upserts rows into the journal tables. Parsing is heading-convention-based (no YAML frontmatter). Runs hourly at `:45 UTC`.
- `app/routers/journal.py` — public `GET /api/journal/{phases,adrs,glossary}` endpoints, 60/minute.
- `app/routers/admin.py` — six force-action endpoints (`force-poll`, `force-risk-score`, `force-weather`, `force-news`, `force-opensanctions`, `force-journal-index`); all require `X-Admin-Token`, write to `audit_log`, commit.
- `app/auth/admin.py` — shared `require_admin` `Depends` callable (ADR-0027).
- `routers/sanctions.py` retrofitted to use `require_admin` and `append_audit_log`.

**Phase 7b — Admin SPA, DB Explorer, Stats, Attribution**

- Migration `0009` adds four tables: `data_source_status`, `outbound_request_log`, `dependency_audit_log`, `data_source_attribution`.
- `app/services/data_source_status.py` — `record_success()` and `record_failure()` writers; resets/increments `consecutive_failures` and stores payload SHA-1.
- `app/routers/about.py` — public `GET /api/about` endpoint; returns build metadata + all attribution rows.
- DB Explorer: `GET /api/admin/db` (table list), `GET /api/admin/db/{table}?page=N` (50 rows/page), `GET /api/admin/db/{table}/{pk}` (single row). All gated by explicit 25-table allowlist (ADR-0029).
- Stats endpoints under `/api/admin/stats/*`: sources health, vessel type distribution, risk score histogram, top-20 risk vessels, sanctions overview counters, top news entity mentions, audit log tail, dependency audit history.
- Dependency audit cron (`_job_dependency_audit`) — runs pip-audit daily at 06:00 Chicago, writes to `dependency_audit_log`, raises a `warning` audit log entry if HIGH/CRITICAL found.
- Frontend `JournalDrawer.tsx` — public-facing drawer accessible from LiveMap, shows phases/ADRs/glossary in three tabs.
- Frontend Admin SPA at `/admin` — hash/pathname-based routing, 5 tabs: Overview (sources health + audit log + dep audit + force actions), Approvals (sanctions review queue), DB Explorer, Stats (Recharts charts), Ops Swarm (placeholder).

**Phase 7c — Tests**

- `tests/test_phase7a.py` — 20 tests covering phase/ADR/glossary parsing and audit log writer.
- `tests/test_phase7b.py` — 20 tests covering data_source_status writer, about seed logic, DB explorer allowlist, and ORM model schema.

**Phase 7d — SEAM Dashboard Frontend**

- The public frontend was redesigned around the SEAM brand: Singapore Entity Analytics for Maritime.
- `LiveMap.tsx` became the primary full-screen shell with a glass header, live status pill, right-side toolbar, light map tiles, risk filter panel, and integrated admin entry.
- The old dark UI panels were restyled to match the SEAM glass system: news, arrivals, search, journal, geospatial layers, timeline scrubber, risk badges, and entity pills.
- Panel behavior was tightened so only one left-side menu opens at a time, search closes after selecting a vessel, and drawers no longer overlap the header.
- `VesselDetailPanel.tsx` was updated so vessel particulars wrap instead of truncating important values like owner, operator, and classification society.

**Phase 7e — SEAM Admin Dashboard**

- `AdminApp.tsx` was rebuilt as a SEAM admin shell with glass header, animated sidebar navigation, mobile drawer behavior, health pill, and tab transitions.
- Existing real admin features were kept API-backed rather than replaced with mock template data.
- Overview, Approvals, DB Explorer, and Stats tabs were restyled with shared admin card, table, button, chart, and animation classes.
- Recharts tooltips, bars, and pie charts were normalized to the SEAM light palette.
- Ops Swarm remains a placeholder, but it now matches the SEAM admin card style.

**Phase 7f — Local Developer Experience and Simple Docs**

- `dev.py` was added as a terminal control panel for starting/stopping database, backend, frontend, running migrations, viewing logs, and opening the app.
- `start-dev.command` was added as a macOS clickable launcher that runs `python3 dev.py` from the project root.
- `docs/PROJECT_GUIDE.md` was added as the simple practical guide for how the project works, how to run it, where code lives, and how data flows.
- `README.md` now points to `docs/PROJECT_GUIDE.md` before the deeper architecture and ADR documents.

---

## Design Decisions

- **No YAML frontmatter** in journey/ADR docs — parsing uses heading conventions present in existing files (ADR-0028).
- **Append-only audit log** — `audit_log` rows are never updated or deleted; `append_audit_log()` calls `flush()` but not `commit()` so it composes cleanly with any transaction.
- **Shared `require_admin` dependency** — one callsite for token validation across all admin endpoints (ADR-0027).
- **DB Explorer explicit allowlist** — 25 named tables; f-string substitution after validation (ADR-0029).
- **SEAM UI as product shell** — the app now presents itself as SEAM, using the dashboard template as visual direction while preserving existing live API-backed behavior (ADR-0030).
- **Practical guide in docs** — day-to-day project explanation lives in `docs/PROJECT_GUIDE.md`; README stays short and points readers there (ADR-0031).
- **Hash-based admin routing** — no react-router dep added; `/admin` pathname or `#admin` hash triggers lazy-loaded AdminApp.
- **`outbound_request_log` table created, ingest deferred** — table and ORM model exist; actual HTTP middleware instrumentation deferred to Phase 8 to avoid scope creep.
- **Backblaze B2 backup automation deferred** — architecture calls for it but implementation is pure infra; deferred to Phase 8.

---

## What's Left (Phase 8 and Beyond)

- Wire `outbound_request_log` writer into the HTTP client layer (aiohttp/httpx middleware).
- Backblaze B2 nightly database backup job.
- Ops Swarm tab content (multi-agent coordination view).
- Secret rotation reminder cron.

---

## Verification

- `npm run typecheck`
- `npm run build`
- `python3 -m py_compile dev.py`
