# Phase 0: Foundation

---

## TL;DR

Week one built the plumbing every subsequent phase depends on: a Postgres database with all three extensions running in Docker, a migration framework that is the only approved way to change the database structure, a FastAPI backend with working health endpoints, a React frontend skeleton with the timezone and attribution components already in place, nine AI development agent role files, and a CI pipeline that catches problems before they reach main. Nothing user-facing exists yet — this phase is all foundation.

---

## Goal

Phase 0 has one job: establish a foundation solid enough that no subsequent phase needs to revisit it. That means the database stack is correct before any tables are created. The migration framework is in place before any schema is written. The CI (continuous integration — the automated test and check pipeline that runs on every code push) is configured before any real logic is committed. The agent role files are in place before development begins in earnest.

The temptation at this stage is to start building features — the map, the vessel list, the detail panel. Resisting that temptation is the point. A shaky foundation creates problems that compound as the project grows; fixing them later costs ten times what they cost now.

---

## What Was Built

**Git repository and Docker Compose stack.** A fresh repository (`oceans-x-visualizer-v2`) with a Docker Compose configuration that starts Postgres 16 with TimescaleDB (a time-series extension for Postgres — compresses historical data automatically) and PostGIS (the geographic extension — answers questions like "which terminal is this ship in?"). The specific Docker image used is `timescale/timescaledb-ha`, the official Timescale image that ships all three components pre-installed. Four database roles were created at initialization: `oceansx_app` (the main API process), `oceansx_ops` (the Operations Swarm worker), `oceansx_promote` (the human-approved promotion role), and `oceansx_readonly` (for analytics and dashboards).

**Alembic migration framework.** Alembic (a database migration tool for Python — keeps a version history of every structural database change) was initialized and configured. The first migration creates the TimescaleDB and PostGIS extensions and applies the role permission grants. No application tables exist yet — this migration is purely infrastructure. The rule is strict: no application code may call `create_all()` to create tables; every schema change goes through an Alembic migration file.

**FastAPI backend skeleton.** A FastAPI application with two working endpoints: `/api/health` (returns database connection status and uptime) and `/api/about` (returns data source attribution information). Middleware, rate limiting (via slowapi — a Python rate limiting library), and structured error handling are configured. No business logic yet.

**React + Vite + Tailwind frontend skeleton.** A React application built with Vite (a fast frontend build tool) and styled with Tailwind CSS (a utility-first CSS framework — styles are applied by adding class names to HTML elements rather than writing separate CSS files). Two components are fully implemented:

- `TimeZoneSelector` — the footer dropdown that lets users switch between America/Chicago, UTC, Asia/Singapore, and browser-detected time. Built with Luxon (a JavaScript date/time library with full DST — Daylight Saving Time — awareness). The selection persists for the session.
- `DataSourceFooter` — the attribution bar that appears on every page, linking to OpenSanctions, Open-Meteo, and MPA Singapore. License compliance requires this attribution to be present.

**Nine Build Swarm agent role files.** All nine `.claude/agents/` markdown files were created and populated: Architect, Database Engineer, Backend Engineer, Frontend Engineer, Agent Engineer, Security Reviewer, Code Reviewer, Test Engineer, and Documentation Maintainer. Each file contains the agent's system prompt, allowed file globs, forbidden actions, mandatory review checklist, and output format. These files are the mechanism by which Claude Code routes development tasks to the appropriate specialized role.

**Documentation structure.** The `docs/journey/`, `docs/adr/`, and `docs/glossary.md` structure was initialized. Phase 0 documentation (this file and its siblings) is the first output of the Documentation Maintainer role.

**GitHub Actions CI pipeline.** A CI workflow that runs on every push to main and every pull request. The pipeline runs: `pytest` (Python backend tests), `vitest` (React frontend tests), `alembic check` (verifies that no pending database migrations exist — catches the case where schema changes were made without an Alembic file), `pip-audit` (checks Python dependencies for known security vulnerabilities), and `npm audit` (same for JavaScript dependencies). PRs that fail any check are blocked from merging.

---

## Decisions Made

Phase 0 implements the first several locked decisions from the architecture plan:

- **Postgres over SQLite (ADR-0001):** The Docker Compose stack and the four database roles are the direct implementation.
- **Alembic over create_all() (implied by ADR-0001):** The first Alembic migration and the rule against `create_all()` in application code.
- **America/Chicago default display timezone (ADR-0011):** The `TimeZoneSelector` component defaults to `America/Chicago` and uses Luxon for DST-aware calculations.
- **15-minute polling cadence (ADR-0004):** The scheduler is configured but has no jobs yet; the cadence will be set in Phase 1.
- **Two-swarm architecture (ADR-0003):** The four database roles implement the permission model. The `.claude/agents/` files implement the Build Swarm side. The Operations Swarm Python process structure is scaffolded but not yet running.
- **Claude Code subagents for the Build Swarm (ADR-0012):** The nine agent files in `.claude/agents/` are the implementation.

---

## What Surprised Me

**The Docker image choice matters immediately.** There are several ways to run Postgres + TimescaleDB + PostGIS in Docker. The `timescale/timescaledb-ha` image is the one that ships all three components tested and verified to work together. Starting with a base Postgres image and manually layering extensions produced version mismatch errors. Using the official Timescale image eliminated the entire class of "extension X doesn't work with version Y" problems.

**Alembic's initial configuration has meaningful choices.** The decision to use `autogenerate = True` in Alembic's configuration (which lets Alembic detect schema changes by comparing the ORM model definitions against the live database) versus purely hand-written migrations required a considered decision up front. For this project, autogenerate is used as a starting point that is always reviewed and edited before committing — not taken as the final migration script.

**The CI check order matters.** Running `alembic check` before deploying catches a specific, common mistake: a developer adds a new SQLAlchemy model class in Python (which defines a table) without writing the corresponding Alembic migration. Without the check, the table exists in code but not in the database, causing errors that only surface at runtime. With the check, the CI pipeline fails immediately.

**Four database roles from day one is not over-engineering.** It would have been simpler to start with one database user and add roles later. But adding roles later means every existing connection, every ORM session, and every migration script would need to be updated to use the new roles. Starting with four roles on day one — even though only one of them is in use yet — means the permission model is correct from the first line of production code.

---

## What I Learned

**Infrastructure decisions made under pressure get made wrong.** Phase 0 is the phase where infrastructure decisions are cheap to make and expensive to change. The Docker Compose configuration, the Alembic setup, the database role model, and the CI pipeline are all things that would be painful to change in Phase 4 when there are already four phases of schema and code built on top of them. Spending a full week on Phase 0 before writing any business logic is not slow — it is the fastest path to a stable Phase 4.

**CI is a commitment, not a checkbox.** Configuring GitHub Actions to run `pip-audit` and `npm audit` as blocking checks means every future dependency addition will be screened for known vulnerabilities. This is easy to configure in week one; retrofitting it in week seven when there are three hundred dependencies would require investigating and resolving every existing finding. The best time to add mandatory security checks is before there is anything to check.

**Tailwind makes the frontend skeleton usable immediately.** Starting with Tailwind rather than plain CSS meant the `TimeZoneSelector` and `DataSourceFooter` components look professional from the first render, without writing a single CSS rule. This is not a cosmetic point — it means the frontend demonstrates clearly and immediately, which matters for a portfolio project.

---

## Connection to the Whole

Phase 0 is the prerequisite for everything. Phase 1 (live tracking parity) adds the vessel and position tables via Alembic migrations, adds the MPA client and the position polling job, and adds the live map — all of which build directly on the database stack, the migration framework, the FastAPI skeleton, and the React skeleton established here.

The Build Swarm agent files created in Phase 0 will be in use for the remaining eight phases. The CI pipeline will run on every commit for the remaining eight weeks. The `TimeZoneSelector` component built here will be exercised in Phase 1 when real timestamps begin flowing through the system. The `DataSourceFooter` will gain additional attribution entries as each new data source is integrated in Phases 3, 4, and 5.

Phase 0 does not produce anything a user can see. It produces everything a developer needs to build everything a user can see.
