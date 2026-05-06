# ADR 0015: SCD2 for Vessel Identity History

**Status:** Accepted  
**Date:** 2026-04-30  
**Phase:** 1

## Context

A vessel's identity — primarily its name and flag — is not immutable. Shadow fleet vessels in particular are known to systematically rename and re-flag to evade sanctions scrutiny. A vessel that is sanctioned under one name may continue operating under a new name with no apparent connection to the original.

The `vessel` table records the current name and flag for each IMO number. Without history, a rename silently overwrites the previous values. This means:
- A vessel sanctioned as "DARK STAR" that renames to "OCEAN SPIRIT" would show no record of its sanctioned name.
- Compliance auditors reviewing historical position data would see the current name only, not the name the vessel operated under at the time of each position.
- Detection of systematic renaming patterns — a signal used in shadow fleet identification — would be impossible.

## Decision

Implement SCD2 (Slowly Changing Dimension Type 2) for the `name`, `flag`, and `vessel_type` fields of the vessel master record.

A dedicated `vessel_scd2_history` table stores the full change history. Each row has:
- `imo` — the vessel identifier (immutable under international convention)
- `name`, `flag`, `vessel_type` — the attribute values for this period
- `valid_from` — the UTC timestamp when this record became current
- `valid_to` — the UTC timestamp when this record was superseded (`NULL` for the current record)

The `record_scd2_changes` function in `app/services/vessel_master.py` runs on every poll cycle for every vessel. It reads the current SCD2 record (`valid_to IS NULL`), compares against the incoming data, and writes a new row only if something changed. The previous row's `valid_to` is set to the `valid_from` of the new row, creating a complete, non-overlapping timeline.

The `vessel` table continues to hold the current values for fast lookup; `vessel_scd2_history` holds the complete timeline for historical analysis.

## Alternatives Considered

**Overwrite in place.** Simplest approach; no history. Rejected because shadow fleet rename detection (Phase 6) requires the full rename timeline, and overwriting destroys it irreversibly.

**Event log (append-only changes table).** Store only the fields that changed, not the full row for each period. Reconstructing the state at any historical point requires replaying all events. Rejected because SCD2's "full row per period" design makes point-in-time queries trivial — `WHERE valid_from <= :t AND (valid_to > :t OR valid_to IS NULL)` — without replay logic.

**Separate audit table populated by Postgres triggers.** A trigger fires on every UPDATE to the `vessel` table and writes the old row to an audit table. Rejected because triggers are invisible to the application layer, making behavior harder to reason about during code review, and the audit table would capture every UPDATE (including no-ops) rather than only meaningful attribute changes.

## Consequences

**Enables:**
- "What name was this vessel operating under at position X?" — needed for compliance audit trails.
- "How many times has this vessel renamed?" — a shadow fleet risk signal.
- Historical sanctions matching: determine whether a vessel was named when a sanction was active.

**Costs:**
- One additional read and conditionally one additional write per vessel per poll cycle (800 vessels = up to 800 additional writes per cycle when names change).
- In practice, renames are rare; most cycles do zero SCD2 writes.

**Reversibility:** 2 of 5. Removing SCD2 after Phase 6 shadow fleet detection is built would require replacing the entire detection pipeline.

## Plain-English Summary

Vessels, especially in the shadow fleet, change their names and flags to avoid scrutiny. This ADR ensures that every name and flag a vessel has ever operated under is permanently recorded with the exact dates it was in use.

When the system detects that a vessel's name has changed — say from "DARK STAR" to "OCEAN SPIRIT" — it doesn't overwrite the old record. Instead it closes the old record with a timestamp and opens a new one. This means a compliance auditor can ask "what was this vessel called on March 15th?" and get a precise answer, and an analyst can see the complete rename history at a glance. Phase 6 will use this rename history as one of the signals for identifying shadow fleet vessels.
