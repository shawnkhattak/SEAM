# ADR 0021: URL SHA-256 Hash for Article Deduplication

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 3

## Context

The same news article can arrive multiple times: pushed by the RSS.app webhook, then returned again by the hourly RSS poll, or pushed twice if RSS.app retries a delivery. The system must not store duplicate articles.

The natural deduplication key is the article URL — each article has a unique URL that does not change between deliveries.

The question is: how should the uniqueness constraint be implemented?

## Decision

Compute `SHA-256(url)` and store the 64-character hex digest in `news_item.url_hash` with a unique constraint.

Before inserting a new article, the ingest function checks:
```python
existing = await session.execute(
    select(NewsItem.id).where(NewsItem.url_hash == url_hash).limit(1)
)
if existing.scalar_one_or_none() is not None:
    return None  # duplicate
```

The `news_item.url` column still stores the original URL for display and linking.

## Alternatives Considered

**Unique constraint directly on `news_item.url`.** Simplest approach — one column, one constraint, no hashing. Rejected because `url` is defined as `VARCHAR(500)`, and a unique B-tree index on a 500-character column is significantly larger and slower than one on a 64-character fixed-width hash. URL strings also vary in Unicode encoding and trailing slashes in ways that SHA-256 normalises away.

**`md5` hash.** Shorter (32 hex chars), faster to compute. Rejected because MD5 is considered cryptographically broken and collision resistance, while not a strict security requirement here, is a hygiene consideration when storing millions of rows.

**Application-level dedup only (no database constraint).** Check before insert in application code, no unique constraint on the column. Rejected because a race condition between two concurrent ingest requests for the same URL would cause duplicate inserts under load.

## Consequences

**Enables:**
- Fast O(1) dedup check via a fixed-length hash index.
- Correct dedup even when URL casing or trailing slash varies slightly (SHA-256 normalises at the character level).
- The database constraint provides a safety net against race conditions.

**Costs:**
- A SHA-256 computation per article on ingest (negligible cost).
- The `url_hash` column adds 64 bytes per row.

**Reversibility:** 4 of 5. Changing the hash function requires a data migration to recompute all existing hashes and a re-index.

## Plain-English Summary

The same news article can show up multiple times if the source sends it twice or if both the push notification and the hourly backup poll deliver it. To avoid storing duplicates, the system computes a short fingerprint of each article's URL (using the SHA-256 algorithm) and stores it in the database. Before saving a new article, it checks whether that fingerprint already exists — if it does, the article is silently skipped.

This approach is faster than comparing full URLs directly (the fingerprint is always the same length regardless of how long the URL is), and it uses the database itself as the ultimate guard against race conditions — even if two requests arrive at exactly the same moment, the database's unique constraint ensures only one of them succeeds.
