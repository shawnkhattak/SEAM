# OceansX Visualizer V2

Maritime compliance and intelligence dashboard for Singapore waters.

V2 reframes the project as a **sanctions screening, shadow-fleet visibility, and risk scoring** platform. Position polling runs at 15-minute cadence; the value proposition is intelligence, not live navigation.

## Key additions over V1

- **Risk & compliance layer** — OpenSanctions (OFAC/OFSI/EU/UN + Tokyo/Paris/Black Sea/Abuja MoU), auto-confirm for IMO-exact matches, admin review queue for all others
- **Shadow Fleet visibility** — dedicated tab, map filter, and marker badges
- **Entity-aware news** — RSS.app feeds parsed for vessel/port/org mentions; clickable entity tags filter the map
- **Two AI swarms** — Build Swarm (Claude Code subagents for development) and Operations Swarm (runtime autonomous agents writing to staging only)

## Stack

| Layer | Technology |
|---|---|
| Database | Postgres 16 + TimescaleDB + PostGIS |
| Migrations | Alembic |
| Backend | FastAPI + uvicorn (Python 3.12+) |
| Frontend | React 18 + Vite + Leaflet + Tailwind |
| Time | All UTC storage; America/Chicago default display via Luxon |
| Reverse proxy | Caddy 2 (production) |

## Local development

### Prerequisites

- Docker + Docker Compose
- Python 3.12+
- Node 20+

### Start the database

```bash
docker compose up -d db
```

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Architecture

For a simple, practical explanation of the whole project, start with
[`docs/PROJECT_GUIDE.md`](./docs/PROJECT_GUIDE.md).

See [`oceansx-v2-architecture.md`](./oceansx-v2-architecture.md) for the full architecture plan.

See [`docs/journey/`](./docs/journey/) for the build journal and [`docs/adr/`](./docs/adr/) for Architecture Decision Records.

## License

Non-commercial use only. All data sources operate under free non-commercial terms.
