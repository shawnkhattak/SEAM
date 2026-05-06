# ADR 0011: UTC Storage with America/Chicago Default Display

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

OceansX V1 had a bug: news articles published with a future-dated timestamp (some RSS feeds publish articles with timestamps slightly ahead of actual clock time) displayed as "in about X hours" in the frontend — a nonsensical label for a news item. The root cause was that V1 stored timestamps without enforcing UTC, processed them inconsistently, and did not guard against future-dated inputs.

V2 handles a wide range of timestamp sources, each with their own quirks:
- MPA API: vessel position timestamps (generally reliable)
- OpenSanctions: sanctions effective dates and MoU inspection dates (occasionally future-dated or missing timezone offsets)
- RSS.app news feeds: article publication timestamps (publishers sometimes future-date articles; RSS date formats vary widely)
- Internal events: scheduler jobs, agent runs, audit log entries

The developer's local timezone is America/Chicago. The maritime data is Singapore-relevant (Asia/Singapore, UTC+8). The system must store, serve, and display times correctly across all these contexts without confusing any of them.

---

## Decision

A four-part timezone strategy:

1. **Storage:** All timestamps stored as Postgres `TIMESTAMPTZ` (timestamp with timezone) — always UTC internally. No `TIMESTAMP WITHOUT TIME ZONE` columns anywhere in the schema.

2. **Ingestion clamp:** Every external timestamp passes through `clamp_future(ts, now, tolerance=5 minutes)`. If the timestamp is more than 5 minutes in the future relative to `now()`, it is replaced with `now()` and the `was_clamped = TRUE` flag is set on the row. This permanently prevents any "in X hours" display for news articles. Applied to news publication dates, sanctions effective dates, and MoU inspection dates.

3. **API serialization:** All timestamp fields in API responses are serialized as ISO 8601 (a standard timestamp format — e.g., `2026-04-30T14:30:00+00:00`) with an explicit `+00:00` UTC offset. Clients know unambiguously that the time is UTC.

4. **Frontend display:** Default display timezone is `America/Chicago` using Luxon (a JavaScript date/time library with full DST awareness — DST, or Daylight Saving Time, is the seasonal clock change). Users can override to UTC, Asia/Singapore, or their browser's detected local timezone via a persistent session dropdown (`TimeZoneSelector` component). The footer always shows the current active timezone abbreviation (CDT, CST, SGT, UTC).

Relative time labels ("X hours ago") are computed against the clamped UTC timestamp and `now()` in the selected timezone. Because all stored times are UTC and all future-dated inputs are clamped to `now()`, a "in X hours" display is structurally impossible.

---

## Alternatives Considered

1. **Store in Asia/Singapore (UTC+8) throughout** — Data is Singapore-relevant; storing in Singapore time seems natural. Rejected because mixing UTC+8 storage with external timestamps in other timezones creates conversion complexity at ingestion. Postgres's `TIMESTAMPTZ` always normalizes to UTC internally regardless of the offset attached at write time, so UTC storage is the correct approach even when the domain is Singapore-centric.

2. **Display in UTC, no per-user override** — Single timezone, no ambiguity. Rejected because the developer (and primary user) works in America/Chicago and reads timestamps most naturally in that timezone. UTC display for a user in Central Time requires constant mental arithmetic. The session-persistent override keeps the experience natural without hardcoding a single timezone for all possible viewers.

3. **Display in Asia/Singapore as default** — Maritime-appropriate timezone. Rejected for the same developer-experience reason as UTC. Asia/Singapore is available as a user-selectable option, which is sufficient for any user who wants to see Singapore local time.

---

## Consequences

- **Enables:** Correct timestamp display in any timezone without conversion bugs; no future-dated news timestamps; a standardized ISO 8601 API surface that any frontend or downstream tool can consume without timezone guesswork; DST-aware relative time calculations.
- **Precludes:** Any `TIMESTAMP WITHOUT TIME ZONE` columns in the schema. This is a hard rule enforced by the Database Engineer Build Swarm agent and verified in Alembic migration review.
- **Costs:** All timestamp-handling code must use `utils/timezone.py` (the project's timezone utility module) rather than calling datetime libraries directly. New external timestamps must explicitly pass through `clamp_future()`. Explicit pytest tests cover the clamp function, ISO 8601 serialization, and DST boundary behavior.
- **Reversibility:** 3 (moderate). Changing the default display timezone is trivial (one configuration value). Changing the storage convention (e.g., to store in Asia/Singapore) would require a migration of every `TIMESTAMPTZ` column and a rewrite of the ingestion and serialization layers — significant but not impossible.

---

## Plain-English Summary

OceansX V1 had a specific, embarrassing bug: news articles sometimes showed timestamps like "in about 3 hours" when the RSS feed had published them with a slightly future-dated timestamp. V2 closes this bug permanently with a rule: any timestamp that claims to be in the future (by more than 5 minutes) is immediately replaced with the current time when it enters the system. The "in X hours" display becomes structurally impossible.

Beyond that bug fix, V2 applies a consistent timezone strategy: every timestamp is stored in UTC (the international standard), served over the API with an unambiguous UTC label, and displayed to the user in America/Chicago time by default (because that is the developer's timezone and the natural reading context). Users can switch to UTC, Singapore time, or their browser's local timezone with a dropdown that persists for the session. The map footer always shows which timezone is currently active, so there is never any ambiguity about what "2:30pm" means on screen.
