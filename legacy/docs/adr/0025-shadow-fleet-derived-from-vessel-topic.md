# ADR-0025: Shadow Fleet Flag Derived from vessel_topic

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 4a

## Context

`vessel.is_shadow_fleet` must reflect whether a vessel is considered a shadow fleet vessel according to OpenSanctions. The OpenSanctions dataset uses a topic tag `mare.shadow` to mark such vessels. The question is whether this flag should be maintained as a materialized boolean column on `vessel`, or derived on-the-fly from `vessel_topic` at query time.

## Decision

Maintain `vessel.is_shadow_fleet` as a materialized boolean, refreshed nightly by a dedicated job (`_job_refresh_shadow_fleet_flags`) that runs 30 minutes after the OpenSanctions ingest. The derivation logic is: `is_shadow_fleet = TRUE` if any row exists in `vessel_topic` with `topic = 'mare.shadow' AND valid_to IS NULL`.

The 30-minute lag is intentional: it ensures the ingest job has completed and committed before the derivation job reads from `vessel_topic`.

## Alternatives Considered

**On-the-fly JOIN at query time.** Remove `vessel.is_shadow_fleet`; instead JOIN to `vessel_topic` in every vessel query. Rejected because the live map query runs against potentially hundreds of vessels at once, and a JOIN to `vessel_topic` on every map render adds latency and complexity. A materialized boolean is read in the same query that fetches position data.

**Trigger-based materialization.** Write a Postgres trigger on `vessel_topic` that updates `vessel.is_shadow_fleet` immediately when a topic row is inserted or invalidated. Rejected because triggers are difficult to test, invisible to the ORM layer, and create hidden coupling between tables. The nightly lag (< 24 hours) is acceptable for a compliance dashboard that does not need real-time shadow fleet detection.

## Consequences

**Enables:**
- Shadow fleet filter on the live map with no extra query complexity.
- Simple index (`ix_vessel_shadow_fleet`) already present from Phase 1 schema.
- Derivation logic is explicit Python code, testable and visible.

**Costs:**
- Up to 24-hour lag between a new entity appearing in OpenSanctions and `is_shadow_fleet` being set. This is acceptable for a compliance dashboard.
- If the derivation job fails, `is_shadow_fleet` may be stale. Monitoring (Phase 7) will alert on job failures.

**Reversibility:** 5 of 5. The derivation job can be re-run at any time; the boolean can be removed if a better approach is found.

## Plain-English Summary

Whether a vessel is on the shadow fleet is stored as a simple yes/no flag on the vessel record. This flag is recalculated every night after the latest sanctions data has been downloaded. The recalculation reads a topic tag table and sets the flag accordingly.

This is simpler than calculating it on the fly every time the map loads, and simpler than using a database trigger. The trade-off is that the flag can be up to 24 hours out of date — but because this is a compliance dashboard (not a real-time navigation tool), a one-day lag is acceptable.
