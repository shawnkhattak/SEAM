# SEAM Rebuild Status

Last updated: 2026-05-06  
Current phase: **Phase 0 — in progress**

Pick up from the last checked-off item in the active phase.

---

## Phase 0 — Repo Scaffolding

- [x] Write REBUILD_PLAN.md
- [x] Write REBUILD_STATUS.md
- [ ] Initialize git repo
- [ ] Copy source files from `/tmp/seam-audit/` (backend + frontend)
- [ ] Delete files in deletion inventory (REBUILD_PLAN.md §1)
- [ ] Apply renames in rebrand inventory (REBUILD_PLAN.md §2)
- [ ] Write `.gitignore`
- [ ] Write `.env.example`
- [ ] Write `seam.py` (dev launcher replacing dev.py)
- [ ] Initial commit: "chore: scaffold SEAM from source"
- [ ] Create GitHub repo and push

## Phase 1 — Backend Core + Database

- [ ] Create `backend/app/core/` (config.py, db.py, deps.py, security.py)
- [ ] Create `backend/app/models/` split files (all 11 domain files)
- [ ] Write Alembic baseline migration `0001_initial.py`
- [ ] Update `main.py` to import from new locations
- [ ] `docker-compose up` → `alembic upgrade head` succeeds
- [ ] `pytest tests/` baseline passes
- [ ] Checkpoint commit: "feat: backend core and clean schema"

## Phase 2 — Backend Routers + Services

- [ ] Port all routers from original, re-point to new models
- [ ] Split `scheduler.py` → `scheduler/scheduler.py` + `scheduler/jobs/`
- [ ] Rename `clients/oceansx.py` → `clients/mpa.py`
- [ ] Delete `auth/oauth.py`
- [ ] All API endpoints respond (mock mode)
- [ ] Checkpoint commit: "feat: backend routers and services"

## Phase 3 — Frontend Scaffold + Map

- [ ] Rename frontend package to `seam-frontend`
- [ ] Create `features/` directory structure
- [ ] Implement `MapView.tsx` with vessel layer
- [ ] Implement SSE connection (`lib/sse.ts`)
- [ ] Vessels appear on map in mock mode
- [ ] Checkpoint commit: "feat: frontend map and live positions"

## Phase 4 — Vessel Inspector (Bottom Sheet)

- [ ] `VesselInspector.tsx` as bottom sheet (not right drawer)
- [ ] Vessel detail, risk score, trail, sanctions tabs
- [ ] Checkpoint commit: "feat: vessel inspector bottom sheet"

## Phase 5 — Search, News, Leaderboard

- [ ] `SearchBar.tsx`, `NlSearchPanel.tsx`, `FilterPanel.tsx`
- [ ] `NewsFeed.tsx`, `NewsItem.tsx`
- [ ] `RiskLeaderboard.tsx`
- [ ] Checkpoint commit: "feat: search news leaderboard"

## Phase 6 — Admin Panel

- [ ] `AdminPanel.tsx` tab container
- [ ] ReviewQueue tab
- [ ] Config tab (API credential CRUD)
- [ ] DataQuality tab
- [ ] JobHistory tab
- [ ] Journal tab
- [ ] OpsSwarm tab (placeholder "Coming soon")
- [ ] Checkpoint commit: "feat: admin panel all tabs"

## Phase 7 — Ops Swarm

- [ ] Agent executor framework
- [ ] Task queue + observation streaming
- [ ] Proposed action review workflow
- [ ] OpsSwarm admin tab wired to live data
- [ ] Checkpoint commit: "feat: ops swarm agent framework"

---

## Resuming After a Break

1. Open this file and find the last unchecked item in the active phase.
2. Read `REBUILD_PLAN.md` for the spec of that phase.
3. Check `/tmp/seam-audit/` — the original source is there for reference.
4. The project DB is `seam` (PostgreSQL 16 + TimescaleDB). Container name: `seam_db`.
5. Dev launcher: `python seam.py` (starts both backend and frontend).
6. All phases require `MOCK_MODE=true` to pass without real API keys.
