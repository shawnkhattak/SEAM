# ADR 0007: Staging Tables as the Operations Swarm Boundary

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

The Operations Swarm (the autonomous AI agent process running on the production server) must produce data — processed sanctions records, entity extraction results, organization profiles — that eventually reaches the production database. But allowing autonomous agents to write directly to production tables is unsafe: a misbehaving agent, a parsing error in an upstream dataset, or an unexpected edge case could corrupt data that the public-facing interface depends on.

The question is what architectural mechanism enforces the boundary between what agents produce and what appears in production.

Three approaches were evaluated:
1. Application-level checks: validate agent output in code before writing to production.
2. Separate database: agents write to a completely separate database; a synchronization process copies approved data to the main database.
3. Staging tables with Postgres role-based permissions: agents write to `staging_*` tables; a dedicated role (`oceansx_promote`) with elevated permissions handles the promotion to production tables.

---

## Decision

Use **staging tables enforced by Postgres role-based permissions**. The database role `oceansx_ops` — used exclusively by the Operations Swarm worker process — has SELECT access on all production tables and INSERT/UPDATE access only on `staging_*` tables. Promotion from staging to production tables requires the `oceansx_promote` role, which is invoked only through admin-approved flows triggered by human action in the admin dashboard.

The staging tables that matter:
- `staging_opensanctions_ingest` — landing zone for processed OpenSanctions data before it is promoted to `vessel`, `organization`, `sanctions_listing`, and related tables.
- `staging_sanctions_match` — holding area for non-IMO-exact sanctions matches before human review.

The `agent_review_queue` table provides the human-readable queue: each pending item shows the agent that produced it, the proposed change, the confidence, and the full context needed for a human to make an approval decision.

---

## Alternatives Considered

1. **Application-level validation only** — Agent code validates its own output before writing to production tables. Rejected because application-level checks can contain bugs, can be bypassed by future code changes, and require the agent process to have production write permissions "in case" its output passes validation. The check and the permission exist in the same layer — a bug in either allows bad data through.

2. **Separate database for agent output** — Complete isolation; agents cannot touch the production database at all. Rejected because a full data synchronization layer between two Postgres instances is significant operational complexity — connection pooling, schema synchronization, cross-database foreign key management. Postgres role permissions within a single database provide equivalent isolation with a fraction of the complexity.

3. **Single shared database with no role separation** — Agent process has full read/write access; output is validated in code. Rejected outright. This is the architecture that the staging/role model is specifically designed to prevent. Any bug in the agent code or unexpected behavior in the AI model could corrupt production data.

---

## Consequences

- **Enables:** A hard enforcement boundary for agent output that cannot be bypassed by code bugs in the agent layer; a clear audit trail of everything an agent has produced, approved, or rejected; the ability to inspect agent output before it affects the public interface; suppression of rejected proposals for 30 days.
- **Precludes:** Any Operations Swarm agent from writing directly to production tables. This is a permanent constraint enforced at the database level, not a convention.
- **Costs:** Staging tables add schema complexity. The promotion flow (`services/promotion.py`, the `oceansx_promote` role, admin queue endpoints) must be maintained. Every category of agent-produced data needs a corresponding staging table and a defined promotion path.
- **Reversibility:** 4 (hard). The role model, staging tables, and promotion flow are woven into the database schema, the agent architecture, and the admin dashboard. Collapsing this boundary would require restructuring all four layers.

---

## Plain-English Summary

The Operations Swarm agents — the AI processes that run automatically on the server — produce data that should eventually appear in the live compliance dashboard. But "should" requires a human to confirm it first. The mechanism that enforces this is built into the database itself: the agent process has a database account (`oceansx_ops`) that can only write to temporary staging tables. It literally cannot write to the production tables that the public interface reads from, because the database won't allow it.

When an agent finishes its work, the results sit in a staging table and appear in the admin review queue. A human opens the queue, reviews the proposed changes with full context, and clicks Approve or Reject. Only Approve causes the data to move from the staging table to production — through a separate, elevated database role that the agent process cannot invoke. This is not a convention that developers need to remember; it is enforced by the database engine itself. No code change, no configuration override, and no misbehaving agent can bypass it.
