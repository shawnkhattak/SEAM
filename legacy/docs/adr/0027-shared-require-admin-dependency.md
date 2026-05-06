# ADR 0027: Shared `require_admin` Dependency Over Inline Header Checks

**Status:** Accepted
**Decided:** 2026-05-02
**Deciders:** Solo (Shawn Khattak)

---

## Context

Phase 7a added six admin force-action endpoints in `routers/admin.py`, all requiring an `X-Admin-Token` header validated against `settings.admin_token`. The first prototype for `routers/sanctions.py` contained an inline `_require_admin(request)` function that duplicated header extraction and comparison logic in the same file. With nine admin-gated endpoints across two routers, duplicated auth logic is a maintenance liability: any future change — token rotation scheme, rate-limiting behaviour, switching from 401 to 403, adding IP allowlisting — must be found and applied in every copy.

---

## Decision

Centralise admin authentication as a reusable FastAPI `Depends` callable at `app/auth/admin.py`. Every admin-gated endpoint injects `_: str = Depends(require_admin)`. The inline `_require_admin` function in `sanctions.py` was removed; `get_settings` and `json` imports added solely for that function were removed at the same time.

---

## Alternatives Considered

1. **Inline per-router check (status quo)** — No new file, each router validates its own token. Rejected because nine endpoints means nine places to update if the auth scheme changes, and divergence is invisible until a security audit.

2. **FastAPI middleware** — A middleware layer validates the token before any admin path is reached. Rejected because it requires distinguishing admin vs non-admin paths in the middleware, making it harder to apply to individual endpoints selectively, and it cannot be composed with `Depends`-based testing overrides cleanly.

3. **Centralised `Depends` callable (chosen)** — One function in `app/auth/admin.py`; injected via FastAPI dependency injection. Works naturally with `pytest` overrides, is co-located with auth logic, and requires a single import change to apply everywhere.

---

## Consequences

- **Enables:** Single-point change for token validation behaviour across all nine admin endpoints.
- **Precludes:** Per-endpoint variation in auth logic without creating a second dependency function (acceptable — all admin endpoints share the same token).
- **Costs:** One additional file (`app/auth/admin.py`). Minor.
- **Reversibility:** 5 (easy to reverse — replace `Depends(require_admin)` with inline check at any endpoint).

---

## Plain-English Summary

When we added admin-only endpoints across two different parts of the backend, each one was checking the same secret token using copy-pasted code. Copy-pasted security checks are dangerous: if we ever need to change how the token is validated, we have to find every copy and update them all — and it's easy to miss one.

We moved the check into a single shared function that every admin endpoint calls. Now there is exactly one place to look when something changes — the auth function in `app/auth/admin.py`. All nine admin endpoints across both routers use it automatically.
