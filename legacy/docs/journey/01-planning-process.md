# Phase 1: The Planning Process

---

## TL;DR

Before writing a single line of code, five rounds of structured AI conversation produced a 49-decision, 12-domain, 9-phase architecture plan that is now locked and ready for implementation. The plan is the artifact. Starting with it rather than without it is the point.

---

## Goal

The goal of this phase was not to plan in the abstract — it was to produce a specific, locked architecture document that answers every significant question before implementation begins: which database, which data sources, which matching rules for sanctions, how autonomous agents are constrained, how the frontend updates without polling, what the cost ceiling is, and what each of the nine implementation phases delivers.

A plan at this level of detail is not normal for a solo portfolio project. It is normal for a system where getting the architecture wrong early — choosing the wrong database, designing the wrong agent boundary, picking the wrong sanctions matching rule — would require rework that is expensive and disruptive across multiple phases.

---

## What Was Built

The output of this phase is the architecture document: `/oceansx-v2-architecture.md`. It contains:

- **49 locked decisions** — each one specific enough that a developer (or an AI agent) can implement against it without needing to make a judgment call. Not "use a good database" but "Postgres 16 + TimescaleDB + PostGIS via `timescale/timescaledb-ha` Docker image."
- **12 database domains** — the full logical data model across vessel history, organizations, ports, positions, sanctions, MoU inspections, news, risk scoring, agent observability, system/cache, attribution, and project journal.
- **9 implementation phases** — each phase bounded by what it delivers, in an order that builds on prior phases without requiring future phases to work.
- **4 runtime AI agents** with defined cadences, models, permission scopes, and cost ceilings.
- **9 Build Swarm roles** with defined tool sets, mandatory checklists, and forbidden actions.
- **A complete cost projection** — $51/month total at full feature set, of which $33 is the AI API budget.
- **A documentation strategy** — including the journal structure you are reading now, the ADR format, and the glossary.

This document was produced across five structured conversation rounds, each building on the previous:

- **Round 1:** Core architecture, database design, V1-to-V2 migration posture, initial swarm design.
- **Round 2:** Data sources, OpenSanctions dataset selection, RSS.app configuration, news retention.
- **Round 3:** Security posture, admin dashboard design, backup strategy.
- **Round 4:** Polling cadence, SSE strategy, NL search design, Build Swarm role formalization.
- **Round 5:** Risk scoring formula, natural language search graph traversal, terminal polygon strategy.

---

## Decisions Made

Every locked decision in the architecture document is the output of this phase. The twelve ADRs (Architecture Decision Records — short documents capturing the reasoning for a significant choice) document the twelve most consequential ones in detail. See the [ADR index](../adr/README.md).

The decisions that required the most deliberation:

- **Sanctions auto-confirm rule (ADR-0005):** The tension between automation convenience and false-positive risk. Landing on IMO-exact-only as the threshold required working through what "confidence" actually means in a fuzzy matching context for compliance data.
- **Two-swarm architecture (ADR-0003):** Distinguishing between AI that assists development (Build Swarm) and AI that runs autonomously on the server (Operations Swarm) and designing the right permission boundary between them.
- **SSE vs. polling (ADR-0008):** Understanding why a 15-minute backend cadence and a 5-minute frontend polling interval produce a worse user experience than SSE push, and how to implement SSE correctly with React Query.

---

## What Surprised Me

The volume of decisions that would have been made implicitly — without conscious thought — if I had started coding directly. "Just start coding" is appealing because it feels like forward progress. But "start coding" without a locked answer to "which database?" means making that choice under time pressure, without a structured evaluation of the alternatives, and potentially building several phases of work on a foundation that later turns out to be wrong.

The other surprise was how much the planning conversation surfaced dependencies I had not considered. The SSE push strategy depends on the 15-minute polling decision. The tiered entity extraction (ADR-0009) cost estimate depends on the news volume, which depends on the RSS.app feed configuration, which was worked out in Round 2. The staging table boundary (ADR-0007) depends on the two-swarm architecture (ADR-0003), which depends on having clearly named the two distinct use cases. Each decision links to others.

---

## What I Learned

**Architecture documentation is not overhead — it is the deliverable for this phase.** A 49-decision locked plan is more valuable than 49 lines of uncommitted code. The code is easy to write once the decisions are made. The decisions are hard to recover from when they are wrong.

**Structured AI conversation requires you to know what you are deciding.** The planning conversation produced useful output because each round had a specific goal — design the agent boundary, spec the risk scoring formula, validate the cost model — not a general "help me build this." The more specific the question, the more specific (and useful) the answer.

**"Locked" means something.** A decision that can be quietly revisited under time pressure is not really a decision — it is a preference. The 49 locked decisions in the architecture document are locked because the consequence of changing them mid-build is documented in the corresponding ADR's Reversibility score. A Reversibility-5 decision (the database choice) is hard to change. That hardness is a feature, not a bug — it forces the decision to be made correctly before implementation, not corrected expensively after.

---

## Connection to the Whole

This phase produces the plan that all subsequent phases execute against. Phase 0 (foundation) implements the first three or four decisions: the repo, the Docker Compose stack, Alembic, the FastAPI skeleton, and the React skeleton. Each subsequent phase implements the next group of decisions. Without this phase, each implementation phase would need to make those decisions on the fly — which is how inconsistent, hard-to-maintain systems get built.

The architecture document also seeds the documentation structure: the ADR template, the glossary format, the phase journal template. The Documentation Maintainer Build Swarm agent is responsible for keeping these artifacts current as the project progresses.
