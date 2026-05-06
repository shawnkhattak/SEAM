# Phase 5b: Risk API, RiskBadge, and High-Risk Map Filter

**Phase:** 5b (UI and API endpoints)  
**Week:** 6 (second half)  
**Status:** Complete

---

## What Was Built

Phase 5b surfaces the risk scoring engine from Phase 5a in the user interface. It adds two API endpoints, a reusable risk badge component, a risk section in the vessel detail panel, and a high-risk filter slider on the map.

### Risk API Endpoints

Two new endpoints under `/api/risk/`:

| Endpoint | Purpose |
|---|---|
| `GET /api/risk/vessel/{imo}?days=30` | Latest risk scores for a vessel (most-recent first). Returns up to 200 rows covering the requested number of days. Returns 404 if no scores exist yet. |
| `GET /api/risk/leaderboard?limit=20&min_score=0` | Top vessels by composite risk, scored in the last 24 hours, ordered descending. Supports `limit` (1–100) and `min_score` filter parameters. |

The leaderboard uses `DISTINCT ON (vessel_imo)` to get the latest score per vessel before sorting — this avoids showing the same vessel multiple times at different historical scores.

### latest_composite_risk in the Positions Response

`VesselPosition` now includes a `latest_composite_risk` field (nullable float). The positions endpoint already performed a bulk DB query for `is_shadow_fleet` and `current_sanctions_status`; a second query fetches the latest risk composite for each IMO in the same response cycle. This means the map can apply the risk threshold filter immediately on load without an additional request per vessel.

### RiskBadge Component

`src/components/RiskBadge.tsx` — a small colored badge showing the composite score as an integer with a tier label:

| Range | Color | Label |
|---|---|---|
| 0–24 | Green | Low |
| 25–49 | Amber | Medium |
| 50–74 | Orange | High |
| 75–100 | Red | Critical |

Available in three sizes (`sm`, `md`, `lg`) for use in different contexts.

### Vessel Detail Panel — Risk Section

A new "Risk Score" section appears in the detail panel when a risk score exists for the selected vessel (query for `days=1` — today's scores only). It shows:

- The composite score as a large `RiskBadge`
- Time of last scoring (relative)
- A mini component breakdown with a progress bar for each non-zero contributing factor (sanctions, shadow fleet, flag MoU, age)

### High-Risk Map Filter Slider

A new "Risk" button appears in the top-right control cluster (below Shadow). Clicking it opens a compact inline slider panel:

- Range: 0–100, step 5
- Default: 0 (show all vessels)
- When threshold > 0: only vessels with `latest_composite_risk >= threshold` are rendered
- The "Risk" button shows the active threshold (e.g., "Risk ≥ 50") and turns red when active
- The status bar shows "N risk ≥ 50" with a red dot when active
- A "Clear filter" link resets to 0

The threshold is stored in the global `useVesselStore` (Zustand), so it persists across panel opens and map interactions within the session.

---

## Design Decisions

**Why `latest_composite_risk` lives in the positions response, not the vessel table.**

Adding a `latest_composite_risk` column to the `vessel` table would require a migration and a write on every hourly score run. Instead, the positions endpoint fetches it in a second bulk query (`DISTINCT ON (vessel_imo)` from `risk_score`) at the same time it fetches the sanctions flags. The overhead is one extra query per positions request (which is cached for 60 seconds), not per-vessel.

**Why the leaderboard scope is 24 hours.**

The risk scorer only runs for vessels active in the last 24 hours. Expanding the leaderboard scope beyond 24 hours would surface scores for vessels that left Singapore days ago. The 24-hour window keeps the leaderboard relevant to what is currently visible on the map.

**Why the slider step is 5, not 1.**

At step=1, the slider has 101 positions covering the 0–100 range. Most meaningful thresholds cluster around conventional round numbers (25, 50, 75). Step=5 gives 21 positions, all interpretable, and avoids the false precision of a score like "47."

---

## Files Added or Changed

**New backend files:**
- `app/routers/risk.py` — `GET /api/risk/vessel/{imo}`, `GET /api/risk/leaderboard`

**Modified backend files:**
- `app/schemas.py` — `VesselPosition` extended with `latest_composite_risk`; new `RiskScoreResponse` and `RiskLeaderboardItem` schemas
- `app/routers/vessels.py` — positions endpoint adds bulk risk composite lookup
- `app/main.py` — risk router registered

**New frontend files:**
- `frontend/src/api/risk.ts` — `fetchVesselRisk`, `fetchRiskLeaderboard`
- `frontend/src/components/RiskBadge.tsx` — tiered score badge with bar

**Modified frontend files:**
- `frontend/src/types/index.ts` — `VesselPosition` extended; new `RiskScoreResponse` and `RiskLeaderboardItem` types
- `frontend/src/components/VesselDetailPanel.tsx` — risk section with `RiskBadge` and component breakdown
- `frontend/src/components/LiveMap.tsx` — risk filter slider wired to `riskThreshold` store

---

## What Was Deferred

- Risk leaderboard tab in the main UI (Phase 7 admin dashboard)
- Weather score formula
- Terminal congestion continuous aggregate
- Flag performance fixture refresh job (Phase 7)
