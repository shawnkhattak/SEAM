# Phase 1: Live Tracking Parity

---

## TL;DR

Week two brought the map to life. Phase 1 adds the MPA OceansX API client, the 15-minute position polling job, live vessel markers on a Leaflet map, an SSE (Server-Sent Events) push channel so the frontend updates the moment new positions arrive rather than on an independent timer, a vessel detail drawer, and the full position storage pipeline — including deduplication, SCD2 history for vessel identity changes, and a two-table position design that separates the current snapshot from the 24-hour archive.

At the end of Phase 1 the map shows real ships in Singapore waters, updates every 15 minutes, and clicking any vessel opens a detail panel with its name, flag, speed, heading, and inferred port status.

---

## Goal

Phase 1 has one job: achieve live tracking parity with V1. V1's core feature was an interactive map showing vessel positions updated every few minutes. Everything else in V2 builds on top of that baseline — you cannot do compliance scoring, sanctions matching, or risk ranking if you don't know where the vessels are.

"Parity" means the map works, positions refresh automatically, vessel detail is accessible, and the data persists to the database. It does not mean the compliance features exist — those are Phases 4–6. Phase 1 is the foundation that everything else will build on, analogous to how Phase 0 was the infrastructure foundation for Phase 1 itself.

---

## What Was Built

**MPA OceansX API client.** A fully typed async HTTP client (`app/clients/oceansx.py`) that wraps the MPA Singapore OceansX data API. The client handles authentication, request signing, and response parsing. It also implements a mock mode — when the `OCEANSX_MOCK` environment variable is set, it reads responses from JSON fixture files in `app/mocks/` instead of making real API calls. This means the backend can run fully offline for development and CI, without requiring API credentials.

**Position parsing and status inference.** The raw API response for each vessel includes a timestamp, coordinates, speed, course, heading, navigation status code, and draft. The parser (`app/services/vessels.py`) converts these into typed Python dicts. MPA timestamps are in Singapore local time (UTC+8); the parser converts them to UTC on ingest and clamps any future-dated values to the current time. A status inference function reads the AIS navigation status code and vessel speed to derive a human-readable status: `arrived`, `departing`, `incoming`, or `departed`.

**Two-table position design.** Each polling cycle writes to two tables (ADR-0014):
- `position_live` — one row per vessel, upserted on every poll. Answers the question "where is vessel X right now?"
- `position_archive` — an append-only historical log. Answers the question "where was vessel X over the past 24 hours?" New archive rows are written only when the vessel has moved enough to matter, using the deduplication thresholds in ADR-0018 (100 m distance, 5° heading change, 0.5-knot speed change — any one of these must be exceeded).

**SCD2 vessel master history.** The `vessel` table (also called `vessel_master`) tracks the vessel's identity attributes — name, flag, and IMO. Vessel names and flags do change over time, especially for shadow fleet vessels that rename to evade scrutiny. Phase 1 implements SCD2 (Slowly Changing Dimension Type 2 — a database technique that preserves the full history of record changes rather than overwriting them) via `app/services/vessel_master.py`. Each change to a vessel's name or flag creates a new row in `vessel_scd2_history` with `valid_from` and `valid_to` timestamps, preserving the complete rename history (ADR-0015).

**APScheduler position polling job.** A `_job_poll_positions` function runs every 15 minutes via APScheduler (an async Python job scheduler). Each cycle fetches all current positions, upserts the vessel master and SCD2 history, writes `position_live`, runs the PostGIS terminal containment check to populate `terminal_id`, writes `position_archive` where the dedup rule permits, commits the transaction, invalidates the L1 cache, and fires an SSE event. The job is configured with `max_instances=1` and `coalesce=True`, which means if two executions overlap (unlikely at 15 minutes) the second one is discarded rather than running in parallel.

**SSE broadcaster.** An `EventBroadcaster` class publishes `positions_updated` events to all connected clients after each successful poll cycle (ADR-0008). The frontend's `useLivePositions` hook subscribes via the browser's `EventSource` API and triggers a React Query refetch exactly once per event. This means the frontend never independently polls — it updates precisely when the backend has new data.

**Vessel markers and detail panel.** The Leaflet map renders each vessel as a rotatable directional marker (arrow pointing in the vessel's heading direction). Color codes the vessel by inferred status: green (arrived), amber (incoming/departing), grey (departed). Clicking a marker opens the `VesselDetailPanel` — a drawer showing IMO, name, flag, speed, course, heading, draft, navigation status, inferred status, and last-updated timestamp displayed in the session's selected timezone.

**In-memory L1 cache.** A simple TTL (time-to-live) cache in `app/cache.py` avoids hitting the database on every API request for frequently-read data (positions list, vessel particulars). The position cache is invalidated explicitly after each polling cycle so callers always see fresh data after an update.

**Vessel particulars enrichment.** A second background job (`_job_enrich_vessel_particulars`) runs hourly and enriches up to 50 vessels per cycle with additional static data from the OceansX particulars endpoint: vessel type, built year, gross tonnage, deadweight, length, beam. Vessels are processed oldest-enriched-first (using `nullsfirst(asc(Vessel.last_enriched_at))`), ensuring new vessels are enriched quickly and no vessel is permanently skipped.

---

## Decisions Made

- **15-minute polling cadence (ADR-0004):** Confirmed and implemented. The scheduler interval is controlled by the `POLL_POSITIONS_SECONDS` setting, defaulting to 900 (15 minutes).
- **SSE push over frontend polling (ADR-0008):** Confirmed and implemented. The `EventBroadcaster` publishes to all connected SSE clients after each poll. The frontend never independently schedules position refetches.
- **Two-table position design (ADR-0014):** `position_live` (current snapshot) separated from `position_archive` (historical log). Dedup prevents archive bloat.
- **SCD2 for vessel identity history (ADR-0015):** Name and flag changes produce SCD2 rows rather than overwriting. Phase 6 will use this to detect systematic renaming patterns in shadow fleet vessels.
- **Mock API mode with file fixtures (ADR-0016):** The `OCEANSX_MOCK` flag enables full offline operation. All subsequent API clients follow the same pattern.
- **Position archive dedup thresholds (ADR-0018):** 100 m / 5° / 0.5 kn. Any single threshold exceeded triggers an archive write. Vessels at anchor produce very few rows; vessels in transit produce rows proportional to their actual movement.

---

## What Surprised Me

**AIS navigation status codes are not sufficient on their own.** The AIS `navStatus` field (an integer code from the AIS specification) is what vessels self-report. Vessels at anchor often report `0` (underway using engine) because their AIS transponders are not properly configured. Phase 1 adds a status inference function that combines `navStatus` with speed: a vessel reporting "underway" but moving at 0.1 knots is classified as `arrived`. This is not a perfect heuristic, but it produces meaningful results for the Singapore strait context where vessel behavior is well-characterized.

**UTC clamping is necessary immediately.** MPA's API occasionally returns timestamps a few minutes in the future, presumably due to server clock skew. Without clamping, a future timestamp sorts after the current time in `DISTINCT ON` queries, producing unexpected results. The clamp is applied at ingest, not at query time, so the database is always internally consistent.

**The `coalesce=True` setting matters for polling jobs.** APScheduler's `coalesce` option means that if a job misses two scheduled executions (say, because the server was briefly down), it fires exactly once when the server comes back rather than firing twice rapidly. Without this, a brief outage followed by recovery would double-write positions and double-fire SSE events. With `coalesce=True`, recovery is clean.

---

## What I Learned

**SSE is simpler than WebSockets for this use case.** Server-Sent Events are one-directional (server to client only) and reconnect automatically. For a dashboard that only needs to know "new data is available — go fetch it," SSE is sufficient and requires no additional library on either end. WebSockets add bidirectional complexity that this application does not need until Phase 6 (natural language search).

**Separating the snapshot from the archive is worth the extra table.** The temptation is to use a single position table and always query the latest row per vessel. In practice, `DISTINCT ON` queries across millions of rows are slow and require carefully maintained indexes. A dedicated `position_live` table with one row per vessel makes the live map query trivially fast. The archive table can grow as large as it needs to without affecting map performance.

**Dedup thresholds need to be conservative, not aggressive.** An early draft used tighter thresholds (50 m, 2°, 0.1 kn). This produced too many archive rows for vessels that are stationary but have noisy GPS — the AIS signal from an anchored vessel varies by 20–30 meters from poll to poll. The final thresholds (100 m, 5°, 0.5 kn) correctly suppress GPS noise while capturing genuine movement.

---

## Connection to the Whole

Phase 1 is the position pipeline that all compliance and intelligence features will query against. Phase 2 (this document's successor) adds the PostGIS terminal containment query, which assigns a `terminal_id` to each position row, making it possible in later phases to answer "which vessels called at which terminal, and when." Phase 4 (sanctions) will join against the vessel master to flag vessels with active sanctions. Phase 5 (risk scoring) will use the archive to calculate dwell time at anchorage zones. Phase 6 (intelligence) will use the trail for the 24-hour playback feature.

Everything that makes V2 useful — the compliance scoring, the shadow fleet tracking, the risk ranking — depends on the position data that Phase 1 establishes. The data quality decisions made here (UTC storage, status inference, dedup thresholds) propagate through every subsequent feature.
