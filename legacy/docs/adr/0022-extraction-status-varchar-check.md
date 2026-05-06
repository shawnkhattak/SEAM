# ADR 0022: extraction_status as VARCHAR with CHECK Constraint

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 3

## Context

`news_item.extraction_status` tracks which tier of entity extraction has completed for each article. The valid values in Phase 3 are `pending`, `done`, and `error`. Phase 6 will add a `gliner_done` state and potentially `haiku_done` as the remaining tiers are implemented.

The column needs a type that enforces a closed set of valid values while remaining extensible without painful migrations.

## Decision

Use `VARCHAR(30)` with a `CHECK` constraint:

```sql
CHECK (extraction_status IN ('pending', 'done', 'error'))
```

When Phase 6 adds new states, the constraint is updated with `ALTER TABLE news_item DROP CONSTRAINT ck_news_item_extraction_status` followed by `ADD CONSTRAINT ... CHECK (extraction_status IN ('pending', 'done', 'error', 'gliner_done', 'haiku_done'))`. This requires a migration but not a type drop and recreate.

## Alternatives Considered

**Postgres ENUM type.** A native `CREATE TYPE extraction_status AS ENUM(...)` enforced at the database level. More explicit than VARCHAR, prevents any out-of-set value from the ORM layer. Rejected because adding a new value to a Postgres ENUM requires `ALTER TYPE ... ADD VALUE`, which is not transactional in older Postgres versions and cannot be used inside a migration transaction block. SQLAlchemy's Alembic also requires special handling (`schema=None`, `create_type=True`) that creates operational friction. The extensibility cost is too high for what is essentially an application-layer state machine.

**Integer status codes.** Map `pending=0`, `done=1`, `error=2`. Fast for comparisons and indexing. Rejected because integer codes are opaque in `psql` queries and application logs, making debugging harder with no compensating advantage at the scale of news ingestion.

**No constraint (free VARCHAR).** Accept any string. Rejected because invalid states (typos, code bugs) would be silently stored and would require a full table scan to detect.

## Consequences

**Enables:**
- Human-readable status values in raw queries and logs.
- Adding new states in Phase 6 with a single `ALTER TABLE` migration inside a transaction.
- The ORM model validates values at application startup via the `CheckConstraint` declaration.

**Costs:**
- Adding new states requires a migration, not just a code change.
- The CHECK constraint is not enforced by the ORM — it is enforced only by the database, so ORM-level unit tests that bypass the database would not catch invalid states.

**Reversibility:** 4 of 5. Migrating to ENUM later is possible but requires a type cast and data transformation.

## Plain-English Summary

Each news article has a status that records how far through the entity extraction pipeline it has been processed: waiting (`pending`), finished (`done`), or failed (`error`). Future versions will add more stages as the AI extraction tiers are enabled.

This status is stored as a short text string rather than a database-native restricted type (called an ENUM). The reason is flexibility: Postgres's native restricted type requires a special, tricky procedure to add new values to it later, which becomes a maintenance burden. A text column with a simple check rule is slightly less strict but much easier to extend — adding a new stage requires only a straightforward one-line database change, not a multi-step type manipulation.
