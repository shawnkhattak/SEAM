# ADR 0018: Position Archive Deduplication Thresholds

**Status:** Accepted  
**Date:** 2026-04-30  
**Phase:** 1

## Context

`position_archive` is the 24-hour historical log of vessel positions. With 800 vessels polled every 15 minutes, an unconstrained archive accumulates up to 76,800 rows per day and 6.9 million rows over 90 days. Most of those rows would be redundant: a vessel at anchor, or a vessel moving slowly through congested water, produces nearly identical position readings across consecutive polls.

Storing identical or near-identical readings serves no analytical purpose. It wastes storage, bloats query results, and makes the 24-hour trail scrubber noisy — a user scrubbing through a vessel's trail that is anchored for 12 hours should see it as stationary, not as 48 nearly-identical intermediate points.

The question is: what counts as "different enough" to write to the archive?

## Decision

Write a new archive row only if the vessel has changed in at least one of three dimensions since its last archive row:

| Dimension | Threshold | Rationale |
|---|---|---|
| Distance | ≥ 100 m | Eliminates GPS jitter for anchored vessels (AIS GPS noise ≈ 20–30 m) |
| Heading change | ≥ 5° | Captures genuine turns; ignores compass noise |
| Speed change | ≥ 0.5 kn | Captures acceleration/deceleration; ignores speed sensor noise |

If all three dimensions are below their thresholds, the archive row is skipped. If any one threshold is exceeded, the row is written. The check is OR, not AND.

This is implemented in `maybe_write_position_archive` in `app/services/history.py`. The function reads the most recent archive row for the vessel, computes the delta for each dimension, and returns `False` (skip) or `True` (write) accordingly.

## Alternatives Considered

**Time-based dedup (write at most once per N minutes).** Write an archive row only if the previous archive row is older than some minimum interval (e.g., 30 minutes). Simple to implement; guarantees a maximum storage rate. Rejected because a vessel executing a fast berth manoeuvre (high heading change over a short time) could be missed if it falls within the time window, losing the manoeuvre from the trail.

**Distance-only dedup.** Write only when the vessel has moved ≥ X metres. Simpler. Rejected because a vessel rotating in place (turning in a berth) is behaviorally significant but covers zero distance — distance-only would suppress the entire manoeuvre.

**No dedup (write every poll).** Maximum fidelity; simplest code. Rejected on storage grounds: 6.9 million rows per 90 days per 800 vessels is manageable, but it scales linearly with fleet size and retention window. The analytical value of sub-100-metre GPS jitter rows is zero.

**Machine learning anomaly detection for significant events.** Train a model to determine which position readings are "interesting." Rejected as disproportionate complexity for a storage optimization problem with a straightforward threshold-based solution.

## Consequences

**Enables:**
- Storage reduction of 60–80% for anchored vessels (the dominant state for many Singapore strait vessels overnight).
- Clean 24-hour trails that show only meaningful movement without post-processing.
- Predictable maximum archive size for capacity planning.

**Costs:**
- The archive is not a complete record of all polls — it is a record of all *meaningful* state changes. Compliance audits that require proof of *every* poll result cannot rely on the archive alone (they would need the raw API response log, if that were implemented separately).
- Each archive write requires one preceding read (the most recent row for that vessel). At 800 vessels per cycle this is 800 reads per poll cycle.

**Reversibility:** 4 of 5. The thresholds are configuration values and can be adjusted without schema changes. Lowering a threshold retroactively will not recover already-skipped rows.

## Plain-English Summary

Every 15 minutes the system checks each vessel's position. Rather than writing every reading to the historical log, it first asks: has this vessel actually done anything different since the last time we wrote it down? "Different enough" means the vessel has moved at least 100 metres, turned at least 5 degrees, or changed speed by at least half a knot — any one of those is sufficient to write a new log entry.

This prevents the log from filling up with dozens of near-identical readings for a ship that is sitting anchored and barely drifting. An anchored vessel might go from producing 96 log entries per day (one per 15-minute poll) to producing 4–8 (one each time its GPS drifts past the threshold). The 24-hour trail scrubber on the map shows only these meaningful state changes, so the trail of an anchored vessel looks like what it is — a single point with a tight cluster — rather than a cloud of noise.
