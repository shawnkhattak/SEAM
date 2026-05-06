# Phase 4b: Sanctions UI, Shadow Fleet Filter, and Admin Review Queue

**Phase:** 4b (UI and admin endpoints)  
**Week:** 5 (continued)  
**Status:** Complete

---

## What Was Built

Phase 4b surfaces the sanctions and shadow fleet data built in Phase 4a in the user interface. It also wires up the admin review queue endpoints so a human reviewer can act on pending sanctions matches.

### Visual Indicators on the Map

Before Phase 4b, all vessel markers looked the same — an arrow in a status color (green at berth, amber departing, blue incoming, grey departed). Now the markers carry two additional signals:

- **Sanctioned vessels** — a red ring surrounds the arrow. The vessel is also sorted to the front (higher z-index) so it stays visible even when overlapping other markers. The tooltip shows "⚠ Sanctioned."
- **Shadow fleet vessels** — a small amber dot appears in the top-right corner of the marker. The tooltip shows "Shadow fleet."
- A vessel that is both sanctioned and shadow fleet shows both indicators.

These signals are derived from `current_sanctions_status` and `is_shadow_fleet` fields now included in every positions response. The positions endpoint was updated to merge these flags from the database in a single additional query per poll cycle, then cache them with the rest of the position data for 60 seconds.

### Shadow Fleet Filter

A new "Shadow" toggle button sits in the top-right control cluster (below Layers and News). When toggled on:
- Only shadow fleet vessels are rendered on the map.
- The status bar changes from "N vessels" to "N shadow fleet" with an amber indicator dot instead of green.

This allows an analyst to immediately isolate the shadow fleet without any other mode changes. Toggling it off returns all vessels.

### Vessel Detail Panel — Compliance Section

The vessel detail panel now shows:

1. **Alert banners** — one for sanctions status (red background) and one for shadow fleet status (amber background), only shown when relevant. These were already present as stubs in Phase 1; Phase 4b fills them in properly with status labels from the `SANCTIONS_STATUS_CONFIG` map.

2. **Sanctions Matches section** — loaded from `GET /api/sanctions/vessel/{imo}` when the panel opens. Each match card shows:
   - Entity name (from the raw OpenSanctions payload)
   - Match method (IMO exact, name + flag, name fuzzy, org link)
   - Status (Confirmed auto, Confirmed, Pending review, Rejected) with color coding
   - Datasets the entity appears in (e.g. "us_ofac_sdn, ru_nsd_sdn")
   - Confidence percentage (for non-IMO matches)

### Sanctions API Endpoints

Four new endpoints under `/api/sanctions/`:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/sanctions/vessel/{imo}` | Public (rate-limited) | All matches for a vessel |
| `GET /api/sanctions/review-queue` | X-Admin-Token | Open/all review queue items |
| `POST /api/sanctions/review-queue/{id}/confirm` | X-Admin-Token | Confirm a pending match |
| `POST /api/sanctions/review-queue/{id}/reject` | X-Admin-Token | Reject a pending match |

The review queue endpoints are protected by the `admin_token` setting (X-Admin-Token header). When a reviewer confirms a queue item, the corresponding `sanctions_match` row is updated to `confirmed` and a `sanctions_match_history` row is written with `changed_by = "admin"`.

---

## Design Decisions

**Why put is_shadow_fleet and current_sanctions_status in the positions endpoint?**

The positions response is fetched by the frontend once per 15-minute backend poll cycle (triggered by SSE). If sanctions status were a separate endpoint, the frontend would need to either batch-fetch all IMOs or wait for a vessel to be clicked before showing indicators. Including both flags in the positions response means the map can show all indicators immediately on load, with one extra DB query per poll cycle (a single `SELECT imo, is_shadow_fleet, current_sanctions_status FROM vessel WHERE imo IN (...)` covering all visible vessels at once).

**Why X-Admin-Token instead of OAuth?**

The admin review queue is a low-volume internal workflow used by one or two analysts. A shared secret header is simpler than OAuth flows for a single-tenant system. The token is configured via environment variable. Phase 7 hardening will evaluate whether stronger authentication is needed.

---

## Files Added or Changed

**New backend files:**
- `app/routers/sanctions.py` — 4 endpoints for vessel sanctions + admin review queue

**Modified backend files:**
- `app/schemas.py` — `VesselPosition` extended with `is_shadow_fleet` + `current_sanctions_status`; new `SanctionsMatchResponse` and `ReviewQueueItem` schemas
- `app/routers/vessels.py` — positions endpoint merges DB flags per poll
- `app/main.py` — sanctions router registered; X-Admin-Token added to CORS headers

**New frontend files:**
- `frontend/src/api/sanctions.ts` — `fetchVesselSanctions`, `fetchReviewQueue`, `confirmReviewItem`, `rejectReviewItem`

**Modified frontend files:**
- `frontend/src/types/index.ts` — `VesselPosition` extended; new `SanctionsMatch` and `ReviewQueueItem` types
- `frontend/src/components/VesselMarker.tsx` — red ring (sanctioned) + amber dot (shadow fleet) badge overlays
- `frontend/src/components/LiveMap.tsx` — shadow fleet filter toggle + filtered rendering
- `frontend/src/components/VesselDetailPanel.tsx` — compliance alert banners + sanctions match cards

---

## What Was Deferred to Phase 4b+

- Paris, Black Sea, and Abuja MoU detention datasets (Tokyo only for now)
- Organization full graph traversal for `org_link` match method
- A dedicated admin dashboard page (Phase 7)
- Bulk review queue actions (Phase 7)
