# ADR 0020: Dictionary-Only Entity Extraction in Phase 3

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 3

## Context

ADR-0009 defined a three-tier entity extraction pipeline:
1. Dictionary matching (exact, word-boundary regex against known vessel and port names).
2. GLiNER (a local AI model) for entities the dictionary misses.
3. Claude Haiku for low-confidence GLiNER results.

The question for Phase 3 is: how much of this pipeline should be implemented now?

## Decision

Implement only Tier 1 (dictionary matching) in Phase 3. GLiNER and Haiku tiers are deferred to Phase 6.

The dictionary is built from:
- All vessel names in the `vessel` table (min 4 characters).
- All port names in the `port` table (min 4 characters).
- All port aliases in the `port_alias` table (min 4 characters, empty until Phase 5 seeds them).

Matching uses `re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)`. The `port_alias` table is included in the dictionary now — not in Phase 5 — so the extraction function requires no modification when Phase 5 populates that table.

## Alternatives Considered

**Implement all three tiers in Phase 3.** Maximum extraction quality from day one. Rejected because GLiNER requires model download and GPU memory management, and Haiku adds per-call cost and latency. Neither is needed until the dictionary has demonstrably low recall, which requires production traffic data that does not yet exist.

**Dictionary-only, no port aliases.** Simpler Phase 3 scope. Rejected because the cost of including the alias table join is zero (the table is empty), and including it now avoids a code change in Phase 5.

**Skip entity extraction entirely in Phase 3.** Deliver only the ingestion pipeline; add extraction in Phase 4 or 5. Rejected because entity-tagged articles are a primary user value proposition — the UI "clickable entity pills" feature requires extraction to be present at launch.

## Consequences

**Enables:**
- Entity-tagged news articles available from first ingestion, with no external API calls.
- Port alias entities auto-activated when Phase 5 populates `port_alias`, with no code change.
- Phase 6 can add GLiNER tier by wrapping the existing extraction path, not replacing it.

**Costs:**
- Entities not in the dictionary (e.g., company names, person names, newly-named vessels not yet in `vessel`) are missed.
- Dictionary recall degrades if vessel names are abbreviated or misspelled in articles.

**Reversibility:** 5 of 5. The extraction function is additive — later tiers are appended to the pipeline, not substituted.

## Plain-English Summary

The system automatically reads every incoming news article and looks for the names of known vessels and ports. In Phase 3, it uses only a simple word-for-word lookup — if a vessel named "Idemitsu Maru" is in the database, the system finds that exact phrase in articles and tags it. Shorter names (under four letters) are excluded to avoid false matches.

This simple approach is fast, free, and good enough for a first version. A smarter approach using AI models — which can recognise entities even when they are referred to differently — is designed and will be added in Phase 6, once production traffic reveals which types of entities the simple lookup misses most often. The architecture is already prepared for this: the Phase 6 tiers wrap the Phase 3 tier rather than replacing it.
