# ADR 0029: Generic DB Explorer via Raw SQL With Explicit Allowlist

**Status:** Accepted
**Decided:** 2026-05-02
**Deciders:** Solo (Shawn Khattak)

---

## Context

The admin SPA requires a DB row browser for operational debugging — inspecting live data in individual tables without needing `psql` access or a separate database GUI. The explorer must be safe to expose behind the admin token: it must not allow access to internal Postgres system tables, the `pg_shadow` secrets table, or any migration or auth table not in the intended scope. It also needs to scale gracefully as the schema grows past 20 tables without requiring a new endpoint per table.

---

## Decision

Use raw SQL (`SELECT * FROM {table}`) with an explicit `_ALLOWED_TABLES` Python set of 25 permitted table names in `app/routers/admin.py`. Table name validation happens before any SQL executes; names not in the set return 404. `LIMIT`/`OFFSET` and the single-row `pk` parameter are passed as bound parameters; only the table name is substituted via f-string, and only after allowlist validation — it is not user-controlled.

Pagination is fixed at 50 rows per page (`_PAGE_SIZE = 50`). All three explorer endpoints (`GET /admin/db`, `GET /admin/db/{table}`, `GET /admin/db/{table}/{pk}`) require the admin token and are rate-limited to 30/minute.

---

## Alternatives Considered

1. **ORM-based per-model endpoint** — Fully type-safe; serialisation is explicit. Rejected because it requires a new endpoint for every table and does not serve the operational use-case well — the point is to browse any table quickly without pre-writing serialisation code for each one.

2. **SQLAlchemy `inspect()` reflection** — Dynamic; automatically discovers all tables without a hardcoded list. Rejected because it exposes any table that exists in the database, including internal migration tables (`alembic_version`), future tables added in development, or accidentally created tables. An explicit allowlist is a smaller attack surface.

3. **Third-party DB GUI (Adminer, pgAdmin)** — Feature-rich, no backend code required. Rejected because it requires a separate service deployment, adds a separate auth surface, and is disproportionate for a portfolio project with an internal admin token.

4. **Raw SQL with explicit allowlist (chosen)** — One generic endpoint pair, security enforced by an enumerated set. Any new table added to the schema requires a one-line addition to `_ALLOWED_TABLES`. The explorer cannot see anything not on the list.

---

## Consequences

- **Enables:** Browse any of 25 explicitly named tables from the admin SPA without new backend code per table.
- **Precludes:** Accessing Postgres system tables, `alembic_version`, or any table not added to the allowlist. Single-row lookup assumes `id` as the primary key column — tables with composite or non-integer PKs need a custom endpoint.
- **Costs:** Each new table requires a one-line allowlist addition. SQL injection risk is limited to the table name substitution, which is validated against a hardcoded set before use.
- **Reversibility:** 4 (easy to replace the generic endpoint with per-table endpoints later if richer serialisation is needed).

---

## Plain-English Summary

The admin dashboard needs to show rows from any table in the database — useful for debugging live data without having to SSH in and run database commands manually. The challenge is doing this safely: a fully open query tool could accidentally expose internal system tables, password tables, or data that shouldn't be visible.

The solution is an explicit list of 25 allowed table names. When the admin asks to browse a table, the backend first checks that the table name is on the list before running any query. If it's not on the list, the request is rejected. Everything on the list is a normal application table. The only cost is remembering to add new tables to the list when they are created.
