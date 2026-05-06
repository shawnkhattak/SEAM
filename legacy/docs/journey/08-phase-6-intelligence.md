# Phase 6: Intelligence Layer — AI Summaries, New Arrivals, and Natural-Language Search

**Phase:** 6 (6a data plumbing + 6b UI)
**Week:** 7
**Status:** Complete

---

## What Was Built

Phase 6 adds three intelligence features to OceansX: on-demand AI-generated news summaries powered by Claude Haiku, a new-arrivals panel showing vessels that entered Singapore waters in the last 24 hours, and a natural-language search bar that translates plain-English queries into structured database filters.

### 6a: Data Plumbing

**Migration 0007** adds `tokens_in` and `tokens_out` columns to the existing `news_summary` table. These record how many tokens each AI summary consumed, both for cost tracking and for any future rate-limit or budget logic.

**Anthropic client** (`app/clients/anthropic_client.py`) is a thin, mock-aware wrapper around the Anthropic SDK. When `anthropic_mock_mode = True` in config (the default), it reads a local JSON fixture instead of calling the live API. This lets the full feature work without an API key in development. The live path calls `claude-haiku-4-5-20251001` and returns `(text, tokens_in, tokens_out)`.

**News summarizer** (`app/services/news_summarizer.py`) is idempotent: it checks whether a summary already exists for a given `news_id` before calling the LLM. If the summary exists, it is returned immediately. If not, Haiku is called with a maritime-focused system prompt and the result is stored. The endpoint calls `session.flush()` (not `commit()`) to let the router own the transaction boundary.

**New-arrivals endpoint** (`GET /api/vessels/new-arrivals?hours=24`) returns vessels where `first_observed_at >= now() - N hours`, ordered by newest first, capped at 100 rows. The `hours` parameter accepts 1–168 (one week).

**SearchFilterSpec** (`app/schemas.py`) is a Pydantic model with `extra="forbid"` — any field the LLM hallucinates that is not in the schema will raise a `ValidationError` before it can contaminate the query. The 12 filter fields cover the main maritime compliance use cases: flag, vessel type, sanctions status, shadow fleet, risk score range, org-connectivity, arrival recency, age, and tonnage.

**NL→SQL translator** (`app/services/nl_search.py`) is a pure function `spec_to_query(spec)` that takes a `SearchFilterSpec` and returns a SQLAlchemy `Select`. It has no side effects and needs no database, which makes it straightforward to unit-test.

**Recursive CTE** (`_sanctioned_org_imos_cte()`) implements the `connected_to_sanctioned_org` filter. It traverses the vessel–organization graph: starting from organizations with a `sanction%` topic, it expands through `vessel_organization_link` to find all IMOs reachable within 3 hops. Cycle detection is enforced by an `ARRAY`-tracked `visited_imos` list: any IMO already in the array is excluded from further expansion. The depth cap (`array_length < 3`) prevents runaway traversal on densely connected ownership graphs.

**NL search endpoint** (`POST /api/search/nl`) rate-limits to 10 requests per minute, enforces a 5-second `asyncio.wait_for` timeout on the LLM parse call, and caches results for 10 minutes keyed on the SHA-256 hash of the *parsed spec* (not the raw query string). Two identical queries worded differently will share a cache entry if they parse to the same filter.

### 6b: UI

**NewsDrawer** gains a per-article "Summary" button with a sparkle icon. On first click, it calls `POST /api/news/{id}/summarize` via a `useMutation`. The summary appears inline below the article in a slightly highlighted box. A second click toggles the summary off; the result is held in component state so subsequent toggles cost no API call.

**NewArrivalsDrawer** is a left-side slide-in panel (same position as NewsDrawer, opened with a dedicated "Arrivals" button). Each vessel card shows name, IMO, flag, type, first-observed time, and compliance badges (shadow fleet, sanctioned). Clicking any card selects the vessel on the map and opens the detail panel.

**SearchBar** is a centered overlay input that appears when the "Search" button is clicked. It accepts free-text natural-language queries and calls `POST /api/search/nl` on Enter. Results appear in a scrollable list below the input. Each result shows vessel name, IMO, flag, type, compliance badges, and the active risk badge if a score exists. Clicking a result selects the vessel on the map. A "spec summary" row shows the parsed filter as pill tags (e.g. "Tanker", "Sanctioned", "Risk ≥ 50") so the user can see what the AI understood their query to mean.

The right-side button column in the map now has five buttons: Layers, News, Arrivals, Shadow, Risk, Search — each toggling its respective panel.

---

## Design Decisions

**Why Haiku, not Sonnet, for summarization.**
Summaries are 2–3 sentences from a short news article. Haiku handles this comfortably at a fraction of the cost of Sonnet and with lower latency. The task does not require deep reasoning.

**Why mock mode is the default.**
The full intelligence feature works without an Anthropic API key. This means new developers can run the app, and CI runs without live API calls. Flipping `anthropic_mock_mode = False` in the environment enables live mode.

**Why the NL search cache key is the parsed spec, not the raw query.**
"Sanctioned tankers" and "tankers that are sanctioned" parse to identical `SearchFilterSpec` objects. Keying on the spec means these share a cache entry, halving the database hit rate for common queries.

**Why `extra="forbid"` on SearchFilterSpec.**
The LLM might invent a field that looks plausible (e.g. `port_name`) but has no backing implementation. `extra="forbid"` turns this into an immediate `ValidationError` at the API layer rather than silently ignoring the field, which would confuse the user ("why didn't my port filter work?").

**Why 5 seconds for the LLM timeout.**
Haiku is fast. A 5-second timeout is generous for a 256-token response. If Haiku takes longer than 5 seconds, something is wrong with the API or the network, and the user should see an error rather than a hanging UI.

---

## Files Added or Changed

**New backend files:**
- `app/alembic/versions/0007_phase6a_intelligence.py` — ALTER news_summary ADD tokens_in, tokens_out
- `app/clients/anthropic_client.py` — mock-aware Haiku wrapper
- `app/services/news_summarizer.py` — idempotent summarize-and-cache
- `app/services/nl_search.py` — SearchFilterSpec→SQL translator, recursive CTE, parse + execute
- `app/routers/search.py` — POST /api/search/nl (rate limited, timeout, cached)
- `app/mocks/haiku_summary_response.json` — mock fixture for news summaries
- `app/mocks/haiku_nl_parse_response.json` — mock fixture for NL parse
- `tests/test_nl_search.py` — 20 unit tests (spec validation, cache key, query builder, CTE)

**Modified backend files:**
- `app/config.py` — added `anthropic_mock_mode: bool = True`
- `app/models.py` — NewsSummary extended with tokens_in, tokens_out
- `app/schemas.py` — added NewsSummaryResponse, SearchFilterSpec, NlSearchRequest, NlSearchResult; VesselDetail extended with first_observed_at
- `app/routers/news.py` — POST /api/news/{news_id}/summarize
- `app/routers/vessels.py` — GET /api/vessels/new-arrivals; first_observed_at in new_arrivals response
- `app/main.py` — search router registered

**New frontend files:**
- `frontend/src/api/intelligence.ts` — fetchNewsSummary, fetchNewArrivals, fetchNlSearch
- `frontend/src/components/NewArrivalsDrawer.tsx` — 24h arrival list with compliance badges
- `frontend/src/components/SearchBar.tsx` — NL search overlay with spec pill summary

**Modified frontend files:**
- `frontend/src/types/index.ts` — VesselDetail extended with first_observed_at; NewsSummaryResponse, SearchFilterSpec, NlSearchResult types added
- `frontend/src/components/NewsDrawer.tsx` — per-article summarize button with inline summary display
- `frontend/src/components/LiveMap.tsx` — Arrivals and Search buttons; NewArrivalsDrawer and SearchBar wired in; button column extended from 4 to 6 entries

---

## What Was Deferred

- Risk leaderboard tab in the main UI (Phase 7 admin dashboard)
- Weather score formula (congestion and weather scores remain hardcoded at 0.0)
- Org-to-org relationship edges in the sanctions graph (not yet in the data model)
- Search result highlighting on the map (vessels found by NL search are selectable but not visually distinguished from unpinned vessels)
