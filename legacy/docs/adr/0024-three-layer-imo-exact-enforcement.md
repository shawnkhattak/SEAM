# ADR-0024: Three-Layer Enforcement of IMO-Exact-Only Auto-Confirm

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 4a

## Context

ADR-0005 established that `status = 'auto_confirmed'` is only permitted for `match_method = 'imo_exact'`. This is a business-critical rule: incorrectly auto-confirming a non-IMO match could label a clean vessel as sanctioned, with significant legal and commercial consequences for the vessel operator or cargo owner.

The question is how to enforce this rule so that it cannot be bypassed by a future code change or a well-intentioned but mistaken developer.

## Decision

Enforce the rule in three independent, non-redundant layers:

1. **Application code.** The matcher service only calls `_record_match(..., status='auto_confirmed', ...)` when `match_method == 'imo_exact'`. All other call sites pass `status='pending'`.

2. **Database CHECK constraint.** `ck_sanctions_match_auto_confirm_imo_only` on the `sanctions_match` table: `CHECK (NOT (status = 'auto_confirmed' AND match_method != 'imo_exact'))`. This rejects invalid rows at the storage layer regardless of how they were generated — even via `psql` or a direct ORM call that bypasses the service layer.

3. **Unit test.** `test_auto_confirm_never_set_for_non_imo_methods` verifies the application-layer rule, and `test_auto_confirm_imo_only_constraint_exists` verifies the database-layer constraint declaration is present in the ORM model.

## Alternatives Considered

**Application code only.** Simpler — just enforce it in the service. Rejected because a future developer could add a second code path that calls `_record_match` with wrong arguments, and the check would be bypassed. Also rejected because it provides no audit-time guarantee: the data in the database does not itself prove the rule was followed.

**Database constraint only.** Let the database reject invalid rows; don't check in code. Rejected because the database error would surface as a generic constraint violation at runtime, with no guidance on why it failed. The application-layer check provides clearer error context and catches mistakes before they hit the database.

**Application + test, no database constraint.** Accepted in many systems. Rejected here because a test is a development-time check, not a runtime guarantee. The database constraint is a permanent, runtime enforcement that survives code refactors, test deletions, and direct SQL access.

## Consequences

**Enables:**
- Any audit of the `sanctions_match` table can prove the rule was followed — every `auto_confirmed` row has `match_method = 'imo_exact'`, by database guarantee.
- Future developers get a clear database error if they attempt to violate the rule, with the constraint name pointing them to the ADR.
- The unit test catches accidental regressions in the application layer before deployment.

**Costs:**
- Three enforcement points means three places to update if the rule ever changes. This is acceptable because the rule is intentionally hardcoded and documented as a locked decision (ADR-0005).
- The CHECK constraint cannot prevent all misuse (e.g., someone who drops the constraint first), but it raises the bar significantly.

**Reversibility:** 3 of 5. Relaxing the rule requires deleting the database constraint, updating the service code, and updating the tests — all of which are deliberate steps that a developer must consciously take.

## Plain-English Summary

The rule that says "only IMO-exact matches can be auto-confirmed" is enforced in three places, not one. The code checks it, the database enforces it, and the test suite verifies it. This redundancy is intentional: for a rule with legal consequences (falsely labelling a vessel as sanctioned), a single enforcement point is not enough, because a future code change or direct database access could bypass it.

The database constraint is particularly important because it is permanent and survives code changes. Even if the application code were rewritten tomorrow, a row with `status='auto_confirmed'` and `match_method='name_fuzzy'` would still be rejected by the database. This makes the rule auditable in the data itself, not just in the code.
