# OceansX V2 Glossary

Plain-English definitions for every technical term used in this project.
Written for non-technical readers — executives, recruiters, and curious observers.

If you encounter a term here while reading a phase journal or ADR and still have questions, the "Related terms" field points to other entries that add context.

---

## IMO Number

**Category:** Maritime

An IMO number is a permanent seven-digit identifier assigned to a ship by the International Maritime Organization, the United Nations body that governs global shipping. Once assigned, this number never changes — it stays with the vessel for its entire life, even if the ship is renamed, re-flagged, or sold to a new owner.

**Why it matters in this project.** IMO numbers are the gold standard for vessel identity. When we match a vessel against a sanctions list, we use the IMO number as the primary key. A name match alone is unreliable (many ships share similar names; owners deliberately rename vessels to evade detection), but a matching IMO number is essentially definitive. This is why OceansX V2 only auto-confirms a sanctions match when the IMO numbers agree exactly — any other approach introduces unacceptable risk of false positives. See ADR-0005 for the full decision.

**Related terms:** Sanctions Match, Shadow Fleet, Port State Control

---

## Shadow Fleet

**Category:** Maritime, Compliance

The "shadow fleet" (also called the "dark fleet") refers to a loosely defined collection of older tankers — mostly aging crude oil carriers — used to move Russian oil in circumvention of Western sanctions imposed after Russia's 2022 invasion of Ukraine. These vessels typically operate under flags of convenience (registration in small nations with minimal oversight), change ownership frequently through anonymous shell companies, and disable or manipulate their AIS tracking signals (the radio system ships use to broadcast their position).

OpenSanctions, the data provider we use, tags these vessels with the category label `mare.shadow`. Importantly, a vessel can be shadow-fleet tagged without being formally sanctioned by any government authority — the tag reflects the vessel's operational pattern, not a legal designation.

**Why it matters in this project.** Shadow fleet visibility is one of the four headline features of OceansX V2. Singapore waters sit at the junction of two of the world's busiest shipping lanes, and shadow fleet tankers transiting or anchoring here represent a compliance risk for port operators and financial institutions. We give shadow fleet vessels a dedicated map filter, a dedicated drawer tab, and visual badge overlays so they are immediately visible — even when the Sanctions tab is empty. See ADR-0006 for the display decision.

**Related terms:** IMO Number, Sanctions Match, Port State Control, OpenSanctions

---

## OpenSanctions

**Category:** Compliance

OpenSanctions is a non-profit, open-source project that aggregates sanctions lists and watchlists from governments and intergovernmental organizations worldwide into a single, standardized, freely downloadable dataset. It covers major programs including OFAC (the U.S. Treasury's Office of Foreign Assets Control), the UK Sanctions List (formerly OFSI), the European Union Council list, United Nations Security Council resolutions, and all four major Port State Control memoranda (Tokyo MoU, Paris MoU, Black Sea MoU, and Abuja MoU).

The data is structured using FollowTheMoney (FtM), a schema designed to represent entities — vessels, people, companies, properties — and the relationships between them.

**Why it matters in this project.** Using OpenSanctions eliminates the need to write and maintain separate parsers for eight or more government data sources, each of which publishes data in a different format and updates on a different schedule. We download a daily bulk snapshot from OpenSanctions and run our own local matching — we do not call their API at runtime. The license is free for non-commercial use (CC-BY 4.0). See ADR-0002 for the build-vs-buy decision.

**Related terms:** Sanctions Match, FtM / FollowTheMoney, Tokyo MoU, Paris MoU, Shadow Fleet

---

## Tokyo MoU

**Category:** Compliance

The Tokyo Memorandum of Understanding on Port State Control (Tokyo MoU) is a regional agreement among maritime authorities across the Asia-Pacific region. It coordinates inspections of foreign vessels calling at member ports to verify compliance with international safety, labor, and environmental standards. When inspectors find serious deficiencies, they can detain the vessel until the problems are fixed.

"Port State Control" refers to the right of a country to inspect foreign vessels in its ports — the "port state" is the country where the ship is visiting, as distinct from the "flag state" where the ship is registered.

**Why it matters in this project.** Singapore is a member of the Tokyo MoU. A vessel with a recent Tokyo MoU detention carries a documented safety or compliance deficiency, which contributes directly to its risk score in OceansX V2. We ingest Tokyo MoU inspection and detention records daily via OpenSanctions.

**Related terms:** Paris MoU, Port State Control, Risk Score, IMO Number

---

## Paris MoU

**Category:** Compliance

The Paris Memorandum of Understanding on Port State Control is the European equivalent of the Tokyo MoU — a cooperative inspection regime covering vessels calling at ports in Europe and the North Atlantic. Its "black list" / "grey list" / "white list" flag state classification (based on detention rates over a rolling three-year window) is widely cited as an industry benchmark for flag state performance.

**Why it matters in this project.** Many Singapore-bound vessels have European port call histories. Paris MoU detention records feed into the flag performance component of each vessel's risk score. We ingest Paris MoU data from OpenSanctions alongside the Tokyo MoU dataset. See ADR-0002 for dataset scope decisions.

**Related terms:** Tokyo MoU, Port State Control, Risk Score, OpenSanctions

---

## Sanctions Match

**Category:** Compliance

A sanctions match is a record linking a vessel in our database to an entity on a sanctions list. In OceansX V2, a match goes through a defined lifecycle: it starts as `pending`, moves to `auto_confirmed` (if the IMO numbers match exactly), or routes to the admin review queue for human judgment (if the match was made by name similarity or organizational connection rather than IMO number).

The match record stores the method used (IMO exact, name-and-flag fuzzy, organizational link), a confidence score, the reviewer's identity and timestamp, and the full audit history.

**Why it matters in this project.** Sanctions matches are the highest-stakes output of the system. A false positive — flagging a legitimate vessel as sanctioned — could have serious reputational consequences. A false negative — missing a genuinely sanctioned vessel — defeats the system's purpose. The IMO-exact-only auto-confirm rule (ADR-0005) is the primary safety mechanism. All other matches require explicit human approval before they appear in the production interface.

**Related terms:** IMO Number, OpenSanctions, Risk Score, FtM / FollowTheMoney

---

## TimescaleDB

**Category:** Database

TimescaleDB is an extension for Postgres (the database system we use) that adds specialized support for time-series data — data that is indexed by time and appended continuously. It automatically partitions large time-series tables into smaller chunks (by day or by week), compresses old chunks to a fraction of their original size, and maintains fast query performance even as the table grows to millions of rows.

**Why it matters in this project.** OceansX V2 collects vessel positions every 15 minutes, weather readings every hour, and risk scores every hour. Over a year, these tables would contain tens of millions of rows. TimescaleDB keeps queries fast (finding the last known position of a vessel) and keeps storage costs low (compressing data older than 7 days by roughly 90%). See ADR-0001 for the full database technology decision.

**Related terms:** Postgres, PostGIS, Hypertable, Alembic

---

## PostGIS

**Category:** Database

PostGIS is an extension for Postgres that adds geographic and spatial data types, functions, and indexes. It allows a database to answer questions like "which terminal polygon does this latitude/longitude coordinate fall inside?" — the kind of question that would require complex trigonometry in a standard database but becomes a single line of SQL with PostGIS.

**Why it matters in this project.** Singapore's port is divided into distinct terminals (Tuas, Pasir Panjang, Jurong, Sembawang, and others). OceansX V2 uses PostGIS to determine which terminal a vessel is in at any given moment, simply by checking whether the vessel's position falls within the terminal's geographic polygon. This feeds the anchorage dwell calculation, which in turn feeds the congestion component of the risk score. See ADR-0001.

**Related terms:** TimescaleDB, Postgres, Hypertable

---

## Hypertable

**Category:** Database

A hypertable is the TimescaleDB term for a time-series table that has been enabled for automatic partitioning and compression. From the application's perspective, it looks and behaves like a regular Postgres table — you insert and query rows the same way. Behind the scenes, TimescaleDB automatically splits the data into time-bounded chunks and manages them independently.

**Why it matters in this project.** Four tables in OceansX V2 are hypertables: `position_live` (vessel positions, 14-day retention), `position_archive` (365-day retention), `weather_observation` (365-day retention), and `risk_score` (365-day retention). The automatic compression on chunks older than 7 days is what keeps the database manageable without manual maintenance.

**Related terms:** TimescaleDB, PostGIS, Alembic

---

## Alembic

**Category:** Database

Alembic is a database migration tool for Python. A migration is a versioned, reversible script that changes the structure of a database — adding a table, adding a column, creating an index. Alembic keeps a history of every migration that has been applied, so the database schema can always be evolved safely without losing data or requiring a manual rebuild.

**Why it matters in this project.** OceansX V2 uses Alembic as the only approved way to make structural changes to the database. The alternative — using SQLAlchemy's `create_all()` command, which just creates whatever tables the code defines without tracking history — was explicitly prohibited. Migration-managed databases are reproducible, auditable, and deployable to new environments consistently. See ADR-0001 for context. Every phase of the project adds new Alembic migration files as the schema evolves.

**Related terms:** TimescaleDB, Postgres, PostGIS

---

## SCD2 / Slowly Changing Dimension Type 2

**Category:** Database

SCD2 (Slowly Changing Dimension Type 2) is a standard data warehousing technique for tracking the history of a value that changes over time. Instead of overwriting the old value when something changes, a new row is added with a `valid_from` timestamp, and the old row's `valid_to` timestamp is filled in. The current state is always the row where `valid_to` is null.

**Why it matters in this project.** Vessels in Singapore waters change their names, flags, owners, and operators — sometimes deliberately to obscure identity. OceansX V2 uses SCD2 to preserve the complete history of these changes. When a match is found against a vessel's name that it carried six months ago, that history is available. When a sanctions listing is delisted, the history is preserved with a `valid_to` date rather than deleted. The compliance picture is always complete, not just current.

**Related terms:** Sanctions Match, IMO Number, Alembic

---

## SSE / Server-Sent Events

**Category:** Backend

Server-Sent Events (SSE) is a web standard that allows a server to push updates to a browser in real time over a persistent HTTP connection. Unlike the older approach of having the browser repeatedly ask "do you have new data yet?" (polling), SSE keeps a connection open and the server sends a message only when there is actually something new to report.

**Why it matters in this project.** OceansX V2 polls the MPA API every 15 minutes for vessel positions. Without SSE, the frontend would have to guess when to check for new data — polling every minute wastes network and server resources; polling every 15 minutes might show stale data for up to 14 minutes. With SSE, the backend sends a `positions_updated` signal immediately after each successful position poll, and the frontend re-fetches only at that moment. The user sees fresh data within seconds of the backend poll completing. See ADR-0008 for the full decision.

**Related terms:** Operations Swarm, Build Swarm

---

## Operations Swarm

**Category:** Backend

The Operations Swarm is OceansX V2's runtime AI team — a set of four automated agents that run on the server (not on the developer's computer) and perform ongoing data enrichment tasks: downloading and processing daily sanctions data, extracting entity mentions from news articles, summarizing news on demand, and computing risk scores. These agents run on a schedule (daily, hourly, or triggered by events) and write their output to staging tables (temporary holding areas) rather than directly to the live database, ensuring that any AI-generated data passes through a human review step before appearing in the public interface.

The four agents are: OpenSanctions Watcher, Entity Extractor, News Summarizer, and Risk Scorer.

**Why it matters in this project.** The Operations Swarm is what turns OceansX V2 from a position tracker into a compliance intelligence platform. It is also the component with the most architectural care around safety boundaries — agents cannot write to production tables directly, cannot make outbound HTTP calls to unapproved domains, and are subject to daily cost caps. See ADR-0003 and ADR-0007 for the boundary decisions.

**Related terms:** Build Swarm, SSE / Server-Sent Events, Staging Tables, HMAC

---

## Build Swarm

**Category:** Backend

The Build Swarm is OceansX V2's developer-side AI team — nine specialized Claude Code subagents (software assistants), each with a defined role, a restricted set of tools, and an explicit checklist. The roles are: Architect, Database Engineer, Backend Engineer, Frontend Engineer, Agent Engineer, Security Reviewer, Code Reviewer, Test Engineer, and Documentation Maintainer. Claude Code automatically routes tasks to the appropriate agent based on its description; agents can also be invoked by name.

Unlike the Operations Swarm, the Build Swarm does not run autonomously on the server. It assists with development on the developer's local machine, inside the Claude Code environment.

**Why it matters in this project.** Structuring AI assistance as a team of specialists with explicit constraints is a deliberate architecture choice. A single general-purpose AI prompt for all tasks produces inconsistent results. Nine specialists with constrained scopes, mandatory checklists, and forbidden actions produce consistent, reviewable output. See ADR-0012 for the full rationale. The agent files live in `.claude/agents/` in the repository.

**Related terms:** Operations Swarm, SSE / Server-Sent Events

---

## FtM / FollowTheMoney

**Category:** Compliance

FollowTheMoney (FtM) is an open-source data schema developed by the Organized Crime and Corruption Reporting Project (OCCRP) for representing entities — people, companies, vessels, properties, legal cases — and the relationships between them. It was designed specifically for investigative journalism and financial intelligence use cases where entities have multiple names, identities overlap, and connections matter.

OpenSanctions publishes its data in FtM format. An FtM "entity" can represent a vessel, a company, a person, or a sanctions listing, and each entity carries a list of "referents" — other entity IDs that have been merged into it (because they turned out to be the same thing).

**Why it matters in this project.** OceansX V2 stores the raw FtM JSON payloads from OpenSanctions in a dedicated table (`opensanctions_entity_raw`) as the authoritative record, then projects the relevant fields into relational tables for querying. This means if OpenSanctions evolves its schema, we can re-project from the stored raw data without re-downloading everything. It also means the full richness of the FtM graph — ownership chains, organizational relationships, alias networks — is available for natural language search queries.

**Related terms:** OpenSanctions, Sanctions Match, SCD2

---

## HMAC

**Category:** Backend

HMAC (Hash-based Message Authentication Code) is a cryptographic technique for verifying that a message came from a trusted sender and has not been modified in transit. Both sender and recipient share a secret key. The sender computes a signature over the message content using the key and includes it in the request. The recipient recomputes the signature independently and rejects the request if the signatures do not match.

**Why it matters in this project.** OceansX V2 receives news articles via a webhook (an automatic HTTP call) from RSS.app. Anyone on the internet could send fake news articles to that endpoint if it were open. Each of the three RSS.app feeds has its own HMAC secret key. The backend rejects any webhook delivery whose signature does not match, preventing injection of fabricated news content into the system.

**Related terms:** Operations Swarm, Build Swarm

---

## Risk Score

**Category:** Compliance

The risk score in OceansX V2 is a composite indicator computed hourly for each vessel, made up of six components: sanctions score (is this vessel confirmed sanctioned?), shadow fleet score (is this vessel in the shadow fleet?), flag MoU score (how does this vessel's flag state perform on port state control inspections?), age score (how old is the vessel?), congestion score (is the vessel's current terminal congested?), and weather score (are current marine conditions severe?).

The components are stored as a vector (all six values, not collapsed into one number) so the UI can show each indicator separately with a clear label. For sorting and filtering, a composite is computed: if any compliance indicator (sanctions or shadow fleet) is non-zero, it overrides the others. Otherwise, the operational components are weighted (flag MoU: 40%, age: 30%, congestion: 20%, weather: 10%).

Risk bands: 0–25 Low, 26–50 Medium, 51–75 High, 76–100 Critical.

**Why it matters in this project.** Risk scoring is what turns raw data into actionable intelligence. Port agents and compliance officers cannot manually review every vessel in Singapore waters; the risk leaderboard and high-risk map filter surface the vessels most deserving attention. Every risk display in the UI carries a disclaimer: "Risk indicators are derived from public data sources and should not be relied upon for operational or commercial decisions."

**Related terms:** Sanctions Match, Shadow Fleet, Tokyo MoU, Paris MoU, Port State Control

---

## Port State Control

**Category:** Compliance

Port State Control (PSC) is the system by which the country where a foreign ship is visiting (the "port state") exercises its legal right to inspect that ship for compliance with international safety, crew welfare, and environmental standards — even though the ship is registered in another country (the "flag state"). If inspectors find serious deficiencies, they can detain the vessel until the problems are corrected.

The Tokyo MoU, Paris MoU, Black Sea MoU, and Abuja MoU are the four regional cooperative frameworks that coordinate PSC inspections in their respective geographic areas.

**Why it matters in this project.** PSC inspection and detention records are one of the most reliable public indicators of vessel quality and compliance culture. A vessel repeatedly detained by Tokyo MoU inspectors has a documented history of deficiencies. OceansX V2 ingests detention records from all four MoU regions via OpenSanctions and factors them into both the flag MoU risk score component and the direct `mou_inspection` database domain.

**Related terms:** Tokyo MoU, Paris MoU, Risk Score, OpenSanctions, IMO Number

---

## Postgres

**Category:** Database

Postgres (formally PostgreSQL) is a free, open-source relational database system with over 35 years of active development. A relational database organizes data into tables with rows and columns, and allows tables to be linked to each other through shared keys — so a vessel record can be linked to its owner record, its position history, and its sanctions matches without duplicating data. Postgres is notable for its extensibility: it supports custom extensions like TimescaleDB (for time-series data) and PostGIS (for geographic data) that add specialized capabilities while remaining within the standard Postgres ecosystem.

**Why it matters in this project.** Postgres replaces the SQLite file-based database used in V1. The switch was required because V2 has three separate processes writing to the database simultaneously, needs geographic queries for terminal membership, needs time-series compression for position history, and needs JSONB (binary JSON) indexing for OpenSanctions entity payloads — none of which SQLite supports. See ADR-0001 for the full decision. The entire schema of OceansX V2 is managed through Postgres, versioned through Alembic migrations, and extended with two specialized plugins.

**Related terms:** TimescaleDB, PostGIS, Hypertable, Alembic, SCD2 / Slowly Changing Dimension Type 2

---

## Staging Tables

**Category:** Database

Staging tables are temporary holding tables — database tables prefixed with `staging_` — where data is written first before it is reviewed and promoted to the main production tables. The staging area acts as a buffer zone: data in a staging table is visible to administrators in the review queue but is not shown in the live public-facing interface. Promotion from staging to production requires an explicit human approval action and uses a separate, elevated database role (`oceansx_promote`) that the automated agent processes cannot invoke.

**Why it matters in this project.** The staging table boundary is the primary safety mechanism for the Operations Swarm (the autonomous AI agent process). The `oceansx_ops` database role — used by all Operations Swarm agents — can only write to `staging_*` tables, not to any production table. This is enforced by Postgres role permissions at the database level, not by application-level code that could contain bugs. No matter what an agent does, it cannot corrupt production data. See ADR-0007 for the full decision.

**Related terms:** Operations Swarm, Postgres, Alembic, Sanctions Match

---

## SEAM

**Category:** Frontend, Product

SEAM stands for Singapore Entity Analytics for Maritime. It is the current product identity for the OceansX V2 frontend. The name reflects the app's focus: connecting live maritime entities, compliance data, risk scores, news, and operational context into one dashboard for Singapore waters.

**Why it matters in this project.** SEAM is now the primary UI shell for both the public map dashboard and the admin dashboard. The standalone SEAM dashboard template provided the visual direction, but the production app keeps the existing React components and live API-backed data flows. See ADR-0030 for the full decision.

**Related terms:** React, Admin Dashboard, Risk Score, Sanctions Match

---

## Admin Dashboard

**Category:** Frontend, Operations

The admin dashboard is the internal control surface at `/admin`. It provides operational tools that should not be exposed as normal user-facing controls: force actions for data jobs, data source health, dependency audit history, sanctions review queue, database explorer, and aggregate statistics.

**Why it matters in this project.** The admin dashboard is how a human operator reviews uncertain sanctions matches, triggers ingestion jobs, inspects database tables, and checks whether upstream data sources are healthy. It uses the same SEAM glass interface as the main map, but its API calls require an `X-Admin-Token` header. See ADR-0027 and ADR-0030.

**Related terms:** Sanctions Match, Staging Tables, SEAM, Audit Log

---

## Project Guide

**Category:** Documentation

The project guide is the practical developer-facing overview at `docs/PROJECT_GUIDE.md`. It explains what the app does, how to run it, where major code lives, how data flows through the system, what the admin dashboard does, and how to troubleshoot common problems.

**Why it matters in this project.** The architecture plan, journey documents, ADRs, and glossary are intentionally detailed. The project guide is the simpler starting point for day-to-day work. It keeps onboarding fast without replacing the deeper documentation. See ADR-0031.

**Related terms:** ADR, Journey, Glossary

---

## Development Control Panel

**Category:** Developer Experience

The development control panel is `dev.py`, a terminal user interface for local development. It can start and stop the database, backend, and frontend, run Alembic migrations, view service logs, and open the app in a browser. On macOS, `start-dev.command` launches it by double-clicking.

**Why it matters in this project.** OceansX V2 has three local services that must be connected: Postgres, FastAPI, and Vite. The control panel reduces startup friction and makes it easier to see which part of the stack is down when something fails.

**Related terms:** FastAPI, Vite, Alembic, Postgres

---

## Audit Log

**Category:** Backend, Operations

The audit log is an append-only database record of important administrative and operational events. "Append-only" means entries are added but not edited or deleted. Events include force actions, review decisions, dependency audit warnings, and other admin-visible system activity.

**Why it matters in this project.** Compliance tools need traceability. If a sanctions review item is confirmed, rejected, or re-scored, the system should retain a record of who or what performed that action and when. The audit log supports the admin dashboard's Recent Activity view and makes operational behavior easier to investigate.

**Related terms:** Admin Dashboard, Sanctions Match, Dependency Audit

---

## Dependency Audit

**Category:** Security, Operations

A dependency audit checks the third-party libraries used by the project for known security vulnerabilities. In this project, the backend scheduler runs `pip-audit` and stores the result in `dependency_audit_log`.

**Why it matters in this project.** OceansX V2 uses external packages for web serving, database access, mapping, charts, and API calls. Vulnerabilities in those packages can become application risks. The dependency audit gives the admin dashboard a simple view of recent audit runs and warning counts.

**Related terms:** Admin Dashboard, Audit Log, Deterministic Security
