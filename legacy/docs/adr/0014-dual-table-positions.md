# ADR 0014: Dual-Table Position Design (position_live + position_archive)

**Status:** Accepted  
**Date:** 2026-04-30  
**Phase:** 1

## Context

Vessel positions need to serve two distinct query patterns:

1. **Live map** — "Where is every vessel right now?" This query runs on every map load and every SSE-triggered refresh. It needs to be fast (sub-100 ms) and return exactly one position per vessel.
2. **Trail / history** — "Where was vessel X over the last 24 hours?" This query runs when a user selects a vessel. It can return many rows per vessel and may tolerate slightly higher latency.

The naive design uses a single `position` table and gets the latest row per vessel with `SELECT DISTINCT ON (imo) ... ORDER BY imo, recorded_at DESC`. This works at small scale but degrades as the table grows. With 800 vessels polling every 15 minutes, the table accumulates ~76,800 rows per day. After 90 days (the planned retention window) that is 6.9 million rows. `DISTINCT ON` over 6.9 million rows requires scanning all rows or maintaining an index that covers both the `DISTINCT ON` column and the `ORDER BY` column — a partial index on the latest row per vessel is complex and brittle.

## Decision

Split into two tables:

- **`position_live`** — one row per vessel, upserted on every poll using `ON CONFLICT (imo) DO UPDATE`. The primary key is `imo`. This table is always small (one row per tracked vessel, currently ~800 rows). The live map query is a full-table scan of 800 rows — trivially fast with no index required.

- **`position_archive`** — append-only historical log, one row per position event that passes the deduplication filter (ADR-0018). The `imo + recorded_at` pair is the natural key. TimescaleDB is applied to this table as a hypertable partitioned by `recorded_at`, enabling automatic chunk management and future compression.

Both tables have a `terminal_id` foreign key that is populated by the PostGIS containment check in Phase 2.

## Alternatives Considered

**Single table with `DISTINCT ON`.** Simpler schema; avoids the write amplification of writing two rows per position event. Rejected because query performance degrades linearly with table size and the `DISTINCT ON` pattern is sensitive to planner decisions.

**Single table with a `is_latest` boolean flag.** Each insert clears `is_latest` on the previous row for the same vessel, then sets `is_latest = true` on the new row. Allows a simple `WHERE is_latest = true` query for the live map. Rejected because the update pattern under concurrent writes requires careful locking, and the flag becomes stale if the background update fails.

**Materialized view for live positions.** Keep a single archive table and maintain a materialized view for the latest position per vessel. Rejected because materialized views must be explicitly refreshed; they add operational complexity and have a stale window between refresh and query.

## Consequences

**Enables:**
- Live map queries over a fixed-size table regardless of archive growth.
- TimescaleDB compression on `position_archive` without affecting live map performance.
- Independent retention policies: `position_live` retains the single latest snapshot indefinitely; `position_archive` can be expired or compressed after 90 days.

**Costs:**
- Two writes per position event (one to each table), plus one read of the most recent archive row for dedup.
- Schema complexity: two tables instead of one, with a `terminal_id` FK that must be populated consistently in both.

**Reversibility:** 3 of 5. Merging the tables later would require a data migration and query rewrites across several services.

## Plain-English Summary

Every 15 minutes the backend fetches vessel positions and stores them in two places. The first place (`position_live`) keeps only the current position of each vessel — one row per ship, always overwritten with the latest data. This makes the "show me all ships on the map" query instant regardless of how long the system has been running.

The second place (`position_archive`) is a permanent log of where each vessel has been. It doesn't store every single poll result — if a ship hasn't moved, there's no point logging it again. But when a vessel moves meaningfully, a new archive row is written. This log is what powers the 24-hour trail scrubber and, in later phases, dwell-time calculations.

The cost of this design is that each position event writes to two tables instead of one. The benefit is that live map queries never slow down as historical data accumulates.
