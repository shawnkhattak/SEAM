# ADR 0008: SSE Push Instead of Frontend Polling

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

OceansX V1 used React Query (a data-fetching library for React) configured to refetch vessel positions automatically every 5 minutes. This is frontend polling — the browser repeatedly asks the server "do you have new data?" on a timer, regardless of whether anything has changed.

V2 changes the backend polling cadence to 15 minutes. With frontend polling at 5 minutes and backend polling at 15 minutes, the browser will make two or three unnecessary API calls between each actual data update. Worse, if the frontend poll happens to occur 14 minutes after the last backend poll, the user waits up to 1 additional minute before seeing the freshest data. The mismatch is wasteful and provides worse user experience.

The question is how to ensure users see fresh position data as quickly as possible after each backend poll, without the browser independently polling at an interval that may or may not align with the backend schedule.

---

## Decision

Replace frontend polling with **SSE (Server-Sent Events) push notification**:

1. The backend exposes a persistent SSE endpoint at `/api/sse/positions`.
2. After every successful `poll_positions` job (the 15-minute backend poll), the SSE broadcaster sends a `positions_updated` event to all subscribed clients.
3. The frontend subscribes to the SSE channel once on app mount and keeps the connection open.
4. React Query's `staleTime` is set to `Infinity` for the positions query — meaning React Query will never independently decide to refetch.
5. When the frontend receives a `positions_updated` SSE event, it calls `queryClient.invalidateQueries(['positions'])`, which triggers exactly one refetch.

Result: the browser makes exactly as many position API calls as the backend makes MPA API calls — once every 15 minutes, immediately after each backend poll completes.

**Fallback:** If the SSE connection drops and fails to reconnect within the retry window, the frontend falls back to polling once per minute as a safety measure, so users never see indefinitely stale data due to a broken SSE connection.

---

## Alternatives Considered

1. **Continue V1 React Query polling, tuned to 15 minutes** — Simple change, no new server infrastructure. Rejected because a 15-minute React Query timer does not align with the 15-minute backend timer — they run on independent clocks. A user opening the app at minute 14 of the backend's cycle would wait up to 29 minutes to see fresh data. The user experience is unpredictable.

2. **WebSockets** — Full bidirectional real-time communication; commonly used for live data dashboards. Rejected because OceansX V2 does not need bidirectional communication — the browser only needs to receive notifications, not send them. SSE is a simpler, HTTP-native protocol with automatic reconnection built into the browser standard, no additional libraries required, and better compatibility with HTTP/2 and reverse proxy layers (like Caddy). WebSockets are the right choice for chat or collaborative applications; SSE is the right choice for server-to-client push.

3. **Long polling** — Browser sends a request; server holds it open until data is ready; browser immediately sends the next request. Rejected because long polling effectively implements a continuous connection but with significantly more HTTP overhead than SSE (a new request per notification), and the implementation on both server and client is more complex than SSE without any capability advantage for this use case.

---

## Consequences

- **Enables:** Users see fresh position data within seconds of each backend poll, regardless of when they opened the app; the frontend makes zero unnecessary API calls; a single SSE channel can also carry other event types (e.g., `queue_updated` for admin review queue notifications) without additional connections.
- **Precludes:** Standard React Query polling for positions. The positions query must be kept at `staleTime: Infinity` and only invalidated in response to SSE events or manual triggers.
- **Costs:** A persistent SSE connection from each browser to the server for the duration of a session. At low user counts (this is a portfolio project / single-user tool), this is negligible. The Caddy reverse proxy and uvicorn are both SSE-compatible without configuration changes.
- **Reversibility:** 2 (easy). Removing SSE means setting `staleTime` back to an interval and deleting the SSE subscription hook. The backend SSE endpoint can be left in place without breaking anything.

---

## Plain-English Summary

V1's browser checked for new vessel data every 5 minutes, regardless of whether anything had changed on the server. V2 has the server poll the MPA API every 15 minutes. If the browser kept polling on its own 5-minute timer, it would make three unnecessary round trips for every one actual data update — wasting bandwidth and still potentially showing the user data that is several minutes behind.

The fix uses a feature built into modern web browsers called Server-Sent Events (SSE). The browser opens a single, persistent connection to the server and listens. The moment the server finishes its 15-minute position poll, it sends the browser a message: "new data is ready." The browser immediately fetches the fresh data and updates the map. No timer. No guessing. No wasted calls. The browser learns about new data within seconds of the server getting it, every time — and never polls on its own.
