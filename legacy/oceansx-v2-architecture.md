# OceansX Visualizer V2 — Architecture Plan (Final Consolidated)

**Status:** Planning complete. Ready for Phase 0 implementation.
**Project posture:** Greenfield rewrite. V1 data not migrated.
**License posture:** Strictly non-commercial. All chosen data sources have free non-commercial terms.
**Positioning:** V2 is a maritime compliance and intelligence dashboard for Singapore waters, not a real-time tracker. Position polling is 15-minute cadence; the value proposition is sanctions/risk/news/intelligence, not live navigation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Target Topology](#2-target-topology)
3. [VPS Provisioning Guide](#3-vps-provisioning-guide)
4. [Data Sources and Attribution](#4-data-sources-and-attribution)
5. [Database Architecture](#5-database-architecture)
6. [Backend Service Layout](#6-backend-service-layout)
7. [Time Zone Strategy](#7-time-zone-strategy)
8. [Frontend Changes and Update Strategy](#8-frontend-changes-and-update-strategy)
9. [Build Swarm — Developer-Side AI Team](#9-build-swarm--developer-side-ai-team)
10. [Operations Swarm — Runtime AI Team](#10-operations-swarm--runtime-ai-team)
11. [Security Posture (Deterministic Only)](#11-security-posture-deterministic-only)
12. [Admin Dashboard V2](#12-admin-dashboard-v2)
13. [Project Journal and Documentation Strategy](#13-project-journal-and-documentation-strategy)
14. [Backup and Disaster Recovery](#14-backup-and-disaster-recovery)
15. [Cost Projection](#15-cost-projection)
16. [Migration / Project Bootstrap Plan](#16-migration--project-bootstrap-plan)
17. [Open Items Deferred to Follow-Up Sessions](#17-open-items-deferred-to-follow-up-sessions)
18. [Appendix A — Decisions Locked](#appendix-a--decisions-locked)

---

## 1. Executive Summary

V2 reframes OceansX Visualizer as a **maritime compliance and intelligence dashboard** for Singapore waters. The V1 framing as a live vessel tracker is dropped; with 15-minute polling cadence, the value proposition is sanctions screening, shadow-fleet visibility, port-state-control history, news-driven entity intelligence, and risk scoring — not real-time navigation.

Four primary additions over V1:

1. **Risk and compliance intelligence layer** — sanctions matching, shadow fleet tagging, MoU detention/inspection records, flag state performance, vessel age, anchorage dwell-derived congestion, weather risk. All sanctions and detention data sourced from **OpenSanctions** via daily bulk download, eliminating per-source parsing for OFAC/OFSI/EU/UN/Tokyo MoU/Paris MoU/Black Sea MoU/Abuja MoU.
2. **Entity-aware news layer** — articles parsed for vessel, organization, port, and terminal mentions; clickable entity tags filter the live map; per-port AI summaries on demand. RSS.app handles upstream curation via three topic-split feeds with webhook ingestion.
3. **Shadow Fleet visibility** — dedicated map filter, drawer tab, and marker badges for vessels OpenSanctions tags as shadow-fleet (Russian oil sanctions circumvention) even when not formally sanctioned.
4. **Two AI assistance systems** — a developer-side **Build Swarm** (Claude Code subagents in `.claude/agents/` for implementation, review, and documentation) and a runtime **Operations Swarm** (autonomous standing service for sanctions ingestion, entity extraction, news summarization) with a strict staging/approval boundary preventing autonomous writes to production tables.

The substrate moves from SQLite to **Postgres 16 + TimescaleDB + PostGIS**. Migrations managed by Alembic. Backend remains FastAPI; frontend remains React + Vite + Leaflet, with **SSE push** added so the frontend never polls the backend for position updates.

**Key constraints:**
- Sanctions auto-confirm: only IMO-exact matches; everything else routes to admin review queue
- Position polling: 15-minute cadence to MPA, well under any reasonable rate limit
- Force-update: admin dashboard only, never user-facing
- All times: stored UTC, served as ISO 8601, displayed America/Chicago default with per-session override
- AI agent monthly cost ceiling: ~$33/month with full feature set

---

## 2. Target Topology

Single VPS hosting all production workloads. No multi-region, no Kubernetes, no Redis.

```
┌─────────────────────────────────────────────────────────────────┐
│  VPS (Ubuntu 24.04 LTS)                                         │
│                                                                 │
│  ┌──────────┐                                                   │
│  │  Caddy   │  ← TLS termination, reverse proxy, HTTP/2         │
│  │  :80/443 │                                                   │
│  └─────┬────┘                                                   │
│        │                                                        │
│        ├──► /api/*       ──► FastAPI (uvicorn, port 8000)       │
│        ├──► /api/sse/*   ──► FastAPI (long-lived SSE streams)   │
│        ├──► /admin       ──► FastAPI (token-gated)              │
│        └──► /            ──► Static React build                 │
│                                                                 │
│  ┌─────────────────────────┐    ┌─────────────────────────┐     │
│  │  FastAPI app process    │    │  Operations Swarm       │     │
│  │  - HTTP API + SSE       │    │  worker process         │     │
│  │  - APScheduler jobs     │    │  - opensanctions_watcher│     │
│  │  - L1 in-memory cache   │    │  - entity_extractor     │     │
│  │  - SSE broadcaster      │    │  - news_summarizer      │     │
│  │  DB user: oceansx_app   │    │  - risk_scorer          │     │
│  └────────────┬────────────┘    │  DB user: oceansx_ops   │     │
│               │                 └────────────┬────────────┘     │
│               └──────────────┬───────────────┘                  │
│                              ▼                                  │
│             ┌────────────────────────────────┐                  │
│             │  Postgres 16                   │                  │
│             │  + TimescaleDB                 │                  │
│             │  + PostGIS                     │                  │
│             └────────────────────────────────┘                  │
│                                                                 │
│  Deterministic security (no AI):                                │
│  - fail2ban (sshd, caddy auth jails)                            │
│  - ufw firewall                                                 │
│  - cron: daily pip-audit + npm audit (logs only)                │
│  - cron: quarterly secret rotation reminder (email + log)       │
│  - outbound HTTP allowlist enforced at httpx transport layer    │
│                              │                                  │
│                              ▼                                  │
│             ┌────────────────────────────────┐                  │
│             │  Off-VPS encrypted backups     │                  │
│             │  (Backblaze B2)                │                  │
│             └────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

**Process model:** one uvicorn worker for FastAPI, one Python process for the Operations Swarm worker, one Postgres instance with four database roles (`oceansx_app`, `oceansx_ops`, `oceansx_promote`, `oceansx_readonly`).

**External data sources contacted from the VPS:** MPA OceansX (positions/particulars/macro/geo), `data.opensanctions.org` (daily bulk), `marine-api.open-meteo.com` (hourly single point), RSS.app (3 webhook feeds), Anthropic API (LLM calls).

---

## 3. VPS Provisioning Guide

Reference for VPS purchase and setup.

### 3.1 Hardware Recommendation

| Tier | RAM | vCPU | SSD | Use case |
|---|---|---|---|---|
| Minimum | 4 GB | 2 | 40 GB | Tight on agent memory, no headroom |
| **Recommended** | **8 GB** | **4** | **80 GB** | Single user with full agent swarm |
| Comfortable | 16 GB | 4 | 160 GB | Larger TimescaleDB chunks in RAM |

**Recommendation: 8 GB / 4 vCPU / 80 GB.**

### 3.2 Provider Recommendations

| Provider | 8 GB / 4 vCPU monthly | Notes |
|---|---|---|
| Hetzner Cloud (CPX31) | ~€16 / month | Cheapest reputable option. No Singapore region. |
| Hetzner Storage Box (BX11) | ~€4 / month | Off-VPS backup target. 1 TB. |
| Vultr Singapore | ~$48 / month | Singapore region available. |
| DigitalOcean Singapore | ~$48 / month | Singapore region available. |

For a Singapore-focused project, latency to MPA's API matters. Hetzner US is acceptable; Vultr or DigitalOcean Singapore is faster to MPA.

### 3.3 OS and Base Software

- **OS:** Ubuntu 24.04 LTS
- **Stack:**
  - Postgres 16 + TimescaleDB + PostGIS (use Timescale's official Docker image)
  - Python 3.12
  - Node.js 20 LTS
  - Caddy 2 (TLS + reverse proxy with SSE support)
  - ufw, fail2ban, unattended-upgrades, logrotate
  - rclone (backup transport)
  - git, build-essential, htop, tmux

### 3.4 Firewall, Hardening, Domain & TLS

Same as before:
- ufw allow 22/80/443; deny others; localhost-only Postgres
- SSH key-only, fail2ban sshd jail
- Non-root `oceansx` user; secrets in `/etc/oceansx/secrets.env` mode 0600
- Public domain + Caddy ACME when going live; Cloudflare proxy free tier optional

---

## 4. Data Sources and Attribution

| Source | Purpose | Endpoint pattern | Auth | License | Attribution |
|---|---|---|---|---|---|
| MPA OceansX | Positions, particulars, movements, macro, geo overlays | `oceans-x.mpa.gov.sg/api/v1/*` | API key (or mock) | per MPA terms | Yes — MPA Singapore |
| OpenSanctions | Sanctioned vessels + orgs + Tokyo/Paris/Black Sea/Abuja MoU detentions | `data.opensanctions.org/datasets/latest/{dataset}/{format}` | None (bulk) | Free non-commercial; CC-BY 4.0 | Yes — OpenSanctions |
| Open-Meteo Marine | Wave/wind/swell/currents/SST | `marine-api.open-meteo.com/v1/marine` | None | Free non-commercial under CC-BY 4.0 | Yes — Open-Meteo / DWD ICON Wave |
| RSS.app | Curated maritime news (3 feeds) | per-feed RSS URLs + webhook | per RSS.app account | per RSS.app terms | Per-article: original publisher |
| Anthropic API | LLM calls | `api.anthropic.com/*` | API key | per Anthropic terms | N/A |

### 4.1 OpenSanctions Datasets Ingested

Five datasets pulled daily as full snapshots, SHA1-checked against last fetch to skip unchanged downloads. Combined daily payload < 25 MB.

| Dataset | Format | Approx. size | Purpose |
|---|---|---|---|
| Maritime export | CSV | < 5 MB | All sanctioned vessels + IMO-bearing orgs — primary screening dataset |
| `tokyo_mou` | FtM JSON | < 10 MB | Asia-Pacific PSC detentions — primary relevance for Singapore |
| `paris_mou` | FtM JSON | < 5 MB | European PSC detentions |
| `bs_mou` | FtM JSON | < 2 MB | Black Sea PSC detentions |
| `abuja_mou` | FtM JSON | < 1 MB | West/Central Africa PSC detentions |

**Ingestion mechanics:** bulk download (not the OpenSanctions `/match` API), daily full snapshot (not delta updates), local fuzzy matching. Rationale: scope is small enough that delta complexity isn't justified, and `/match` adds external runtime dependency.

### 4.2 Open-Meteo Marine Polling

| Setting | Value |
|---|---|
| Coordinate | 1.265°N, 103.82°E (Singapore Strait, between harbour and Riau Islands) |
| Variables stored | All available marine variables: `wave_height`, `wave_direction`, `wave_period`, `wind_wave_height`, `wind_wave_direction`, `wind_wave_period`, `swell_wave_height`, `swell_wave_direction`, `swell_wave_period`, `ocean_current_velocity`, `ocean_current_direction`, `sea_surface_temperature` |
| Cadence | Hourly at :30 |
| Daily call count | 24 (vs 10,000/day free-tier limit) |
| Granularity | Single point applied to all vessels in/near Singapore harbour |

Final risk-scoring formula deferred until V2 is operational; storing all variables avoids re-pulling history when scoring logic changes.

### 4.3 RSS.app Feed Configuration

Three topic-split feeds. RSS.app's filter primitives (whitelist/blacklist with AND/OR, regex, age-based auto-hide, dedup) handle source curation upstream. Feeds deliver via webhook to `/api/news/ingest` with per-feed HMAC; safety hourly poll as fallback.

**Feed 1: Singapore Maritime General**
- Bundle: Splash247, gCaptain, Hellenic Shipping News, Maritime Executive, TradeWinds, Lloyd's List
- Whitelist (OR, title + description): `Singapore`, `MPA Singapore`, `PSA Singapore`, `Tuas`, `Jurong`, `Sembawang`, `Pasir Panjang`, `Changi`, `Strait of Singapore`, `Strait of Malacca`, `Singapore Strait`
- Blacklist: `Singapore Airlines`, `Singapore Air`, `F1`, `Formula 1`
- Auto-hide age > 14 days, missing date or description
- Dedup by title and description

**Feed 2: Sanctions / Shadow-Fleet Intelligence**
- Bundle: trade press + Google News-style keyword search
- Whitelist (OR): `shadow fleet`, `dark fleet`, `OFAC sanctions vessel`, `sanctioned tanker`, `Russian oil tanker`, `ship-to-ship transfer`, `STS transfer`, `sanctions evasion vessel`, `flag of convenience tanker`, `aging tanker`, `sanctioned shipping`
- Blacklist: `sports`, `entertainment`
- Auto-hide age > 30 days, missing date

**Feed 3: Port Operations / Disruption**
- Bundle: trade press + keyword search
- Whitelist (OR): `port congestion Singapore`, `terminal strike Singapore`, `vessel detention Singapore`, `MPA detention`, `marine accident Singapore`, `maritime incident Strait Singapore`, `oil spill Singapore`, `vessel collision Singapore`, `bunker fuel Singapore`, `shipping strike Singapore`
- Auto-hide age > 14 days

**RSS.app global settings:** max 100 posts per feed, image and HTML description tags included, output to webhook with HMAC.

### 4.4 Attribution Display

- Footer of every page: `Sanctions: OpenSanctions.org · Weather: Open-Meteo.com · Vessels: MPA Singapore`
- `/about` page lists all sources with links and license summaries
- Per-news-item attribution shows original publisher
- Per-vessel detail panel: "Sanctions data via OpenSanctions" link if listed

---

## 5. Database Architecture

### 5.1 Choice of Postgres + TimescaleDB + PostGIS

SQLite cannot handle V2's concurrent-writer workload (FastAPI + scheduler + Operations Swarm), has no first-class geospatial indexing, no JSON path indexing, no native time-series compression. Postgres + TimescaleDB + PostGIS resolves all four; `pg_dump` simplifies backup. TimescaleDB hypertables auto-partition `position_live`, `position_archive`, `weather_observation`, `risk_score`. PostGIS supports terminal polygon queries and geospatial overlays.

### 5.2 Database Roles and Permissions

| Role | Used by | Permissions |
|---|---|---|
| `oceansx_app` | FastAPI process, scheduler | SELECT/INSERT/UPDATE on operational tables; SELECT on staging |
| `oceansx_ops` | Operations Swarm worker | SELECT on production; INSERT/UPDATE on staging only |
| `oceansx_promote` | Approval flow (admin endpoints) | Full access; promotes staging to production |
| `oceansx_readonly` | Analytics, dashboards | SELECT-only |

The staging boundary is the architectural guarantee that an autonomous agent cannot corrupt deterministic systems.

### 5.3 Schema Overview

Twelve domains. Full DDL via Alembic during implementation; this is the logical model.

#### Domain 1: Vessel Master and SCD2 History

| Table | Purpose | Notes |
|---|---|---|
| `vessel` | One row per IMO. Latest particulars. | PK `imo` BIGINT (7-digit + Luhn). Columns include `first_observed_at`, `last_observed_at`, `is_shadow_fleet` BOOL, `current_sanctions_status` enum, `latest_risk_score_at`, `last_manual_review_at`. |
| `vessel_name_history` | Every name carried. | SCD2 `valid_from`, `valid_to`. |
| `vessel_flag_history` | Flag state. | SCD2. |
| `vessel_owner_history` | Registered owner. | SCD2. |
| `vessel_operator_history` | Operator/manager. | SCD2. |
| `vessel_class_history` | Classification society. | SCD2. From MoU detention records. |
| `vessel_topic` | OpenSanctions topic tags. | One row per (imo, topic, source_dataset, valid_from). Topics: `sanction`, `sanction.linked`, `crime.maritime`, `mare.detention`, `mare.shadow`, `reg.warn`. SCD2. |

#### Domain 2: Organizations (Full OpenSanctions Graph)

| Table | Purpose |
|---|---|
| `organization` | Generic entity. `org_type` polymorphic (owner, operator, ism_manager, beneficial_owner, terminal_operator, parent_company, sanctioning_authority, news_publisher). |
| `organization_alias` | Alternate names, transliterations. Indexed on `lower(alias)`. |
| `organization_address` | Multiple addresses; geocoded if PostGIS-resolvable. |
| `organization_topic` | OpenSanctions topic tags. |
| `organization_role_link` | Ownership/control relationships. SCD2. `from_org_id`, `to_org_id`, `role`, `share_pct`. |
| `vessel_organization_link` | Vessel↔org. SCD2. `imo`, `org_id`, `role` (registered_owner, beneficial_owner, operator, ism_manager, charterer, classification_society). |
| `opensanctions_entity_raw` | Full FtM JSON storage. `os_entity_id` PK, `schema_type`, `payload` JSONB, `referents` JSONB array, `first_seen_at`, `last_seen_at`. Authoritative store; relational tables are derived projections. |

#### Domain 3: Ports and Terminals

| Table | Purpose |
|---|---|
| `port` | Top-level. "Port of Singapore" is root. |
| `terminal` | Child of port. PSA Tuas, Pasir Panjang, Jurong, Sembawang, Changi, Eastern Anchorage, Western OPL. |
| `terminal_geom` | PostGIS `GEOGRAPHY(POLYGON, 4326)` with GiST. Sourced from MPA OceansX `/api/v1/geospatial/ports-and-services` (area type) at Phase 2 ingestion. Coverage gaps filled by point-radius fallback (1 km default radius) per missing terminal; gaps documented in an ADR. |
| `port_alias` | Names used in news. |

#### Domain 4: Time-Series Positions (TimescaleDB Hypertables)

| Table | Hypertable | Retention | Purpose |
|---|---|---|---|
| `position_live` | Yes, chunk by 1 day | 14 days | Every poll. Source for current-state map. |
| `position_archive` | Yes, chunk by 1 month | 365 days | Dedup'd long-term archive. Source for 24h timeline scrubber. |

**Cadence:** position polling at 15-minute intervals. With 96 polls/day per vessel, `position_live` retains ~1344 rows per vessel per 14 days.

**Archive write rule:** every poll attempts to write to `position_archive`. Skip if within **100 m AND |Δheading| < 5° AND |Δspeed| < 0.5 kn** of the most recent archive row for that IMO. (Replaces the V1 hourly archive job.) For a moored vessel, archive ends up with one row per port-call. For a moving vessel, ~4 rows/hour pass dedup.

**Columns:** `imo`, `recorded_at` (TIMESTAMPTZ UTC), `lat`, `lon`, `speed_knots`, `course_degrees`, `heading_degrees`, `nav_status`, `draft_meters`, `inferred_status`, `terminal_id` (FK derived via `ST_Within` at insert).

#### Domain 5: Sanctions and Shadow Fleet

| Table | Purpose |
|---|---|
| `sanctions_source` | Authority. OFAC, OFSI/UK Sanctions List, EU Council, UN Security Council, etc. |
| `sanctions_listing` | One row per FtM Sanction entity. `os_listing_id`, `target_os_id` FK to `opensanctions_entity_raw`, `program`, `effective_at`, `delisted_at`, `justification_text`, raw payload JSONB. |
| `sanctions_match` | Match between OpenSanctions entity and our vessel. `vessel_imo`, `os_entity_id`, `confidence`, `match_method` (`imo_exact`, `name_flag_fuzzy`, `name_fuzzy`, `org_link`), `status` (`pending`/`auto_confirmed`/`manually_confirmed`/`rejected`), `reviewed_by`, `reviewed_at`. |
| `sanctions_match_history` | SCD2 view of "currently sanctioned." Powers UI badges. |
| `staging_opensanctions_ingest` | Operations Swarm landing zone. |
| `staging_sanctions_match` | Staging for non-IMO-exact matches. |

**Auto-confirm rule (locked):** Only `match_method = 'imo_exact'` auto-confirms. All other methods route to admin review queue regardless of confidence. Hardcoded check in `services/sanctions_matcher.py`, verified by Security Reviewer Build Swarm role.

**Shadow Fleet status:** `vessel.is_shadow_fleet` BOOL derived nightly from `vessel_topic WHERE topic = 'mare.shadow' AND valid_to IS NULL`.

#### Domain 6: MoU Inspections and Detentions

All four MoU datasets ingested from OpenSanctions:

| Table | Purpose |
|---|---|
| `mou_inspection` | One row per detention/inspection. `vessel_imo`, `mou` (`tokyo`/`paris`/`black_sea`/`abuja`), `inspection_date`, `port_of_inspection`, `country_of_inspection`, `deficiencies_count`, `detained` BOOL, `detention_duration_hours`, `classification_society_at_time`, `flag_at_time`, `owner_at_time`, raw FtM payload JSONB. |
| `mou_inspection_deficiency` | Per-deficiency. `code`, `description`, `category`, `extra_fields` JSONB. |
| `flag_performance_year` | Annual MoU flag band. `flag_code`, `mou`, `year`, `performance_band` (white/grey/black). |

#### Domain 7: News and Entity Extraction

| Table | Purpose |
|---|---|
| `news_item` | Article. `published_at_utc`, `published_at_source_raw`, `was_clamped` BOOL, `extraction_status`, `feed_id`. Retention 90 days. |
| `news_entity_mention` | Many-to-many news↔entity. `news_id`, `entity_type` (`vessel`/`organization`/`port`/`terminal`/`sanctions_listing`), `entity_ref_id`, `surface_form`, `confidence`, `extraction_method`. |
| `news_summary` | Cached AI summary. Per-article or per-(port, time_window). `model_used`, `tokens_in`, `tokens_out`, `generated_at`. |
| `news_feed` | Static rows for the 3 feeds. Tracks last-fetch and counts. |
| `port_news_link` | Materialized view joining mentions where entity_type = port/terminal. Refreshed on news ingest. |

The tier-1 dictionary auto-builds from our DB: `vessel_name_history`, `organization_alias`, `port_alias`. Because OpenSanctions populates organizations and vessels deeply, dictionary matching automatically catches sanctioned/shadow-fleet mentions.

#### Domain 8: Risk Scoring

| Table | Hypertable | Retention | Purpose |
|---|---|---|---|
| `risk_score` | Yes, chunk by 7 days | 365 days | Hourly snapshot. Vector + components JSONB. |
| `weather_observation` | Yes, chunk by 7 days | 365 days | Hourly Open-Meteo Marine reading. |
| `anchorage_dwell` | No | Indefinite (small) | Per dwell event. |
| `terminal_congestion_hourly` | TimescaleDB continuous aggregate | 365 days | Materialized from `anchorage_dwell`. |

Risk score components stored as a vector (no scalar collapse at storage):

- **`sanctions_score`** — 100 confirmed match, 50 pending in queue, 25 previously sanctioned in last 90 days, 0 otherwise
- **`shadow_fleet_score`** — 100 if `is_shadow_fleet`, 0 otherwise
- **`age_score`** — 0 if year_built ≤ 10 years, scales linearly to 100 at 25 years
- **`flag_mou_score`** — 0 white, 50 grey, 100 black; override to 100 if any MoU detention in last 24 months
- **`congestion_score`** — From current `terminal_congestion_hourly` for vessel's current/arriving terminal
- **`weather_score`** — From latest `weather_observation`. Final formula deferred

UI shows each as a separate badge with disclaimer: "Risk indicators are derived from public data sources and should not be relied upon for operational or commercial decisions."

For sorting/filtering ("risk leaderboard," "high risk filter") a tiered composite is computed at query time:

```
composite_risk =
    IF sanctions_score > 0 OR shadow_fleet_score > 0:
        max(sanctions_score, shadow_fleet_score)
    ELSE:
        flag_mou_score   * 0.40 +
        age_score        * 0.30 +
        congestion_score * 0.20 +
        weather_score    * 0.10
```

Compliance indicators (sanctions, shadow fleet) act as overrides — a confirmed-sanctioned vessel scores 100 regardless of operational state. When no compliance flag exists, weights favor detention-predictive factors (flag MoU + age) over transient operational state (congestion + weather).

**Risk band thresholds (UI):**
- 0–25: Low
- 26–50: Medium
- 51–75: High
- 76–100: Critical

The "high risk" map filter slider defaults to 50. The composite is computed in `services/risk_scorer.py` at score-write time and stored as `risk_score.composite` (denormalized for sort performance).

#### Domain 9: Agent Observability

| Table | Purpose |
|---|---|
| `agent_run` | Per invocation. `agent_name`, `swarm`, `started_at`, `ended_at`, `status`, `model_used`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `summary`, `triggered_by`. |
| `agent_action` | Per tool call. `run_id`, `tool_name`, `input` JSONB, `output` JSONB, `success`, `latency_ms`, `error`. |
| `agent_review_queue` | Pending changes. `change_type` enum (`sanctions_match`, `mou_inspection_promotion`, `org_promotion`). `submitted_by_run_id`, `target_table`, `target_id`, `proposed_payload` JSONB, `confidence`, `status`, `reviewed_by`, `reviewed_at`. **No `security_alert` change_type** — security is deterministic. |
| `agent_cost_daily` | Materialized rollup per agent per day. |

#### Domain 10: System and Cache

| Table | Purpose |
|---|---|
| `cache_entry` | Generic key/value cache (Postgres-backed L2). |
| `audit_log` | Admin actions: cache clears, manual re-polls, approvals/rejections, config changes, secret rotations. |
| `outbound_request_log` | Every external HTTP call. Retention 30 days. Viewable in admin dashboard. |
| `data_source_status` | Per-source health. `source_name`, `last_success_at`, `last_attempt_at`, `last_error`, `consecutive_failures`, `last_payload_sha1`. Drives health cards. |
| `dependency_audit_log` | Daily pip-audit/npm-audit results. Retention 90 days. Viewable in admin. |

#### Domain 11: Attribution and Licensing Metadata

| Table | Purpose |
|---|---|
| `data_source_attribution` | One row per external source. `source_name`, `display_text`, `url`, `license_summary`, `attribution_required` BOOL, `non_commercial_only` BOOL. Surfaced via `/api/about`. |

#### Domain 12: Project Journal Documentation

This domain stores the chronological project documentation as queryable data, complementing the markdown files in `docs/journey/` and `docs/adr/`. Lets the admin dashboard render a timeline view of the build process.

| Table | Purpose |
|---|---|
| `journal_phase` | One row per implementation phase (~9 rows total). `phase_number`, `title`, `started_at`, `completed_at`, `summary_md`, `markdown_file_path`. |
| `journal_adr` | One row per Architecture Decision Record. `adr_number`, `title`, `status` (proposed/accepted/superseded/deprecated), `decided_at`, `summary_md`, `markdown_file_path`, `superseded_by_adr_number`. |
| `journal_event` | Timestamped narrative events. `occurred_at`, `event_type` (decision/milestone/blocker/learning), `title`, `body_md`. |
| `glossary_term` | Plain-English definitions of technical terms. `term`, `category`, `plain_definition`, `why_it_matters_in_project`, `markdown_file_path`. |

### 5.4 Indexing Strategy

- `position_live (imo, recorded_at DESC)`
- `position_archive (imo, recorded_at DESC)`
- `position_archive` GiST on `(lat, lon)::geography` for terminal-membership
- `vessel (last_observed_at DESC)` — "new vessels in last 24h"
- `vessel (is_shadow_fleet) WHERE is_shadow_fleet = true` — partial index for shadow tab
- `vessel_topic (imo, topic) WHERE valid_to IS NULL` — current topics
- `news_item (published_at_utc DESC)`
- `news_item (extraction_status, published_at_utc)` — extractor pickup
- `news_entity_mention (entity_type, entity_ref_id, news_id)`
- `sanctions_match (status, vessel_imo)`
- `sanctions_match_history (vessel_imo, valid_to)`
- `mou_inspection (vessel_imo, inspection_date DESC)`
- `mou_inspection (mou, inspection_date DESC)`
- `risk_score (vessel_imo, scored_at DESC)`
- `weather_observation (recorded_at DESC)`
- `anchorage_dwell (terminal_id, started_at DESC) WHERE ended_at IS NULL`
- `agent_run (agent_name, started_at DESC)`
- `terminal_geom` GiST on geography
- `organization_alias (lower(alias))`
- `opensanctions_entity_raw (schema_type, last_seen_at)`

### 5.5 Retention and Compaction

| Table | Retention |
|---|---|
| `position_live` | 14 days |
| `position_archive` | 365 days |
| `weather_observation` | 365 days |
| `risk_score` | 365 days |
| `news_item`, `news_entity_mention` | 90 days |
| `agent_run`, `agent_action` | 90 days |
| `outbound_request_log` | 30 days |
| `dependency_audit_log` | 90 days |
| `cache_entry` | TTL-based, swept hourly |
| `audit_log`, `journal_*`, `glossary_term` | Indefinite |
| `mou_inspection`, `sanctions_*`, `vessel*`, `organization*`, `opensanctions_entity_raw`, `port`, `terminal` | Indefinite |

TimescaleDB compression: `position_archive`, `weather_observation`, `risk_score` chunks older than 7 days compressed (~90% reduction).

### 5.6 Migrations

Alembic, no exceptions. `SQLModel.metadata.create_all()` removed. Build Swarm Database Engineer role owns migrations.

---

## 6. Backend Service Layout

```
backend/app/
├── clients/
│   ├── oceansx.py
│   ├── opensanctions.py        # SINGLE client for all sanctions + 4 MoU datasets
│   ├── openmeteo.py
│   ├── rss_app.py              # webhook receiver helpers
│   └── anthropic.py
├── routers/
│   ├── vessels.py
│   ├── macro.py
│   ├── geospatial.py
│   ├── news.py
│   ├── history.py              # 24h dynamic timeline
│   ├── meta.py                 # /health, /lookups, /about
│   ├── sanctions.py
│   ├── shadow_fleet.py
│   ├── risk.py
│   ├── ports.py
│   ├── nl_search.py            # 10/min limit
│   ├── sse.py                  # SSE channels for position updates, queue updates
│   ├── journal.py              # phase/ADR/glossary endpoints for /about and admin
│   └── admin.py                # overhauled (DB explorer + stats tab + actions)
├── services/
│   ├── vessels.py
│   ├── vessel_master.py
│   ├── history.py
│   ├── macro.py
│   ├── geospatial.py
│   ├── news.py
│   ├── news_summary.py
│   ├── entity_extraction.py    # tiered: dict → GLiNER → Claude
│   ├── opensanctions_ingest.py # FtM parser + projection
│   ├── sanctions_matcher.py    # IMO-exact auto, others to queue
│   ├── risk_scorer.py
│   ├── anchorage_dwell.py
│   ├── port_news.py
│   ├── nl_search.py            # graph-aware NL parsing
│   ├── weather.py
│   ├── promotion.py            # staging → production approval flow
│   └── sse_broadcaster.py      # broadcasts events to SSE subscribers
├── agents/
│   ├── runtime.py              # AgentRun wrapper + observability
│   ├── tools.py                # restricted tools
│   ├── opensanctions_watcher.py
│   ├── entity_extractor.py
│   ├── news_summarizer.py
│   └── risk_scorer_agent.py    # deterministic; no LLM
├── auth/
│   ├── admin.py
│   └── oauth.py                # placeholder
├── utils/
│   ├── geo.py
│   ├── imo.py
│   ├── timezone.py
│   ├── fuzzy.py
│   ├── ftm.py
│   └── http_allowlist.py       # outbound HTTP allowlist enforcement
├── cache.py
├── config.py
├── db.py
├── limiter.py
├── main.py
├── metrics.py
├── models.py
├── observability.py
├── schemas.py
├── scheduler.py
└── alembic/
```

**No Sentinel agent. No Triage agent.** Security is enforced deterministically (see §11).

### 6.1 Updated Scheduler Job Set

| Job | Trigger | Owner | Notes |
|---|---|---|---|
| `poll_positions` | Every 15 min | App | Writes to live AND attempts archive write (dedup) per poll. Replaces hourly archive job. |
| `enrich_vessel_particulars` | Every 1h | App | Up to 50 vessels per cycle; oldest-enriched-first ordering |
| `compute_anchorage_dwell` | At :10 hourly | App | |
| `score_risk_hourly` | At :15 hourly | Ops Swarm (deterministic agent) | |
| `extract_entities` | At :20 hourly + event-driven on news webhook | Ops Swarm | |
| `pull_weather` | At :30 hourly | App | Single Open-Meteo call |
| `refresh_news` | Webhook-driven; safety poll every 1h | App | |
| `pull_opensanctions` | Daily 04:00 America/Chicago | Ops Swarm | One job pulls all 5 datasets, SHA1-checked |
| `flag_performance_refresh` | Weekly Monday 05:00 | Ops Swarm | |
| `refresh_macro` | Daily 03:00 America/Chicago | App | |
| `refresh_geospatial` | Daily 04:00 America/Chicago | App | |
| `prune_history` | Daily 02:00 America/Chicago | App | TimescaleDB retention does most of the work |
| `refresh_shadow_fleet_flags` | Daily 04:30 America/Chicago | App | After OpenSanctions pull |
| `dependency_audit` | Daily 06:00 America/Chicago | Cron (not agent) | Writes to `dependency_audit_log` |
| `secret_rotation_reminder` | Quarterly 1st 09:00 America/Chicago | Cron (not agent) | Writes to `audit_log` if secret > 90 days old |
| `backup_postgres` | Daily 03:30 America/Chicago | Cron | |
| `journal_indexer` | Hourly | App | Walks `docs/journey/` and `docs/adr/` and updates `journal_*` tables |

### 6.2 New Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/sanctions/current` | Confirmed sanctions matches |
| GET | `/api/sanctions/possible` | Pending matches |
| GET | `/api/sanctions/history/{imo}` | Full sanctions history including delisted |
| GET | `/api/shadow-fleet/current` | Currently visible shadow-fleet vessels |
| GET | `/api/shadow-fleet/all` | All shadow-fleet vessels in DB |
| GET | `/api/risk/{imo}` | Current risk vector |
| GET | `/api/risk/leaderboard` | Top N highest-risk currently visible |
| GET | `/api/vessels/new-arrivals` | First-seen in last 24h |
| GET | `/api/ports` | Port + terminal hierarchy |
| GET | `/api/ports/{port_id}/news?since=` | Port-news, optionally summarized |
| POST | `/api/news/ingest` | RSS.app webhook receiver, HMAC-gated per feed |
| POST | `/api/search/nl` | Natural language search; 10/min limit |
| GET | `/api/about` | Data source attribution + license summaries |
| GET | `/api/journal/phases` | Phase entries for journal timeline |
| GET | `/api/journal/adrs` | ADR entries |
| GET | `/api/journal/glossary` | Glossary terms |
| GET | `/api/sse/positions` | SSE stream of position updates |
| GET | `/api/sse/queue` | SSE stream of admin queue events |
| GET | `/api/admin/queue/sanctions` | Pending matches review |
| POST | `/api/admin/queue/sanctions/{id}/approve` | |
| POST | `/api/admin/queue/sanctions/{id}/reject` | |
| GET | `/api/admin/data-sources/status` | Per-source health |
| GET | `/api/admin/db/{table}` | DB explorer: paginated table view (50 rows/page) |
| GET | `/api/admin/db/{table}/{pk}` | Single-row detail with linked entities |
| GET | `/api/admin/stats/*` | Stats endpoints feeding visualizations tab |

### 6.3 Natural Language Search

Expanded scope: graph queries, threshold queries, compound conditions. Rate limited 10/min/user.

**Examples the parser must handle:**
- `"show me all VLCC tankers arriving in next 6 hours"` — filter by vessel_type + arrival_window
- `"all vessels with risk score above 75"` — filter by composite risk threshold
- `"VLCCs connected to sanctioned companies"` — graph traversal: vessel_type=VLCC AND (registered_owner OR operator OR ism_manager OR beneficial_owner) has any `organization_topic = 'sanction'`
- `"chemical tankers from Russian-flagged owners"` — vessel_type + owner.flag/registered_country
- `"shadow fleet vessels in Eastern Anchorage"` — is_shadow_fleet + current terminal
- `"vessels detained by Tokyo MoU in last 90 days"` — mou_inspection filter
- `"ships built before 2005 with confirmed sanctions"` — age threshold + sanctions status

**Parser pipeline:**
1. Frontend submits to `/api/search/nl` (rate limit 10/min/user, cache 5 min on identical query)
2. Backend calls Claude Haiku 4.5 with system prompt defining schema:
   - `vessel_type` (enum)
   - `flag_country` (string code)
   - `arrival_window_hours`, `departure_window_hours` (int)
   - `risk_threshold_min`, `risk_threshold_max` (0–100)
   - `risk_component` (which component, optional)
   - `sanctions_status` (enum: confirmed/pending/previous/clean/any)
   - `shadow_fleet_only` (bool)
   - `age_min_years`, `age_max_years` (int)
   - `terminal_id` or `terminal_name` (string)
   - `connected_to_sanctioned_org` (bool, default false)
   - `connection_depth` (int 1–5; default determined by NL parser from query phrasing)
   - `mou_detention_window_days` (int, optional)
   - `mou_detention_authority` (enum: tokyo/paris/black_sea/abuja, optional)
3. Claude returns structured JSON matching Pydantic schema
4. Validation enforces only allowed dimensions
5. Backend translates to Postgres query with explicit JOINs (no string interpolation)
6. Response includes both the parsed filter (so user sees what was interpreted) and matched vessel list

**Graph traversal:** depth determined per query by NL parser intent.
- "directly owned by", "directly connected", "registered owner is" → depth 1 (vessel's immediate registered_owner, beneficial_owner, operator, ism_manager, charterer, classification_society)
- "connected to", "controlled by", "beneficially owned by", "ultimately owned by", or absent qualifier → depth 5 (effectively unlimited within practical bounds)

**Implementation:** Postgres recursive CTE traversing `vessel_organization_link` UNION `organization_role_link`, with cycle detection via a `path` array (each visited org_id appended; reject if next candidate already in path). Hard cap depth 5 — anything beyond is effectively the entire connected subgraph and produces too many false positives. Per-query timeout 5 seconds via asyncio; if hit, returns partial results with explicit `truncated: true` flag and explanatory note in response. Result cached 10 minutes keyed on full filter spec hash.

**Why depth 5:** Real-world ownership chains for shadow-fleet vessels rarely exceed 4 hops (vessel → registered owner shell → beneficial owner shell → controlling individual or sanctioned entity). Depth 5 covers virtually all real cases while preventing runaway traversal across the connected component of unrelated commercial fleets.

---

## 7. Time Zone Strategy

V1 bug: future-dated news timestamps display as "in about X hours."

V2 strategy:
- **Storage:** Postgres `TIMESTAMPTZ`, all UTC
- **Ingestion clamp:** every external timestamp passes through `clamp_future(ts, now, tolerance=5min)`. If `ts > now + tolerance`, replace with `now` and set `was_clamped = TRUE`. Applied to news, sanctions effective dates, MoU inspection dates
- **API serialization:** ISO 8601 with explicit `+00:00` offset
- **Frontend default display:** `America/Chicago` (DST-aware) via Luxon
- **User override:** session-persistent dropdown (America/Chicago, UTC, Asia/Singapore, browser-detected)
- **Footer indicator:** always shows `All times: America/Chicago (CDT)` or current zone with abbreviation
- **Relative time:** "X hours ago" computed against clamped UTC and `now()` in selected zone — future renders impossible

---

## 8. Frontend Changes and Update Strategy

### 8.1 Update Strategy with 15-Min Polling

V1 had React Query refetch positions every 5 min. V2 changes:

- **Backend SSE channel:** `GET /api/sse/positions` — long-lived stream from FastAPI. After every successful `poll_positions` job, the broadcaster sends a `positions_updated` event. Frontend subscribes once on app load.
- **Frontend React Query:** `useLivePositions()` initial fetch on mount; `staleTime: Infinity`. SSE event triggers `queryClient.invalidateQueries(['positions'])` which re-fetches once.
- **Result:** Frontend never polls. Backend hits MPA at most every 15 min. User sees fresh data ~immediately after each backend poll.
- **Reconnection:** SSE auto-reconnects on disconnect with 5s backoff. Stale SSE → fall back to one fetch per minute as safety.
- **Per-vessel detail:** lazy-loaded only on click; cached 60s.
- **Macro and geospatial:** React Query staleTime 1h and 24h respectively (matching server cache headers).

### 8.2 New Components

| Component | Purpose |
|---|---|
| `RiskBadge` | Per-vessel risk vector display |
| `SanctionsAlert` | Banner on DetailPanel for sanctioned vessels |
| `SanctionsTab` | Drawer listing currently-sanctioned visible vessels |
| `ShadowFleetTab` | Parallel drawer; lists shadow-fleet visible vessels |
| `ShadowFleetBadge` | Marker overlay icon, visible at any zoom |
| `NewArrivalsTab` | Vessels first seen in last 24h |
| `EntityTagPills` | Inside news items; click → filter map |
| `PortNewsPopup` | Click port marker → recent news with Summarize button |
| `NLSearchBar` | Replaces V1 substring search; falls back if NL parse fails |
| `TimeZoneSelector` | Footer dropdown |
| `DataSourceFooter` | Attribution |
| `JournalDrawer` | Public-facing journey timeline (phases + ADRs + glossary), accessible from About link |

### 8.3 Map Filter Toggles

In overlay panel:
- Shadow Fleet only
- Sanctioned only
- High risk (slider threshold)

### 8.4 Timeline Bar Fix

- Always represents `now - 24h → now`
- Capped 1440 max points (in practice far fewer with dedup)
- Empty-state if no positions in window
- Scrubber range fixed; trail rendered sparse where data sparse

### 8.5 Removal of Force-Update Button

"Last updated X minutes ago" indicator becomes display-only.

### 8.6 Build Pipeline

Vite, Tailwind, manual chunk splitting. Lazy chunks:
- `nl-search`, `sanctions-drawer`, `shadow-fleet-drawer`, `admin`, `journal-drawer`
- Eager: `risk-badge` (needed in main bundle)

---

## 9. Build Swarm — Developer-Side AI Team

Implemented as **Claude Code subagents** in `.claude/agents/` directory of the V2 repo. Each role is a markdown file with YAML frontmatter (name, description, tools, model). Claude Code auto-delegates based on description; manual invocation via `@agent-name`.

### 9.1 Roles (one .md file per role)

| Role | File | Model | Tools | Scope |
|---|---|---|---|---|
| Architect | `architect.md` | Sonnet | Read, Write, Glob, Grep | High-level design, ADRs, `ARCHITECTURE.md` |
| Database Engineer | `db-engineer.md` | Sonnet | Read, Write, Edit, Bash | Alembic migrations, indexes, query plans |
| Backend Engineer | `backend-engineer.md` | Sonnet | Read, Write, Edit, Bash | Services, routers, clients (excluding DB and agents) |
| Frontend Engineer | `frontend-engineer.md` | Sonnet | Read, Write, Edit, Bash | React components, hooks, styles |
| Agent Engineer | `agent-engineer.md` | Sonnet | Read, Write, Edit | Operations Swarm code only |
| Security Reviewer | `security-reviewer.md` | Sonnet | Read, Grep, Glob, Bash (read-only commands) | Reviews PRs for auth, injection, secrets, agent boundaries |
| Code Reviewer | `code-reviewer.md` | Haiku | Read, Grep, Glob | General review for clarity, tests, idioms |
| Test Engineer | `test-engineer.md` | Sonnet | Read, Write, Edit, Bash | pytest, vitest, fixtures |
| Documentation Maintainer | `doc-maintainer.md` | Sonnet | Read, Write, Edit | `docs/journey/*`, `docs/adr/*`, `glossary.md`, `CHANGELOG.md` |

### 9.2 Operation

Each agent file includes system prompt, allowed file globs, forbidden actions, review checklist, output format. Per-feature workflow:

1. Architect produces an ADR (writes to `docs/adr/NNNN-*.md`)
2. Database Engineer drafts Alembic migration
3. Backend Engineer implements service + router
4. Frontend Engineer implements components
5. Test Engineer adds tests
6. Code Reviewer + Security Reviewer in sequence (Claude auto-delegates based on description)
7. Documentation Maintainer updates phase journal + glossary
8. Manual commit by you

This pattern is supported natively by Claude Code: subagents preserve main context, run in their own windows, return only summaries.

### 9.3 Mandatory Review Checklists

**Security Reviewer must verify:**
- No SQL string interpolation; queries parameterized
- No secrets in code, logs, fixtures
- All admin endpoints use `require_admin`
- Agent tool definitions match permitted scope
- Outbound HTTP only to allowlisted domains
- IMO inputs validated at router boundary
- New endpoints have rate limits
- Sanctions auto-confirm respects IMO-exact-only

**Code Reviewer must verify:**
- Tests exist and cover the change
- No dead code or commented-out blocks
- Type hints present
- Error handling explicit
- New external deps justified
- Time-handling uses `utils/timezone.py`

**Documentation Maintainer must verify:**
- Phase journal updated within phase boundary
- Any new ADR has a corresponding `journal_adr` row triggered via `journal_indexer`
- New technical terms added to glossary with plain-English definitions
- All ADRs follow the standard template (Context / Decision / Alternatives / Consequences / Plain-English)

PRs without filled-in checklists are not merged.

---

## 10. Operations Swarm — Runtime AI Team

Standing service running on the VPS. Separate Python process. DB user `oceansx_ops`. Writes to staging only; production writes go through approval flow under `oceansx_promote`.

### 10.1 Agents (Reduced Set)

Sentinel and Triage removed. Cybersecurity is deterministic only (see §11).

| Agent | Cadence | Model | Writes to | Approval needed |
|---|---|---|---|---|
| **OpenSanctions Watcher** | Daily 04:00 CT | Sonnet 4.5 (parses FtM, runs IMO-exact matcher) | `staging_opensanctions_ingest`, `staging_sanctions_match` | IMO-exact auto-confirms; everything else queued |
| **Entity Extractor** | Hourly + on news webhook | Tiered: dictionary first → GLiNER (local) → Haiku 4.5 fallback | `news_entity_mention` | No (low-stakes, retention prunes errors) |
| **News Summarizer** | On demand (port-news click, drawer) | Haiku 4.5 short, Sonnet 4.5 long-form | `news_summary` | No (cached by article hash) |
| **Risk Scorer** | Hourly :15 | No LLM (deterministic computation) | `risk_score` | No (append-only) |

### 10.2 Permission Boundaries

| Boundary | Enforcement |
|---|---|
| No production writes from agents | Postgres role permissions |
| No raw SQL from agents | Tool layer exposes only named operations |
| No outbound HTTP outside allowlist | `utils/http_allowlist.py` enforces at httpx transport layer |
| No exceeding daily cost cap | `agent_run` wrapper aborts when day cost > cap |
| No concurrent runs of same agent | Postgres advisory lock per agent name |
| No non-IMO-exact auto-confirm | Hardcoded check in `services/sanctions_matcher.py` |

### 10.3 Approval Flow

1. Agent inserts to `agent_review_queue`
2. Admin dashboard shows pending count + SSE event to live admin sessions
3. Admin opens queue, sees proposed change with full context
4. Approve → `oceansx_promote` copies staging → production, marks queue `approved`, logs `audit_log`
5. Reject → marks `rejected`, never touches production

For sanctions matches: Approve opens or extends `sanctions_match_history` SCD2 record. Reject suppresses re-proposal of the same `(vessel_imo, os_entity_id)` pair for 30 days.

### 10.4 Cost Management

| Mechanism | Detail |
|---|---|
| Per-agent daily $ cap | Hard stop |
| Tiered model selection | Haiku for cheap, Sonnet for parsing/quality |
| Aggressive caching | News summaries cached forever per article hash; entity extractions cached per article hash |
| Dictionary-first | Built from our DB (vessel names, org aliases, port aliases). Falls through to GLiNER only on miss; Claude only on GLiNER low confidence |
| Token logging per call | `agent_run` tracks tokens + cost |
| Anthropic Batch API | 50% discount for non-urgent ingestion |

**Monthly budget at full feature set (~$33/month):**
- OpenSanctions Watcher: $3
- Entity Extractor: $20 (largest user)
- News Summarizer: $10
- Risk Scorer: $0 (deterministic)

### 10.5 Agent Observability

Every run produces `agent_run` row, `agent_action` rows, and `outbound_request_log` entries. Admin dashboard exposes live runs, history with success/failure rates, daily cost per agent with budget bar, failed runs with errors, kill-run button.

---

## 11. Security Posture (Deterministic Only)

No AI agents involved in security. All measures are configuration, code, and cron-based.

### 11.1 Threat Model and Mitigations

| Threat | Mitigation |
|---|---|
| SSH brute-force | Key-only auth, fail2ban sshd jail |
| Brute-force on admin token | slowapi 10 req/min/IP on `/api/_admin/*`; fail2ban Caddy jail on repeated 401/403 |
| Dependency vulnerabilities | `pip-audit` + `npm audit` run daily via cron; results written to `dependency_audit_log` and surfaced in admin dashboard; HIGH/CRITICAL CVEs trigger an entry in `audit_log` |
| SQL injection | SQLModel parameterized queries everywhere; no raw-string SQL in services or agents; reviewed by Security Reviewer Build Swarm role |
| Compromised agent making unauthorized outbound calls | `utils/http_allowlist.py` enforces at httpx transport (not config); allowlist: `oceans-x.mpa.gov.sg`, `data.opensanctions.org`, `marine-api.open-meteo.com`, `*.rss.app`, `api.anthropic.com`. Every call logged to `outbound_request_log` regardless |
| Secret leak in logs | Log sanitizer strips known secret-keyed env values before emit |
| Stale admin token | Cron quarterly checks `audit_log` for last `secret_set_at` per secret name; if > 90 days, writes a new `audit_log` entry with severity=warning that surfaces as banner in admin dashboard |
| DDoS | Cloudflare proxy free tier when going public |
| XSS via news content | DOMPurify on user-rendered HTML; restrictive CSP header |
| Webhook spoofing on `/api/news/ingest` | HMAC per feed using `RSS_APP_FEED_N_HMAC` secrets; reject mismatches |

### 11.2 What Is NOT Monitored by AI

- No real-time log anomaly detection
- No automated traffic-pattern analysis
- No AI classification of failed auth attempts
- No security alerts in `agent_review_queue`

This is acceptable for a single-user, non-public, portfolio-grade project. If usage profile changes (public launch with auth, multi-user), revisit.

### 11.3 Secret Management

Secrets in `/etc/oceansx/secrets.env`, mode 0600, owned by `oceansx`:
- `OCEANSX_API_KEY`
- `ANTHROPIC_API_KEY`
- `ADMIN_TOKEN`
- `POSTGRES_PASSWORD_*` (4 roles)
- `BACKUP_ENCRYPTION_KEY`
- `BACKUP_B2_KEY_ID`, `BACKUP_B2_APPLICATION_KEY`
- `RSS_APP_FEED_1_HMAC`, `RSS_APP_FEED_2_HMAC`, `RSS_APP_FEED_3_HMAC`

Loaded via systemd `EnvironmentFile=`. Quarterly rotation reminder via cron.

### 11.4 OAuth Migration (Future)

When map goes public, replace public access with Google/Microsoft OAuth via Authlib. Sessions in signed cookies (HttpOnly, Secure, SameSite=Lax). User table added at that time. `app/auth/oauth.py` is a placeholder until then.

---

## 12. Admin Dashboard V2

Single React SPA route at `/admin`, gated by `ADMIN_TOKEN`. Lazy-loaded chunk. Five top-level tabs:

1. **Overview** — system health cards, source sparklines, connections diagram, pending approvals count, live log tail
2. **Approvals Queue** — sanctions match review, MoU promotion review, organization promotion review
3. **Operations Swarm** — per-agent status, cost trends, kill controls, run history
4. **DB Explorer** — paginated browse of every major table with linked-entity navigation
5. **Stats & Visualizations** — analytical charts of platform-level data

### 12.1 Overview Tab

```
┌──────────────────────────────────────────────────────────────────┐
│  OceansX Admin                              [Logout]  [Refresh]  │
├──────────────────────────────────────────────────────────────────┤
│  System Health                                                   │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                    │
│  │  DB  │ │ MPA  │ │ RSS  │ │OpnSnc│ │OpnMet│  per-source        │
│  │  ✓   │ │  ✓   │ │  ✓   │ │  ✓   │ │  ✓   │  health cards      │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                    │
├──────────────────────────────────────────────────────────────────┤
│  Sparklines (last 24h)              Connections Diagram          │
│  ┌──────────────────────┐           ┌───────────────────────┐    │
│  │ MPA  ▁▁▂▂▂▂▂▂▂▂▂▂▂   │           │  Force-directed graph │    │
│  │ Opn  ▁____________▁  │           │  Nodes = sources +    │    │
│  │ Wea  ▂▁▂▁▂▁▂▁▂▁▂▁▂   │           │  internal tables      │    │
│  │ News ▃▂▁▂▁▃▂▁▁▁▂▁▂   │           │  Edges = sync time    │    │
│  └──────────────────────┘           └───────────────────────┘    │
├──────────────────────────────────────────────────────────────────┤
│  Pending Approvals (12)             Quick Actions                │
│  Sanctions: 8                       [Force position poll]        │
│  MoU promotion: 3                   [Force OpenSanctions refresh]│
│  Org promotion: 1                   [Force weather pull]         │
│                                     [Recompute risk scores]     │
│                                     [Refresh shadow-fleet flags] │
│                                     [Re-extract last 24h news]   │
│                                     [Clear cache (all)]          │
│                                     [VACUUM ANALYZE]             │
│                                     [Pause / resume scheduler]   │
│                                     [Toggle mock mode]           │
│                                     [Export DB stats]            │
│                                     [Test backup restore]        │
│                                     [Rotate admin token]         │
│                                     [Trigger dependency audit]   │
├──────────────────────────────────────────────────────────────────┤
│  Live Log Tail (last 50 lines)                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 12.2 DB Explorer Tab

Lazy-loaded paginated browser. Key requirements: never render the full DB; always 50 rows per page; relationship navigation via clicks.

**Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│  DB Explorer                                                     │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐   │
│  │ Tables          │  │ vessel  (16,742 rows)                │   │
│  │ ┌─────────────┐ │  │ ┌─────────┬──────┬──────┬──────────┐ │   │
│  │ │ vessel      │ │  │ │ IMO     │ Name │ Flag │ Shadow   │ │   │
│  │ │ organization│ │  │ ├─────────┼──────┼──────┼──────────┤ │   │
│  │ │ sanctions_* │ │  │ │ 9876543 │ ...  │ MH   │  ✓       │ │   │
│  │ │ mou_*       │ │  │ │ 9234567 │ ...  │ PA   │  -       │ │   │
│  │ │ news_*      │ │  │ │ ...     │ ...  │ ...  │  ...     │ │   │
│  │ │ risk_score  │ │  │ └─────────┴──────┴──────┴──────────┘ │   │
│  │ │ position_*  │ │  │ Page 3 of 335   [< Prev] [Next >]    │   │
│  │ │ weather_*   │ │  │ Search: [____________]                │   │
│  │ │ agent_*     │ │  │ Filter: [shadow_fleet=✓] [Apply]      │   │
│  │ │ ...         │ │  └──────────────────────────────────────┘   │
│  │ └─────────────┘ │                                             │
│  └─────────────────┘                                             │
└──────────────────────────────────────────────────────────────────┘
```

**On row click — single-entity detail view:**
- All columns of the row
- All linked entities surfaced as clickable cards: e.g., for a `vessel` row, show the vessel's `organization` links (owner, operator, ism_manager), recent `sanctions_match` rows, recent `mou_inspection` rows, recent `position_archive` rows (limit 50), `risk_score` history (last 30 days)
- Each linked entity is itself clickable, navigating deeper

**Implementation:**
- Generic backend endpoint `GET /api/admin/db/{table}?page=N&filter=...&search=...`
- Schema introspection: backend reads SQLAlchemy metadata to know columns and FK relationships per table; frontend doesn't hardcode anything
- Server-side pagination, filtering, sorting; only 50 rows ever in flight
- `GET /api/admin/db/{table}/{pk}` returns full row + linked entities (subject to per-relation row caps)

### 12.3 Stats & Visualizations Tab

Analytical charts. Initial set (subject to confirmation in clarification round 4):

| Chart | Question it answers |
|---|---|
| **Daily vessel arrivals/departures** | How busy is Singapore? |
| **Vessel type distribution (current)** | What's the fleet mix here right now? |
| **Sanctioned + Shadow Fleet count over time** | Is risk exposure trending up? |
| **Risk score distribution histogram** | What's the typical risk profile? |
| **Top 20 highest-risk vessels currently visible** | Where do I focus attention? |
| **Anchorage dwell time per terminal (last 30 days)** | Which terminals are congested? |
| **MoU detentions per flag (last 365 days)** | Which flags carry detention risk? |
| **News mention frequency: top 20 entities (last 30 days)** | What's in the news? |
| **Entity extraction tier breakdown (dictionary/GLiNER/Claude)** | How often does cheap path work? |
| **Agent cost per day (last 30 days, stacked)** | Am I within budget? |
| **OpenSanctions dataset row count over time** | Are sanctions lists growing? |
| **Sources health: % uptime per source (last 30 days)** | Is my pipeline reliable? |
| **Position archive write rate (per hour, last 7 days)** | Is dedup working as expected? |

All charts built with Recharts. All endpoints under `/api/admin/stats/*`. All cached 1 hour server-side.

### 12.4 Quick Actions

Every action produces an `audit_log` entry, rate-limited 5/min globally.

| Action | Effect |
|---|---|
| Force position poll | Triggers `poll_positions` immediately |
| Force OpenSanctions refresh | Runs Watcher (ignores SHA1 cache) |
| Force weather pull | Triggers Open-Meteo fetch |
| Force news refresh per feed | Re-polls one of 3 feeds |
| Recompute risk scores | Runs Risk Scorer for all vessels |
| Refresh shadow-fleet flags | Re-derives `vessel.is_shadow_fleet` |
| Re-extract entities last 24h | Re-queues news from last 24h |
| Clear cache (all) | Truncates `cache_entry`, evicts L1 |
| Clear cache by key | Targeted eviction |
| VACUUM ANALYZE | Pg maintenance |
| Pause / resume scheduler | Halts all jobs |
| Toggle mock mode | Reload settings without restart |
| Replay last N hours of positions | Re-ingests via mock-replay |
| Export DB stats | Downloads JSON (table sizes, row counts, index usage) |
| Test backup restore | `pg_restore --list` against latest |
| Approve/reject queued change | Per item |
| Mark vessel as manually reviewed | Sets `vessel.last_manual_review_at` |
| Kill agent run | Cancels by `run_id` |
| Rotate admin token | Generates new, invalidates old |
| Trigger dependency audit | Runs pip-audit + npm audit immediately |

---

## 13. Project Journal and Documentation Strategy

For your portfolio/LinkedIn presentation. Combination format: phase summaries + ADRs + glossary.

### 13.1 Directory Structure

```
docs/
├── journey/                    # Phase summaries — narrative arc
│   ├── README.md               # Index / story arc
│   ├── 00-the-problem.md       # Why this project, what it solves
│   ├── 01-planning-process.md  # How the AI conversation produced this plan
│   ├── 02-phase-0-foundation.md
│   ├── 03-phase-1-live-tracking.md
│   ├── 04-phase-2-macro-geospatial.md
│   ├── 05-phase-3-news.md
│   ├── 06-phase-4-opensanctions.md
│   ├── 07-phase-5-weather-risk.md
│   ├── 08-phase-6-intelligence.md
│   ├── 09-phase-7-hardening.md
│   ├── 10-phase-8-deployment.md
│   └── 11-retrospective.md
├── adr/                        # Architecture Decision Records — detailed
│   ├── README.md               # Index of all ADRs with statuses
│   ├── 0001-postgres-over-sqlite.md
│   ├── 0002-opensanctions-replaces-per-source.md
│   ├── 0003-two-swarm-architecture.md
│   ├── 0004-15-min-position-polling.md
│   ├── 0005-imo-exact-only-auto-confirm.md
│   ├── 0006-shadow-fleet-prominent-treatment.md
│   ├── 0007-staging-tables-as-agent-boundary.md
│   ├── 0008-sse-push-vs-frontend-polling.md
│   ├── 0009-tiered-entity-extraction.md
│   ├── 0010-deterministic-security-no-ai.md
│   ├── 0011-utc-storage-cst-display.md
│   ├── 0012-claude-code-subagents-for-build.md
│   └── ...                     # Numbered as decisions accrue
└── glossary.md                 # Plain-English definitions of every technical term
```

### 13.2 Phase Journal Template

Each `docs/journey/NN-phase-X-*.md` follows this structure:

```markdown
# Phase X: [Title]

## TL;DR
Two sentences readable by a non-technical executive.

## Goal
What this phase aimed to deliver and why it matters for the broader project.

## What Was Built
Concrete features and capabilities, in plain language.

## Decisions Made
Links to relevant ADRs (e.g., "See ADR-0004 on polling cadence").

## What Surprised Me
Real challenges, dead ends, things harder than expected.

## What I Learned
Skills/concepts gained that translate beyond this project.

## Connection to the Whole
How this phase connects to phases before and after.
```

### 13.3 ADR Template

Each `docs/adr/NNNN-*.md`:

```markdown
# ADR NNNN: [Title]

**Status:** Proposed | Accepted | Superseded by ADR-XXXX | Deprecated
**Decided:** YYYY-MM-DD
**Deciders:** [Solo / role(s)]

## Context
What problem are we solving? What constraints apply?

## Decision
What did we choose?

## Alternatives Considered
1. **Alternative A** — pros and cons, why rejected
2. **Alternative B** — same
3. **Alternative C** — same

## Consequences
- **Enables:** what becomes possible
- **Precludes:** what we can't do anymore
- **Costs:** ongoing burden or technical debt
- **Reversibility:** how hard to change later (1=easy, 5=very hard)

## Plain-English Summary
Two-paragraph explanation a non-technical reader can follow. Avoid jargon; if a term is unavoidable, link to the glossary.
```

### 13.4 Glossary Template

Each entry in `docs/glossary.md`:

```markdown
## TermName
**Category:** Database | Backend | Frontend | Infrastructure | Maritime | Compliance

**Plain definition.** What it is, in one or two sentences.

**Why it matters in this project.** How we use it, what role it plays.

**Related terms:** [list]
```

### 13.5 Build Swarm Documentation Maintainer Role

The Documentation Maintainer subagent (in `.claude/agents/doc-maintainer.md`) has explicit responsibilities:
- After each phase completes, produce the `docs/journey/NN-phase-X-*.md` file
- After each significant decision, produce a new `docs/adr/NNNN-*.md`
- Add new technical terms to glossary as code introduces them
- Maintain cross-links between phases, ADRs, and glossary
- Write everything for non-technical readability; if a sentence requires jargon, follow it with a parenthetical plain-English clarification

### 13.6 Public Surface

The public frontend includes a `JournalDrawer` component accessible from the About link, showing a timeline of phases and ADRs. This means the project documents itself publicly during portfolio review.

`/api/journal/phases`, `/api/journal/adrs`, `/api/journal/glossary` endpoints serve the data; `journal_indexer` job walks the markdown files hourly and updates the `journal_*` and `glossary_term` tables.

---

## 14. Backup and Disaster Recovery

### 14.1 Strategy

| Layer | Method | Cadence | Retention | Location |
|---|---|---|---|---|
| Postgres | `pg_dump` (custom format, compressed, gpg-encrypted) | Daily 03:30 CT | 7 daily, 4 weekly, 12 monthly | Backblaze B2 (~$0.005/GB/mo) |
| App config | tarball of `/etc/oceansx/` (without secrets) | Weekly | 4 weeks | Same |
| Secrets | Not in backup. Manual record in password manager. | — | — | — |

### 14.2 Restore Test

Monthly cron `pg_restore --list` against latest backup. Manual full-restore quarterly to scratch instance.

### 14.3 RTO / RPO

- RPO: 24 hours
- RTO: 4 hours

### 14.4 Disaster Recovery Runbook

Owned by Documentation Maintainer; lives in `docs/RUNBOOK.md`:
1. Provision new VPS (specs from §3.1)
2. Run setup playbook
3. Restore latest Postgres backup
4. Restore secrets manually
5. Update DNS
6. Verify health endpoints

---

## 15. Cost Projection

Monthly recurring costs at full V2 production:

| Item | Cost |
|---|---|
| VPS (Hetzner CPX31, 8 GB / 4 vCPU / 80 GB) | ~€16 (~$17) |
| Backblaze B2 backup storage (~10 GB) | ~$0.05 |
| Domain (amortized) | ~$1 |
| Anthropic API (4 agents) | ~$33 |
| Cloudflare (free tier) | $0 |
| RSS.app | per your subscription |
| OpenSanctions | $0 (free non-commercial) |
| Open-Meteo | $0 (free non-commercial) |
| MPA OceansX | per MPA terms |
| **Total estimate** | **~$51/month** (excluding RSS.app + MPA) |

Pre-VPS while still on laptop: **~$33/month** (Anthropic only).

---

## 16. Migration / Project Bootstrap Plan

V2 is a greenfield rewrite with no V1 data preserved. 9-week phased timeline (full-time ~5–6 weeks).

### 16.1 Phases

**Phase 0 — Foundation (week 1):**
- New repo `oceans-x-visualizer-v2`
- Postgres + TimescaleDB + PostGIS via Docker Compose
- Alembic initialized
- Skeleton FastAPI + React with TimeZoneSelector
- CI: GitHub Actions (pytest, vitest, alembic check, pip-audit, npm audit)
- `.claude/agents/` populated with all 9 Build Swarm role files
- `docs/journey/`, `docs/adr/`, `docs/glossary.md` initialized

**Phase 1 — Live tracking parity (week 2):**
- OceansX client (async port from V1)
- `vessel`, `vessel_*_history`, `position_live`, `position_archive`, `terminal_geom` schema
- `poll_positions` job at 15-min cadence with per-poll archive dedup
- SSE channel for position updates
- Live map with marker rendering
- Vessel detail panel
- Time zone display fixed

**Phase 2 — Macro and geospatial parity (week 3):**
- Port + terminal hierarchy with PostGIS polygons sourced from MPA's `ports-and-services` geospatial endpoint (area type); coverage gaps filled with point-radius approximations (1 km default) — gaps documented in an ADR
- Macro endpoints
- Geospatial overlays (PostGIS-backed)
- 24h dynamic timeline

**Phase 3 — News and entity extraction (week 4):**
- RSS.app integration (3 feeds, webhook with HMAC)
- Dictionary-based entity extraction
- News drawer with entity pills
- 90-day retention policy

**Phase 4 — OpenSanctions ingestion (week 5):**
- OpenSanctions client + FtM parser + projection
- Domain 2 (orgs full graph), Domain 5 (sanctions), Domain 6 (MoU detentions)
- IMO-exact auto-confirm matcher; review queue for everything else
- Sanctions UI tab + sanctioned banner
- Shadow Fleet tab + map filter + marker badges
- Approval queue endpoints + admin UI

**Phase 5 — Weather + risk scoring (week 6):**
- Open-Meteo client + hourly poll
- Anchorage dwell calc
- Risk Scorer (deterministic)
- Risk badges in UI

**Phase 6 — Intelligence layer (week 7):**
- Port-news with on-demand AI summaries
- New Arrivals tab
- Natural language search (graph-aware, 10/min limit)

**Phase 7 — Hardening (week 8):**
- Deterministic security (fail2ban, audit cron, allowlist)
- Backup automation
- Admin dashboard overhaul (DB Explorer + Stats tab)
- Documentation pass (full journal + ADRs + glossary)
- Attribution pages
- Public Journal Drawer

**Phase 8 — VPS deployment (week 9):**
- Provision VPS per §3
- Deploy via Docker Compose or systemd units
- Restore-test backups
- Cutover

### 16.2 Risk Items

| Risk | Mitigation |
|---|---|
| MPA OceansX API changes | Keep V1 mock fixtures; contract tests fail loudly on shape change |
| OpenSanctions FtM schema evolution | Raw payloads in `opensanctions_entity_raw`; projection layer rebuilt by migration if needed |
| OpenSanctions ID merges/splits | Track `referents`; treat any prior ID as still valid for matching |
| OFSI sunset already happened (Jan 2026) | OpenSanctions handled the migration upstream; we use new UK Sanctions List dataset |
| Agent cost overrun | Daily cost cap is hard-stop |
| TimescaleDB / PostGIS install issues | Use Timescale's official Docker image |
| Time zone bug regression | Explicit pytest tests for clamp + ISO 8601 + DST |
| RSS.app webhook abuse | HMAC per feed; rate limited; staging ingest before promotion |
| 15-min cadence feels too sluggish in UI | Add interpolation later (linear between two known points) without changing backend cadence |
| MPA's port/terminal polygons may be incomplete or imprecise | Inspect during Phase 2; fallback to point-radius (1 km default) for any terminal MPA doesn't cover or covers poorly; document gaps in an ADR; revisit hand-curation if anchorage dwell calculations produce noisy results |
| NL search depth-5 traversal causes slow queries on dense subgraphs | Recursive CTE with cycle detection; 5s asyncio timeout returns partial results with `truncated: true`; 10-min result cache; if persistent, add per-organization `subgraph_size` denormalized column for early bailout |

---

## 17. Open Items Deferred to Follow-Up Sessions

1. **Weather risk scoring formula.** All Open-Meteo variables stored; final formula deferred until V2 is operational and we can correlate.
2. **OpenSanctions delta-update migration** — if daily snapshot becomes too heavy.
3. **OAuth migration** when going public.
4. **Backup encryption key custody** — must not live on the VPS.
5. **Quick-action additions** discovered after a few weeks of operation.
6. **Continuous aggregates** for terminal congestion if real-time too expensive.
7. **Read replica** if multi-user concurrency happens.
8. **Specific GLiNER model selection** for entity extraction tier 2.
9. **Position interpolation** if 15-min cadence feels too jumpy.

---

## Appendix A — Decisions Locked

| # | Decision | Source |
|---|---|---|
| 1 | Postgres 16 + TimescaleDB + PostGIS replaces SQLite | Architectural |
| 2 | Alembic-managed migrations | Implied by Postgres |
| 3 | Greenfield repo; no V1 data migrated | User |
| 4 | Hetzner-class VPS, 8 GB / 4 vCPU / 80 GB | User |
| 5 | Singapore-only scope retained | User |
| 6 | All times stored UTC, served America/Chicago default, user-overridable | User |
| 7 | Two-swarm architecture | User |
| 8 | Operations agents write to staging only | User + safety |
| 9 | Agent observability mandatory | User |
| 10 | Sanctions delisting tracked SCD2 with "previously sanctioned" UI | User |
| 11 | News retention 90d; position archive 365d; position live 14d | Mixed |
| 12 | Risk components vector, hourly recompute, displayed with disclaimer | User |
| 13 | Map publicly accessible initially; OAuth gating later | User |
| 14 | Force-update only via admin dashboard | User |
| 15 | 24h dynamic timeline window, scrubber range fixed | User |
| 16 | "New vessel" = no position record in last 24h | User |
| 17 | Tiered entity extraction: dict → GLiNER → Claude | User |
| 18 | Position dedup: 100 m AND \|Δheading\| < 5° AND \|Δspeed\| < 0.5 kn | Recommended |
| 19 | Daily encrypted off-VPS Postgres backups (B2) | Recommended |
| 20 | Sanctions sourced exclusively from OpenSanctions | User implicit |
| 21 | OpenSanctions datasets: maritime export + Tokyo + Paris + Black Sea + Abuja | User |
| 22 | Daily full snapshot, SHA1-checked; bulk download not `/match` API | Architectural |
| 23 | Detention Parser eliminated; OpenSanctions Watcher handles all | Direct consequence |
| 24 | Open-Meteo: all variables stored, single grid point at 1.265°N 103.82°E, hourly | User |
| 25 | RSS.app: 3 feeds, topic-split | User |
| 26 | RSS.app webhook ingestion with HMAC; safety hourly poll | Architectural |
| 27 | Sanctions auto-confirm: only IMO-exact | User |
| 28 | Organization graph depth: full graph from OpenSanctions | User |
| 29 | Shadow Fleet visibility: prominent (tab + filter + badges) | User |
| 30 | Raw FtM payloads preserved in `opensanctions_entity_raw` | Architectural |
| 31 | Attribution: footer + `/about` + per-source credits | License compliance |
| 32 | License posture: strictly non-commercial, free tiers indefinite | User |
| 33 | Position polling: 15-minute cadence | User Round 4 |
| 34 | Position archive write: per-poll with dedup (replaces hourly job) | Direct consequence |
| 35 | Frontend update strategy: SSE push, no polling | Architectural |
| 36 | NL search: graph traversal supported, 10/min rate limit | User Round 4 |
| 37 | NL search default graph depth: 1 (direct relationships); max 2 | Architectural |
| 38 | Sentinel and Triage agents removed; security is deterministic only | User Round 4 |
| 39 | AI agent budget: ~$33/month full feature set (no Sentinel/Triage) | User Round 4 |
| 40 | Build Swarm = Claude Code subagents in `.claude/agents/` | Confirmed by capability |
| 41 | Admin dashboard: 5 tabs (Overview, Approvals, Ops Swarm, DB Explorer, Stats) | User Round 4 |
| 42 | DB Explorer: lazy-loaded, 50 rows/page, relationship navigation | User Round 4 |
| 43 | Project journal: phases + ADRs + glossary combination format | User Round 4 |
| 44 | Documentation Maintainer added as Build Swarm role | Direct consequence |
| 45 | OpenRouter possible for Operations Swarm (deferred); not for Build Swarm (Claude Code is Anthropic-locked) | User question |
| 46 | Terminal polygons sourced from MPA `ports-and-services` endpoint; point-radius fallback (1 km) for gaps | User Round 5 |
| 47 | Composite risk = tiered: max(sanctions, shadow_fleet) if either > 0; else 0.40·flag_mou + 0.30·age + 0.20·congestion + 0.10·weather | Best judgment per User Round 5 |
| 48 | Risk bands: 0–25 Low / 26–50 Medium / 51–75 High / 76–100 Critical; high-risk filter slider defaults to 50 | Direct consequence of #47 |
| 49 | NL search graph traversal: NL parser determines depth per query; default 5; cycle-detected recursive CTE; 5s timeout; 10-min result cache | User Round 5 |

---

*End of architecture plan. All decisions locked. Phase 0 ready for implementation.*
