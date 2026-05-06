# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SEAM (Singapore Entity Analytics for Maritime) is a map-first maritime compliance and intelligence dashboard. The repo currently contains a `legacy/` folder with the existing implementation and its full documentation. The next phase is a full overhaul — see `legacy/docs/PROJECT_GUIDE.md` for the comprehensive handoff guide and `legacy/oceansx-v2-architecture.md` for the locked architecture plan.

The system is a data flywheel: ingest vessel/sanctions/news/weather data → normalize into Postgres → build intelligence → expose via FastAPI → present on a Leaflet map with a React admin dashboard.

## Development Commands

**Start everything (easiest path):**
```bash
cd legacy && python3 dev.py
```

**Manual start:**
```bash
# Database
docker compose -f legacy/docker-compose.yml up -d db

# Backend
cd legacy/backend
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd legacy/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

**Backend (from `legacy/backend/`):**
```bash
pip install -e ".[dev]"
pytest                        # run all tests
pytest tests/test_risk_scorer.py  # run a single test file
ruff check .                  # lint
alembic upgrade head          # apply migrations
```

**Frontend (from `legacy/frontend/`):**
```bash
npm install
npm run typecheck             # type check without building
npm run build                 # full build
npm run test                  # run vitest tests
npm run lint                  # eslint
```

**URLs:** App at `http://localhost:5173`, Admin at `http://localhost:5173/admin`, Backend health at `http://localhost:8000/api/health`.

## Architecture

### Three layers

1. **Ingestion layer** — APScheduler jobs in `backend/app/scheduler.py` pull from MPA OceansX, OpenSanctions, Open-Meteo, and RSS.app feeds on configured cadences. Admin force-actions can trigger any job manually.

2. **Intelligence API layer** — FastAPI (`backend/app/main.py`) exposes all routes under `/api`. Business logic lives in `services/`, external calls in `clients/`. Routes are thin; services do the work. The backend publishes SSE events after each position poll so the frontend never polls.

3. **SEAM frontend layer** — React 18 + Vite. `App.tsx` routes `/` to `LiveMap` (full-screen Leaflet map) and `/admin` to lazy-loaded `AdminApp`. React Query owns all server state; Zustand owns shared UI state (selected vessel, risk threshold, map filters). Local component state handles panel open/close.

### Backend module responsibilities

| Path | Purpose |
|---|---|
| `app/main.py` | App factory, CORS, router registration, scheduler lifespan |
| `app/scheduler.py` | All APScheduler jobs; job functions call services |
| `app/models.py` | SQLAlchemy async models (single file) |
| `app/schemas.py` | Pydantic request/response models |
| `app/config.py` | Pydantic settings from env |
| `app/db.py` | Async engine and session factory |
| `app/services/` | Business logic and DB writes; most features live here |
| `app/clients/` | External API clients (OceansX, OpenSanctions, Open-Meteo, RSS.app, Anthropic) — all support mock mode |
| `app/routers/` | Thin FastAPI route modules, mounted under `/api` |
| `app/mocks/` | Fixture JSON files for offline/mockmode development |
| `app/utils/vessel_labels.py` | Flag code → country name/emoji, vessel type code → full label |

### Database

Postgres 16 + TimescaleDB + PostGIS. Key design patterns:
- `vessel` is the master table (one row per IMO); SCD2 history tables track name, flag, owner, operator, and class changes with `valid_from`/`valid_to`
- `position_live` (14-day retention) and `position_archive` (365-day, deduped by distance+heading+speed delta) are TimescaleDB hypertables
- `sanctions_match` auto-confirms only IMO-exact matches; everything else goes to `agent_review_queue` for human review — this is a locked architectural decision
- `is_shadow_fleet` on `vessel` is derived nightly from `vessel_topic` entries

Migrations live in `backend/app/alembic/versions/` and are append-only. Run `alembic upgrade head` after pulling.

### Key data flows

**Position poll:** `scheduler._job_poll_positions` → `clients/oceansx.py` → `services/vessels.py` (normalize) → `services/vessel_master.py` (upsert + SCD2) → `services/history.py` (write positions) → SSE broadcast → frontend React Query invalidation.

**Vessel detail click:** Frontend calls `/api/vessels/{imo}` → backend reads DB, fetches particulars from OceansX, saves returned particulars back to DB, returns merged response with DB-first fallback logic.

**Sanctions:** OpenSanctions bulk download → `opensanctions_entity_raw` → projection tables → `sanctions_matcher.py` (IMO-exact auto-confirm; others to review queue) → `vessel.current_sanctions_status`.

**Risk scoring:** `services/risk_scorer.py` reads vessel + sanctions + shadow fleet + weather + MoU data → writes `risk_score` row. Composite = `max(sanctions_score, shadow_fleet_score)` if either > 0, else weighted sum of flag_mou (0.40) + age (0.30) + congestion (0.20) + weather (0.10).

### Frontend state model

- **React Query** — all server data: positions, vessel detail, sanctions, risk, news, trails, admin stats
- **Zustand** (`store/`) — selected vessel IMO, highlighted vessel, risk threshold, timezone preference, map filters
- **Local state** — drawer open/closed, panel toggles

### Admin frontend

`AdminApp.tsx` has tabs: Overview (force actions + health), Approvals (sanctions review queue), DB Explorer (read-only table browser), Stats (charts). Admin requests send `X-Admin-Token` header; backend validates against `ADMIN_TOKEN` env var.

## Configuration

Backend env: `legacy/backend/.env` (copy from `.env.example`). Key vars: `DATABASE_URL`, `ADMIN_TOKEN`, `OCEANSX_API_KEY`, `OCEANSX_MOCK_MODE` (`auto`/`always`/`never`), `ANTHROPIC_API_KEY`, `ANTHROPIC_MOCK_MODE`, `OPENSANCTIONS_MOCK_MODE`.

Frontend env: `legacy/frontend/.env` (copy from `.env.example`). Key vars: `VITE_ADMIN_TOKEN`, `VITE_API_BASE_URL`. Vite proxies `/api` to the backend during dev.

**Mock mode:** The system runs fully offline using fixture files in `app/mocks/`. Set `OCEANSX_MOCK_MODE=always`, `ANTHROPIC_MOCK_MODE=true`, `OPENSANCTIONS_MOCK_MODE=true` for development without API keys.

## Overhaul Context

The `legacy/` folder is the reference implementation. The overhaul target is documented in `legacy/docs/PROJECT_GUIDE.md` sections 28–34 (intended features, overhaul recommendations, acceptance criteria, target data model). Key overhaul mandates:

- Full SEAM identity everywhere (rename away from OceansX Visualizer)
- Clean schema reset — no migration of legacy data required
- Vessel detail must not cover right-side map controls (current right-drawer layout is a known bug)
- Journal/ADR browsing moves from main map into admin dashboard
- Admin-configurable API keys with secure storage, masking, and audit trail
- Field-level provenance for vessel particulars (source, fetch time, confidence, change history)
- Rate-limited particulars enrichment queue with prioritization
- New data model: `vessel_company_relationship` table replacing simple columns; sanctions traceable through company links to vessels

The `.claude/agents/` Build Swarm roles (Architect, DB Engineer, Backend Engineer, Frontend Engineer, Security Reviewer, etc.) are specified in the architecture plan and should be created as part of Phase 0.
