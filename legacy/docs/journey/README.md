# Project Journey

This folder contains the phase-by-phase narrative of building OceansX V2 — a maritime compliance and intelligence dashboard for Singapore waters. Each document covers one phase or one pre-implementation topic: what was built, what decisions were made, what was harder than expected, and what was learned.

The documents are written for a non-technical audience. Technical terms are followed by plain-English parenthetical explanations where they first appear. The goal is that anyone — engineer, recruiter, executive, or curious observer — can read these files and understand not just what was built, but why each choice was made.

---

## The Story Arc

OceansX V1 was a live vessel tracker: an interactive map showing ships in Singapore waters, updated every few minutes, built on a simple file-based database. It worked, but it only answered one question: "where are the ships?" The compliance questions — is this vessel sanctioned? is it a shadow fleet tanker? does it have a detention history? who actually owns it? — had no answers at all.

V2 reframes the entire product. The new question is not "where are the ships?" but "which of these ships should I be paying attention to, and why?" Answering that requires sanctions data, shadow fleet tracking, Port State Control inspection records, organizational ownership graphs, entity-aware news, and risk scoring — all matched against live vessel positions in Singapore waters, updated every 15 minutes.

The build follows a nine-week phased plan produced before a single line of code was written, through a structured architecture conversation that locked 49 decisions, designed 12 database domains, and defined the role of every AI agent in the system. This journal documents that process in full, from the planning conversation through to deployment.

---

## Documents in This Folder

| File | Status | Summary |
|---|---|---|
| [00-the-problem.md](./00-the-problem.md) | Complete | The maritime compliance gap V2 addresses, V1's limitations, and why this matters. |
| [01-planning-process.md](./01-planning-process.md) | Complete | How a structured AI architecture conversation produced a 49-decision locked plan before any code was written. |
| [02-phase-0-foundation.md](./02-phase-0-foundation.md) | Complete | Week 1: Postgres + TimescaleDB + PostGIS, Alembic, FastAPI skeleton, React skeleton, 9 Build Swarm agent files, and CI. |
| [03-phase-1-live-tracking.md](./03-phase-1-live-tracking.md) | Complete | Week 2: Live vessel positions, the MPA client, 15-minute polling, SSE push, and the Leaflet map. |
| [04-phase-2-macro-geospatial.md](./04-phase-2-macro-geospatial.md) | Complete | Week 3: Port and terminal hierarchy, PostGIS polygons, macro endpoints, and the 24-hour timeline scrubber. |
| [05-phase-3-news.md](./05-phase-3-news.md) | Complete | Week 4: RSS.app integration, webhook ingestion with HMAC verification, and entity-aware news with clickable tags. |
| [06-phase-4a-opensanctions.md](./06-phase-4a-opensanctions.md) | Complete | Week 5: OpenSanctions ingestion, IMO-exact sanctions matching (ADR-0005), shadow fleet derivation, and entity extraction expanded to organizations. |
| [06b-phase-4b-sanctions-ui.md](./06b-phase-4b-sanctions-ui.md) | Complete | Week 5: Sanctions badges on map markers, shadow fleet filter, compliance section in vessel panel, admin review queue endpoints. |
| [07-phase-5a-weather-risk-data.md](./07-phase-5a-weather-risk-data.md) | Complete | Week 6: Open-Meteo client, anchorage dwell, deterministic risk scoring engine + 25 unit tests (data plumbing only). |
| [07b-phase-5b-weather-risk-ui.md](./07b-phase-5b-weather-risk-ui.md) | Complete | Week 6: Risk API endpoints, RiskBadge component, VesselDetailPanel risk section, high-risk filter slider. |
| [08-phase-6-intelligence.md](./08-phase-6-intelligence.md) | Complete | Week 7: On-demand AI news summaries (Haiku), new arrivals drawer, NL search with recursive CTE org-graph traversal. |
| [09-phase-7-hardening.md](./09-phase-7-hardening.md) | Complete | Week 8: Security hardening, journal/admin APIs, SEAM frontend and admin dashboard overhaul, local dev launcher, and practical documentation pass. |
| 10-phase-8-deployment.md | Upcoming | Week 9: VPS provisioning, Docker deployment, backup restore testing, and cutover. |
| 11-retrospective.md | Upcoming | Post-launch: what worked, what did not, what would be done differently. |

---

## Related Resources

- **Architecture Decision Records:** [docs/adr/](../adr/README.md) — detailed reasoning for each major technical choice.
- **Glossary:** [docs/glossary.md](../glossary.md) — plain-English definitions for every technical term used in the project.
- **Project Guide:** [docs/PROJECT_GUIDE.md](../PROJECT_GUIDE.md) — simple day-to-day guide for running, debugging, and extending the app.
- **Architecture Plan:** [oceansx-v2-architecture.md](../../oceansx-v2-architecture.md) — the full locked architecture document produced in the planning phase.
