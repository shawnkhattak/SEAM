# Phase 5a: Weather Ingestion, Anchorage Dwell, and Risk Scoring — Data Plumbing

**Phase:** 5a (data plumbing)  
**Week:** 6 (first half)  
**Status:** Complete

---

## What Was Built

Phase 5a adds three new data pipelines and a deterministic composite risk scoring engine to OceansX V2. No new API endpoints or UI components were added in this phase — that is Phase 5b. The work here is entirely backend: tables, services, fixtures, and unit tests.

### Four New Database Tables

**`weather_observation`** — A TimescaleDB hypertable storing hourly marine weather readings from Open-Meteo at a fixed coordinate (1.265°N, 103.82°E — the Singapore anchorage area). Twelve variables are captured per reading: wave height, direction, and period; wind wave and swell equivalents; ocean current velocity and direction; and sea surface temperature. Older than 365 days, rows are automatically dropped by a TimescaleDB retention policy.

**`anchorage_dwell`** — A regular table recording each dwell event: when a vessel entered a terminal polygon, which terminal, and when it left. The `ended_at` column is null while the vessel is still inside. A partial index on `(terminal_id, started_at) WHERE ended_at IS NULL` keeps active-dwell lookups fast.

**`risk_score`** — Another TimescaleDB hypertable storing hourly composite risk snapshots. Each row records the composite score (0–100) and all six component scores, plus a JSONB `components` field with the raw inputs used (sanctions status, flag, year built) for audit purposes.

**`flag_performance_year`** — A small reference table holding annual Tokyo MoU flag performance bands (white / grey / black) for 39 flag states. Seeded from a JSON fixture (`app/mocks/flag_performance_year.json`). The scorer queries the latest available year per flag rather than the current year exactly, so the data degrades gracefully as each year passes without an update.

### Open-Meteo Marine Client

`app/clients/open_meteo.py` fetches hourly marine data from `marine-api.open-meteo.com`. The client parses the API's hourly array response and extracts the most recent observation at or before the current time. In mock mode (the default during development), it reads from `app/mocks/weather_response.json` — a realistic 24-hour Singapore weather day with appropriate wave and swell values for equatorial waters.

### Anchorage Dwell Service

`app/services/anchorage_dwell.py` runs at :10 each hour. It queries the PostGIS `terminal_geom` table using `ST_Within` against each vessel's most-recent position to determine which vessels are currently inside a terminal polygon. Open dwell events whose vessel is no longer inside are closed; vessels newly inside a terminal with no open dwell get a new event opened.

### Risk Scoring Engine

`app/services/risk_scorer.py` implements the deterministic composite formula locked in architecture Decision 47:

```
IF sanctions_score > 0 OR shadow_fleet_score > 0:
    composite = max(sanctions_score, shadow_fleet_score)
ELSE:
    composite = flag_mou_score × 0.40 + age_score × 0.30
                + congestion_score × 0.20 + weather_score × 0.10
```

The six components:
- **`sanctions_score`** — 100 if confirmed-sanctioned, 50 if pending, 25 if previously sanctioned, 0 if clean. Read directly from `vessel.current_sanctions_status`.
- **`shadow_fleet_score`** — 100 if `is_shadow_fleet`, 0 otherwise.
- **`age_score`** — Linear ramp: 0 if ≤10 years old, 100 if ≥25 years old. Returns 0 if `year_built` is null.
- **`flag_mou_score`** — 0 for white-band flags, 50 for grey, 100 for black. Overrides to 100 if any MoU detention was recorded in the last 24 months. Unknown flag defaults to grey (ADR-0026).
- **`congestion_score`** — Hardcoded 0.0. Terminal congestion aggregates are deferred post-V2.
- **`weather_score`** — Hardcoded 0.0. The formula for mapping weather variables to risk is deferred until V2 is operational and correlation analysis is possible.

The compliance short-circuit (sanctions or shadow fleet) ensures that a confirmed-sanctioned vessel scores 100 regardless of its operational factors — this was a locked architecture requirement, not a judgment call.

Scoring runs hourly at :15, scoped to vessels with `last_observed_at >= now() - 24 hours`. Vessels unseen for more than 24 hours are not re-scored, avoiding pointless compute on stale positions.

### Three New Scheduler Jobs

| Job | Trigger | What it does |
|---|---|---|
| `pull_weather` | :30 each hour | Fetches Open-Meteo observation, stores if not duplicate |
| `compute_anchorage_dwell` | :10 each hour | Opens/closes dwell events via PostGIS ST_Within |
| `score_risk_hourly` | :15 each hour | Scores all vessels active in last 24h, updates `vessel.latest_risk_score_at` |

---

## Design Decisions

**Why weather_score and congestion_score are hardcoded constants, not parameters.**

Both are module-level constants (`WEATHER_SCORE = 0.0`, `CONGESTION_SCORE = 0.0`). Making them parameters would invite someone to "temporarily" override them with a plausible-looking value before the formula is validated. Keeping them as named constants forces any future change through a proper code review, at which point the formula derivation should be documented alongside the change.

**Why flag_performance_year uses "latest available year" not "current year."**

If the fixture is seeded with `year=2024` entries and the scorer queries `WHERE year = EXTRACT(YEAR FROM NOW())` (2026), no rows would be returned — every vessel would fall through to the grey default. Querying `ORDER BY year DESC LIMIT 1` instead returns the most recent data regardless of how stale it is, which is correct: a country's flag band from 2024 is better than no data at all.

**Why anchorage dwell uses a 30-minute position window.**

The dwell detector queries `WHERE recorded_at >= now() - interval '30 minutes'`. This is twice the polling interval (15 minutes), so a single missed poll does not incorrectly close an active dwell event. A vessel that misses two consecutive polls (30 minutes of silence) will have its dwell closed, which is an acceptable false-negative for a 15-minute polling system.

---

## Files Added

**Backend:**
- `app/alembic/versions/0006_phase5a_weather_risk.py` — 4 new tables, grants
- `app/clients/open_meteo.py` — Open-Meteo Marine API client, mock-capable
- `app/services/weather.py` — Observation storage with duplicate check
- `app/services/anchorage_dwell.py` — PostGIS-based dwell open/close logic
- `app/services/risk_scorer.py` — Deterministic composite formula + hourly batch job
- `app/mocks/weather_response.json` — 24-hour realistic Singapore marine weather fixture
- `app/mocks/flag_performance_year.json` — 39-entry Tokyo MoU flag performance fixture
- `tests/test_risk_scorer.py` — 25 unit tests covering all formula cases

**Modified:**
- `app/models.py` — Added WeatherObservation, AnchorageDwell, RiskScore, FlagPerformanceYear ORM classes
- `app/scheduler.py` — Added _job_pull_weather, _job_compute_anchorage_dwell, _job_score_risk_hourly

**Docs:**
- `docs/adr/0026-unknown-flag-defaults-to-grey.md`

---

## What Is Deferred to Phase 5b

- `GET /api/risk/{imo}` and `GET /api/risk/leaderboard` endpoints
- RiskBadge component and VesselDetailPanel risk section
- High-risk map filter slider (the `riskThreshold` store field exists but is not yet wired)
- Flag performance fixture seeding via migration data load
- Terminal congestion continuous aggregate
- Weather score formula
