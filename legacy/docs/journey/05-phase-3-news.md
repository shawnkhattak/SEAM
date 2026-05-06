# Phase 3: RSS News and Entity-Aware Articles

**Week:** 4  
**Status:** Complete  
**Phase scope:** RSS.app integration, webhook ingestion with HMAC verification, entity-aware news with clickable tags, 90-day retention policy.

---

## What Was Built

Phase 3 added the first intelligence layer to OceansX V2 — a live maritime news feed where every article is automatically annotated with the vessels and ports it mentions. A user looking at a vessel on the map can open the News drawer and see every recent article that names that vessel, its operator, or a port it frequently visits.

The phase delivered:

- **Four new database tables** — `news_feed`, `news_item`, `news_entity_mention`, `news_summary` — forming the backbone of the news intelligence domain.
- **A webhook ingestion endpoint** — `POST /api/news/ingest/{feed_slot}` — that receives article pushes from RSS.app and verifies their integrity before storing them.
- **An RSS poll fallback** — an hourly APScheduler job that polls each feed's URL via feedparser in case a webhook push was missed.
- **Dictionary-based entity extraction** — every ingested article is scanned against a live dictionary of all vessel names and port names in the database. Matches are stored as `news_entity_mention` rows.
- **A 90-day retention policy** — a daily pruning job deletes articles older than 90 days, preventing unbounded table growth.
- **A news drawer on the frontend** — a slide-in panel listing recent articles with coloured entity tag pills. Each pill is clickable (Phase 6 will use them for graph traversal; they are no-ops in Phase 3).

---

## The Feed Architecture

RSS.app operates as a managed RSS aggregator. Three feed slots were configured in the architecture plan: each slot has a URL (the feed's RSS endpoint) and an HMAC secret used to verify webhook pushes.

The feed slot number is embedded in the webhook URL (`/api/news/ingest/1`, `/api/news/ingest/2`, `/api/news/ingest/3`), which lets the server look up the correct HMAC secret for verification without requiring any additional headers to identify the source.

Feed slot records live in the `news_feed` table, which serves as a registry. The actual HMAC secrets stay in environment variables and are never written to the database — the database only records whether a slot is active and what its human-readable name and URL are.

---

## The Webhook Safety Rule

The single most important correctness constraint in Phase 3 is that HMAC verification must run against the raw request bytes — not against a re-serialised Python dictionary.

This distinction matters because JSON serialisation is not deterministic. If the server received a payload, parsed it to a dict, and then re-serialised it before computing the HMAC, the resulting bytes might differ from the original in key ordering, whitespace, or Unicode encoding. The HMAC comparison would fail even for a legitimate request.

The implementation reads `await request.body()` once and passes those bytes directly to `hmac.new(secret, raw_body, sha256).hexdigest()`. The parsed payload is derived separately from the same raw bytes afterward. This pattern is enforced in a single function, `verify_hmac`, which takes `raw_body: bytes` and makes it structurally impossible to accidentally pass the wrong thing.

---

## Entity Extraction: Dictionary Tier Only

The architecture defines a three-tier entity extraction pipeline: dictionary matching first, then GLiNER (a local AI model) for cases where the dictionary misses entities, then Claude Haiku only for low-confidence GLiNER results (see ADR-0009). Phase 3 implements only the first tier.

The dictionary is built at extraction time from three sources:

1. All vessel names in the `vessel` table.
2. All port names in the `port` table.
3. All port aliases in the `port_alias` table.

Matching uses word-boundary regular expressions — the term must be surrounded by word boundaries (`\b...\b`) so a search for "Idemitsu" does not match inside "Idemitsu Maru". Terms shorter than four characters are excluded to avoid false positives from short abbreviations. Matching is case-insensitive but the matched text is preserved as it appeared in the article.

The port alias table is included in the dictionary now, in Phase 3, even though it is empty until Phase 5 populates it. This is a deliberate design choice: the extraction function does not need to be modified in Phase 5 — it simply finds more entries in the dictionary automatically once the data arrives.

---

## Payload Shape Tolerance

RSS.app's webhook payload format is not strictly documented. In practice it uses a `{"items": [...]}` wrapper, but the implementation also handles a bare list at the top level and checks for both `items` and `entries` as wrapper keys. Individual item fields are resolved with multiple fallback keys (`url` / `link` / `guid` for URL; `content_text` / `content` / `summary` / `description` for body).

This tolerance was designed in from the start, not added after a failure. The lesson from V1 was that external data sources rarely behave exactly as documented, and defensive parsing costs almost nothing while saving debugging time later.

---

## URL-Hash Deduplication

Articles are deduplicated by URL. Before inserting a new article, the service computes `SHA-256(url)` and checks whether a row with that hash already exists in `news_item`. If it does, the article is silently skipped. This means the same article pushed twice by a webhook (or returned by both the webhook and the RSS poll) is stored exactly once.

SHA-256 was chosen over a plain URL unique constraint because URL strings can be long and variable, and a hash index on a fixed 64-character string is smaller and faster than a unique index on a 500-character text column.

---

## Retention Policy

The `_job_prune_history` scheduler job runs daily at 02:00 America/Chicago and deletes `news_item` rows older than 90 days. Because `news_entity_mention` rows reference `news_item` with `ON DELETE CASCADE`, the mention rows are removed automatically.

The prune job was designed as a shared job from the start — future phases (Phase 5 for sanctions data, Phase 6 for summary cost management) will add their own cleanup logic to the same job function rather than creating new jobs. This keeps the scheduler job count manageable and makes the nightly maintenance window a single predictable event.

---

## The Frontend: News Drawer

The news drawer (`NewsDrawer.tsx`) opens from a "News" toggle button in the top-right corner of the map. It is a left-anchored slide-in panel (outside `MapContainer`, so Leaflet never intercepts its events) that lists the 50 most recent articles.

Each article shows:
- Title as a link to the original source.
- Relative time ("3h ago") computed from `published_at_utc`.
- Entity tag pills (`EntityTagPills.tsx`) — colour-coded badges for each entity mentioned in the article. Vessel tags are blue; port tags are green. Clicking a pill is wired to a handler that logs the entity — in Phase 6 it will open the vessel detail or port panel and filter the news drawer to that entity.

The drawer accepts optional filter props (`filterEntityType`, `filterEntityRefId`) so that in future phases it can be opened pre-filtered to a specific vessel or port. The query key includes the filter values, so React Query treats filtered and unfiltered views as separate cache entries.

---

## What Was Harder Than Expected

**Timestamp parsing.** RSS feeds use RFC 2822 timestamps (`Fri, 01 May 2026 06:00:00 +0000`); JSON:Feed uses ISO 8601; some sources use neither. The `_parse_published` function tries RFC 2822 first (using Python's `email.utils.parsedate_to_datetime`), then ISO 8601, then falls back to "now". The `clamp_future` utility from `app/utils/timezone.py` is applied after parsing to prevent future-dated articles from appearing with incorrect relative timestamps in the UI.

**Entity extraction timing.** Webhook-pushed articles are extracted inline during the request, so the article arrives in the database with `extraction_status = "done"` and entity mentions already written. RSS-polled articles take the same inline path. The `_job_extract_entities` scheduler job (runs at :20 each hour) handles any articles that somehow remained in `pending` state — for example, if an extraction failed with an exception, the status is set to `error` so it is not retried in an infinite loop.

---

## What Was Deferred

Per the architecture plan, Phase 3 does not include:
- GLiNER or Claude Haiku entity extraction tiers (Phase 6).
- AI-generated article summaries (Phase 6 — the `news_summary` table exists but is empty).
- The `port_news_link` materialised view (Phase 6).
- Clickable entity tag navigation (Phase 6 — clicking a pill logs to console only).
- Sanctions and shadow fleet entity types in extraction (Phase 4 adds those entities to the database, at which point they are picked up automatically by the dictionary).

---

## Decisions Made in This Phase

- ADR-0019: HMAC verification against raw request bytes.
- ADR-0020: Dictionary-only entity extraction in Phase 3, three-tier pipeline deferred.
- ADR-0021: URL SHA-256 hash deduplication.
- ADR-0022: `extraction_status` as VARCHAR with CHECK constraint, not Postgres ENUM.
