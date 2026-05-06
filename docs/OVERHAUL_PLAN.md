# SEAM Overhaul — Phase-by-Phase Implementation Plan

> Generated from `legacy/docs/PROJECT_GUIDE.md` and `legacy/oceansx-v2-architecture.md`.
> This is the canonical rebuild blueprint. Execute phases in order.

---

## Guiding Principles

The new SEAM is a ground-up rebuild in `/home/user/SEAM/` (outside `legacy/`). There is no data migration. The legacy code is a reference implementation, not a base to modify.

**Key overhaul mandates driving every phase:**

- Full SEAM identity: rename all package/DB/container names from `oceansx` → `seam`
- New data model: `vessel_company_relationship` instead of flat ownership columns; `vessel_particular_fact` for field-level provenance
- Vessel detail must not cover right-side map controls — implement as bottom sheet or `/vessels/:imo` inspector route
- Journal/ADR browsing moves from map toolbar into admin dashboard
- Admin-configurable encrypted API keys in `app_config` table (not env vars)
- Rate-limited priority enrichment queue (`vessel_enrichment_queue`)
- Build Swarm agents in `.claude/agents/` (9 roles, SEAM identity throughout)
- Launcher is `start.py`, not `dev.py`

---

## Port vs Rewrite Classification

| Legacy file | New disposition |
|---|---|
| `clients/oceansx.py` | Port — rename comments/logs; factory reads key from `app_config` |
| `clients/opensanctions.py` | Port — same factory pattern |
| `clients/anthropic_client.py` | Port — same factory pattern |
| `clients/rss_app.py` | Port — read URLs + HMAC from `app_config` |
| `clients/open_meteo.py` | Port unchanged (no key needed) |
| `services/vessels.py` | Port unchanged |
| `services/history.py` | Port unchanged (dedup rule locked) |
| `services/vessel_master.py` | **Rewrite** — writes `vessel_particular_fact` + `vessel_company_relationship` instead of flat columns |
| `services/geospatial.py` | Port unchanged |
| `services/ports.py` | Port unchanged |
| `services/news.py` | Port unchanged |
| `services/entity_extraction.py` | Port unchanged |
| `services/opensanctions_ingest.py` | Port — project into `company`/`company_alias`/`company_identifier` instead of `organization*` |
| `services/sanctions_matcher.py` | Port — rename model imports |
| `services/shadow_fleet.py` | Port unchanged |
| `services/risk_scorer.py` | Port — rename imports only |
| `services/weather.py` | Port unchanged |
| `services/anchorage_dwell.py` | Port unchanged |
| `services/nl_search.py` | Port — update CTE to use `vessel_company_relationship` instead of `vessel_organization_link` |
| `services/news_summarizer.py` | Port unchanged |
| `services/journal_indexer.py` | Port unchanged |
| `services/audit_log.py` | Port unchanged |
| `services/data_source_status.py` | Port unchanged |
| `services/sse_broadcaster.py` | Port unchanged |
| `services/macro.py` | Port unchanged |
| `routers/vessels.py` | **Rewrite** — enqueue on detail view, return provenance fields |
| `routers/admin.py` | **Rewrite** — add config CRUD, secrets masking, enrichment queue management |
| All other routers | Port with import/tag renames |
| `auth/admin.py` | **Rewrite** — reads token from `app_config`, falls back to env bootstrap |
| `config.py` | **Rewrite** — remove individual API key fields (moved to `app_config`), add `encryption_key` |
| `scheduler.py` | **Rewrite** — add enrichment queue worker, per-minute rate-limited trigger |
| `main.py` | Port — rename title to `"SEAM API"` |
| Frontend `App.tsx` | Port — add `react-router-dom` for `/vessels/:imo` route |
| Frontend `LiveMap.tsx` | Port — remove Journal toolbar button |
| Frontend `VesselDetailPanel.tsx` | **Rewrite** → `VesselDetailSheet.tsx` — bottom sheet with provenance tab |
| Frontend `AdminApp.tsx` | Port — add Config tab, Journal tab |
| `dev.py` → `start.py` | **Rewrite** — update all paths and brand strings |
| `SEAM Dashboard template.html` | **Delete** — dead artifact, do not recreate |
| `seam/tweaks-panel.jsx` | **Delete** — dead artifact, do not recreate |

---

## Phase 0 — Foundation

**Goal:** Properly shaped repo, CI green, DB migrates, frontend and backend start with health checks, Build Swarm agents in place.

### 0.1 Repo skeleton

```
/home/user/SEAM/
├── start.py                    # renamed from dev.py; brand: "SEAM Control Panel"
├── docker-compose.yml          # seam_db service, POSTGRES_DB: seam, volume: seam_pgdata
├── .gitignore
├── .env.example                # POSTGRES_PASSWORD_SUPERUSER only
├── CLAUDE.md                   # already created
└── docs/
    ├── PROJECT_GUIDE.md        # SEAM identity, updated commands
    ├── glossary.md
    ├── adr/README.md
    └── journey/00-the-problem.md
```

`docker-compose.yml` changes from legacy:
- Service name: `seam_db` (was `db`)
- `POSTGRES_DB: seam` (was `oceansx`)
- Volume name: `seam_pgdata`
- Init script: `./backend/scripts/init-db.sql`

### 0.2 Build Swarm agents

Create 9 files in `.claude/agents/`. Each uses YAML frontmatter (`name`, `description`, `tools`, `model: claude-sonnet-4-6`). All say "SEAM" not "OceansX".

| File | Role | Key constraint |
|---|---|---|
| `architect.md` | ADRs, locked decisions | Knows about `vessel_particular_fact`, `vessel_company_relationship`, `app_config` encrypted keys |
| `db-engineer.md` | Alembic migrations, indexes | Forbidden from writing app Python; knows hypertable syntax |
| `backend-engineer.md` | Services, routers, clients | Must not touch migrations |
| `frontend-engineer.md` | React/TypeScript/Tailwind | Must follow SEAM CSS variable naming |
| `agent-engineer.md` | Operations Swarm code | Staging-only writes |
| `security-reviewer.md` | Auth, injection, secrets | Encrypted-at-rest key checklist |
| `code-reviewer.md` | Clarity, test coverage | |
| `test-engineer.md` | pytest/vitest | Knows mock fixtures location |
| `doc-maintainer.md` | docs/journey/, docs/adr/, glossary | Writes newest-to-oldest |

### 0.3 Backend skeleton

**`backend/pyproject.toml`:**
```toml
[project]
name = "seam-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]", "sqlalchemy[asyncio]>=2.0",
  "psycopg[binary,pool]", "alembic", "geoalchemy2", "shapely",
  "apscheduler>=3.10", "httpx", "slowapi", "pydantic-settings",
  "anthropic", "feedparser", "python-dateutil", "cachetools",
  "cryptography",    # NEW — Fernet encryption for app_config secrets
  "prometheus-client", "python-multipart", "itsdangerous",
]
[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "pytest-httpx", "ruff", "pip-audit"]
```

**`backend/scripts/init-db.sql`:**
```sql
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'seam_app') THEN
    CREATE ROLE seam_app LOGIN PASSWORD 'changeme_app';
  END IF;
END $$;
```

**`backend/app/config.py`** — `Settings` class:
- Keep: `database_url`, `cors_origins`, `log_level`, `display_timezone`, `poll_positions_seconds`, `enrich_particulars_seconds`, `refresh_news_seconds`
- Add: `encryption_key: str = ""` — Fernet key for encrypting `app_config` secrets; `admin_token: str = ""` — bootstrap only; `max_enrich_per_minute: int = 10`
- **Remove** all individual API key fields (`oceansx_api_key`, `anthropic_api_key`, etc.) — those move to `app_config` DB table

**`backend/app/main.py`:** title `"SEAM API"`, same middleware stack

### 0.4 Migration 0001 — extensions and roles

```python
# 0001_init_extensions_and_roles.py
# CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE
# CREATE EXTENSION IF NOT EXISTS postgis CASCADE
# CREATE EXTENSION IF NOT EXISTS pg_trgm
```

### 0.5 Frontend skeleton

**`frontend/package.json`:** `"name": "seam-frontend"`, add `react-router-dom`

**`frontend/src/App.tsx`** — `<Routes>`: `/` → `<LiveMap />`, `/admin` → lazy `<AdminApp />`, `/vessels/:imo` → lazy `<VesselInspector />`

Port SEAM CSS variables, Tailwind config from legacy.

### 0.6 CI

`.github/workflows/ci.yml` — port from legacy; DB name `seam_test`, role `seam_app`.

### Bootstrap commands

```bash
docker compose up -d db
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# In another terminal:
cd ../frontend && npm install && npm run dev
```

**ADR:** ADR-0032: SEAM as canonical project identity.

---

## Phase 1 — Live Tracking

**Goal:** Vessels on map, position polling, SSE push, vessel detail in bottom sheet.

### 1.1 New data model (`backend/app/models.py`)

**`vessel`** — remove `ism_manager`, `registered_owner`, `operator`, `classification_society` (moved to `vessel_company_relationship`). Add `enrichment_priority: int = 5`.

**`vessel_particular_fact`** — new table:
```
imo (BigInt FK vessel), field_name (String 100), field_value (Text),
source (String 100), fetch_time (TIMESTAMPTZ), confidence (Float = 1.0),
valid_from (TIMESTAMPTZ), valid_to (TIMESTAMPTZ nullable), created_at (TIMESTAMPTZ)
Index: (imo, field_name, valid_from)
```

**`vessel_enrichment_queue`** — new table:
```
imo (BigInt PK), priority (Int = 5), enqueued_at (TIMESTAMPTZ),
last_attempt_at (TIMESTAMPTZ nullable), next_attempt_at (TIMESTAMPTZ nullable),
attempt_count (Int = 0), last_error (Text nullable), locked_until (TIMESTAMPTZ nullable)
```

**`company`** — replaces `organization`:
```
id (Int PK), name (String 300), country (String 5),
first_seen_at (TIMESTAMPTZ), last_seen_at (TIMESTAMPTZ)
```

**`company_alias`** — replaces `organization_alias`:
```
id (Int PK), company_id (FK company), alias (String 300)
Index: lower(alias)
```

**`company_identifier`** — new:
```
id (Int PK), company_id (FK company), identifier_type (String 50), identifier_value (String 200)
CheckConstraint: identifier_type IN ('os_entity_id','registration_number','lei','mmsi','topic')
UniqueConstraint: (company_id, identifier_type, identifier_value)
```

**`vessel_company_relationship`** — replaces `vessel_organization_link`:
```
id (Int PK), imo (BigInt), company_id (FK company), role (String 50),
valid_from (TIMESTAMPTZ), valid_to (TIMESTAMPTZ nullable),
source (String 100), confidence (Float = 1.0)
CheckConstraint: role IN ('registered_owner','beneficial_owner','operator',
                          'ism_manager','classification_society',
                          'commercial_manager','ship_manager')
Index: (imo, role, valid_from)
```

**`app_config`** — new table:
```
key (String 100 PK), value_encrypted (Text nullable), value_plain (Text nullable),
is_secret (Bool = false), description (Text nullable),
updated_at (TIMESTAMPTZ), updated_by (String 100)
```
Secret keys: `oceansx_api_key`, `anthropic_api_key`, `rss_app_feed_*_url`, `rss_app_feed_*_hmac`, `admin_token`.
Non-secret keys: `oceansx_mock_mode`, `anthropic_mock_mode`, `opensanctions_mock_mode`, `poll_positions_seconds`, `enrich_particulars_seconds`, `max_enrich_per_minute`, `display_timezone`.

**Remove** (replaced by `vessel_company_relationship` + `vessel_particular_fact`):
- `vessel_owner_history`, `vessel_operator_history`, `vessel_class_history`

**Keep unchanged:**
- `position_live` (TimescaleDB hypertable, 14-day retention)
- `position_archive` (TimescaleDB hypertable, 365-day retention, dedup rule locked)
- `vessel_name_history`, `vessel_flag_history` (SCD2)

### 1.2 Migration 0002

```python
# 0002_vessel_position_schema.py
# Creates all tables above
# SELECT create_hypertable('position_live', 'recorded_at', if_not_exists => TRUE)
# SELECT create_hypertable('position_archive', 'recorded_at', if_not_exists => TRUE)
# SELECT add_retention_policy('position_live', INTERVAL '14 days')
# SELECT add_retention_policy('position_archive', INTERVAL '365 days')
# Seeds app_config with default non-secret keys
```

### 1.3 Config service

`backend/app/services/config_service.py`:
- `get_config(session, key) -> str | None` — reads from `app_config`, decrypts if `is_secret=True` using Fernet(`settings.encryption_key`)
- `set_config(session, key, value, actor, is_secret=False)` — encrypts if secret, writes, appends `audit_log`
- `get_all_configs_masked(session) -> list[dict]` — returns all keys; secrets show `"***"`
- Use a 5-minute in-memory `ConfigCache` class to avoid DB round-trips on every request

### 1.4 Client factory pattern

All clients that need API keys must call `await config_cache.get(session, "key")` at request time instead of reading from `Settings`. This allows keys changed in the admin UI to be picked up within 5 minutes without restart.

### 1.5 `vessel_master.py` rewrite

`update_from_particulars(session, imo, particulars)`:
- For each company field (`registered_owner`, `operator`, `ism_manager`, `classification_society`): resolve or create a `company` row → insert/update `vessel_company_relationship` with `valid_from=now`, close any open conflicting relationship for same role
- For each scalar field: insert a `vessel_particular_fact` row with `source="mpa_particulars"`, close the previous open fact for `(imo, field_name)`
- **Null handling rule:** write a null-value fact only when the API explicitly returned null for a field that previously had a value. Treat omitted fields differently from explicit nulls.

`get_latest_particulars(session, imo) -> dict` — reads latest open `vessel_particular_fact` rows, assembles into response dict.

### 1.6 Enrichment queue service

`backend/app/services/enrichment_queue.py`:
- `enqueue(session, imo, priority=5)` — insert or update; if already queued with lower priority, raise priority
- `dequeue_batch(session, max_count, max_per_minute_window) -> list[int]` — fetch up to `max_count` where `next_attempt_at <= now()` and `locked_until IS NULL OR locked_until < now()`, ordered `(priority ASC, next_attempt_at ASC NULLS FIRST)`; set `locked_until = now() + 2 minutes` for fetched rows
- `mark_success(session, imo)` — delete from queue
- `mark_failure(session, imo, error, is_rate_limit=False)` — exponential backoff: `min(3600, 60 * 2^attempt_count)`; on 429: flat 300s

### 1.7 Scheduler rewrite

- Replace hourly `_job_enrich_vessel_particulars` (50 vessels) with `_job_enrich_vessel_particulars_worker` on `IntervalTrigger(seconds=60)` using `dequeue_batch(max_count=settings.max_enrich_per_minute)`
- Add `_job_enqueue_stale_vessels` on `CronTrigger(hour=1)` — enqueue vessels not enriched in 7 days at priority 7
- Add `coalesce=True` to enrichment trigger to prevent overlapping runs

### 1.8 Vessels router rewrite

`GET /api/vessels/{imo}`:
- After fetching particulars from API: `enqueue(session, imo, priority=1)` (user-triggered = highest)
- Return `particulars_facts: list[ParticularsFactResponse]`
- Return `company_relationships: list[CompanyRelationshipResponse]`

New endpoint: `GET /api/vessels/{imo}/provenance` — full `vessel_particular_fact` history.

### 1.9 Frontend — bottom sheet

`VesselDetailSheet.tsx`:
- Position: `absolute bottom-0 left-0 right-0 z-[620]`
- Max height: `max-h-[60vh]` mobile / `max-h-[40vh]` desktop
- Three tabs: Summary | Provenance | Relationships
- Drag-to-dismiss handle

`VesselInspector.tsx` — full-page route for `/vessels/:imo`, linked from bottom sheet.

### 1.10 Auth rewrite

`auth/admin.py` — read admin token from `app_config` first; fall back to `settings.admin_token` bootstrap value.

**ADRs:** ADR-0033 (provenance), ADR-0034 (company graph), ADR-0035 (encrypted config), ADR-0036 (bottom sheet), ADR-0037 (enrichment queue).

**High-risk:**
- `vessel_particular_fact` SCD2 close logic — use `SELECT FOR UPDATE` to atomically close previous open fact
- Enrichment queue `locked_until` mechanism — test concurrent scheduler cycles with `coalesce=True`
- ConfigCache TTL — 5-minute window between key change and clients picking it up

---

## Phase 2 — Macro + Geospatial

**Goal:** Port geospatial layers, terminal polygons, macro statistics.

### 2.1 Migration 0003

Port from legacy `0003_phase3_geospatial.py`. Creates: `port`, `port_alias`, `terminal`, `terminal_geom` (PostGIS POLYGON with GiST index).

Add FKs `position_live.terminal_id` → `terminal.id` and `position_archive.terminal_id` → `terminal.id`.

### 2.2 Batch spatial join optimization

The `update_position_terminal` in legacy calls per-vessel. Replace with a single batch spatial join:

```sql
SELECT DISTINCT ON (pl.imo) pl.imo, tg.terminal_id
FROM position_live pl
JOIN terminal_geom tg ON ST_Within(
    ST_Point(pl.lon, pl.lat)::geography, tg.geom
)
WHERE pl.recorded_at > now() - interval '1 hour'
ORDER BY pl.imo, pl.recorded_at DESC
```

Verify query plan with `EXPLAIN (ANALYZE, FORMAT JSON)` before going live.

### 2.3 Services + routers

Port `geospatial.py`, `ports.py`, `macro.py` and their routers unchanged. Preserve Shapely point-radius fallback for terminals missing polygon geometry (document coverage gaps in ADR).

### 2.4 Scheduler

`_job_refresh_macro` — daily 03:00 America/Chicago  
`_job_refresh_geospatial` — daily 04:00 America/Chicago

---

## Phase 3 — News + Entity Extraction

**Goal:** RSS.app feeds ingested, entity extraction runs, news drawer functional.

### 3.1 Migration 0004

Port from legacy `0004_phase3_news.py`. Creates: `news_feed`, `news_item`, `news_entity_mention`, `news_summary`. Set 90-day retention.

### 3.2 RSS client config

`clients/rss_app.py` — read feed URLs and HMAC secrets from `app_config` via `config_service.get_config(session, "rss_app_feed_1_url")`.

### 3.3 Services + routers

Port `news.py`, `entity_extraction.py`, `news_summarizer.py` and their routers unchanged.

### 3.4 Scheduler

`_job_refresh_news` — hourly  
`_job_extract_entities` — at :20 each hour  
`_job_prune_history` — daily 02:00 America/Chicago

---

## Phase 4 — OpenSanctions + Shadow Fleet

**Goal:** FtM parsing, IMO-exact matching, review queue, shadow fleet flags.

### 4.1 Migration 0005

Port from legacy `0005_phase4a_opensanctions.py`. Rename `organization` → `company`, `organization_alias` → `company_alias`. Add `company_identifier`. Keep: `opensanctions_entity_raw`, `sanctions_source`, `sanctions_listing`, `sanctions_match`, `sanctions_match_history`, `agent_review_queue`, `vessel_topic`, `mou_inspection`, `flag_performance_year`.

### 4.2 Services

`opensanctions_ingest.py` — project FtM `Company`/`Organization` into `company` + `company_alias` + `company_identifier` tables.

`sanctions_matcher.py` — port; rename `organization` → `company`. **The IMO-exact-only auto-confirm rule is locked and unchanged.**

`shadow_fleet.py` — port unchanged.

### 4.3 NL search CTE

Update `_sanctioned_org_imos_cte` in `nl_search.py` to use `vessel_company_relationship` and `company`/`company_identifier` instead of `vessel_organization_link` and `organization_topic`. Depth cap at 3 hops unchanged. Add partial index: `vessel_company_relationship(company_id) WHERE valid_to IS NULL`.

### 4.4 Scheduler

`_job_refresh_opensanctions` — daily 04:00 America/Chicago  
`_job_refresh_shadow_fleet_flags` — daily 04:30 America/Chicago

**ADR:** ADR-0005 (port and update): IMO-exact-only; reference `vessel_company_relationship` for org-link matching.

---

## Phase 5 — Weather + Risk Scoring

**Goal:** Open-Meteo weather, anchorage dwell detection, composite risk scoring.

### 5.1 Migration 0006

Port from legacy `0006_phase5a_weather_risk.py`. Creates `weather_observation` (hypertable), `anchorage_dwell`, `risk_score` (hypertable), `flag_performance_year`, `mou_inspection`. Set 90-day retention on weather and risk score.

### 5.2 Services

Port `weather.py`, `anchorage_dwell.py`, `risk_scorer.py` unchanged (rename imports only).

Risk composite formula (locked):
```
composite =
  IF sanctions_score > 0 OR shadow_fleet_score > 0:
    max(sanctions_score, shadow_fleet_score)
  ELSE:
    flag_mou * 0.40 + age * 0.30 + congestion * 0.20 + weather * 0.10
```

### 5.3 Scheduler

`_job_pull_weather` — at :30 each hour  
`_job_compute_anchorage_dwell` — at :10 each hour  
`_job_score_risk_hourly` — at :15 each hour

---

## Phase 6 — Intelligence

**Goal:** NL search, new arrivals, AI news summaries.

### 6.1 Migration 0007

Port from legacy `0007_phase6a_intelligence.py`. Creates `data_source_status`, `outbound_request_log`. Ensures `news_summary` exists.

### 6.2 Services + routers

Port `nl_search.py` (with CTE already updated in Phase 4), `news_summarizer.py`, `journal_indexer.py` unchanged.

Port routers: `search.py`, `about.py`, `meta.py`, `journal.py`.

### 6.3 Frontend

Port `SearchBar.tsx`, `NewArrivalsDrawer.tsx`, `DataSourceFooter.tsx` unchanged.

---

## Phase 7 — Hardening + Admin Overhaul

**Goal:** Admin config UI, journal tab in admin, security hardening, DB Explorer + Stats, dependency audit.

### 7.1 Migration 0008

Port from legacy `0009_phase7b_admin.py`. Creates: `journal_phase`, `journal_adr`, `journal_event`, `glossary_term`, `data_source_attribution`, `dependency_audit_log`.

### 7.2 Admin router extensions

Add to `routers/admin.py`:

- `GET /api/admin/config` — returns all config keys; secrets shown as `"***"` (calls `get_all_configs_masked`)
- `PUT /api/admin/config/{key}` — encrypts before storing if `is_secret=True`; audit logs `{key: "***"}` (never the value)
- `DELETE /api/admin/config/{key}` — audit logged
- `GET /api/admin/stats/enrichment-queue` — count by priority bucket, oldest `next_attempt_at`, total stuck
- `GET /api/admin/stats/company-graph` — row counts for company graph tables

Security rules for config endpoints:
- Secrets are encrypted at rest (Fernet)
- `GET /api/admin/config` never returns decrypted values
- Audit log entry never contains the secret value
- Admin token for the admin endpoints is itself stored in `app_config` (once configured)

### 7.3 Frontend admin overhaul

New tabs in `AdminApp.tsx`:

**Config tab** (`ConfigTab.tsx`):
- Table of all config keys with masked values
- Inline edit, Save button
- Confirmation modal for secrets: "This will be stored encrypted"
- Never shows decrypted value — only success/error toast

**Journal tab** (`JournalTab.tsx`):
- Moves journal browsing from main map toolbar
- Sub-tabs: Phases | ADRs | Glossary
- Sort newest-to-oldest

Remove Journal button from `LiveMap.tsx` toolbar.

### 7.4 Scheduler

`_job_index_journal` — at :45 each hour  
`_job_dependency_audit` — daily 06:00 America/Chicago

### 7.5 Port remaining fixtures

Port all JSON mock fixtures from `legacy/backend/app/mocks/` to `backend/app/mocks/` unchanged.

**ADRs:** ADR-0038 (encrypted config in DB), ADR-0039 (journal in admin).

---

## Phase 8 — VPS Deployment

**Goal:** Production Docker Compose, Nginx reverse proxy, deployment bootstrap.

### 8.1 `docker-compose.prod.yml`

- `seam_db`: `timescale/timescaledb-ha:pg16`
- `seam_backend`: `Dockerfile.backend`, env from `.env.production`
- `seam_nginx`: Alpine Nginx serving built frontend, proxying `/api`

### 8.2 `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
COPY app/ app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 8.3 Bootstrap script (`scripts/deploy.sh`)

1. `docker compose -f docker-compose.prod.yml up -d seam_db`
2. Wait for DB health
3. `docker compose run --rm seam_backend alembic upgrade head`
4. `docker compose up -d`
5. Seed `app_config` with initial API keys via admin API

**ADR:** ADR-0040: Two Docker Compose files — dev (DB only) and prod (full stack).

---

## Highest-Risk Items

### 1. Missing particulars debugging (Phase 1)

The legacy `vessel_master.py` silently ignores null fields from the API. With `vessel_particular_fact`, nulls must be explicitly handled:
- Explicit null from API on a previously-populated field → write a null-value fact row
- Field omitted from API response entirely → keep previous fact open, do not close it

This distinction needs a unit test with three cases: field returned, field returned as null, field omitted.

### 2. PostGIS terminal polygon performance (Phase 2)

`ST_Within` runs per-vessel in legacy. Replace with a single batch spatial join (see query above). Requires `ix_terminal_geom_gist` GiST index. Verify with `EXPLAIN (ANALYZE)` before Phase 2 is considered done.

### 3. NL search graph traversal (Phase 4)

Recursive CTE with 3-hop depth cap. Add partial index `vessel_company_relationship(company_id) WHERE valid_to IS NULL`. Add `statement_timeout = '5s'` to the NL search execution path. Mock response should default `connected_to_sanctioned_org: false` to avoid triggering CTE in dev.

### 4. ConfigCache TTL (Phase 1)

API keys are now in DB. Clients must read them through a `ConfigCache` (5-minute TTL). Key changed in admin UI → picked up within 5 minutes without restart. Test: change `oceansx_api_key` via admin, verify next enrichment cycle uses new key.

### 5. Enrichment queue concurrency (Phase 1)

`locked_until` prevents double-processing, but APScheduler `coalesce=True` on the 60-second trigger prevents overlapping runs within the same process. Verify behavior if two scheduler processes start simultaneously (e.g., hot-reload during development).

---

## ADR Register (New ADRs for This Overhaul)

| Number | Title | Phase |
|---|---|---|
| ADR-0032 | SEAM as canonical project identity | 0 |
| ADR-0033 | Field-level provenance via `vessel_particular_fact` | 1 |
| ADR-0034 | `vessel_company_relationship` replaces flat ownership columns | 1 |
| ADR-0035 | Admin-configurable encrypted API keys in `app_config` | 1 |
| ADR-0036 | Vessel detail as bottom sheet | 1 |
| ADR-0037 | Rate-limited enrichment queue with exponential backoff | 1 |
| ADR-0038 | Journal browsing moved to admin dashboard | 7 |
| ADR-0039 | Two Docker Compose files for dev and prod | 8 |

---

## Quick Reference: Legacy vs New

| Concern | Legacy | New |
|---|---|---|
| Project identity | OceansX Visualizer V2 / SEAM hybrid | SEAM everywhere |
| Package names | `oceansx-frontend`, `oceansx-backend` | `seam-frontend`, `seam-backend` |
| DB name | `oceansx` | `seam` |
| DB role | `oceansx_app` | `seam_app` |
| Launcher | `dev.py` | `start.py` |
| API keys | Env vars in `Settings` | Encrypted in `app_config` table |
| Vessel ownership | Flat columns on `vessel` | `vessel_company_relationship` table |
| Particulars provenance | None | `vessel_particular_fact` SCD2 |
| Enrichment | 50 vessels/hour fixed | Priority queue, per-minute rate limiting, backoff |
| Vessel detail UI | Right-side drawer (covers controls) | Bottom sheet (does not cover controls) |
| Journal/ADR in UI | Main map toolbar | Admin dashboard only |
| Dead files | `SEAM Dashboard template.html`, `tweaks-panel.jsx` | Not recreated |

---

## Critical Files (Write These First)

1. `backend/app/models.py` — entire new data model; write before any service or migration
2. `backend/app/services/vessel_master.py` — most complex rewrite; drives `vessel_particular_fact` and `vessel_company_relationship`
3. `backend/app/services/enrichment_queue.py` — new file; drives rate-limited particulars enrichment
4. `backend/app/services/config_service.py` — all other services depend on it for API keys
5. `frontend/src/components/VesselDetailSheet.tsx` — key UX fix; requires understanding Leaflet z-index from `LiveMap.tsx`
