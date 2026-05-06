# ADR 0001: Postgres Over SQLite

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

OceansX V1 used SQLite as its database — a lightweight, file-based database that lives entirely in a single file on disk. SQLite is an excellent choice for small, single-process applications, and it served V1 well for a basic vessel tracker with one reader (the FastAPI server).

V2 changes the picture in four concrete ways:

1. **Multiple concurrent writers.** V2 has three processes writing to the database simultaneously: the FastAPI application server, the APScheduler (the job runner that polls MPA every 15 minutes), and the Operations Swarm worker (the autonomous AI agent process). SQLite's file-level locking means concurrent writes from separate processes either block each other or fail. This is a structural mismatch.

2. **Geospatial queries.** Determining which terminal a vessel is currently in — a core operation in V2 for anchorage dwell calculations and congestion scoring — requires checking whether a lat/lon coordinate falls inside a geographic polygon. SQLite has no native support for this. It would require loading geometry libraries into Python and executing the geometry logic in application code for every vessel on every position poll.

3. **Time-series compression and partitioning.** OceansX V2 stores vessel positions every 15 minutes, weather readings every hour, and risk scores every hour. After a year, the position archive alone would contain tens of millions of rows. SQLite has no time-series compression; query performance degrades as tables grow.

4. **JSON path indexing.** OpenSanctions data is stored as raw JSONB (binary JSON) payloads, with relational projections built on top. Efficient indexing of fields inside JSON documents requires a database with JSONB support and JSON path indexing.

---

## Decision

Use **Postgres 16 + TimescaleDB (time-series extension) + PostGIS (geospatial extension)**, deployed via the official `timescale/timescaledb-ha` Docker image, which ships all three pre-installed. Manage all schema changes through Alembic (database migration tool). Remove all uses of `SQLModel.metadata.create_all()` from the codebase.

---

## Alternatives Considered

1. **Keep SQLite** — Simplest deployment (one file, no Docker required). Rejected because it cannot handle concurrent writers from three separate processes, has no native geospatial or time-series support, and does not support JSONB indexing. The V2 feature set simply cannot be built reliably on SQLite.

2. **Managed Postgres (DigitalOcean Managed Database, AWS RDS)** — Eliminates database administration burden. Rejected because the project runs on a single VPS to minimize cost (~$51/month total). A managed database service would add $15–50/month for the smallest tier, conflict with the single-VPS architecture, and add network latency between the app and the database. `pg_dump` backups to Backblaze B2 provide sufficient durability for a non-commercial portfolio project.

3. **MySQL / MariaDB** — Widely used, good concurrent write support. Rejected because MySQL has no TimescaleDB equivalent for time-series compression, and its geospatial support (via MySQL Spatial) lacks the maturity, documentation, and community tooling of PostGIS. The combination of time-series and geospatial requirements makes Postgres the clear choice.

---

## Consequences

- **Enables:** Concurrent writers from three separate processes; geospatial terminal membership queries using `ST_Within`; automatic time-series partitioning and 90% compression on old chunks via TimescaleDB hypertables; JSONB path indexing for OpenSanctions entity payloads; simple encrypted backup via `pg_dump`.
- **Precludes:** SQLite's zero-install simplicity. Running this project locally now requires Docker (or a local Postgres installation). This is an acceptable trade-off for a project at this scale.
- **Costs:** Docker Compose must be running for local development. The `timescale/timescaledb-ha` image is ~1 GB. The Database Engineer Build Swarm agent owns all Alembic migrations — no schema changes outside that workflow.
- **Reversibility:** 5 (very hard). Every table schema, every index, and every domain design assumes Postgres-specific features (JSONB, TimescaleDB hypertables, PostGIS geometry). Migrating back to SQLite or forward to a different database system would require rewriting the majority of the backend.

---

## Plain-English Summary

V1 used a simple file-based database that worked fine when only one thing was reading and writing at a time. V2 has three separate processes that all need to read and write the database simultaneously — the web server, the job scheduler, and the AI agent worker. A file-based database cannot handle this reliably. It also cannot answer geographic questions like "which terminal is this ship currently in?" or efficiently store and compress the millions of timestamped position records V2 will accumulate.

We switched to Postgres — the gold-standard open-source database used by companies from startups to Fortune 500 — and added two specialized extensions: TimescaleDB for time-series compression (which reduces old data storage by about 90%), and PostGIS for geographic queries. The whole stack runs in a Docker container using an official image that ships all three pre-installed. This is a one-way door: the entire system is designed around these capabilities. The complexity cost is real — you need Docker running locally — but it's the right foundation for what V2 actually does.
