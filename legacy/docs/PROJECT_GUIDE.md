# OceansX Visualizer V2 / SEAM Project Guide

This is the main handoff guide for the OceansX Visualizer V2 project, now presented in the frontend as SEAM: Singapore Entity Analytics for Maritime.

The purpose of this guide is to make the project understandable before a major overhaul. It explains what the system is, how the code is arranged, what every major feature does, what is already implemented, what is intended to exist, what data flows through the system, and where the likely weak spots are.

## 1. Executive Summary

OceansX Visualizer V2 is a maritime intelligence dashboard focused on Singapore waters. It combines vessel position data, vessel particulars, sanctions screening, shadow fleet indicators, risk scoring, news intelligence, weather, geospatial overlays, and admin workflows into a single map-first application.

The project is not designed as a real-time navigation tool. It is designed as a compliance and intelligence interface. Position polling runs on a scheduled cadence, currently defaulting to 15 minutes. The value is not second-by-second tracking; the value is combining vessel movement with risk, sanctions, ownership, flag, news, and operational context.

The current frontend identity is SEAM. The backend and repo still use OceansX Visualizer V2 naming in many places.

At a high level, the system has three layers:

1. Ingestion layer: scheduled jobs and admin force actions pull external data into Postgres.
2. Intelligence API layer: FastAPI exposes normalized vessels, risk, sanctions, news, geospatial, journal, and admin endpoints.
3. SEAM frontend layer: React presents the intelligence as a full-screen map and an admin dashboard.

## 2. Product Definition

### What the product is

SEAM is a map-first maritime compliance dashboard for Singapore waters. A user can open the dashboard, see vessels near Singapore, inspect vessel details, view compliance/risk indicators, filter for shadow fleet or high-risk vessels, read relevant maritime news, search with natural language, and use admin workflows to inspect data quality or force data refreshes.

### What the product is not

SEAM is not:

- a certified navigation system
- an ECDIS replacement
- a real-time collision-avoidance tool
- a commercial vessel registry
- a sanctions authority
- a legal compliance decision engine

The UI includes risk and sanctions indicators, but those are derived from public or configured sources and should be treated as decision support, not final compliance determinations.

### Current primary users

The current design appears to target:

- maritime analysts
- sanctions/compliance reviewers
- port operations analysts
- project maintainers
- admins who need to inspect ingestion health and data

### Core user jobs

The app should help a user:

- see vessel activity in and around Singapore waters
- identify high-risk or sanctioned vessels
- inspect vessel details and ownership/manager/class data when available
- understand vessel position history and current movement state
- filter the map by risk and shadow fleet status
- review non-exact sanctions matches
- force ingestion/scoring jobs during development or operations
- inspect database tables from the admin UI
- understand the project journey, ADRs, and glossary from inside the app

## 3. Branding And Naming

### Repository/project name

The repo is named OceansX Visualizer V2.

### Frontend product name

The current frontend brand is SEAM.

SEAM appears in:

- the main map header
- the admin dashboard shell
- the design language
- CSS naming and visual identity

### Practical guidance during overhaul

Decide whether the project should remain "OceansX Visualizer V2" internally or fully become "SEAM" across:

- README
- package names
- API docs
- frontend copy
- Docker/project naming
- database names
- docs and ADRs

Right now, it is a mixed identity by design/history.

## 4. Technology Stack

| Layer | Technology |
|---|---|
| Frontend runtime | React 18, TypeScript, Vite |
| Frontend data | React Query, Zustand |
| Frontend styling | Tailwind CSS, custom SEAM global CSS |
| Maps | Leaflet, React Leaflet |
| Charts | Recharts |
| Backend | FastAPI, Python 3.12+ |
| Backend data access | SQLAlchemy async |
| Database | Postgres 16, TimescaleDB, PostGIS |
| Migrations | Alembic |
| Scheduling | APScheduler in FastAPI lifespan |
| Rate limiting | SlowAPI |
| External HTTP | httpx |
| AI/LLM | Anthropic client with mock mode |
| Local launcher | `dev.py`, `start-dev.command` |
| Containers | Docker Compose for database |

## 5. Repository Layout

```text
.
|-- README.md
|-- dev.py
|-- start-dev.command
|-- docker-compose.yml
|-- oceansx-v2-architecture.md
|-- SEAM Dashboard template.html
|-- backend/
|   |-- README.md
|   |-- pyproject.toml
|   |-- alembic.ini
|   |-- scripts/
|   |   `-- init-db.sql
|   |-- app/
|   |   |-- main.py
|   |   |-- scheduler.py
|   |   |-- config.py
|   |   |-- db.py
|   |   |-- models.py
|   |   |-- schemas.py
|   |   |-- cache.py
|   |   |-- limiter.py
|   |   |-- metrics.py
|   |   |-- observability.py
|   |   |-- alembic/
|   |   |-- auth/
|   |   |-- clients/
|   |   |-- mocks/
|   |   |-- routers/
|   |   |-- services/
|   |   `-- utils/
|   `-- tests/
|-- frontend/
|   |-- package.json
|   |-- vite.config.ts
|   |-- tailwind.config.ts
|   |-- index.html
|   `-- src/
|       |-- App.tsx
|       |-- main.tsx
|       |-- api/
|       |-- components/
|       |-- components/admin/
|       |-- lib/
|       |-- store/
|       |-- styles/
|       `-- types/
|-- docs/
|   |-- PROJECT_GUIDE.md
|   |-- glossary.md
|   |-- adr/
|   `-- journey/
`-- seam/
    `-- tweaks-panel.jsx
```

## 6. How To Run The Project

### Easiest local path

Use:

```bash
python3 dev.py
```

On macOS, the clickable launcher is:

```text
start-dev.command
```

The launcher/control panel is intended to make local development easier by starting the database, backend, and frontend in a coordinated way.

### Manual local path

Start the database:

```bash
docker compose up -d db
```

Start the backend:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://localhost:5173
```

Admin dashboard:

```text
http://localhost:5173/admin
```

## 7. Configuration

### Backend configuration

Backend settings live in:

```text
backend/app/config.py
```

Local environment file:

```text
backend/.env
```

Template:

```text
backend/.env.example
```

Important backend variables:

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy database URL for Postgres |
| `APP_ENV` | Environment name |
| `DEBUG` | Debug flag |
| `CORS_ORIGINS` | Allowed frontend origins |
| `ADMIN_TOKEN` | Token accepted by admin endpoints |
| `OCEANSX_API_KEY` | MPA OceansX API key |
| `OCEANSX_MOCK_MODE` | `auto`, `always`, or `never` |
| `ANTHROPIC_API_KEY` | Anthropic API key for summaries and NL search |
| `ANTHROPIC_MOCK_MODE` | Enables mock AI responses |
| `OPENSANCTIONS_MOCK_MODE` | Enables local OpenSanctions fixture usage |
| `RSS_APP_FEED_1_URL` | RSS.app feed slot 1 |
| `RSS_APP_FEED_2_URL` | RSS.app feed slot 2 |
| `RSS_APP_FEED_3_URL` | RSS.app feed slot 3 |
| `RSS_APP_FEED_1_HMAC` | HMAC secret for feed slot 1 webhook |
| `RSS_APP_FEED_2_HMAC` | HMAC secret for feed slot 2 webhook |
| `RSS_APP_FEED_3_HMAC` | HMAC secret for feed slot 3 webhook |
| `POLL_POSITIONS_SECONDS` | Vessel position polling cadence |
| `ENRICH_PARTICULARS_SECONDS` | Vessel particulars enrichment cadence |
| `REFRESH_NEWS_SECONDS` | News polling cadence |

### Frontend configuration

Frontend local environment file:

```text
frontend/.env
```

Template:

```text
frontend/.env.example
```

Important frontend variables:

| Variable | Meaning |
|---|---|
| `VITE_ADMIN_TOKEN` | Sent to admin endpoints as `X-Admin-Token` |
| `VITE_API_BASE_URL` | Optional API base URL for clients that use explicit base URLs |

During Vite development, most frontend API calls are made to `/api` and proxied to the backend.

## 8. Backend Application Architecture

The backend starts in:

```text
backend/app/main.py
```

Main responsibilities:

- create the FastAPI app
- configure CORS and middleware
- register routers under `/api`
- start and stop the scheduler in lifespan
- expose health/meta endpoints
- integrate observability/rate limiting pieces

Backend folder responsibilities:

| Folder/file | Purpose |
|---|---|
| `config.py` | Pydantic settings from env |
| `db.py` | Async engine/session factory |
| `models.py` | SQLAlchemy database models |
| `schemas.py` | Pydantic request/response models |
| `scheduler.py` | Recurring ingestion/scoring/indexing jobs |
| `cache.py` | In-process cache helpers |
| `limiter.py` | SlowAPI limiter setup |
| `metrics.py` | Metrics support |
| `observability.py` | Observability hooks/utilities |
| `auth/` | Admin auth and OAuth placeholder logic |
| `clients/` | External API clients |
| `routers/` | FastAPI route modules |
| `services/` | Business logic and database writes |
| `utils/` | Small utilities: IMO validation, timezone, HTTP allowlist, vessel labels |
| `mocks/` | Local fixture data |
| `alembic/` | Migration scripts and Alembic env |

## 9. Backend Routers And APIs

All application routes are mounted under `/api`.

### Meta routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Health check with DB status and version |
| GET | `/api/about` | Basic app/about metadata |

### About/source attribution routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/about` | Source attribution and dataset metadata |

Note: there are both meta/about concerns and the `/about` router. During an overhaul, consider consolidating naming if duplicate route behavior becomes confusing.

### Vessel routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/vessels/positions` | Current vessel positions for the map |
| GET | `/api/vessels/{imo}` | Full vessel detail, particulars, current position, movements |
| GET | `/api/vessels/new-arrivals` | Vessels first observed within a given hour window |
| GET | `/api/vessels/due-to-arrive` | MPA due-to-arrive data |
| GET | `/api/vessels/due-to-depart` | MPA due-to-depart data |

Current vessel responses include:

- IMO
- MMSI
- display name with flag emoji
- raw flag code
- flag country name
- flag emoji
- raw vessel type code
- full vessel type label
- year built
- gross tonnage
- current lat/lon
- speed/course/heading
- inferred status
- sanctions/shadow-fleet flags
- latest composite risk when available

The detail endpoint also attempts to save returned vessel particulars back to the database.

### History routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/history/trail/{imo}` | 24-hour vessel trail from `position_archive` |

### SSE routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/sse/positions` | Server-sent events for position updates |

The frontend subscribes to this endpoint so the map can refresh when the backend finishes a poll.

### Geospatial routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/geo/layers` | List available geospatial layers |
| GET | `/api/geo/layer/{layer_name}` | Return one GeoJSON layer |

These feed the layer panel in the map UI.

### Macro routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/macro/cargo/throughput` | Cargo throughput data |
| GET | `/api/macro/container/throughput` | Container throughput data |
| GET | `/api/macro/bunkers/sales` | Bunker sales data |
| GET | `/api/macro/shipping/tonnage` | Shipping tonnage data |
| GET | `/api/macro/vessel-calls` | Vessel call volume data |

These appear to be planned or supporting maritime context endpoints. The current main UI does not use all of them heavily.

### Ports routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/ports/terminals` | Terminal and port geometry/support data |

### News routes

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/news/ingest/{feed_slot}` | RSS.app webhook ingestion |
| POST | `/api/news/{news_id}/summarize` | AI-generated article summary |
| GET | `/api/news/items` | News list with optional entity filtering |

News supports:

- URL deduplication
- feed slots
- entity extraction
- vessel/port/entity tags
- summary generation

### Sanctions routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/sanctions/vessel/{imo}` | Sanctions matches for a vessel |
| GET | `/api/sanctions/review-queue` | Admin review queue |
| POST | `/api/sanctions/review-queue/{item_id}/confirm` | Confirm a pending match |
| POST | `/api/sanctions/review-queue/{item_id}/reject` | Reject a pending match |

Sanctions design rule:

- IMO-exact matches can be auto-confirmed.
- Non-exact matches must go to review.

### Risk routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/risk/vessel/{imo}` | Recent risk history for a vessel |
| GET | `/api/risk/leaderboard` | Top vessels by latest composite risk |

Risk responses include:

- composite score
- sanctions score
- shadow fleet score
- age score
- flag MoU score
- congestion score
- weather score
- optional components JSON

### Search routes

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/search/nl` | Natural-language vessel search |

This uses an LLM parser or mock parser to transform user language into a structured `SearchFilterSpec`, then runs deterministic SQL filters.

### Journal routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/journal/phases` | Indexed journey phase docs |
| GET | `/api/journal/adrs` | Indexed ADR docs |
| GET | `/api/journal/glossary` | Indexed glossary terms |

The journal drawer in the frontend reads these endpoints.

### Admin routes

All admin routes require admin auth.

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/admin/force-poll` | Force vessel position poll |
| POST | `/api/admin/force-risk-score` | Force risk scoring |
| POST | `/api/admin/force-weather` | Force weather pull |
| POST | `/api/admin/force-news` | Force news poll/extraction path |
| POST | `/api/admin/force-opensanctions` | Force OpenSanctions ingest/matching |
| POST | `/api/admin/force-journal-index` | Force journal/glossary indexing |
| GET | `/api/admin/db` | List DB Explorer tables |
| GET | `/api/admin/db/{table}` | Read one table page |
| GET | `/api/admin/db/{table}/{pk}` | Read one row by primary key |
| GET | `/api/admin/stats/sources` | Data source health |
| GET | `/api/admin/stats/vessel-types` | Vessel type distribution |
| GET | `/api/admin/stats/risk-histogram` | Risk histogram |
| GET | `/api/admin/stats/top-risk` | Highest-risk vessels |
| GET | `/api/admin/stats/sanctions-overview` | Sanctions/shadow/review counters |
| GET | `/api/admin/stats/news-entities` | Top news entity mentions |
| GET | `/api/admin/stats/audit-log` | Recent audit log |
| GET | `/api/admin/stats/dependency-audit` | Dependency audit history |

## 10. Services Layer

The services layer contains most of the business behavior.

| Service | Responsibility |
|---|---|
| `anchorage_dwell.py` | Computes dwell intervals around terminals/anchorages |
| `audit_log.py` | Writes audit log rows |
| `data_source_status.py` | Tracks source success/failure health |
| `entity_extraction.py` | Extracts entities from news articles |
| `geospatial.py` | Loads/returns geospatial layers |
| `history.py` | Writes live/archive positions and trails |
| `journal_indexer.py` | Parses docs into journal tables |
| `macro.py` | Fetches macro maritime stats |
| `news.py` | News feed ingestion and deduplication |
| `news_summarizer.py` | AI/mocked news summaries |
| `nl_search.py` | Natural language parse and SQL filter execution |
| `opensanctions_ingest.py` | Stores/project OpenSanctions data |
| `ports.py` | Terminal and port lookup |
| `risk_scorer.py` | Composite risk scoring |
| `sanctions_matcher.py` | Sanctions matching logic |
| `shadow_fleet.py` | Derives vessel shadow fleet flags |
| `sse_broadcaster.py` | Broadcasts SSE events |
| `vessel_master.py` | Upserts vessel master and SCD2 history |
| `vessels.py` | Normalizes MPA vessel records |
| `weather.py` | Pulls weather observations |

## 11. External Clients

| Client | File | Purpose |
|---|---|---|
| OceansX/MPA | `clients/oceansx.py` | Vessel positions, particulars, movements, due arrivals/departures, geospatial/macro data |
| OpenSanctions | `clients/opensanctions.py` | Maritime sanctions entities |
| Open-Meteo | `clients/open_meteo.py` | Marine weather observations |
| RSS.app | `clients/rss_app.py` | Maritime RSS feeds |
| Anthropic | `clients/anthropic_client.py` | Summaries and natural-language parsing |

Each client generally supports mock behavior or has mock fixtures available.

## 12. Database Model

The database is Postgres with TimescaleDB and PostGIS extensions.

Target new-version database principle:

- The database should become an interconnected maritime intelligence graph implemented with strong relational tables.
- Vessels, companies, owners, operators, ISM managers, class societies, sanctions entities, source records, and historical relationships should be queryable without relying on UI-only logic.
- LLMs can assist with extraction and linking, but durable truth should be represented in auditable tables with source provenance, confidence, validity windows, and review status.

### Vessel master and history

| Table | Purpose |
|---|---|
| `vessel` | One row per IMO with current vessel facts |
| `vessel_name_history` | SCD2 name history |
| `vessel_flag_history` | SCD2 flag history |
| `vessel_owner_history` | SCD2 owner history |
| `vessel_operator_history` | SCD2 operator/manager history |
| `vessel_class_history` | SCD2 classification society history |
| `vessel_topic` | OpenSanctions/topic tags |
| `vessel_organization_link` | Vessel-to-organization relationships |

The vessel table stores fields such as:

- IMO
- MMSI
- name
- call sign
- flag
- vessel type
- year built
- tonnage
- dimensions
- owner/operator/ISM/class
- shadow fleet flag
- sanctions status
- first and last observed timestamps
- last enrichment timestamp

Target new-version vessel history:

- Every material vessel-particular change should be stored with `valid_from`, `valid_to`, source, confidence, and detection timestamp.
- Ownership and operator changes should be visible from vessel detail.
- Company-linked sanctions should resolve through relationship tables to affected vessels.
- Current values should be derived from the latest valid relationship/fact, not manually duplicated in multiple places without clear source rules.

### Position tables

| Table | Purpose |
|---|---|
| `position_live` | Current/recent position rows |
| `position_archive` | Deduped historical positions |

Design:

- `position_live` is the active snapshot-style table.
- `position_archive` stores movement history only when the vessel moved enough.
- Archive dedup is based on distance, heading delta, and speed delta.

### Ports and terminals

| Table | Purpose |
|---|---|
| `port` | Port records |
| `port_alias` | Alternate port names |
| `terminal` | Terminal records |
| `terminal_geom` | Terminal geometry |

### News

| Table | Purpose |
|---|---|
| `news_feed` | RSS feed slot metadata |
| `news_item` | Articles |
| `news_entity_mention` | Extracted vessel/port/org/entity mentions |
| `news_summary` | AI-generated summaries |

### Sanctions and organizations

| Table | Purpose |
|---|---|
| `opensanctions_entity_raw` | Raw OpenSanctions payloads |
| `organization` | Projected organization entities |
| `organization_alias` | Organization aliases |
| `organization_topic` | Organization topics |
| `sanctions_source` | Sanctions source/dataset metadata |
| `sanctions_listing` | Vessel-level sanctions entries |
| `sanctions_match` | Vessel-to-sanctions matches |
| `sanctions_match_history` | Status transition history |
| `agent_review_queue` | Human review queue for non-exact matches |

### Risk, weather, and port state

| Table | Purpose |
|---|---|
| `weather_observation` | Open-Meteo marine weather observations |
| `anchorage_dwell` | Vessel dwell events |
| `risk_score` | Hourly composite risk scores |
| `flag_performance_year` | MoU flag performance ratings |
| `mou_inspection` | Port State Control inspection records |

### Admin, journal, and provenance

| Table | Purpose |
|---|---|
| `audit_log` | Admin/system audit events |
| `journal_phase` | Indexed project journey phase docs |
| `journal_adr` | Indexed ADR docs |
| `journal_event` | Journal events |
| `glossary_term` | Indexed glossary terms |
| `data_source_status` | Last success/failure per data source |
| `outbound_request_log` | External request logging |
| `dependency_audit_log` | Dependency audit results |
| `data_source_attribution` | Source attribution metadata |

## 13. Migrations

Migrations live in:

```text
backend/app/alembic/versions/
```

Current migration sequence:

| Migration | Purpose |
|---|---|
| `0001_init_extensions_and_roles.py` | Extensions and base database setup |
| `0002_vessel_and_position_schema.py` | Vessel and position tables |
| `0003_phase2_geospatial.py` | Geospatial tables |
| `0004_phase3_news.py` | News tables |
| `0005_phase4a_opensanctions.py` | OpenSanctions/sanctions tables |
| `0006_phase5a_weather_risk.py` | Weather, dwell, risk, flag performance |
| `0007_phase6a_intelligence.py` | Intelligence additions |
| `0008_phase7a_hardening.py` | Hardening additions |
| `0009_phase7b_admin.py` | Admin/dashboard support |

Run migrations:

```bash
cd backend
alembic upgrade head
```

During overhaul, keep migrations append-only unless you intentionally reset local development databases.

## 14. Scheduled Jobs

Scheduler file:

```text
backend/app/scheduler.py
```

The scheduler starts with FastAPI.

| Job function | Trigger | Purpose |
|---|---|---|
| `_job_index_journal` | hourly | Index docs/ADRs/glossary into DB |
| `_job_poll_positions` | interval from `POLL_POSITIONS_SECONDS` | Poll MPA positions, write vessel/position data, publish SSE |
| `_job_enrich_vessel_particulars` | interval from `ENRICH_PARTICULARS_SECONDS` | Enrich stale vessels with particulars |
| `_job_refresh_macro` | daily at 03:00 America/Chicago | Refresh macro maritime data |
| `_job_refresh_geospatial` | daily at 04:00 America/Chicago | Refresh geospatial layers |
| `_job_refresh_news` | interval from `REFRESH_NEWS_SECONDS` | Poll RSS feed slots |
| `_job_extract_entities` | minute 20 UTC hourly | Extract entities from pending news |
| `_job_prune_history` | daily at 02:00 America/Chicago | Prune configured history/news |
| `_job_refresh_opensanctions` | daily at 04:00 America/Chicago | Ingest OpenSanctions data |
| `_job_refresh_shadow_fleet_flags` | daily at 04:30 America/Chicago | Derive shadow fleet flags |
| `_job_pull_weather` | minute 30 UTC hourly | Pull Open-Meteo weather |
| `_job_compute_anchorage_dwell` | minute 10 UTC hourly | Compute dwell records |
| `_job_score_risk_hourly` | minute 15 UTC hourly | Score vessel risk |
| `_job_dependency_audit` | daily at 06:00 America/Chicago | Run dependency audit |

Admin force actions trigger a subset of these flows manually.

## 15. Data Flows

### Position ingestion flow

1. Scheduler or admin force poll calls `clients/oceansx.py`.
2. `services/vessels.py` normalizes upstream MPA records.
3. `services/vessel_master.py` upserts `vessel`.
4. `services/vessel_master.py` records name and flag SCD2 changes.
5. `services/history.py` writes `position_live`.
6. `services/history.py` writes `position_archive` if dedup rules allow.
7. `services/history.py` attempts terminal assignment.
8. Backend invalidates the positions cache.
9. Backend publishes `positions_updated` over SSE.
10. Frontend invalidates React Query position cache and refetches.

### Vessel detail/enrichment flow

1. User clicks a vessel.
2. Frontend calls `/api/vessels/{imo}`.
3. Backend reads the `vessel` row.
4. Backend fetches particulars and movements from OceansX.
5. Backend saves returned particulars to `vessel` and history tables where possible.
6. Backend fetches the current live position snapshot.
7. Backend returns detail data with DB values first, then particulars fallback, then live-position fallback.

Important limitation:

- Owner, operator, ISM manager, and classification society are not available in all live position records.
- Those fields depend on the particulars endpoint.
- If the source does not return those fields, the UI should say "Not returned by source".

### Sanctions flow

1. Scheduler downloads or mocks OpenSanctions maritime entities.
2. Raw payloads are inserted into `opensanctions_entity_raw`.
3. Projection tables are updated.
4. Matcher runs against vessels.
5. IMO-exact matches can become `auto_confirmed`.
6. Fuzzy/name/org-link matches enter `agent_review_queue`.
7. Admin confirms or rejects review items.
8. Vessel status and sanctions matches appear in detail panel and risk scoring.

### Shadow fleet flow

1. OpenSanctions/topic information is ingested.
2. `vessel_topic` records represent relevant topic tags.
3. `shadow_fleet.py` derives `vessel.is_shadow_fleet`.
4. The frontend displays marker badges and a shadow fleet filter.

### Risk scoring flow

1. Risk scorer reads vessel data and related signals.
2. Component scores are calculated.
3. `risk_score` row is written.
4. Map and detail panel can show latest risk.
5. Admin stats show risk distribution and top-risk vessels.

Current components:

- sanctions score
- shadow fleet score
- age score
- flag MoU score
- congestion score
- weather score

### News intelligence flow

1. RSS.app webhook or scheduled polling provides article data.
2. `news.py` deduplicates articles by URL hash.
3. Entity extraction identifies vessels/ports/entities.
4. News drawer lists articles.
5. User can request summary.
6. Summary is written to `news_summary`.
7. Entity tags can be used as UI filters.

### Geospatial flow

1. Scheduler refreshes geospatial data.
2. Service stores/serves GeoJSON layers.
3. Frontend layer panel lists available layers.
4. User toggles layers on the Leaflet map.

### Journal flow

1. Markdown docs live under `docs/journey`, `docs/adr`, and `docs/glossary.md`.
2. `journal_indexer.py` parses them.
3. Indexed data is written to journal tables.
4. Frontend journal drawer displays phases, ADRs, and glossary.

## 16. Frontend Architecture

Frontend entry point:

```text
frontend/src/main.tsx
```

Main route switch:

```text
frontend/src/App.tsx
```

`App.tsx` chooses:

- `LiveMap` for `/`
- lazy-loaded `AdminApp` for `/admin` or `#admin`

Frontend folders:

| Folder | Purpose |
|---|---|
| `api/` | API client functions |
| `components/` | Main user interface components |
| `components/admin/` | Admin dashboard tabs |
| `lib/` | SSE, timezone, live position hooks |
| `store/` | Zustand local state |
| `styles/` | Global Tailwind/SEAM CSS |
| `types/` | TypeScript API/domain interfaces |

## 17. Frontend State Model

### React Query owns server state

Examples:

- vessel positions
- vessel detail
- vessel sanctions
- vessel risk
- trails
- geospatial layers
- news
- journal data
- admin stats
- review queue

### Zustand owns shared UI state

Examples:

- selected vessel IMO
- highlighted vessel IMO
- risk threshold
- timezone preference
- map filters

### Local component state owns panel toggles

Examples:

- news drawer open/closed
- arrivals drawer open/closed
- journal drawer open/closed
- search open/closed
- geospatial layers panel
- risk slider panel

## 18. Main Frontend Components

### `LiveMap.tsx`

Main full-screen map shell.

Responsibilities:

- render the Leaflet map
- load live vessel positions through `useLivePositions`
- apply shadow fleet and risk filters
- render vessel markers
- render selected vessel trail
- render top SEAM header
- render toolbar buttons
- manage drawer/popup open state
- mount `VesselDetailPanel` for selected vessels

### `VesselMarker.tsx`

Renders each vessel as a Leaflet marker.

Features:

- heading-aware arrow icon
- status color
- selected marker size
- red ring for sanctioned vessels
- amber dot for shadow fleet vessels
- tooltip with vessel name, sanctions/shadow status, speed, flag country, and vessel type

### `VesselDetailPanel.tsx`

Right-side vessel detail drawer.

Features:

- vessel name with flag emoji
- IMO
- sanctions/shadow alerts
- risk score and components
- current position
- full flag country name
- full vessel type name
- year built, tonnage, DWT, LOA, beam
- owner/operator/ISM/class
- sanctions matches
- last observed timestamp
- risk disclaimer

Intended behavior:

- If particulars are missing from the source, show a clear "Not returned by source" message.
- If detail endpoint returns new particulars, backend should save them.

Target new-version behavior:

- Avoid covering right-side map tabs/tools; consider a bottom sheet, inspector route, resizable drawer, split view, or selected-vessel workspace instead of the current fixed right drawer.
- Show current particulars and historical changes in separate sections.
- Include timelines for name, flag, owner, operator, ISM manager, and classification society.
- Show related companies and sanctions-linked organizations connected to the vessel.
- Show provenance and freshness for important fields.
- Clearly distinguish missing source data from not-yet-fetched data.

### `NewsDrawer.tsx`

Left-side news drawer.

Features:

- lists maritime news
- shows article age
- shows feed/source metadata
- shows entity tags
- can filter by clicked entity
- can request AI summary

### `NewArrivalsDrawer.tsx`

Left-side drawer for vessels first observed recently.

Features:

- lists vessels first observed in the last 24 hours by default
- shows flag country/emoji
- shows full vessel type
- shows sanctions/shadow badges
- selecting an item opens vessel detail

### `SearchBar.tsx`

Natural-language vessel search popup.

Features:

- user enters plain language query
- backend parses query into structured filters
- displays parsed filter pills
- lists matching vessels
- selecting result opens vessel detail

Expected query types:

- sanctioned vessels
- shadow fleet vessels
- vessels under a flag
- vessels above/below risk thresholds
- vessel type filters
- age/tonnage filters

### `JournalDrawer.tsx`

Project documentation drawer.

Features:

- phases
- ADRs
- glossary terms
- status badges

### `GeospatialOverlay.tsx`

Geospatial layers.

Features:

- fetches layer list
- fetches selected GeoJSON layers
- renders them on Leaflet
- provides layer toggle panel

### `TimelineBar.tsx`

Trail and scrubber.

Features:

- fetches selected vessel trail
- renders polyline
- exposes 24-hour scrub control

### `DataSourceFooter.tsx`

Displays source/disclaimer style footer information.

### `RiskBadge.tsx`

Small score badge.

Expected role:

- consistent risk tier display across detail/admin/list views

### `TimeZoneSelector.tsx`

Allows display timezone selection.

Storage rule:

- backend stores UTC
- frontend can display selected timezone

## 19. Admin Frontend

Admin shell:

```text
frontend/src/components/admin/AdminApp.tsx
```

Admin tabs:

| Tab | Component | Purpose |
|---|---|---|
| Overview | `OverviewTab.tsx` | Force actions, data source health, audits |
| Approvals | `ApprovalsTab.tsx` | Sanctions review queue |
| Data Explorer | `DBExplorerTab.tsx` | Read-only table browser |
| Stats | `StatsTab.tsx` | Charts and counters |
| Ops Swarm | inline placeholder | Intended runtime operations swarm panel |

Target new-version admin additions:

- Configuration tab for API keys, source settings, mock/live mode, and connection testing.
- Journal/ADR/glossary tab moved from the main map into admin.
- Newest-to-oldest sorting for journal entries, ADRs, and change history.
- Job history tab showing scheduler runs, failures, retries, and admin-forced runs.
- Data quality tab for missing particulars, stale vessels, enrichment failures, and source coverage.

### Admin Overview

Features:

- force poll
- force risk score
- force weather
- force news
- force OpenSanctions
- force journal index
- data source health table
- audit log
- dependency audit log

### Admin Approvals

Features:

- load review queue
- filter queue by status
- confirm pending sanctions matches
- reject pending sanctions matches

Expected future improvements:

- richer match evidence display
- reviewer notes input
- bulk actions
- reviewer identity

### Admin DB Explorer

Features:

- table list
- page through rows
- inspect allowed tables only
- dynamically filters allowed tables to those that exist in connected DB

Important limitation:

- It is a lightweight internal read-only explorer.
- It is not a replacement for a database admin tool.

### Admin Stats

Features:

- vessel type distribution
- risk histogram
- top-risk vessels
- sanctions overview counters
- news entity mentions

## 20. API Client Layer

Frontend API clients:

| File | Purpose |
|---|---|
| `api/vessels.ts` | positions, vessel detail, trails, geospatial layers |
| `api/news.ts` | news list |
| `api/intelligence.ts` | summaries, new arrivals, NL search |
| `api/sanctions.ts` | vessel sanctions and review queue |
| `api/risk.ts` | vessel risk and leaderboard |
| `api/journal.ts` | journal docs |
| `api/admin.ts` | admin actions, DB explorer, stats |

Admin requests include `X-Admin-Token`.

## 21. Styling And Design System

The frontend uses Tailwind plus global CSS:

```text
frontend/src/styles/index.css
```

Current design language:

- glass panels
- muted light maritime palette
- compact dashboard density
- Leaflet full-screen map
- right-side vessel detail drawer
- left-side utility drawers
- animated popovers and panel entrances
- admin shell aligned with SEAM dashboard template

Important CSS primitives:

- `glass-panel`
- `glass-panel-bright`
- `toolbar-btn`
- `tab-btn`
- `admin-shell`
- `admin-sidebar`
- `admin-nav-item`
- `admin-card`
- `admin-table`
- `vessel-detail-panel`
- `left-drawer-panel`
- `menu-popover`
- `search-popover`

During overhaul, preserve consistency by using these classes or replacing them with a coherent design system.

## 22. Vessel Display Normalization

Backend utility:

```text
backend/app/utils/vessel_labels.py
```

Current responsibilities:

- normalize flag codes
- produce flag emoji
- convert flag codes to full country/registry names
- convert vessel type codes to full labels
- produce display vessel names with flag emoji

Examples:

| Raw | Display |
|---|---|
| `PA` | Panama |
| `SG` | Singapore |
| `CS` | Container Ship |
| `BC` | Bulk Carrier |
| `GT` | Gas Tanker |
| `TA` | Oil Tanker |
| `TC` | Chemical Tanker |

Important note:

- The database stores raw flag and vessel type values.
- API responses add display labels.
- Frontend should display labels and preserve raw codes where helpful.

## 23. Security Model

### Admin auth

Admin endpoints use:

```text
X-Admin-Token
```

Backend source:

```text
ADMIN_TOKEN
```

Frontend source:

```text
VITE_ADMIN_TOKEN
```

The admin auth module also accepts Bearer-style admin tokens in recent code.

### HMAC webhooks

RSS.app webhook ingestion is designed to validate HMAC signatures using per-feed secrets.

### HTTP allowlist

There is a utility for outbound HTTP allowlisting:

```text
backend/app/utils/http_allowlist.py
```

### Current security level

This is suitable for local/internal development. A production deployment should add:

- real user authentication
- role-based access control
- HTTPS/TLS termination
- secure secret management
- admin audit identity
- stronger frontend/admin separation
- rate limit tuning
- deployment-level network controls

## 24. Observability And Health

Implemented/supporting pieces:

- `/api/health`
- data source status table
- audit log table
- dependency audit log table
- outbound request log table
- metrics module
- scheduler logs
- admin overview dashboard

Expected operational behavior:

- every source pull should record success/failure
- force actions should write audit events
- dependency audit results should be visible in admin
- failures should appear in backend logs and data source health

## 25. Testing

Backend tests:

```text
backend/tests/
```

Current test areas:

- health endpoint
- vessel normalization and history helpers
- sanctions matcher
- risk scorer
- natural-language search
- hardening behavior
- admin behavior

Frontend tests:

```text
frontend/src/lib/timezone.test.ts
```

Common verification commands:

```bash
cd backend
pytest
```

```bash
cd frontend
npm run typecheck
npm run build
```

Known test note:

- Some vessel tests may be stale relative to current IMO validation/mock data behavior. Treat failing tests as useful signal before overhaul; do not blindly delete them.

## 26. Mocks And Offline Development

Mock fixtures live in:

```text
backend/app/mocks/
```

Important fixtures:

- `vessel_positions_snapshot.json`
- `vessel_particulars.json`
- `vessel_movements.json`
- `vessels_due_to_arrive.json`
- `vessels_due_to_depart.json`
- geospatial layer JSON files
- macro statistics JSON files
- `opensanctions_maritime.json`
- `weather_response.json`
- AI response mocks
- RSS/news webhook mock
- flag performance data

Mock behavior:

- OceansX can use mocks when no API key exists.
- Anthropic can use mock mode.
- OpenSanctions can use mock mode.

This is important because the project should remain runnable without paid or restricted external access.

## 27. Complete Feature Inventory

### Implemented main-dashboard features

- full-screen Leaflet map
- live vessel markers
- heading-based marker direction
- status-colored markers
- selected vessel marker sizing
- sanctioned marker ring
- shadow fleet marker indicator
- vessel tooltip
- flag emoji in vessel display name
- full flag country display
- full vessel type display
- vessel detail drawer
- vessel particulars display
- current position display
- vessel movements fetch
- sanctions match display
- risk score display
- risk component rows
- last observed time display
- risk disclaimer
- left-side news drawer
- news entity tags
- AI summary request for articles
- new arrivals drawer
- natural-language search
- parsed search spec pills
- geospatial layer toggle panel
- GeoJSON map rendering
- shadow fleet-only filter
- risk threshold filter
- 24-hour trail polyline
- timeline scrubber
- project journal drawer
- phases/ADRs/glossary browser
- SEAM header
- source/status footer components
- panel and menu animations

### Implemented admin features

- admin dashboard shell
- admin token header support
- force poll
- force risk scoring
- force weather
- force news
- force OpenSanctions
- force journal indexing
- data source health
- audit log
- dependency audit log
- sanctions review queue
- confirm review item
- reject review item
- DB Explorer table list
- DB Explorer pagination
- DB Explorer row lookup
- vessel type chart
- risk histogram
- top-risk list
- sanctions overview counters
- news entity stats
- Ops Swarm placeholder tab

### Implemented backend/data features

- async FastAPI app
- Postgres/Timescale/PostGIS models
- Alembic migrations
- scheduled position polling
- live position persistence
- deduped archive persistence
- vessel master upsert
- SCD2 name history
- SCD2 flag history
- SCD2 owner history
- SCD2 operator history
- SCD2 class history
- vessel particulars enrichment
- current detail fallback logic
- label normalization for flags/types
- SSE position update broadcasting
- geospatial layer ingestion/serving
- macro data endpoints
- news webhook ingestion
- news polling fallback
- article deduplication
- entity extraction
- news summarization
- OpenSanctions ingest
- sanctions matching
- review queue
- shadow fleet derivation
- Open-Meteo weather ingestion
- anchorage dwell computation
- composite risk scoring
- journal indexing
- admin auth dependency
- data source status tracking
- dependency audit logging
- audit logging
- mock-mode support

## 28. Intended Features And Expected Future Direction

These features are implied by the architecture, existing placeholders, ADRs, or partial implementation. They are the most important candidates for the overhaul backlog.

### Product and UX

- clearer analyst workflow from alert to review to decision
- better vessel detail layout for dense particulars
- redesigned vessel detail presentation that does not cover or conflict with right-side map tabs/tools
- vessel hover tooltip should avoid duplicate flag display; if the emoji appears in the vessel name, the country line should not repeat the same flag symbol
- richer sanctions evidence panel
- vessel comparison view
- persistent saved filters
- bookmark/watchlist support
- alerting for new high-risk arrivals
- map legend
- better mobile layout or explicit desktop-only positioning
- improved empty/error/loading states everywhere
- unified source attribution in each panel
- journal/project documentation should move out of the main map toolbar and into the admin dashboard
- journal/admin documentation views should sort newest-to-oldest by default
- full SEAM identity should be applied across the new version, replacing mixed OceansX Visualizer naming where practical

### Admin and operations

- real authenticated user accounts
- RBAC for admin/reviewer/operator roles
- admin-configurable API keys and external service settings, with secure storage and clear validation/test-connection controls
- admin configuration UI for mock mode versus live API mode where appropriate
- reviewer notes in approvals UI
- bulk confirm/reject
- audit identity per admin action
- richer job status page
- scheduler/job run history
- failed job retry controls
- DB Explorer column filters/search
- safer DB Explorer row rendering for large JSON fields
- admin-visible configuration audit history so API key/source setting changes are documented
- journal and ADR management/indexing should be accessible from admin, not the main analyst map

### Ops Swarm

The admin UI has an Ops Swarm placeholder. The intended concept from docs/ADRs is a runtime operations swarm that can observe data quality and operational health while writing only to staging/controlled tables.

Expected eventual features:

- agent status list
- agent task queue
- agent-generated observations
- proposed actions requiring approval
- staging table review
- audit trail of autonomous suggestions
- hard boundary preventing autonomous destructive writes

### Intelligence

- richer entity extraction beyond dictionary matching
- organization linking from news to vessels
- better vessel-owner/operator network graph
- interconnected company, vessel, ownership, manager, operator, and sanctions database
- ability to trace sanctions or adverse signals from a company to all linked vessels
- ability to trace a vessel back to companies, owners, operators, managers, sanctions entities, and historical relationships
- cheap LLM-assisted extraction/linking may be used, but the core relationship graph should be enforced by a strong relational database structure
- article clustering
- multilingual news handling
- explainable AI summaries with citations/source snippets
- confidence scoring for extracted entities

### Risk

- more transparent risk formula UI
- historical risk trend chart
- component explanations
- configurable risk weights
- risk model versioning
- risk backtesting
- false-positive review feedback loop

### Sanctions

- more complete dataset coverage
- match evidence display
- organization-link matching UI
- match confidence calibration
- rescreening history
- sanctions status timeline
- exportable compliance report

### Vessel data

- stronger vessel particulars coverage
- debug and verify why owner/operator/ISM manager/class are missing for many vessels; assume this may be a bug until proven to be upstream absence
- systematic gathering and persistence of all vessel data and particulars in the backend
- every fetched vessel detail/particulars response should be saved or considered for saving, not only displayed transiently
- historical changes to vessel name, flag, ownership, operator, ISM manager, classification society, and other important particulars should be persisted and visible when a vessel is clicked
- vessel detail UI should include a history/timeline section showing changes in ownership, name, flag, class, manager, and operator
- richer flag registry handling
- better vessel type taxonomy
- owner/operator/ISM/class source confidence
- data freshness indicators per field
- UI distinction between "unknown", "not returned", and "not yet enriched"
- scheduled enrichment prioritization for selected/high-risk vessels
- explicit freshness and provenance per particulars field, including source name and last fetched timestamp
- prioritization queue for vessels missing important particulars

### Geospatial

- better layer metadata
- layer legends
- terminal names and hover info
- anchorage areas
- port boundary overlays
- geofence alerts

### Deployment

- production Dockerfile(s)
- Caddy/reverse-proxy config if deploying publicly
- environment-specific config
- secret management
- database backup/restore docs
- migration rollback strategy
- CI pipeline
- frontend visual regression checks
- backend integration tests against ephemeral Postgres

### Performance and freshness

- optimize for the user seeing useful data as fast as possible
- keep the default map payload lean and avoid sending deep particulars for every vessel on initial load
- cache carefully while making data freshness clear
- the main "live" vessel map only needs to represent roughly the past hour of activity
- older detailed history should remain available in historical tables, but should not slow down the main map experience
- backend APIs should separate lightweight list/map payloads from heavy detail/relationship payloads
- vessel detail panels should lazy-load deep history, ownership graph, sanctions evidence, and particulars only when needed
- indexes should be designed around the main user queries: current vessels, selected vessel detail, latest risk, sanctions status, and company/vessel relationship lookups

### Codebase simplification

- remove unnecessary files, abandoned components, unused template artifacts, stale experiments, and dead code during the overhaul
- simplify the architecture to only what is essential for the app's actual product direction
- rename files and concepts where it improves clarity, especially if the product identity becomes SEAM
- consider renaming `dev.py` to a clearer launcher name such as `start.py`, `run.py`, or `seam.py`
- update docs, scripts, references, and developer commands after any rename so the project remains easy to start
- avoid preserving old abstractions only because they exist; keep only what serves ingestion, intelligence, admin operations, and the map/dashboard experience

## 29. Current Gaps And Risks

### Data quality gaps

- Not all vessel particulars are returned by the upstream API.
- Owner/operator/ISM/class may be unavailable for many vessels.
- Missing owner/operator/ISM/class data needs a focused debugging pass in the new version before accepting it as an upstream limitation.
- The system needs a more rigorous distinction between "source did not return this", "not fetched yet", "fetch failed", and "field changed historically".
- Company/vessel/ownership relationships are not yet modeled deeply enough for full sanctions network tracing.
- Mock data may not match real source behavior exactly.
- Vessel type codes require an explicit mapping and may need expansion.
- Flag names are mapped locally and may need a complete ISO/registry list.

### Technical gaps

- Frontend test coverage is minimal.
- Some backend tests may be stale.
- Admin auth is token-based, not full user auth.
- The DB Explorer is internal and simple.
- Error boundaries are limited.
- There may be naming drift between OceansX and SEAM.
- API keys and external service configuration are currently env-driven; the target overhaul should support secure admin-dashboard configuration.
- Some files and code paths are historical or transitional and should be removed if not essential.

### Operational gaps

- No full production deployment guide in this document yet.
- No CI/CD description.
- No backup/restore process documented.
- No job-run history table beyond logs/audit-style tables.
- No full incident response playbook.
- No complete admin-managed configuration system for external data sources, API keys, mock/live mode, and validation.

### Product gaps

- Ops Swarm is a placeholder.
- Review workflow is functional but basic.
- Risk explainability can be improved.
- News/entity intelligence can be deeper.
- Analyst workflows need sharper end-to-end design.
- Journal/ADR browsing currently exists in the main map experience, but the new version should move it into admin.
- Vessel detail currently uses a right drawer that can compete with right-side map tools; the new version needs a cleaner layout pattern.

## 30. Development Commands

Backend:

```bash
cd backend
pytest
ruff check .
alembic upgrade head
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
npm run test
```

Local launcher:

```bash
python3 dev.py
```

macOS launcher:

```bash
./start-dev.command
```

## 31. Common Maintenance Tasks

### Add a backend endpoint

1. Add route in `backend/app/routers/`.
2. Put business logic in `backend/app/services/`.
3. Add request/response model in `schemas.py` if needed.
4. Register router in `main.py` if it is a new router.
5. Add tests under `backend/tests/`.
6. Add frontend API client if UI needs it.

### Add a database table

1. Add SQLAlchemy model in `models.py`.
2. Add Alembic migration.
3. Add schema models if API exposes it.
4. Add service-layer writes/reads.
5. Add admin DB Explorer allowlist entry if appropriate.
6. Run `alembic upgrade head`.
7. Add tests.

### Add a scheduled job

1. Implement job function in `scheduler.py`.
2. Put reusable logic in `services/`.
3. Add data source status logging where appropriate.
4. Add audit log if user/admin initiated.
5. Register with APScheduler.
6. Add admin force action if useful.
7. Document cadence and side effects.

### Add a frontend feature

1. Add API client in `frontend/src/api`.
2. Add TypeScript types in `frontend/src/types`.
3. Use React Query for server data.
4. Use Zustand only for shared UI state.
5. Add component under `components`.
6. Reuse SEAM styles or update the design system coherently.
7. Run typecheck/build.

### Add an admin feature

1. Add protected backend route under `/api/admin`.
2. Use `require_admin`.
3. Add API function to `frontend/src/api/admin.ts`.
4. Add UI to an admin tab.
5. Write audit log entries for mutating operations.
6. Add tests.

## 32. Troubleshooting

### Frontend loads but API calls fail

Check backend:

```bash
curl http://localhost:8000/api/health
```

Check Vite proxy:

```text
frontend/vite.config.ts
```

### Admin returns 401

Make sure:

```text
backend/.env: ADMIN_TOKEN=...
frontend/.env: VITE_ADMIN_TOKEN=...
```

Restart both backend and frontend after changing env.

### Admin DB Explorer returns 500

Likely causes:

- stale table name in frontend/browser state
- migration not applied
- database schema mismatch
- table exists in model but not current database

The current backend filters explorer tables to those that exist, but direct stale URLs can still be confusing.

### Stats page is empty

Likely causes:

- no data ingested yet
- no risk scoring run yet
- admin token missing
- database is empty
- scheduled jobs disabled/not running

Use admin force actions:

- Force Poll
- Force Risk
- Force Weather
- Force OpenSanctions
- Force Journal Index

### Map has no vessels

Likely causes:

- backend is down
- database is down
- position poll has not run
- MPA key missing while mock mode is `never`
- Vite proxy is not reaching backend

### Vessel owner/operator/ISM/class missing

Likely causes:

- upstream particulars endpoint did not return the field
- vessel has not been enriched yet
- real source has incomplete data
- current mock returns only one generic particulars record

The detail endpoint now attempts to persist returned particulars when a vessel is clicked.

### Build creates `frontend/tsconfig.tsbuildinfo`

This is generated by TypeScript incremental build. It is not source. It can be removed if it appears in `git status`.

## 33. Overhaul Recommendations

### First decisions

Before rewriting major pieces, decide:

- Confirm that the new version's product identity is SEAM everywhere.
- Decide the exact SEAM expansion, logo, app metadata, package names, docs naming, database naming, and route naming.
- Is this an analyst tool, admin tool, or both?
- What is the primary user workflow?
- Which external data sources are required versus optional?
- Should Postgres schema be reset or migrated forward?
- Should admin become a separate app/route/package?
- Should mock mode remain a first-class development feature?
- Which API keys and external-source settings should be configurable from the admin dashboard?
- Which files, scripts, templates, components, and docs are not essential and should be deleted?
- What should the local launcher be named in the SEAM version: `start.py`, `run.py`, `seam.py`, or another clear command?
- What vessel history and company relationship graph must be visible from a vessel click on day one?

### Recommended overhaul sequence

1. Stabilize domain model and naming.
2. Fully rebrand identity to SEAM across code, docs, UI, scripts, and runtime metadata.
3. Delete or archive unnecessary files and dead code.
4. Write/update architecture diagrams around the essential app only.
5. Design the company-vessel-ownership-sanctions relationship schema.
6. Decide production auth and admin configuration model.
7. Design secure admin-managed API key/source configuration.
8. Normalize API response contracts.
9. Add integration tests around ingestion, particulars enrichment, ownership history, and detail views.
10. Improve frontend state boundaries.
11. Redesign vessel detail so it does not cover right-side map controls.
12. Move journal/ADR/glossary browsing into admin and sort newest-to-oldest.
13. Expand data quality and freshness indicators.
14. Redesign admin workflows.
15. Add CI checks.
16. Add deployment/operations docs.

### Things to preserve

- map-first intelligence concept
- Postgres/PostGIS/Timescale foundation
- SCD2 vessel history idea
- IMO-exact-only auto-confirm decision
- admin review queue for uncertain matches
- mock mode for local development
- journal/ADR system
- SSE position update model
- local/offline development through mocks
- systematic persistence of vessel positions and particulars

### Things to revisit

- token-only admin auth
- mixed product naming
- limited frontend tests
- status inference assumptions
- vessel type taxonomy
- flag/country mapping completeness
- risk score explainability
- sparse owner/operator/class data handling
- Ops Swarm placeholder scope
- right-side vessel detail drawer layout
- duplicate flag display in vessel hover tooltips
- env-only API key configuration
- local launcher naming
- old template and experiment files

### Mandatory planning requirements for the next version

These are explicit requirements for the overhaul, not current implementation tasks:

- The new version should be SEAM-first in identity, naming, UI, docs, and developer commands.
- API keys and external source settings should be configurable from the admin dashboard with secure storage, masking, validation, and audit history.
- The architecture should be reduced to the essential app: ingestion, intelligence APIs, admin operations, and map/dashboard user experience.
- Unnecessary files, unused code, stale templates, and abandoned experiments should be removed.
- Rename project files when it improves clarity; `dev.py` should be reconsidered as `start.py`, `run.py`, or another clear launcher.
- Vessel positions and particulars should be systematically gathered, persisted, and enriched in the backend.
- Historical changes to vessel name, flag, owner, operator, ISM manager, classification society, and other material particulars should be stored and visible from the vessel detail view.
- The detail view should include ownership/history timelines and relationship context, not only current values.
- The map should optimize for fast user experience and only needs "live" freshness for approximately the past hour.
- Older history can remain in archive tables but should not burden the main map payload.
- Journal and ADR browsing should move to the admin dashboard and sort newest-to-oldest.
- Every meaningful architecture/product/data-model change should be documented in the journal and, when it is a decision, in an ADR.
- Vessel particulars gaps, especially owner/operator/ISM/class missing values, should be debugged in the new version before being treated as source limitations.
- Vessel detail should use a layout that does not cover or fight with right-side map tabs.
- Vessel hover should show flag information once, not both in the name and repeated with another flag symbol.
- The new data model should support an interconnected database of companies, vessels, owners, operators, managers, class societies, sanctions entities, topics, and historical relationships.
- Sanctions tied to a company should be traceable to its linked vessels, and vessel detail should show company-linked sanctions context.
- LLMs may assist with entity extraction and relationship linking, but the source-of-truth structure should be deterministic, queryable, and relational.

## 34. Glossary Snapshot

## 34. Overhaul Specification Addendum

This section turns the overhaul notes into a more actionable rebuild blueprint. It is not a record of current implementation. It describes what the next major version should be designed to satisfy.

### Acceptance criteria for the new version

The new version should not be considered complete until these baseline outcomes are true:

- The product identity is SEAM across the UI, docs, scripts, package names, route labels, and developer commands wherever practical.
- A new developer can start the app with one clear launcher command.
- The main map loads quickly with lightweight vessel data and does not block on deep particulars, ownership graphs, or historical records.
- The map reflects vessel activity from roughly the past hour and clearly communicates data freshness.
- Clicking a vessel opens a detail experience that does not cover or conflict with right-side map tools.
- Vessel detail shows current particulars, historical changes, source provenance, and freshness.
- Owner, operator, ISM manager, classification society, and related company data are debugged and either populated or clearly marked with a precise reason.
- Company-linked sanctions can be traced to affected vessels.
- A sanctions-linked company appears in vessel detail when there is a relationship path from that company to the vessel.
- Admin users can configure external API keys and source settings without editing `.env` files directly.
- API key changes are masked, validated, securely stored, and audited.
- Journal, ADR, and glossary browsing live in the admin dashboard and sort newest-to-oldest.
- Every major new architecture/data-model/product decision is documented in an ADR and surfaced in the journal.
- Dead files, stale templates, abandoned components, and unused code are removed or explicitly archived outside the app runtime.

### Target data model sketch

The next version should model maritime relationships directly instead of treating company and ownership data as simple vessel columns.

Recommended core entities:

| Entity/table | Purpose |
|---|---|
| `vessel` | One row per IMO with stable vessel identity |
| `vessel_identifier` | IMO, MMSI, call sign, previous identifiers if needed |
| `vessel_particular_fact` | Current and historical vessel particulars by field |
| `company` | Owners, operators, managers, beneficial owners, class societies where modeled as organizations |
| `company_alias` | Alternate spellings and names |
| `company_identifier` | Registration numbers, OpenSanctions IDs, other IDs |
| `vessel_company_relationship` | Time-bounded vessel-company links by role |
| `sanctions_entity` | Projected sanctions entity/person/company/vessel |
| `sanctions_listing` | Dataset-specific sanctions listings |
| `sanctions_relationship` | Links sanctions entities to companies/vessels/people |
| `source_observation` | Raw or normalized source observation with source, payload hash, fetch time, and confidence |
| `entity_resolution_candidate` | Candidate links needing review |
| `review_queue` | Human review queue for uncertain links/matches |

Recommended relationship roles:

- registered owner
- beneficial owner
- operator
- ship manager
- ISM manager
- technical manager
- commercial manager
- classification society
- sanctions-listed vessel
- sanctions-linked company
- alias/name match
- previous owner/operator

Every relationship should support:

- `valid_from`
- `valid_to`
- `source_id` or source observation reference
- confidence
- review status
- first seen timestamp
- last seen timestamp
- superseded/replaced marker where needed

### Field-level provenance rules

Every important vessel detail field should answer five questions:

1. Where did this value come from?
2. When was it fetched?
3. Is it current or historical?
4. How confident is the system?
5. What changed compared with the previous value?

Important fields requiring provenance:

- name
- flag
- MMSI
- call sign
- vessel type
- year built
- gross tonnage
- deadweight
- length
- beam
- owner
- operator
- ship manager
- ISM manager
- classification society
- sanctions status
- shadow fleet status

Suggested write behavior:

- Never overwrite a known value with null just because a later source response omitted the field.
- Treat omitted fields differently from explicit blank/unknown values.
- Store raw source responses or source observation hashes so changes can be audited.
- Create a history record when a material value changes.
- Attach source and fetch timestamp to each current value.
- Let the UI show "not fetched yet", "not returned by source", "fetch failed", and "historical value superseded" as different states.

### Vessel particulars enrichment without rate limiting

The new version should gather particulars systematically without making aggressive calls to OceansX.

Recommended approach:

- Maintain a `vessel_enrichment_queue` or equivalent table.
- Prioritize vessels by user relevance: selected vessels, high-risk vessels, sanctioned/shadow vessels, new arrivals, stale records, and vessels missing owner/operator/ISM/class.
- Use a strict global rate limit for particulars calls.
- Use exponential backoff after 429, 5xx, timeout, or source errors.
- Store `last_attempt_at`, `last_success_at`, `last_error`, `next_attempt_at`, and `attempt_count`.
- Cache successful particulars by IMO with a sensible TTL.
- Do not re-fetch stable particulars too frequently unless the vessel is high priority or the previous response was incomplete.
- Deduplicate concurrent requests so multiple users clicking the same vessel do not trigger multiple upstream calls.
- Use lazy enrichment on vessel click only when data is missing or stale.
- Run a background trickle enrichment job that processes the queue slowly and safely.
- Show enrichment state in admin: pending, fetched, incomplete, failed, rate limited, deferred.
- Prefer batch endpoints if OceansX provides them; otherwise assume single-IMO calls are rate-limited.

For roughly 1,000 vessels, the system should avoid "fetch everything now" behavior. A safe pattern is:

1. Fetch live positions for the map.
2. Upsert vessel identities and lightweight particulars from position payloads.
3. Queue all vessels needing deeper particulars.
4. Immediately enrich only selected/high-risk/new vessels.
5. Slowly fill the rest in the background under a configured rate limit.
6. Record missing fields and retry incomplete records later.

Admin should allow tuning:

- max particulars calls per minute
- max retries
- retry backoff
- stale-after threshold
- high-priority queue rules
- mock/live mode

### Performance budget

The overhaul should define measurable performance targets. Suggested initial targets:

| User action | Target |
|---|---:|
| Initial app shell visible | under 1 second locally |
| Initial vessel map useful | under 2 seconds locally with mock/local DB |
| Vessel marker interaction | immediate UI feedback |
| Vessel detail current facts | under 500 ms from local DB |
| Vessel detail deep graph/history | lazy load after panel opens |
| Admin overview load | under 2 seconds locally |
| Map payload | lightweight enough to avoid sending deep particulars for every vessel |

Performance principles:

- Keep map list payloads shallow.
- Load details on demand.
- Precompute current risk/status fields.
- Index common query paths.
- Avoid joining full company/sanctions graphs into the base vessel positions endpoint.
- Prefer background enrichment over blocking user interaction.

### Security requirements for admin-managed API keys

Admin-configurable API keys need production-grade handling.

Requirements:

- Secrets are encrypted at rest.
- Secrets are masked in the UI.
- Secrets are never returned to the frontend after save.
- Admin can replace or delete a key.
- Admin can test a connection without exposing the key.
- Every create/update/delete/test action is audited.
- Role permissions control who can view configuration metadata and who can update secrets.
- Backend workers read decrypted secrets only server-side.
- Secret values are not written to logs, audit details, traces, browser storage, or error messages.
- There is a safe fallback for local development using `.env`.

### Clean schema/no-import migration strategy

For the overhaul, there is no requirement to import old project data.

Recommended migration stance:

- Treat the overhaul as a clean new schema unless a specific dataset is explicitly worth preserving.
- Keep the current project as reference material.
- Design the new schema around the target SEAM domain model.
- Re-seed local/dev data from mocks, source APIs, and curated fixtures.
- Do not spend effort writing complex one-off import scripts for old local data.
- If any old tables are useful, document them as reference only.

### Deletion and rename inventory

Before rebuilding, audit these categories:

- old template HTML files
- abandoned SEAM tweak/experiment files
- unused frontend components
- old top bars or layout components no longer mounted
- generated files
- stale docs superseded by the new guide
- outdated architecture docs once replaced
- unused backend routers/services
- unused mock fixtures
- duplicate naming around OceansX versus SEAM

Potential rename candidates:

| Current | Possible new name |
|---|---|
| `dev.py` | `start.py`, `run.py`, or `seam.py` |
| OceansX Visualizer V2 | SEAM |
| `LiveMap` | `SeamMap` or `MapDashboard` |
| `VesselDetailPanel` | `VesselInspector` |
| `JournalDrawer` | Admin Journal tab |

Renames should be done only if they reduce confusion and are applied consistently.

### User workflow specifications

The new version should be designed around explicit workflows.

#### Investigate a high-risk vessel

1. User sees high-risk vessel on map or risk list.
2. User opens vessel inspector.
3. Inspector shows current facts, risk score, risk components, sanctions context, and company links.
4. User reviews ownership and historical changes.
5. User can open source/provenance for each important claim.

#### Review a sanctions match

1. Admin opens review queue.
2. Admin sees match evidence, confidence, source, and linked entities.
3. Admin confirms or rejects.
4. Decision updates vessel/company risk context.
5. Audit trail records reviewer, time, decision, and note.

#### Configure an API source

1. Admin opens configuration tab.
2. Admin enters or rotates API key.
3. Backend validates and stores the key securely.
4. Admin runs a connection test.
5. Data source status reflects the result.
6. Audit log records the change without exposing the secret.

#### Inspect missing particulars

1. Admin opens data quality tab.
2. Admin filters vessels missing owner/operator/ISM/class.
3. Admin sees last attempt, error, source response state, and next retry time.
4. Admin can prioritize a vessel or group for enrichment.

#### Trace company sanctions to vessels

1. User opens a sanctions-linked company or vessel.
2. UI shows relationship graph/path.
3. User can see which vessels are linked by ownership/operator/manager roles.
4. User can see source observations and confidence for each link.

### Observability requirements

The new version should expose:

- job run history
- job duration
- job status
- job error messages
- source freshness
- source failure streaks
- particulars queue size
- particulars rate limit status
- missing-particulars counts
- high-risk vessel counts
- sanctions review counts
- stale data warnings
- admin configuration audit events

Admin should be able to answer:

- Is the system ingesting?
- Which source is failing?
- Which vessels are stale?
- Which vessels are missing important particulars?
- Are we being rate limited?
- What changed recently?

### Known bugs and debug targets

Track these explicitly during the overhaul:

- owner/operator/ISM/class missing for many vessels
- whether missing particulars are upstream absence, parsing issue, caching issue, or persistence issue
- duplicate flag display in vessel hover tooltip
- vessel detail drawer overlapping right-side controls
- stale vessel tests and mock IMO validity mismatch
- admin stats empty states
- stale DB Explorer table names
- mixed OceansX/SEAM naming
- frontend generated files appearing in git status

## 35. Glossary Snapshot

| Term | Meaning |
|---|---|
| AIS | Automatic Identification System vessel tracking data |
| IMO | Seven-digit vessel identifier |
| MMSI | Maritime Mobile Service Identity |
| SCD2 | Slowly Changing Dimension Type 2; history table pattern |
| DWT | Deadweight tonnage |
| GT | Gross tonnage |
| LOA | Length overall |
| ISM manager | International Safety Management responsible manager |
| Classification society | Organization certifying vessel class |
| Shadow fleet | Vessels associated with opaque/sanctions-evasion activity |
| MoU | Memorandum of Understanding, e.g. Tokyo MoU port state control |
| SSE | Server-Sent Events |
| ADR | Architecture Decision Record |

For the full glossary, see:

```text
docs/glossary.md
```

## 36. Documentation Map

| Document | Purpose |
|---|---|
| `README.md` | Top-level project intro and quick start |
| `docs/PROJECT_GUIDE.md` | This comprehensive handoff guide |
| `oceansx-v2-architecture.md` | Original architecture plan |
| `docs/adr/` | Architecture Decision Records |
| `docs/journey/` | Build journey by phase |
| `docs/glossary.md` | Domain glossary |
| `backend/README.md` | Backend-specific notes |

## 37. Final Mental Model

Think of SEAM as a data flywheel:

1. Pull vessel, sanctions, weather, news, geospatial, and macro data.
2. Normalize and persist it in Postgres.
3. Build history and derived intelligence.
4. Expose stable APIs.
5. Present the result as a map-first analyst interface.
6. Let admins inspect, force, and correct the system.

The overhaul should protect that flywheel while improving reliability, clarity, auth, data quality, and analyst workflows.
