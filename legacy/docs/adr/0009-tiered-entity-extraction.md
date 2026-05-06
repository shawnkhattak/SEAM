# ADR 0009: Tiered Entity Extraction Pipeline

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

One of OceansX V2's headline features is entity-aware news: news articles are processed to identify mentions of specific vessels, organizations, ports, and terminals, then tagged with clickable links that filter the live map. This entity extraction must run on every ingested news article, potentially dozens per day.

The question is what technical approach to use for extracting these entity mentions from free-form text, balancing accuracy, cost, and latency.

Three options were considered:

1. **Pure Claude API (LLM-only extraction)** — Send every article to a Claude model and ask it to identify entity mentions. High accuracy, handles unlisted entities, understands context. But at the volume of news articles this project ingests, the API cost could reach $20/month or more just for entity extraction — the single largest AI cost in the system.

2. **Dictionary matching only** — Build a lookup table from the database (vessel names from `vessel_name_history`, organization aliases from `organization_alias`, port names from `port_alias`) and scan each article for exact or near-exact matches. Near-zero cost, near-instant, no API dependency. But misses entities not yet in our database — newly arrived vessels, organizations mentioned before OpenSanctions has processed them.

3. **GLiNER (a local named entity recognition model)** — An open-source machine learning model that runs locally on the server without any API calls. GLiNER identifies named entities (person names, organization names, location names, etc.) in text without needing a lookup table. Free to run, reasonably accurate, but requires server memory and produces occasional low-confidence results that need follow-up.

---

## Decision

Use a **tiered pipeline** that applies the cheapest method first and escalates only when necessary:

**Tier 1: Dictionary matching** — Built automatically from the live database (vessel names, organization aliases, port and terminal names). Runs first. If the article contains terms matching known entities with sufficient confidence, extraction completes without any AI call. Cost: $0. Latency: milliseconds.

**Tier 2: GLiNER (local NER model)** — Runs on articles (or article segments) that Tier 1 did not cover. GLiNER identifies named entities in the remaining text. If GLiNER returns high-confidence results, extraction completes. Cost: $0 (local compute). Latency: seconds.

**Tier 3: Claude Haiku 4.5** — Runs only on entity mentions where GLiNER returned low confidence. Haiku (the smallest, fastest, cheapest Claude model) reviews those specific mentions and makes a final determination. Cost: fractions of a cent per call, but used sparingly. Latency: 1–2 seconds per call.

Because OpenSanctions populates our database with a rich set of vessel names, organization aliases, and their variants, the dictionary tier is expected to cover the majority of sanctions- and compliance-related entity mentions. The tiers are logged: each extracted mention records which method was used (`extraction_method` column), enabling the Stats tab to show what fraction of extractions hit each tier.

---

## Alternatives Considered

1. **Claude API only (Opus or Sonnet for all articles)** — Maximum accuracy; handles novel entities; understands nuanced references. Rejected because the Entity Extractor is already the most expensive Operations Swarm agent at approximately $20/month with the tiered approach. Using a larger model for every article would push costs significantly higher and is disproportionate for a portfolio project with a $33/month total AI budget.

2. **Dictionary only** — Zero cost; no AI dependency; fully deterministic. Rejected as the sole approach because maritime news frequently mentions vessels, companies, and organizations before they are in our database. A newly flagged shadow fleet vessel mentioned in a news article one day before the OpenSanctions pull would produce zero matches. The dictionary is the right first tier, not the only tier.

3. **GLiNER only (no dictionary, no Claude fallback)** — Local, free, handles novel entities. Rejected as the sole approach because GLiNER requires non-trivial server memory, has lower precision than dictionary matching for entities already in the database, and cannot produce the structured, database-linked output (e.g., "this mention refers to vessel IMO 9876543") that the dictionary tier provides directly.

---

## Consequences

- **Enables:** Entity extraction that is fast and free for the common case (known entities); novel entity detection for the uncommon case; per-mention audit trail showing extraction method and confidence; a Stats tab visualization showing tier distribution over time.
- **Precludes:** Any guarantee that all entity mentions in news articles will be detected. The tiered approach is probabilistic — it is better than any single approach at a given cost point, but not perfect.
- **Costs:** GLiNER requires a specific model to be selected and loaded on the server (specific model selection is deferred to implementation; see Open Items in the architecture doc). Server memory usage for the GLiNER model process. The `extraction_method` column and confidence logging add a small overhead to each extraction.
- **Reversibility:** 2 (easy per tier). Individual tiers can be disabled or reordered without affecting the others. The `extraction_method` logging makes it straightforward to evaluate whether GLiNER is adding value or just adding latency.

---

## Plain-English Summary

Every news article ingested by OceansX V2 needs to be scanned for mentions of specific vessels, companies, and ports — so those mentions can become clickable links on the map. Doing this with an AI model for every article would be the most accurate approach but would also be the most expensive, quickly consuming a large fraction of the monthly AI budget.

The solution is a three-tier system that works from cheapest to most expensive. First, we check whether any terms in the article match names already in our database — vessels we are tracking, organizations we know about, ports and terminals. This is dictionary matching, and it costs nothing and runs in milliseconds. If that does not find everything, we run a local AI model (GLiNER) on the server at no API cost. Only if GLiNER produces uncertain results do we call the Claude API — and then only the smallest, cheapest available model, and only for the specific uncertain mentions, not the whole article. This design keeps AI costs to approximately $20/month for the entity extraction function while maintaining meaningful accuracy across novel and known entities.
