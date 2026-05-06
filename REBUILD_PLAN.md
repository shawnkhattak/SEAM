# SEAM Rebuild Plan

**Project:** Singapore Entity Analytics for Maritime (SEAM)  
**Source:** oceans-x-visualizer-V2  
**Status:** See REBUILD_STATUS.md  

---

## 1. What Gets Deleted

These files exist in the source repo and must NOT be carried into SEAM:

| File/Path | Reason |
|-----------|--------|
| `SEAM Dashboard template.html` | Standalone prototype, superseded |
| `seam/tweaks-panel.jsx` | Experiment, not wired to anything |
| `oceansx-v2-architecture.md` | Old architecture doc, replaced by this plan |
| `start-dev.command` | macOS double-click launcher, replaced by `seam.py` |
| `dev.py` | Renamed to `seam.py` |
| `backend/app/auth/oauth.py` | Stub placeholder, never implemented |
| Any `__pycache__`, `.pyc` files | Build artifacts |

---

## 2. Rename / Rebrand Inventory

Every occurrence of "OceansX" / "oceansx" must become "SEAM" / "seam":

| Location | Old | New |
|----------|-----|-----|
| `backend/pyproject.toml` `name` | `oceansx-backend` | `seam-backend` |
| `frontend/package.json` `name` | `oceansx-frontend` | `seam-frontend` |
| `backend/app/main.py` title | `"OceansX Visualizer API"` | `"SEAM API"` |
| `backend/app/config.py` DB URL | `oceansx` | `seam` |
| `docker-compose.yml` container_name | `oceansx_db` | `seam_db` |
| `docker-compose.yml` DB name | `oceansx` | `seam` |
| `backend/app/clients/oceansx.py` | filename | `mpa.py` (MPA = Maritime & Port Authority) |
| Static mount path | `/seam` | keep `/seam` (already correct) |
| All Python imports referencing old names | various | updated in-place |

---

## 3. Final Directory Structure

```
SEAM/
├── seam.py                        # Dev launcher (replaces dev.py)
├── docker-compose.yml             # seam_db, DB name seam
├── .env.example
├── .gitignore
├── REBUILD_PLAN.md                # This file
├── REBUILD_STATUS.md              # Phase tracking
│
├── backend/
│   ├── pyproject.toml             # name = seam-backend
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/              # Single new baseline migration
│   └── app/
│       ├── __init__.py
│       ├── main.py                # App factory, lifespan, CORS, mounts
│       │
│       ├── core/                  # NEW — replaces scattered config/db code
│       │   ├── config.py          # Pydantic settings (DATABASE_URL, keys, feature flags)
│       │   ├── db.py              # Engine, SessionLocal, get_db dependency
│       │   ├── deps.py            # FastAPI dependency injectors (pagination, auth, db)
│       │   └── security.py        # Fernet encryption for API credential values
│       │
│       ├── models/                # Split from monolithic models.py
│       │   ├── base.py            # DeclarativeBase, metadata, TimestampMixin
│       │   ├── vessel.py          # Vessel, VesselParticularFact
│       │   ├── position.py        # PositionLive, PositionArchive
│       │   ├── company.py         # Company, CompanyAlias, VesselCompanyRelationship
│       │   ├── geo.py             # Port, Terminal, TerminalGeom, AnchorageDwell
│       │   ├── sanctions.py       # OpenSanctionsEntity, SanctionsMatch, ReviewQueue
│       │   ├── risk.py            # RiskScore
│       │   ├── news.py            # NewsFeed, NewsItem, EntityMention, NewsSummary
│       │   ├── admin.py           # ApiCredential, VesselEnrichmentQueue, JobRun
│       │   ├── journal.py         # JournalEntry
│       │   └── ops.py             # OpsAgent, OpsTask, OpsObservation, OpsProposedAction
│       │
│       ├── routers/               # One file per resource group
│       │   ├── vessels.py
│       │   ├── positions.py
│       │   ├── sanctions.py
│       │   ├── risk.py
│       │   ├── news.py
│       │   ├── search.py
│       │   ├── admin.py
│       │   ├── journal.py
│       │   └── ops.py
│       │
│       ├── services/              # Business logic, no HTTP concerns
│       │   ├── vessel_service.py
│       │   ├── enrichment_service.py
│       │   ├── sanctions_service.py
│       │   ├── risk_service.py
│       │   ├── news_service.py
│       │   └── nl_search_service.py
│       │
│       ├── scheduler/
│       │   ├── scheduler.py       # APScheduler setup, job registration
│       │   └── jobs/              # One module per job
│       │       ├── position_ingest.py
│       │       ├── vessel_enrichment.py
│       │       ├── sanctions_sync.py
│       │       ├── risk_scoring.py
│       │       ├── news_fetch.py
│       │       └── news_summarize.py
│       │
│       ├── clients/               # External API wrappers
│       │   ├── mpa.py             # MPA AIS (was oceansx.py)
│       │   ├── opensanctions.py
│       │   ├── myshiptracking.py
│       │   └── anthropic_client.py
│       │
│       ├── auth/
│       │   └── admin.py           # X-Admin-Token / Bearer auth (oauth.py deleted)
│       │
│       └── sse.py                 # SSE event bus
│
├── frontend/
│   ├── package.json               # name = seam-frontend
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── types/
│       │   └── index.ts           # All shared TS interfaces
│       ├── lib/
│       │   ├── api.ts             # Axios instance + typed request helpers
│       │   ├── queryClient.ts     # React Query client config
│       │   └── sse.ts             # SSE hook
│       ├── store/
│       │   └── appStore.ts        # Zustand global state
│       └── features/              # Feature-based organization
│           ├── map/
│           │   ├── MapView.tsx    # Leaflet map, vessel markers, trail layer
│           │   ├── MapControls.tsx
│           │   └── hooks/
│           │       └── useVesselLayer.ts
│           ├── vessel/
│           │   ├── VesselInspector.tsx   # Bottom sheet (replaces right drawer)
│           │   ├── VesselCard.tsx
│           │   ├── RiskBadge.tsx
│           │   ├── TrailLayer.tsx
│           │   └── hooks/
│           │       ├── useVesselDetail.ts
│           │       └── useVesselTrail.ts
│           ├── search/
│           │   ├── SearchBar.tsx
│           │   ├── NlSearchPanel.tsx
│           │   └── FilterPanel.tsx
│           ├── news/
│           │   ├── NewsFeed.tsx
│           │   └── NewsItem.tsx
│           ├── leaderboard/
│           │   └── RiskLeaderboard.tsx
│           └── admin/
│               ├── AdminPanel.tsx      # Tab container
│               ├── tabs/
│               │   ├── ReviewQueue.tsx
│               │   ├── Config.tsx       # API credential management
│               │   ├── DataQuality.tsx  # Stale vessels, enrichment failures
│               │   ├── JobHistory.tsx   # JobRun log
│               │   ├── Journal.tsx      # Analyst notes (moved from map)
│               │   └── OpsSwarm.tsx     # Placeholder tab
│               └── hooks/
│                   └── useAdminData.ts
│
└── docs/
    └── adr/                       # Architecture Decision Records (trimmed, SEAM-only)
```

---

## 4. Database Schema

### Design Principles
- **Current state denormalized on `vessel`** — fast reads for the map, no joins needed
- **`vessel_particular_fact` for history/provenance** — field-level audit trail (which API gave us this value and when)
- **SCD2 simplified** — the 5 separate history tables (name/flag/owner/operator/class) collapse into a single `vessel_particular_fact` table
- **`company` replaces `Organization`** — cleaner name, same purpose, proper aliases table
- **Encrypted credentials** — `api_credential` stores values via Fernet; key comes from `SEAM_CRED_KEY` env var
- **Dual positions** — `position_live` (one row per vessel, upsert) + `position_archive` (hypertable, all points)
- **`job_run`** — lightweight job execution log (replaces nothing; new table)
- **Ops Swarm tables** — created but empty; no scheduler jobs touch them yet

### Table Inventory

#### Core Vessel

```sql
vessel (
  imo                      BIGINT PRIMARY KEY,
  name                     TEXT NOT NULL,
  mmsi                     TEXT,
  call_sign                TEXT,
  flag                     CHAR(2),          -- ISO 3166-1 alpha-2
  flag_name                TEXT,
  flag_emoji               TEXT,
  vessel_type              TEXT,
  vessel_type_label        TEXT,
  year_built               SMALLINT,
  gross_tonnage            INTEGER,
  deadweight               INTEGER,
  length_overall           NUMERIC(7,2),
  beam                     NUMERIC(7,2),
  ism_manager              TEXT,             -- current value, denormalized
  registered_owner         TEXT,
  operator                 TEXT,
  classification_society   TEXT,
  is_shadow_fleet          BOOLEAN NOT NULL DEFAULT FALSE,
  current_sanctions_status TEXT NOT NULL DEFAULT 'clear',
  latest_composite_risk    NUMERIC(5,2),
  first_observed_at        TIMESTAMPTZ,
  last_observed_at         TIMESTAMPTZ,
  last_enriched_at         TIMESTAMPTZ,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
```

```sql
vessel_particular_fact (
  id           BIGSERIAL PRIMARY KEY,
  imo          BIGINT NOT NULL REFERENCES vessel(imo),
  field_name   TEXT NOT NULL,               -- e.g. "name", "flag", "registered_owner"
  field_value  TEXT,
  source       TEXT NOT NULL,               -- e.g. "mpa_ais", "myshiptracking", "manual"
  source_ref   TEXT,                        -- optional external record ID
  valid_from   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  valid_to     TIMESTAMPTZ,                 -- NULL = currently active
  recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
-- Indexes: (imo, field_name, valid_from), (imo, field_name) WHERE valid_to IS NULL
```

#### Positions (ADR-0014)

```sql
position_live (
  imo              BIGINT PRIMARY KEY REFERENCES vessel(imo),
  lat              DOUBLE PRECISION NOT NULL,
  lon              DOUBLE PRECISION NOT NULL,
  geom             GEOMETRY(Point, 4326),
  speed_knots      NUMERIC(6,2),
  course_degrees   NUMERIC(6,2),
  heading_degrees  NUMERIC(6,2),
  nav_status       TEXT,
  inferred_status  TEXT NOT NULL DEFAULT 'unknown',
  recorded_at      TIMESTAMPTZ NOT NULL,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

position_archive (
  id               BIGSERIAL,
  imo              BIGINT NOT NULL REFERENCES vessel(imo),
  lat              DOUBLE PRECISION NOT NULL,
  lon              DOUBLE PRECISION NOT NULL,
  geom             GEOMETRY(Point, 4326),
  speed_knots      NUMERIC(6,2),
  course_degrees   NUMERIC(6,2),
  heading_degrees  NUMERIC(6,2),
  nav_status       TEXT,
  inferred_status  TEXT NOT NULL DEFAULT 'unknown',
  recorded_at      TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (id, recorded_at)
)
-- TimescaleDB hypertable on recorded_at, chunk_time_interval = '7 days'
-- Index: (imo, recorded_at DESC)
```

#### Company / Ownership

```sql
company (
  id           BIGSERIAL PRIMARY KEY,
  name         TEXT NOT NULL,
  country      CHAR(2),
  company_type TEXT,                        -- "owner", "operator", "ism_manager", "charterer"
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

company_alias (
  id         BIGSERIAL PRIMARY KEY,
  company_id BIGINT NOT NULL REFERENCES company(id),
  alias      TEXT NOT NULL,
  source     TEXT,
  UNIQUE (company_id, alias)
)

vessel_company_relationship (
  id           BIGSERIAL PRIMARY KEY,
  imo          BIGINT NOT NULL REFERENCES vessel(imo),
  company_id   BIGINT NOT NULL REFERENCES company(id),
  role         TEXT NOT NULL,               -- "registered_owner", "operator", "ism_manager"
  valid_from   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  valid_to     TIMESTAMPTZ,
  source       TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
```

#### Geography

```sql
port (
  id        SERIAL PRIMARY KEY,
  locode    CHAR(5) UNIQUE,
  name      TEXT NOT NULL,
  country   CHAR(2),
  lat       DOUBLE PRECISION,
  lon       DOUBLE PRECISION,
  geom      GEOMETRY(Point, 4326)
)

terminal (
  id       SERIAL PRIMARY KEY,
  port_id  INTEGER REFERENCES port(id),
  name     TEXT NOT NULL,
  code     TEXT
)

terminal_geom (
  id          SERIAL PRIMARY KEY,
  terminal_id INTEGER NOT NULL REFERENCES terminal(id),
  geom        GEOMETRY(Polygon, 4326) NOT NULL,
  label       TEXT
)

anchorage_dwell (
  id            BIGSERIAL PRIMARY KEY,
  imo           BIGINT NOT NULL REFERENCES vessel(imo),
  terminal_id   INTEGER REFERENCES terminal(id),
  arrived_at    TIMESTAMPTZ NOT NULL,
  departed_at   TIMESTAMPTZ,
  duration_h    NUMERIC(8,2),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
```

#### Sanctions

```sql
opensanctions_entity (
  id            TEXT PRIMARY KEY,           -- OpenSanctions canonical ID
  name          TEXT NOT NULL,
  entity_type   TEXT,
  datasets      TEXT[] NOT NULL DEFAULT '{}',
  properties    JSONB,
  last_seen     TIMESTAMPTZ,
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

sanctions_match (
  id              BIGSERIAL PRIMARY KEY,
  imo             BIGINT NOT NULL REFERENCES vessel(imo),
  os_entity_id    TEXT NOT NULL REFERENCES opensanctions_entity(id),
  match_method    TEXT NOT NULL,            -- "imo_exact", "name_fuzzy", etc.
  confidence      NUMERIC(4,3),
  status          TEXT NOT NULL DEFAULT 'pending',
                                            -- pending | auto_confirmed | confirmed | rejected
  reviewed_by     TEXT,
  reviewer_note   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_at     TIMESTAMPTZ,
  UNIQUE (imo, os_entity_id)
)

review_queue (
  id             BIGSERIAL PRIMARY KEY,
  sanctions_match_id BIGINT NOT NULL REFERENCES sanctions_match(id),
  status         TEXT NOT NULL DEFAULT 'open',  -- open | confirmed | rejected
  assigned_to    TEXT,
  reviewer_note  TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at    TIMESTAMPTZ
)
```

#### Risk

```sql
risk_score (
  id                BIGSERIAL PRIMARY KEY,
  imo               BIGINT NOT NULL REFERENCES vessel(imo),
  scored_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  composite         NUMERIC(5,2) NOT NULL,
  sanctions_score   NUMERIC(5,2) NOT NULL DEFAULT 0,
  shadow_fleet_score NUMERIC(5,2) NOT NULL DEFAULT 0,
  age_score         NUMERIC(5,2) NOT NULL DEFAULT 0,
  flag_mou_score    NUMERIC(5,2) NOT NULL DEFAULT 0,
  congestion_score  NUMERIC(5,2) NOT NULL DEFAULT 0,
  weather_score     NUMERIC(5,2) NOT NULL DEFAULT 0,
  components        JSONB
)
-- Index: (imo, scored_at DESC)
```

#### News

```sql
news_feed (
  id          SERIAL PRIMARY KEY,
  name        TEXT NOT NULL,
  url         TEXT NOT NULL UNIQUE,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

news_item (
  id           BIGSERIAL PRIMARY KEY,
  feed_id      INTEGER REFERENCES news_feed(id),
  guid         TEXT NOT NULL UNIQUE,
  title        TEXT,
  url          TEXT,
  published_at TIMESTAMPTZ,
  content_raw  TEXT,
  fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

entity_mention (
  id           BIGSERIAL PRIMARY KEY,
  news_item_id BIGINT NOT NULL REFERENCES news_item(id),
  imo          BIGINT REFERENCES vessel(imo),
  entity_text  TEXT NOT NULL,
  mention_type TEXT,                        -- "vessel", "company", "person"
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

news_summary (
  id             BIGSERIAL PRIMARY KEY,
  news_item_id   BIGINT NOT NULL REFERENCES news_item(id) UNIQUE,
  summary_text   TEXT NOT NULL,
  model_used     TEXT NOT NULL,
  generated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  tokens_in      INTEGER,
  tokens_out     INTEGER
)
```

#### Admin

```sql
api_credential (
  id            SERIAL PRIMARY KEY,
  service_name  TEXT NOT NULL UNIQUE,       -- "mpa_ais", "myshiptracking", "opensanctions"
  description   TEXT,
  encrypted_value TEXT NOT NULL,            -- Fernet-encrypted
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  last_tested_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

vessel_enrichment_queue (
  id            BIGSERIAL PRIMARY KEY,
  imo           BIGINT NOT NULL REFERENCES vessel(imo),
  priority      SMALLINT NOT NULL DEFAULT 5,  -- 1 (highest) to 10
  reason        TEXT,
  status        TEXT NOT NULL DEFAULT 'pending',  -- pending | processing | done | failed
  attempts      SMALLINT NOT NULL DEFAULT 0,
  last_error    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at  TIMESTAMPTZ
)

job_run (
  id          BIGSERIAL PRIMARY KEY,
  job_name    TEXT NOT NULL,
  started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  status      TEXT NOT NULL DEFAULT 'running',   -- running | success | failed
  rows_affected INTEGER,
  error_msg   TEXT,
  meta        JSONB
)
```

#### Journal

```sql
journal_entry (
  id          BIGSERIAL PRIMARY KEY,
  imo         BIGINT REFERENCES vessel(imo),  -- NULL = global note
  body        TEXT NOT NULL,
  author      TEXT NOT NULL DEFAULT 'analyst',
  tags        TEXT[] NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
```

#### Ops Swarm (placeholder — tables only, no jobs)

```sql
ops_agent (
  id          SERIAL PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  role        TEXT NOT NULL,               -- "researcher", "risk_scorer", "sanctions_checker"
  model       TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
  is_active   BOOLEAN NOT NULL DEFAULT FALSE,
  config      JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

ops_task (
  id           BIGSERIAL PRIMARY KEY,
  agent_id     INTEGER NOT NULL REFERENCES ops_agent(id),
  trigger      TEXT NOT NULL,              -- "scheduled", "manual", "event"
  input        JSONB,
  status       TEXT NOT NULL DEFAULT 'queued',  -- queued | running | done | failed
  started_at   TIMESTAMPTZ,
  finished_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

ops_observation (
  id         BIGSERIAL PRIMARY KEY,
  task_id    BIGINT NOT NULL REFERENCES ops_task(id),
  content    TEXT NOT NULL,
  role       TEXT NOT NULL DEFAULT 'assistant',  -- "user" | "assistant" | "tool"
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

ops_proposed_action (
  id           BIGSERIAL PRIMARY KEY,
  task_id      BIGINT NOT NULL REFERENCES ops_task(id),
  action_type  TEXT NOT NULL,
  payload      JSONB,
  status       TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | executed
  reviewed_by  TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_at  TIMESTAMPTZ
)
```

---

## 5. Key Architecture Decisions (ADRs Carried Forward)

| ADR | Decision | Rule |
|-----|----------|------|
| ADR-0005 | IMO-exact sanctions auto-confirm | Only matches via `imo_exact` method get `auto_confirmed` status; all others go to `review_queue` |
| ADR-0014 | Dual position tables | `position_live` = upsert (one row/vessel). `position_archive` = TimescaleDB hypertable. Write to both on every ingest. |
| ADR-0017 | Mock mode | All external clients check `MOCK_MODE=true` env var and return fixture data. System must run fully without paid API keys. |
| NEW-001  | Encrypted credentials | API keys stored in `api_credential` table encrypted with Fernet. Plaintext never written to disk. Bootstrap key via `SEAM_CRED_KEY` env var. |
| NEW-002  | vessel_particular_fact | Field-level provenance via single `vessel_particular_fact` table instead of 5 SCD2 history tables. |
| NEW-003  | Ops Swarm placeholder | All four Ops Swarm tables created in baseline migration. No scheduler jobs reference them. OpsSwarm admin tab renders a "Coming soon" state. |

---

## 6. Phases

Each phase ends at a clean checkpoint: backend migrates, server starts, tests pass.

### Phase 0 — Repo Scaffolding
- [ ] Initialize git repo in `/Users/shawnkhattak/PycharmProjects/SEAM`
- [ ] Copy source files from `/tmp/seam-audit/` (backend + frontend skeleton)
- [ ] Delete files in deletion inventory (section 1)
- [ ] Apply all renames in rebrand inventory (section 2)
- [ ] Write `.gitignore`, `.env.example`
- [ ] Write `seam.py` (dev launcher)
- [ ] Initial commit: "chore: scaffold SEAM from source"
- [ ] Create GitHub repo `SEAM` and push

### Phase 1 — Backend Core + Database
- [ ] Create `backend/app/core/` with config.py, db.py, deps.py, security.py
- [ ] Create `backend/app/models/` split files (all tables from section 4)
- [ ] Write Alembic baseline migration (single `0001_initial.py`)
- [ ] Update `main.py` to import from new locations
- [ ] `docker-compose up` → `alembic upgrade head` succeeds
- [ ] `pytest tests/` baseline passes
- [ ] Checkpoint commit: "feat: backend core and clean schema"

### Phase 2 — Backend Routers + Services
- [ ] Port all routers from original, re-point to new models
- [ ] Split `scheduler.py` into `scheduler/scheduler.py` + `scheduler/jobs/`
- [ ] Rename `clients/oceansx.py` → `clients/mpa.py`
- [ ] Delete `auth/oauth.py`
- [ ] All API endpoints respond (mock mode)
- [ ] Checkpoint commit: "feat: backend routers and services"

### Phase 3 — Frontend Scaffold + Map
- [ ] Rename frontend package to `seam-frontend`
- [ ] Create `features/` directory structure
- [ ] Implement `MapView.tsx` with vessel layer
- [ ] Implement SSE connection (`lib/sse.ts`)
- [ ] Vessels appear on map in mock mode
- [ ] Checkpoint commit: "feat: frontend map and live positions"

### Phase 4 — Vessel Inspector (Bottom Sheet)
- [ ] `VesselInspector.tsx` as bottom sheet
- [ ] Vessel detail, risk score, trail, sanctions tabs
- [ ] Checkpoint commit: "feat: vessel inspector bottom sheet"

### Phase 5 — Search, News, Leaderboard
- [ ] `SearchBar.tsx`, `NlSearchPanel.tsx`, `FilterPanel.tsx`
- [ ] `NewsFeed.tsx`, `NewsItem.tsx`
- [ ] `RiskLeaderboard.tsx`
- [ ] Checkpoint commit: "feat: search news leaderboard"

### Phase 6 — Admin Panel
- [ ] `AdminPanel.tsx` tab container
- [ ] ReviewQueue tab (existing functionality)
- [ ] Config tab (API credential CRUD with encryption)
- [ ] DataQuality tab (stale vessels, enrichment queue)
- [ ] JobHistory tab (job_run log)
- [ ] Journal tab (analyst notes)
- [ ] OpsSwarm tab (placeholder "Coming soon")
- [ ] Checkpoint commit: "feat: admin panel all tabs"

### Phase 7 — Ops Swarm (After Everything Else Works)
- [ ] Agent executor framework
- [ ] Task queue + observation streaming
- [ ] Proposed action review workflow
- [ ] OpsSwarm admin tab wired to live data
- [ ] Checkpoint commit: "feat: ops swarm agent framework"

---

## 7. Mock Mode Contract

Every external client module (`mpa.py`, `opensanctions.py`, `myshiptracking.py`, `anthropic_client.py`) must:

1. Check `settings.MOCK_MODE` (bool, default `True`)
2. If true: return fixture data from `backend/app/fixtures/`
3. If false: make real HTTP calls using credentials from `api_credential` table

Fixture files:
- `fixtures/positions.json` — 10–20 synthetic vessel positions in Singapore Strait
- `fixtures/vessels.json` — matching vessel particulars
- `fixtures/sanctions.json` — 2–3 test matches (one auto-confirmable via IMO exact)
- `fixtures/news.json` — 5 synthetic news items

The frontend dev server proxies to `http://localhost:8000` and works correctly in mock mode with no additional setup.

---

## 8. Environment Variables

```bash
# Required in production, have defaults for dev
DATABASE_URL=postgresql+psycopg://seam:seam@localhost:5432/seam
SEAM_CRED_KEY=<fernet-key>           # generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ADMIN_TOKEN=dev-admin-token

# Feature flags
MOCK_MODE=true                        # Set false to use real APIs
ENABLE_OPS_SWARM=false               # Gates ops swarm scheduler jobs

# Optional — only needed when MOCK_MODE=false
MPA_AIS_API_KEY=
MYSHIPTRACKING_API_KEY=
OPENSANCTIONS_API_KEY=
ANTHROPIC_API_KEY=
```

---

## 9. Testing Strategy

- **Backend**: `pytest` with `pytest-asyncio`; fixtures create isolated test DB transactions
- **Frontend**: Vitest + Testing Library; mock API calls via `msw`
- **Mock mode tests**: All scheduler job tests run with `MOCK_MODE=true`
- **Integration**: At minimum, one end-to-end test per Phase that covers the critical path
