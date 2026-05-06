# ADR 0019: HMAC Verification Against Raw Request Bytes

**Status:** Accepted  
**Date:** 2026-05-01  
**Phase:** 3

## Context

RSS.app signs each webhook push with an HMAC-SHA256 signature. The signature is computed over the raw JSON bytes of the payload. The server must verify this signature before trusting the payload content.

The question is: what bytes are used as the HMAC input on the server side?

There are two approaches:
1. Verify against `await request.body()` — the original bytes exactly as received over the wire.
2. Parse the body to a Python dict, then re-serialise it to JSON, then compute HMAC on those bytes.

## Decision

Verify against `await request.body()` — the raw bytes, before any parsing.

This is implemented in `app/clients/rss_app.py`:

```python
def verify_hmac(raw_body: bytes, slot: int, signature_header: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    candidate = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, candidate)
```

The router calls `raw_body = await request.body()` once, passes it to `verify_hmac`, and then passes the same bytes to `parse_webhook_payload` for parsing. The raw bytes are never discarded before verification completes.

## Alternatives Considered

**Parse first, then re-serialise.** Parse the JSON payload to a Python dict, re-serialise it with `json.dumps`, compute the HMAC on the result. Rejected because JSON serialisation is not deterministic across implementations: key ordering, Unicode normalisation, and whitespace handling may differ between RSS.app's signing code and Python's `json.dumps`. Even a correctly signed payload would fail verification if the serialisations diverged by a single byte.

**Trust without verification.** Accept all webhook pushes without checking the signature. Rejected because the webhook endpoint is public — without verification, any party that discovers the URL can inject arbitrary articles into the news feed.

## Consequences

**Enables:**
- Correct signature verification for all well-formed RSS.app pushes.
- No false negatives from serialisation differences.
- The verification function is independent of the payload parser — they can evolve separately.

**Costs:**
- `request.body()` must be called before any middleware or dependency that might consume the body stream. FastAPI buffers request bodies by default, so this is not an operational constraint, but it must be documented.
- The raw bytes must be held in memory for the duration of the request. For news payloads (typically < 100 KB) this is not a concern.

**Reversibility:** 5 of 5. The verification strategy is internal to `verify_hmac` and can be changed without touching the router or other services.

## Plain-English Summary

When RSS.app sends a batch of articles to the server, it includes a digital signature — a short code computed from the exact bytes of the message it sent. The server must compute the same code from the same bytes and compare them. If they match, the message is genuine; if they do not, the message has been tampered with or came from an impostor.

The critical rule is: the server must compute the signature from the *original* bytes it received, not from a reformatted copy. Reformatting — even slightly — produces a different signature and causes the check to fail. This rule is enforced structurally by reading the raw bytes once at the start of the request and passing them directly to the verification function, before any parsing happens.
