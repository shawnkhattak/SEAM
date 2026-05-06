# ADR-0023: Raw Insert Independent of Projection

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 4a

## Context

OpenSanctions FtM entities must be stored and then projected into relational tables (`organization`, `vessel_topic`, etc.). The projection logic may change as the schema evolves. If projection and raw storage are coupled, a bug in the projection discards data that cannot be recovered without re-downloading the entire dataset.

## Decision

Store every FtM entity in `opensanctions_entity_raw` first, before running any projection. The raw insert is committed independently; the projection is a separate step that reads from the raw table. This means the projection can be re-run at any time from `opensanctions_entity_raw` without a new download.

## Alternatives Considered

**Coupled insert.** Insert into raw and projection tables in a single transaction. Simpler code, but if the projection fails mid-batch, the transaction rolls back and the raw data is lost too. A re-run requires a new download.

**Projection only, no raw storage.** Save only the projected rows. Simpler schema, but loses provenance — there is no way to audit what the source data actually contained, or to re-project with different logic.

## Consequences

**Enables:**
- Re-projection without a new download (any code fix can be applied retroactively).
- Full audit trail of what OpenSanctions actually provided on each ingestion date.
- Safe debugging: raw data survives even if projection code is wrong.

**Costs:**
- `opensanctions_entity_raw` grows to store every JSONB payload, which is large. Requires a periodic trim policy (not implemented in Phase 4a; deferred to Phase 7).
- Two writes per entity instead of one.

**Reversibility:** 4 of 5. Adding more projection tables later is straightforward.

## Plain-English Summary

Every piece of data from the OpenSanctions download is saved twice: once in a raw archive table and once in the structured operational tables the dashboard reads. This is deliberate redundancy — if the conversion logic from "raw" to "structured" ever has a bug or needs to be improved, all the original source data is still there and can be re-processed without going back to the internet.

Think of it like photographing a receipt before entering it into a spreadsheet. If the spreadsheet formula was wrong, you can fix the formula and re-enter from the photo. Without the photo, a mistake would mean you have to find the receipt again.
