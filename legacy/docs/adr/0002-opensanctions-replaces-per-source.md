# ADR 0002: OpenSanctions Replaces Per-Source Sanctions Parsing

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

OceansX V1 had no sanctions screening layer at all. V2 introduces sanctions matching as a headline feature. To do this, the system needs machine-readable data from the major sanctions authorities: OFAC (the U.S. Treasury's Office of Foreign Assets Control), the UK Sanctions List, the European Union Council, the United Nations Security Council, and the four regional Port State Control memoranda (Tokyo MoU, Paris MoU, Black Sea MoU, and Abuja MoU).

Each of these authorities publishes their data independently, in different formats, on different update schedules, with different field names and structures. Building and maintaining parsers for each source is a significant ongoing engineering burden — each government publisher can and does change their format without notice.

Additionally, sanctions data requires not just parsing but entity resolution: the same company or vessel can appear under different names across different lists, and individual records need to be linked across sources to build a coherent compliance picture.

The key question: should we scrape each source independently, use OpenSanctions, or pay for a commercial sanctions data API?

---

## Decision

Use **OpenSanctions daily bulk download** as the sole source for all sanctions and Port State Control detention data. Download the following five datasets daily:

1. Maritime export (CSV) — all sanctioned vessels and IMO-bearing organizations across all authorities
2. `tokyo_mou` (FtM JSON) — Asia-Pacific Port State Control detentions
3. `paris_mou` (FtM JSON) — European Port State Control detentions
4. `bs_mou` (FtM JSON) — Black Sea Port State Control detentions
5. `abuja_mou` (FtM JSON) — West and Central Africa Port State Control detentions

Each dataset is SHA1-checked (a fingerprint comparison) against the last downloaded version; unchanged datasets are skipped to minimize bandwidth. Combined daily payload is under 25 MB. License: free for non-commercial use (CC-BY 4.0), which matches the project's strictly non-commercial posture.

We use the bulk download approach rather than OpenSanctions' `/match` API endpoint. This means all matching logic runs locally, with no runtime dependency on OpenSanctions' servers being available.

---

## Alternatives Considered

1. **Scrape each source independently (OFAC, OFSI/UK, EU, UN, and four MoUs)** — Complete control over data pipeline; no third-party dependency. Rejected because this requires eight separate parsers, eight separate monitoring jobs, and eight separate points of failure when publishers change their formats. Government agencies change their CSV/XML schemas without versioning or notice. The ongoing maintenance burden is disproportionate for a portfolio project, and entity resolution across sources (linking the same vessel across OFAC and EU lists, for example) would require significant additional engineering.

2. **Commercial sanctions API (e.g., Dow Jones Risk & Compliance, World-Check, Refinitiv)** — Enterprise-grade data quality, legal indemnification, real-time updates. Rejected because pricing starts at hundreds or thousands of dollars per month, which is incompatible with the project's ~$51/month total cost target and its non-commercial license posture. These APIs are designed for financial institutions with compliance obligations, not portfolio projects.

3. **OpenSanctions `/match` API** — Simpler integration, no local data management. Rejected in favor of bulk download because it introduces a runtime dependency — if OpenSanctions' servers are unavailable, live matching stops. With bulk download and local matching, the system continues operating from the last downloaded snapshot indefinitely. Bulk also allows us to preserve the raw FtM JSON payloads, enabling schema changes to be handled by re-projecting stored data rather than re-downloading.

---

## Consequences

- **Enables:** Eight sanctions/detention sources covered by a single pipeline and client; local matching with no runtime external dependency; raw FtM payload preservation for future schema evolution; free non-commercial use under CC-BY 4.0; shadow fleet detection via the `mare.shadow` OpenSanctions tag.
- **Precludes:** Real-time sanctions updates (bulk is daily; a vessel sanctioned at 11am may not appear in our system until the next 4am run). This is acceptable for a compliance intelligence dashboard, not a trading compliance system.
- **Costs:** Daily download and processing job (OpenSanctions Watcher agent). Local storage of raw FtM payloads in `opensanctions_entity_raw` table. Attribution required on all public-facing pages: "Sanctions: OpenSanctions.org".
- **Reversibility:** 3 (moderate). The FtM parsing layer (`services/opensanctions_ingest.py`) is the coupling point. Switching sources would require rewriting that parser and the projection logic, but the downstream relational schema could survive. Raw payloads stored locally reduce the risk of losing data if OpenSanctions changes.

---

## Plain-English Summary

To run sanctions checks on vessels, we need access to the lists of sanctioned entities published by the U.S. Treasury, the UK, the EU, the UN, and the four regional maritime inspection authorities. Each of these publishers produces data in a different format, updated on a different schedule, with different field names. Building a custom parser for each would take weeks and require constant maintenance as governments update their formats.

OpenSanctions is an open-source project that has already done this work. It aggregates all of these sources, resolves duplicate entries, and publishes a clean, standardized daily download in a single format — for free, for non-commercial use. We download this data once a day (the whole file is under 25 MB), run matching locally against our vessel database, and never depend on OpenSanctions being online for live queries. It covers everything we need, costs nothing, and eliminates eight separate maintenance headaches.
