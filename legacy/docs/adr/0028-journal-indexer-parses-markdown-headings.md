# ADR 0028: Journal Indexer Parses Markdown Headings Without YAML Frontmatter

**Status:** Accepted
**Decided:** 2026-05-02
**Deciders:** Solo (Shawn Khattak)

---

## Context

The project journey files in `docs/journey/` and ADR files in `docs/adr/` were written as plain GitHub-flavored Markdown with no YAML frontmatter. Phase 7a required a structured indexer to populate `journal_phase`, `journal_adr`, and `glossary_term` tables so the frontend JournalDrawer and API can serve metadata, decision records, and glossary definitions without shipping raw Markdown to the client. The documents already existed with consistent heading conventions; the question was whether to add structured metadata or parse what was already there.

---

## Decision

Parse structure from Markdown heading conventions rather than adding YAML frontmatter. The rules are:

- **Phase files:** `# Phase N: TITLE` (first H1); `**Status:** VALUE`; body of `## What Was Built` = summary_md
- **ADR files:** `# ADR NNNN: TITLE`; `**Status:** VALUE`; `**Decided:** YYYY-MM-DD`; body of `## Context` = summary_md
- **Glossary:** `## TERM` (H2 sections); `**Category:** VALUE`; first plain paragraph = plain_definition; paragraph starting with `**Why it matters` = why_it_matters_in_project

The `_RE_BOLD_FIELD` regex uses `[^*:]` (colon excluded from character class) so `**Status:**` yields key `"status"` rather than `"status:"`.

---

## Alternatives Considered

1. **Add YAML frontmatter to all documents** — Structured, unambiguous, widely supported by static site generators. Rejected because it requires retrofitting 30+ already-written documents and makes the files harder to read in a plain text editor. The heading conventions are already consistent enough to parse reliably.

2. **Separate metadata sidecar files (e.g. `0001.meta.json`)** — Keeps documents clean, schema is explicit. Rejected because it doubles the file count, creates sync risk between sidecar and document, and still requires parsing the document body for summaries.

3. **Parse heading conventions (chosen)** — Zero document changes required. Parsing is 50 lines of regex; the convention is stable across all 30+ existing files. Divergent new documents silently produce `None` (skipped), which is an acceptable fail-safe.

---

## Consequences

- **Enables:** All 30+ existing documents indexed without modification; indexer runs hourly at `:45 UTC` and is force-triggerable via `POST /api/admin/force-journal-index`.
- **Precludes:** Free-form heading variation in new documents — `# Phase Seven` instead of `# Phase 7:` would not be indexed.
- **Costs:** Convention drift in new documents silently drops them. The `_rel(path)` helper uses `try/except ValueError` so temp-dir test paths don't crash `relative_to()`.
- **Reversibility:** 2 (easy to add frontmatter later and update the parser — not a structural commitment).

---

## Plain-English Summary

All of the project's documentation files were already written in plain Markdown with consistent heading patterns — things like `# Phase 3: News` and `# ADR 0009: Tiered Entity Extraction`. Rather than going back and adding structured metadata tags to every file, we wrote a parser that reads those heading patterns and extracts the information directly. It's a bit like reading a book's table of contents instead of asking the author to fill out a form.

The trade-off is that the parser is picky about heading format: a new document that doesn't follow the pattern will be silently skipped rather than loudly rejected. The upside is that all existing documents work without any changes, and the parser itself is small enough to read in a few minutes.
