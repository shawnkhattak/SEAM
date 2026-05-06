# ADR 0003: Two-Swarm Architecture

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

OceansX V2 uses AI assistance in two fundamentally different contexts:

1. **Development assistance.** Writing code, reviewing security, drafting database migrations, maintaining documentation. This happens on the developer's laptop, inside the Claude Code environment, and produces files and commits. It is not automated — each task is initiated by the developer.

2. **Runtime data enrichment.** Processing daily sanctions downloads, extracting entity mentions from news articles, summarizing news on demand, computing risk scores. This happens on the production server, on a schedule or in response to events, without developer intervention.

Treating these two use cases as a single "AI layer" would create architectural problems. Runtime agents need different tools, different database permissions, different cost management, and different safety boundaries than development agents. A development agent needs to write code files; a runtime agent must never touch code files. A runtime agent needs read access to the production database; a development agent has no business accessing production data.

---

## Decision

Implement a **two-swarm architecture**:

**Build Swarm** — developer-side AI team implemented as nine Claude Code subagent files in `.claude/agents/`. Each file defines a role (Architect, Database Engineer, Backend Engineer, Frontend Engineer, Agent Engineer, Security Reviewer, Code Reviewer, Test Engineer, Documentation Maintainer), a restricted tool set, an explicit checklist, and a list of forbidden actions. These agents run on the developer's machine inside Claude Code. They assist with writing, reviewing, and documenting code. They do not run autonomously.

**Operations Swarm** — runtime AI team implemented as a standalone Python process with its own database role (`oceansx_ops`). Four agents run on the production server: OpenSanctions Watcher (daily), Entity Extractor (hourly), News Summarizer (on demand), and Risk Scorer (hourly, no LLM). These agents operate autonomously on a schedule, but are constrained to write only to staging tables — temporary holding areas that require human approval before data is promoted to the production interface.

The staging boundary is the critical safety mechanism: no Operations Swarm agent can corrupt production data because Postgres role permissions physically prevent it.

---

## Alternatives Considered

1. **Ad-hoc AI prompts for both development and runtime** — No structured agent files, just "ask Claude" as needed for development; no runtime automation. Rejected because ad-hoc prompts produce inconsistent results, have no safety boundaries, leave no audit trail, and cannot run autonomously on a schedule. V2's compliance features require continuous data enrichment — sanctions data must be refreshed daily, entity extraction must run hourly. Manual prompting cannot fulfill this.

2. **Single AI system covering both contexts** — One agent architecture with broad permissions covering both development help and runtime enrichment. Rejected because mixing development permissions (write code files, read the whole codebase) with runtime permissions (access production database, make external API calls) in a single agent creates an enormous blast radius if the agent behaves unexpectedly. The two contexts have incompatible safety requirements.

3. **Operations Swarm in a separate database** — Completely isolated database for the Operations Swarm, with no access to the main application database. Rejected because it would require maintaining a full data synchronization layer between databases, doubling storage and complexity. Postgres role-level permissions within a single database provide the necessary isolation with far less operational overhead.

---

## Consequences

- **Enables:** Clear separation of development-time and runtime AI concerns; granular permission control via Postgres roles; full observability of runtime agent activity via `agent_run`, `agent_action`, and `outbound_request_log` tables; ability to kill or pause individual agents without affecting the rest of the system; documented agent roles that can be explained to collaborators or reviewers.
- **Precludes:** Any runtime agent from writing directly to production tables (this is a constraint, not a limitation — it is the point). Operations Swarm agents cannot use Claude Code features; they use the Anthropic API directly.
- **Costs:** Nine agent `.md` files to maintain in `.claude/agents/`. Separate Python process management for the Operations Swarm worker. Per-agent cost tracking infrastructure (`agent_run` table, daily budget caps).
- **Reversibility:** 3 (moderate). The Build Swarm agent files are just markdown files — easy to change. The Operations Swarm architecture is baked into the service layout (`backend/app/agents/`) and the database role model. Collapsing the two swarms would require restructuring both.

---

## Plain-English Summary

OceansX V2 uses AI in two completely different ways that need to be kept separate. The first is development assistance — an AI team that helps write code, review security, draft database changes, and maintain documentation, all on the developer's computer and never running without human initiation. The second is a runtime automation team that runs continuously on the production server, downloading sanctions data, reading news articles, and computing risk scores while the developer is not actively working.

These two roles have incompatible requirements. A development assistant needs to read and write code files. A runtime automation agent must never touch code — it only reads vessel and news data from the database. Keeping them architecturally separate, with the runtime agents restricted to a dedicated database user account that cannot touch production data directly, is what makes the system safe to run autonomously. The human review step — approving what the runtime agents produce before it appears on screen — is not bolted on as an afterthought. It is enforced by the database itself.
