# ADR 0013: Terminal Coverage Gaps — Fallback Strategy

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 2

## Context

Terminal containment (`ST_Within`) assigns a `terminal_id` to each position row when the vessel's lat/lon falls inside a known terminal polygon. Those polygons come from MPA's `ports_and_services_a` GeoJSON layer, which covers only officially registered terminals within Singapore port limits.

Three gap cases arise:

1. **Anchorage areas** — vessels at anchor outside named terminals (Eastern Anchorage, Western Anchorage, Strait of Malacca anchor berths) have no polygon coverage. `terminal_id` stays `NULL`.
2. **Ungeometrized terminals** — some `ports_and_services_a` features are points or lines, not polygons. The ingestion pipeline tries a 1 km `ST_Buffer` fallback around the centroid; if no centroid coordinates are in the properties, the terminal row is created but `terminal_geom` is omitted entirely.
3. **Vessels in transit** — `terminal_id = NULL` is the correct value for vessels underway through the strait. It is not an error.

## Decision

- `terminal_id = NULL` is a valid, expected state. It must not be treated as data quality failure in alerting or UI.
- For polygon-less terminals the `buffered = true` flag on `terminal_geom` signals that the geometry is approximate. The UI may render buffered terminals with a dashed border to indicate uncertainty.
- We do **not** pre-fill coverage gaps with manual polygons in Phase 2. Anchorage-zone polygon boundaries are operationally complex and change seasonally. Phase 5 (weather + risk scoring) will introduce anchorage zone awareness from a dedicated dataset.
- The `ST_Within` query uses `geography::geometry` cast so the index (`USING gist`) is used efficiently. Casting both sides to `geometry` avoids spheroid math overhead on every row during bulk refresh.

## Consequences

- ~30–40% of position rows are expected to have `terminal_id = NULL` at any given time — primarily vessels in the strait and at anchorage.
- Terminal assignment accuracy is bounded by MPA polygon quality. No mitigations are applied in Phase 2.
- The `buffered` column enables Phase 7 to surface data-quality caveats in the admin dashboard without schema changes.
