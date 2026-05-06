# ADR 0016: Mock API Mode with File Fixtures

**Status:** Accepted  
**Date:** 2026-04-30  
**Phase:** 1

## Context

The MPA OceansX API requires authentication credentials. Running the backend in development or CI without those credentials causes every API call to fail, which means:
- Developers without credentials cannot run the backend locally.
- CI runs cannot test the position polling pipeline without embedding live credentials in the pipeline environment.
- Automated tests that exercise the full request-to-database path are not possible without making real API calls that consume rate limit quota.

V1 solved this by embedding hardcoded fixture data directly in the test files. This worked but created drift: as the API response format changed, the fixtures fell out of date silently and tests continued passing against stale data.

## Decision

Add a `OCEANSX_MOCK` environment variable to the OceansX API client. When set to any truthy value, the client reads responses from JSON fixture files in `app/mocks/` instead of making HTTP calls.

- Each API method has a corresponding fixture file named `{method_name}.json`.
- Fixtures are committed to the repository.
- Mock responses go through the full parsing pipeline — the same `parse_mpa_timestamp`, status inference, and field normalization code that runs against real API responses.
- The same pattern is followed for all subsequent API clients added in Phases 2–5.

The fixture files contain minimal but representative data: enough features to exercise all geometry types (polygon, line, point), all status codes, and all field presence/absence combinations that the parsing code must handle.

## Alternatives Considered

**`pytest-httpx` response mocking in tests only.** Mock the HTTP layer at the test framework level. This is the correct approach for unit tests of the HTTP client itself, but it does not help with running the full backend server locally without credentials — `pytest-httpx` only works inside a test session, not during `uvicorn` startup.

**Separate fixture loader class injected at startup.** A `MockOceansXClient` class that implements the same interface as the real client but reads from files. Cleaner separation of concerns, but doubles the maintenance surface: two client classes that must stay in sync as new methods are added. The `OCEANSX_MOCK` flag in the single client class achieves the same result with less code.

**Replay proxy (record real responses and replay them).** Tools like VCR (a test cassette recorder — intercepts HTTP calls and plays them back) can record real API responses and replay them in tests. Rejected because it requires an initial live recording step with real credentials, and replayed cassettes go stale in the same way as manually written fixtures, with the additional problem of potentially capturing sensitive response data.

## Consequences

**Enables:**
- Full backend stack runs locally without API credentials.
- CI tests exercise the real parsing and storage pipeline with predictable fixture data.
- New API methods added in later phases follow an established pattern.

**Costs:**
- Fixture files must be kept in sync with API response formats. A breaking API change will cause fixture-based tests to pass but production to fail.
- Fixtures do not cover every edge case in production data. Some bugs will only surface against live API responses.

**Reversibility:** 5 of 5. The mock flag can be removed at any time with no data migration required.

## Plain-English Summary

The MPA data API requires credentials that not every developer has, and that should not be embedded in automated test pipelines. This ADR adds a "fake mode" to the API client: when a specific environment variable is set, the client reads pre-written example responses from files instead of calling the real API.

This means any developer can start the full backend server and see it behave like a real system — vessels appear on the map, polling jobs run, data is written to the database — without needing live API access. The CI pipeline uses the same fake mode to test the complete data pipeline without consuming API quota. The fake responses are real enough that they exercise all the parsing code paths, catching bugs before they reach production.
