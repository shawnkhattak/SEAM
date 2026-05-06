# Phase 0: The Problem

## TL;DR
SEAM replaces a working but architecturally limited maritime visualizer with a clean, provenance-aware, compliance-grade system. The old system showed vessels on a map; the new one explains *why* each data point is there and *who* owns the vessels.

## Goal
Establish the full foundation — identity, tooling, data model design, and build swarm — before writing a single line of real business logic.

## What Was Built
- Full SEAM identity: branding, package names (`seam-backend`, `seam-frontend`), database name (`seam`), DB role (`seam_app`)
- Docker Compose for Postgres 16 + TimescaleDB + PostGIS
- `start.py` curses control panel replacing the legacy `dev.py`
- 9 `.claude/agents/` role files (Architect, DB Engineer, Backend Engineer, Frontend Engineer, Agent Engineer, Security Reviewer, Code Reviewer, Test Engineer, Documentation Maintainer)
- FastAPI skeleton (`/api/health` endpoint)
- React 18 + Vite + react-router-dom skeleton with three routes: `/`, `/admin/*`, `/vessels/:imo`
- All 27 mock JSON fixtures carried forward
- All utility modules carried forward unchanged (`vessel_labels`, `imo`, `timezone`, `http_allowlist`)
- Initial Alembic migration (0001) for extensions + roles

## Decisions Made
- See ADR-0003: API keys moved to `app_config` table (Fernet-encrypted), not env vars
- See ADR-0004: Vessel detail is a bottom sheet, not a right drawer
- See ADR-0005: Journal/ADR moved to admin dashboard

## What Surprised Me
The legacy `App.tsx` used a simple `window.location.pathname` check to route between map and admin — no react-router-dom at all. The new SEAM needs proper routing because `/vessels/:imo` must be a real URL (linkable, shareable, bookmarkable).

## What I Learned
Establishing SEAM identity first (names, schema, roles) prevents the drift where "OceansX" leaks back in via copy-paste. The progress-log format (`[x]`/`[ ]` per file) proved essential for resuming across context boundaries.

## Connection to the Whole
Phase 0 is the skeleton. Every subsequent phase hangs off the routing, the DB connection, the config system, and the build-swarm roles established here. Phase 1 (Live Tracking) is the first phase to actually write to the DB.
