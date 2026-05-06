# ADR 0017: terminal_geom as a Satellite Table

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 2

## Context

Terminal polygons (the geographic boundaries of each terminal) need to be stored in the database for PostGIS containment queries. The question is where.

The `terminal` table holds terminal identity data: name, short code, port association, and eventually operational metadata (berth count, vessel type restrictions, etc.). Terminal polygons are large binary objects — a detailed polygon can be several kilobytes in the PostGIS wire format. Embedding the polygon as a column on `terminal` means:
- Every query that joins `terminal` to load a terminal's name or code also loads the polygon binary, even when the query has no use for it.
- The polygon binary cannot be separately indexed without the overhead of a functional index on the column.
- The polygon's update lifecycle is independent of the terminal's identity lifecycle: polygons are refreshed daily from MPA chart data, while terminal identity changes rarely.

## Decision

Store terminal polygons in a dedicated satellite table, `terminal_geom`, with `terminal_id` as both the primary key and a foreign key referencing `terminal.id`:

```
terminal_geom
  terminal_id  INTEGER  PK, FK → terminal.id  ON DELETE CASCADE
  geom         Geography(POLYGON, 4326)        NOT NULL
  source       VARCHAR(50)                     NOT NULL
  buffered     BOOLEAN                         NOT NULL  DEFAULT false
```

A GiST spatial index on `geom` enables efficient `ST_Within` containment queries. The `source` column records the MPA layer the polygon came from. The `buffered` column flags polygons that are approximate — synthesized from a point centroid via `ST_Buffer(point, 1000)` because the source data lacked a true polygon boundary.

Queries that need terminal identity but not geometry join only `terminal`. Queries that need geometry (the position assignment job) join `terminal_geom` directly. The two tables are updated independently: identity updates touch `terminal`; daily polygon refreshes touch only `terminal_geom`.

## Alternatives Considered

**`geom` as a nullable column on `terminal`.** Simpler schema; one less table. Rejected because it loads the polygon binary into every terminal join and couples the polygon refresh cycle to the terminal identity update path, increasing the chance of accidental overwrites.

**Separate `geom` column on `terminal` with a deferred/lazy loading pattern at the ORM level.** SQLAlchemy supports `deferred` column loading, which omits a column from the default SELECT. This avoids the "always loaded" problem. Rejected because deferred columns are ORM-layer magic that is invisible at the SQL level, making queries unpredictable during debugging, and because the satellite table approach is more composable — it allows multiple geometry types per terminal in Phase 7 without schema changes.

**Store polygons in a separate GeoJSON file, not in the database.** Serve them directly as static files. Rejected because the PostGIS `ST_Within` containment check — the key operation for assigning `terminal_id` to position rows — requires the polygons to be in the database.

## Consequences

**Enables:**
- Terminal identity queries (for display, filtering, FK joins) never load polygon data.
- Polygon refresh (`ON CONFLICT DO UPDATE` over `terminal_geom`) does not touch or lock `terminal` rows.
- The `buffered` flag allows Phase 7 to surface data-quality caveats in the UI without schema changes.
- Adding additional geometry types per terminal (e.g., an inner berth polygon vs. an outer anchorage zone polygon) can be done by extending `terminal_geom` with a `geometry_type` discriminator, without altering `terminal`.

**Costs:**
- `JOIN terminal_geom` is required for any query that needs polygon data.
- `terminal_id` rows without a corresponding `terminal_geom` row are valid (terminals for which no geometry was available). Queries must handle this absence.

**Reversibility:** 3 of 5. Merging back into `terminal` requires a data migration and updates to the containment query and the refresh job.

## Plain-English Summary

Each terminal's geographic boundary (the polygon that defines which ships are "inside" the terminal) is stored in a separate, dedicated table rather than as an extra column on the terminal record itself. This separation has two main benefits.

First, it keeps the terminal record table lean: any code that just needs to know a terminal's name doesn't accidentally load a large geographic blob along with it. Second, it lets the system update polygon data independently — the daily MPA chart refresh can overwrite just the geometry table without touching the terminal records that other tables reference. A `buffered` flag in the geometry table marks polygons that were approximated from a centroid point rather than taken from a true boundary, so the UI can indicate to users which terminals have precise vs. approximate location data.
