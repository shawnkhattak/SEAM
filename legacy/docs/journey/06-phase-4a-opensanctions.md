# Phase 4a: OpenSanctions Ingestion, Sanctions Matching, and Shadow Fleet

**Phase:** 4a (data plumbing)  
**Week:** 5  
**Status:** Complete

---

## What Was Built

Phase 4a adds the compliance backbone to OceansX V2. When you use the dashboard, it answers the question: "Is this vessel sanctioned?" That answer requires a pipeline — a daily download of sanctions data, an ingestion step, a matching step, and a flag derivation step. Phase 4a builds all of that without any user interface. The UI layer (sanctions tab, shadow fleet filter, admin review queue display) comes in Phase 4b.

### Data Sources

The primary sanctions data source is [OpenSanctions](https://opensanctions.org), an open-source project that aggregates sanctions lists from dozens of governments and international bodies — OFAC (U.S. Treasury), the UN Security Council, the EU, and others — into a single, structured dataset. The dataset uses a format called FtM (FollowTheMoney), where every entity has a unique ID, a schema type (Vessel, Company, etc.), a properties dictionary, and a referents list (other IDs this entity has been merged with or split from over time).

ADR-0002 chose OpenSanctions over building individual parsers for each sanctions list because maintaining eight custom parsers is a fragile engineering burden that scales poorly as lists change their formats.

### The Two-Step Ingestion Design

Every entity that arrives from OpenSanctions is stored in two layers:

**Layer 1 — Raw:** The complete original payload is inserted into `opensanctions_entity_raw`. This happens first, before any interpretation or transformation. If the projection code (Layer 2) has a bug, the raw data can be re-processed without re-downloading anything.

**Layer 2 — Projection:** The raw payload is parsed into structured tables. Vessel entities produce rows in `vessel_topic` (topic tags like `sanction` and `mare.shadow`). Company entities produce rows in `organization`, `organization_alias`, and `organization_topic`.

This design — raw insert independent of projection — is a common pattern in data engineering. It means the system always has a recoverable state: if tomorrow's code is smarter than today's, it can re-derive the projection tables from raw data without losing anything.

### The Sanctions Matcher and ADR-0005

The matcher is where the compliance-critical business rule lives. It looks for vessels in our database that correspond to vessels in the OpenSanctions data.

There is only one automatic confirmation method: **IMO exact match**. If an OpenSanctions vessel entity has an IMO number that exactly matches an IMO we track, the match is automatically confirmed (`status = 'auto_confirmed'`). The vessel's `current_sanctions_status` is set to `'sanctioned'`.

Every other method — fuzzy name matching, flag-combined matching, organizational graph traversal — produces `status = 'pending'` and routes to the human review queue. This rule is enforced in three places:

1. The matcher service code only calls `_record_match(..., status='auto_confirmed', ...)` when `match_method == 'imo_exact'`.
2. A Postgres CHECK constraint (`ck_sanctions_match_auto_confirm_imo_only`) makes it physically impossible for any `sanctions_match` row to have `status = 'auto_confirmed'` with `match_method != 'imo_exact'`. Even if a future code change tried to write such a row, the database would reject it.
3. A unit test (added in this phase) explicitly verifies the application-layer rule and the presence of the database-layer constraint.

Why three layers of enforcement? Because sanctions decisions have legal and financial consequences. A false positive (incorrectly labelling a clean vessel as sanctioned) can cost a company enormous amounts in delayed cargo, blocked transactions, and reputational damage. Triple-layer enforcement makes this rule auditable, not just conventional.

### Referents

OpenSanctions entities sometimes get merged or split as the dataset matures. When two records are merged into one, the old IDs are listed in the new entity's `referents` field. The matcher is referent-aware: it uses the entity's current ID in the `sanctions_match` record, but the underlying query logic can be extended (Phase 4b) to detect when a vessel was previously matched to an old entity ID that has since been superseded.

### Shadow Fleet Derivation

The shadow fleet is not a static list — it is a derived property. OceansX defines a vessel as a shadow fleet vessel if it has an active `mare.shadow` topic tag from OpenSanctions (meaning: `vessel_topic.topic = 'mare.shadow'` AND `vessel_topic.valid_to IS NULL`).

`shadow_fleet.py` implements `refresh_shadow_fleet_flags()`, a nightly job that reads all currently-active shadow fleet tags and sets `vessel.is_shadow_fleet = True` for matching vessels and `False` for all others. This runs at 04:30 America/Chicago every night, 30 minutes after the OpenSanctions ingest completes at 04:00.

### Entity Extraction Gets Organizations

The news entity extraction dictionary (built in Phase 3) now includes organization names and aliases. When a news article mentions "Sovcomflot" or "PAO Sovcomflot," the extraction pipeline will identify it as an organization mention and tag the article accordingly. This requires no UI change — the `NewsEntityMention.entity_type` column already supports arbitrary strings, so `"organization"` is a valid value immediately.

---

## Database Schema

Twelve new tables, plus one ALTER to `vessel_topic` (column rename from `source_dataset` to `os_entity_id`, widened from VARCHAR(50) to VARCHAR(100)) and one new CHECK constraint on `vessel.current_sanctions_status`.

| Table | Purpose |
|---|---|
| `opensanctions_entity_raw` | Raw FtM payloads — authoritative, re-projectable |
| `organization` | Projected company entities |
| `organization_alias` | All name variants per organization |
| `organization_topic` | Topic tags per organization (sanction, etc.) |
| `vessel_organization_link` | Vessel → company graph (owner, manager, operator) |
| `vessel_topic` | Topic tags per vessel (altered from Phase 1 stub) |
| `sanctions_source` | Registry of OpenSanctions datasets loaded |
| `sanctions_listing` | Projected vessel sanctions entries |
| `sanctions_match` | Match results with IMO-only auto-confirm rule |
| `sanctions_match_history` | Audit trail for every status transition |
| `staging_opensanctions_ingest` | Ops Swarm staging boundary |
| `staging_sanctions_match` | Ops Swarm staging boundary |
| `agent_review_queue` | Human review queue for non-IMO matches |
| `mou_inspection` | Tokyo MoU Port State Control records |

### The CHECK Constraint Added to vessel

```sql
ALTER TABLE vessel ADD CONSTRAINT ck_vessel_sanctions_status
  CHECK (current_sanctions_status IN ('clean', 'sanctioned', 'pending', 'prev_sanctioned'));
```

This constraint was missing from the Phase 1 migration even though the column existed. Phase 4a adds it.

---

## Scheduling

Two new nightly jobs join the scheduler:

| Job | Schedule | What it does |
|---|---|---|
| `refresh_opensanctions` | 04:00 America/Chicago | Downloads all maritime-relevant OpenSanctions datasets, ingests raw + projection, runs IMO-exact matcher |
| `refresh_shadow_fleet_flags` | 04:30 America/Chicago | Derives `vessel.is_shadow_fleet` from active `mere.shadow` topic tags |

The 30-minute gap between the two jobs ensures the ingest always completes before the shadow fleet derivation reads from `vessel_topic`.

---

## Files Added or Changed

**New files:**
- `app/mocks/opensanctions_maritime.json` — 5 FtM entities (3 vessels, 2 companies) for offline development
- `app/clients/opensanctions.py` — bulk download client; mock mode reads fixture file
- `app/services/opensanctions_ingest.py` — FtM parser and projection (raw insert → organization/vessel_topic rows)
- `app/services/sanctions_matcher.py` — IMO-exact matcher with referent awareness and ADR-0005 enforcement
- `app/services/shadow_fleet.py` — nightly shadow fleet flag derivation from vessel_topic
- `app/alembic/versions/0005_phase4a_opensanctions.py` — migration 0004→0005
- `tests/test_sanctions_matcher.py` — 7 unit tests covering ADR-0005 rule

**Modified files:**
- `app/models.py` — 13 new ORM classes; updated VesselTopic stub (source_dataset → os_entity_id)
- `app/config.py` — `opensanctions_api_key`, `opensanctions_mock_mode`
- `app/services/entity_extraction.py` — dictionary expanded to include organization names and aliases
- `app/scheduler.py` — `_job_refresh_opensanctions`, `_job_refresh_shadow_fleet_flags`, plus registrations

---

## What Was Deferred

**Phase 4b (UI and admin):**
- Sanctions tab in the vessel detail drawer
- Shadow fleet filter on the map (toggle to show only shadow fleet vessels)
- Badge overlays on map markers for sanctioned/shadow fleet vessels
- Admin review queue API endpoints and UI (for the human review workflow)
- Paris, Black Sea, and Abuja MoU datasets (Tokyo only ingested in Phase 4a)
- Organization full graph traversal for `org_link` match method

---

## What Was Harder Than Expected

**The vessel_topic stub collision.** The Phase 1 migration created `vessel_topic` as a placeholder stub (with a `source_dataset` column) for schema completeness. Phase 4a needed to give this table its real structure (`os_entity_id`, wider `topic` column). The fix was to ALTER the existing table in migration 0005 rather than recreating it — straightforward in the migration, but it required detecting the mismatch between the ORM model stub and the live column name. Discovered during import testing.

**How many execute calls does a test need?** The sanctions matcher makes more database calls than a naive mock anticipates: vessel existence check, match existence check, sanctions source lookup, listing upsert, vessel status update. The test helper needed a flexible side_effect function rather than a fixed list to handle the full call sequence without running out of pre-set responses.

---

## Plain-English Summary

Phase 4a is the compliance plumbing phase. It connects OceansX to the global sanctions system by downloading a structured, aggregated sanctions dataset every morning, matching vessel IMO numbers against it, and flagging matched vessels. The shadow fleet derivation works the same way — it reads a special topic tag from the same dataset and sets a flag on matching vessels.

The one design decision that matters most in this phase is the IMO-only auto-confirm rule. It sounds like a restriction, but it is actually a safety feature: the only match that can be confirmed automatically is one that is certain (identical IMO number). Everything else requires a human to review it. This prevents a fuzzy name match from mistakenly labelling a clean vessel as sanctioned, which could have serious real-world consequences for a vessel operator or cargo owner.
