# Phase 2: Macro Statistics and Geospatial Context

---

## TL;DR

Week three adds two things that make the map legible as a port operations dashboard rather than just a vessel tracker: macro statistics (port throughput, bunker sales, container volumes, and vessel call counts as monthly time series) and geospatial context layers (coastlines, hazards, aids to navigation, port service boundaries, and offshore installations from MPA's official chart data). It also completes the terminal assignment pipeline started in Phase 1 — a PostGIS containment query now assigns every vessel position to the terminal whose polygon it falls inside, making later "dwell at terminal" calculations possible. A 24-hour timeline scrubber lets users drag backwards through a vessel's recent trail on the map.

---

## Goal

Phase 2 has two goals that share an underlying theme: context.

The live map from Phase 1 answers "where are the ships?" Phase 2 begins answering "what is happening in the port around those ships?" The macro statistics give operational context — is throughput up or down this month? are bunker sales elevated (which correlates with vessels waiting for fuel)? The geospatial layers give spatial context — is a vessel anchored in a designated anchorage area, or near a charted hazard, or inside a terminal service zone?

The secondary goal is to complete the terminal assignment pipeline. Phase 1 wrote `terminal_id = NULL` for every position row because the PostGIS terminal polygons didn't exist yet. Phase 2 builds those polygons and the containment check that populates `terminal_id` going forward.

---

## What Was Built

**Port and terminal hierarchy.** Three new tables complete the geospatial hierarchy:
- `port` — the canonical MPA port catalogue, keyed by LOCODE (UN/LOCODE — a standard code system for ports and logistics locations). One row per port.
- `port_alias` — alternative names and codes for ports. Created in schema for Phase 5 use; not yet populated.
- `terminal` — one row per terminal, with a foreign key to `port`. The `terminal` table existed as a stub in Phase 1 migration; Phase 2 adds the foreign key constraint to `port` and removes the stub.

**`terminal_geom` — PostGIS terminal polygons.** A satellite table (one row per terminal, not embedded in `terminal` itself) storing the terminal's geographic polygon as a PostGIS `Geography` type with a GiST spatial index (ADR-0017). Polygons come from MPA's `ports_and_services_a` GeoJSON layer. If a feature has no polygon (only a point or line), the ingestion pipeline falls back to a 1-kilometre `ST_Buffer` circle around the centroid, flagged with `buffered = true`. If no geometry is present at all, the terminal row is created but `terminal_geom` is omitted (ADR-0013).

**`refresh_terminal_polygons` — daily polygon ingestion.** A service function (`app/services/ports.py`) parses the `ports_and_services_a` GeoJSON response, upserts `Port` and `Terminal` rows, and upserts `terminal_geom` rows using `ST_GeographyFromText`. Runs daily at 04:00 America/Chicago via APScheduler `CronTrigger`.

**`find_terminal_for_position` — PostGIS containment check.** A second function in `ports.py` executes `ST_Within(vessel_point::geometry, terminal_polygon::geometry)`. Both sides are cast to the PostGIS `geometry` type (from `geography`) to allow use of the GiST index — without the cast, PostGIS would use spheroid math on every row, which is correct but slow. The function returns the `terminal_id` whose polygon contains the vessel's position, or `None` if the vessel is outside all known polygons (in transit, at anchorage, or in an area without coverage).

**Terminal assignment in the polling loop.** After `write_position_live` writes the position row with `terminal_id = NULL`, `update_position_terminal` runs the PostGIS containment check and updates the live row if a terminal is found. The resolved `terminal_id` is then passed to `maybe_write_position_archive`, so both tables stay consistent — archive rows get the same terminal assignment as their corresponding live row.

**Five macro statistics endpoints.** Five new API endpoints at `/api/macro/*` return monthly time series from MPA:
- `/api/macro/cargo-throughput` — total cargo tonnage per month
- `/api/macro/container-throughput` — TEU (twenty-foot equivalent units — the standard measure for container volumes) volume per month
- `/api/macro/bunkers-sales` — bunker fuel sales volume per month
- `/api/macro/shipping-tonnage` — gross registered tonnage of vessels calling per month
- `/api/macro/vessel-call-volume` — total vessel arrivals per month

All five respond with `Cache-Control: public, max-age=3600` (1-hour client cache) and are refreshed daily by a background job at 03:00 America/Chicago.

**Eleven geospatial layer endpoints.** A single parameterized endpoint `GET /api/geo/layer/{layer_name}` serves GeoJSON for any of eleven named layers from MPA's chart data: coastlines (area and line), dangers (area, line, and point), aids to navigation (point), ports and services (area, line, and point), and offshore installations (area and line). `GET /api/geo/layers` returns the list of available layer names. All respond with `Cache-Control: public, max-age=86400` (24-hour cache).

**`GET /api/ports/terminals` endpoint.** Returns the full list of terminals with their port association, for use by the admin dashboard and future filter features.

**Geospatial layer toggle panel.** The `GeoLayerPanel` component renders a checkbox list of all available layers outside the Leaflet map container (important — see below), with a color-coded swatch for each layer. Enabling a checkbox triggers a React Query fetch for that layer's GeoJSON and renders it on the map via the `GeoLayersRenderer` component, which is inside the map container. The split between panel (outside) and renderer (inside) is a structural requirement of Leaflet (see "What Surprised Me" below).

**24-hour vessel trail and timeline scrubber.** Selecting a vessel fetches its last 24 hours of archive positions and renders them as a dashed polyline on the map (`VesselTrailPolyline`). A range-input scrubber bar (`TimelineScrubber`) lets users drag backwards in time; the polyline updates to show only positions up to the scrubber's timestamp. The scrubber resets to "Now" whenever a different vessel is selected. The scrubber bar is outside the map container for the same Leaflet event capture reason as the layer panel.

---

## Decisions Made

- **`terminal_geom` as a satellite table (ADR-0017):** The polygon is stored in a separate table keyed by `terminal_id`, not as a column on `terminal`. This keeps the `terminal` table lightweight and avoids loading large binary geometry blobs into every join that just needs the terminal name or code.
- **Terminal coverage gaps and NULL policy (ADR-0013):** `terminal_id = NULL` is valid and expected. Vessels in transit, at anchorage, or in areas outside MPA polygon coverage produce NULL terminal_id. This is not an error and must not be treated as one in alerting or UI.
- **UI panels outside `MapContainer` (implemented, no ADR — implementation detail):** React-Leaflet's `MapContainer` intercepts all mouse events for map panning and zooming. Any `div` rendered inside `MapContainer` will have its drag events captured by Leaflet, making sliders and checkbox clicks unreliable. The fix is to split each Phase 2 component into a Leaflet renderer (inside MapContainer) and a UI panel (outside MapContainer in the outer `div`), with shared state lifted to the parent `LiveMap` component.
- **Archive terminal_id parity (implemented):** Archive rows receive the same `terminal_id` as their corresponding live row. The polling loop captures the return value of `update_position_terminal` and passes it directly to `maybe_write_position_archive`. This ensures the two tables are consistent from the time of write.

---

## What Surprised Me

**Leaflet captures mouse events aggressively.** React-Leaflet's `MapContainer` sets up Leaflet's internal event handling on mount, and anything rendered as a child of `MapContainer` is treated as part of the map surface. This is intentional for map controls like zoom buttons, but it means a `<input type="range">` scrubber or a `<label>` checkbox rendered inside `MapContainer` will not behave correctly — drag events on the scrubber trigger map pan instead. The solution (split into renderer inside + panel outside) is clean once you understand the constraint, but it is not obvious until the bug appears.

**The `nullsfirst` import name changed between SQLAlchemy versions.** SQLAlchemy 1.x exports `nulls_first` (with underscore). SQLAlchemy 2.x exports `nullsfirst` (without underscore). The vessel enrichment job imported the 1.x name, which resolved at import time but would have raised `AttributeError` at runtime on the `order_by` call. This was caught during a code review pass — it would have caused the enrichment job to silently fail every hourly cycle.

**GeoJSON from a chart data API is not always polygons.** The MPA `ports_and_services_a` layer (the "a" suffix denotes area features) sometimes contains point features with no area geometry. The "a" in the layer name is the intended geometry type, not a guarantee that every feature has that geometry. The ingestion pipeline handles this with a `_geojson_to_polygon_wkt` function that returns `None` for non-Polygon geometries, triggering the centroid-buffer fallback.

**Both sides of ST_Within must be cast to `geometry`.** PostGIS's `Geography` type uses accurate spheroid math for distance and containment calculations. While more accurate than the `geometry` type's planar approximation, it does not use the GiST spatial index efficiently for `ST_Within` queries. Casting both the vessel point and the terminal polygon from `geography` to `geometry` before the `ST_Within` call allows the GiST index to be used, reducing the containment query from a full-table scan to an index lookup. In the Singapore strait area (near the equator), the planar approximation error is less than 0.1% — acceptable for terminal assignment.

---

## What I Learned

**Separate the "what" from the "where" in geospatial models.** The `terminal` table holds what a terminal is (name, short code, port association). The `terminal_geom` satellite table holds where it is (polygon geometry). These are different concerns with different update rates — terminal identity almost never changes; terminal polygon boundaries change when MPA updates its chart data. Keeping them in separate tables makes it trivial to refresh the geometry independently without touching the terminal records that other tables reference via foreign key.

**Cache-Control headers on geospatial responses are not optional.** Each geo layer response can be hundreds of kilobytes of GeoJSON. Without a 24-hour `Cache-Control` header, every page load fetches all enabled layers fresh. With it, the browser caches the response and subsequent page loads are instant. The backend React Query configuration matches (`staleTime: 24h`), so neither the browser nor React Query makes redundant requests for chart data that changes only once a day.

**Mock fixtures for geo layers need to be minimal but realistic.** The 16 mock JSON fixture files created in Phase 2 each contain 2–5 representative features from the actual layer — enough that the rendering code exercises all geometry types (polygon, line, point) but small enough that the test suite runs in milliseconds. Committing full copies of the production layers (which can be megabytes each) would make the repository large and make diffs unreadable.

---

## Connection to the Whole

Phase 2 establishes the spatial context that Phase 5 (weather and risk scoring) will reason about. Knowing which terminal a vessel is in — and when it arrived — is the prerequisite for calculating dwell time (how long a vessel has been at a terminal), which is itself a risk signal: a vessel that has been at a terminal for six days when the typical stay is 12 hours is anomalous. The terminal containment pipeline built in Phase 2 is what makes that calculation possible.

The macro statistics endpoints built in Phase 2 are the first candidate for the business intelligence tab in Phase 7 (admin dashboard). The 24-hour trail scrubber built here is reused in Phase 5 as the vehicle for displaying historical weather conditions overlaid on the vessel's path.

The structural lesson of Phase 2 — split Leaflet renderers from UI panels — establishes the pattern for all future frontend components that combine map elements with control panels.
