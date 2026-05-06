# ADR-0026: Unknown Flag Defaults to Grey Band in Risk Scoring

**Status:** Accepted  
**Date:** 2026-05-02  
**Phase:** 5a

---

## Context

The flag MoU score component of the risk formula maps a vessel's flag state to a performance band (white=0, grey=50, black=100) using the `flag_performance_year` table. Vessels may have:

- A flag code not present in the fixture (rare or newly registered flag states)
- A `null` flag code (particulars not yet enriched)

A decision is required for both cases so the scorer does not silently return 0 (white) for vessels with genuinely unknown compliance history.

## Decision

When a flag code is absent from `flag_performance_year`, or when `vessel.flag` is null, the flag MoU score defaults to **50 (grey band)**.

## Rationale

- White (0) would under-penalise vessels whose flag is unknown — undesirable for a compliance tool.
- Black (100) would over-penalise vessels with clean flags that are simply not in the fixture.
- Grey (50) is the neutral middle: it signals "unknown, treat with moderate caution" without asserting guilt.
- The `flag_performance_year` fixture covers the most common flag states in Singapore waters (40+ entries, year 2024). Missing entries are unlikely to represent white-list flags.

## Consequences

- Vessels with obscure or unrecognised flag codes score 50 on the flag MoU component.
- The fixture should be updated annually (flag_performance_refresh job, Phase 7).
- If the fixture grows to comprehensive coverage, this default becomes less material.
