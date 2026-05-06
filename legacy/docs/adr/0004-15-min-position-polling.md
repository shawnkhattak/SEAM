# ADR 0004: 15-Minute Position Polling Cadence

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

OceansX V2 sources vessel position data from the MPA (Maritime and Port Authority of Singapore) OceansX API. Every API call retrieves the current positions of vessels in Singapore waters. The frequency of these calls — the polling cadence — determines how fresh the position data is and how many API calls are made per day.

V1 polled every 3 minutes, which produced 480 API calls per day. V2 explicitly reframes the product as a compliance and intelligence dashboard, not a real-time navigation tool. The question is what polling cadence best serves that purpose while remaining well within any reasonable interpretation of the API's usage terms.

Three realistic options were evaluated: 1 minute (too aggressive for a non-navigation tool), 5 minutes (acceptable but still oriented toward real-time tracking), and 15 minutes (clearly positions V2 as a compliance dashboard).

A secondary consideration is the frontend update strategy. With SSE (Server-Sent Events — a persistent connection from server to browser), the frontend learns about new position data immediately after each backend poll. This means users see fresh data within seconds of each 15-minute poll, eliminating the perception of staleness.

---

## Decision

Poll the MPA OceansX API **every 15 minutes**, producing 96 API calls per day. After each successful poll, broadcast a `positions_updated` event to all subscribed SSE clients. The frontend re-fetches position data only in response to this event — it never polls independently.

This cadence deliberately signals the system's purpose: a 15-minute window is inappropriate for live navigation (where a vessel moving at 15 knots covers 3.75 nautical miles in 15 minutes), but entirely appropriate for compliance monitoring (where the question is "is this vessel currently anchored in Singapore?" not "exactly where is this vessel right now?").

---

## Alternatives Considered

1. **1-minute polling** — Maximally fresh position data; 1,440 API calls per day. Rejected because it positions the product as a real-time tracker rather than a compliance dashboard, risks exceeding MPA's API usage expectations, produces 15x more data to store and process, and provides no meaningful compliance benefit (a vessel's sanctions status does not change minute-by-minute).

2. **5-minute polling** — Better freshness than 15 minutes; 288 API calls per day. Rejected because it still orients the product toward near-real-time tracking rather than compliance intelligence. The difference between 5 and 15 minutes has no practical significance for whether a vessel is sanctioned. Choosing 15 minutes is also a more explicit, defensible commitment to the compliance positioning.

3. **On-demand polling (poll only when a user opens the app)** — Zero background API calls; polling triggered by user interaction. Rejected because the Operations Swarm agents (entity extraction, risk scoring, anchorage dwell) depend on regular position updates to function correctly. A user who hasn't opened the app for an hour would see stale compliance intelligence, not just stale positions.

---

## Consequences

- **Enables:** A clear compliance dashboard positioning (not a navigation tool); 96 API calls per day, well within any reasonable rate limit; position archive deduplication running per-poll rather than as a separate hourly job; SSE push delivering fresh data to users within seconds of each poll.
- **Precludes:** Real-time vessel tracking use cases. A vessel moving at speed covers several nautical miles between polls. The timeline scrubber (24-hour position history) will have a maximum of 96 data points per vessel, with gaps where deduplication removed stationary or nearly-stationary positions.
- **Costs:** Users expecting a live navigation experience will be disappointed. The "last updated" indicator in the UI shows the time since the last successful poll, which may be up to 15 minutes. A UI note explaining the 15-minute cadence and its rationale is appropriate.
- **Reversibility:** 2 (easy). The polling cadence is a single configuration value in the scheduler. Changing from 15 to 5 minutes requires one line change and a redeploy. The downstream storage and SSE architecture does not need to change.

---

## Plain-English Summary

Every 15 minutes, OceansX V2 asks the MPA API "where are all the vessels in Singapore waters right now?" and records the answer. In V1, this happened every 3 minutes. The change to 15 minutes is deliberate: this is a compliance monitoring tool, not a ship navigation chart. Knowing a vessel's position within 15 minutes is more than sufficient to determine whether it is anchored in Singapore, whether its anchorage dwell time is unusually long, and which terminal it is in — the three things the compliance layer actually cares about.

Despite the longer interval between polls, users do not see data that is up to 15 minutes stale. The server immediately notifies the browser the moment new position data arrives, using a persistent connection called SSE (Server-Sent Events). The browser refreshes the map within seconds of each backend poll. From the user's perspective, the map updates itself — they just see it happen at 15-minute intervals rather than continuously. The only thing users cannot do is track a moving vessel in real time — which was never the point.
