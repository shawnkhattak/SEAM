# ADR 0006: Prominent Treatment of Shadow Fleet Vessels

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

OpenSanctions applies topic tags to vessels. One tag — `mare.shadow` — marks a vessel as belonging to the "shadow fleet": older tankers used to move Russian oil in circumvention of Western sanctions, typically operating under flags of convenience (registration in small nations with minimal oversight), with frequent ownership changes, and with histories of disabling or manipulating their AIS position signals.

A vessel tagged `mare.shadow` by OpenSanctions is not necessarily formally sanctioned by any government authority. It may have no entry on any OFAC, EU, or UN list. From a strict sanctions screening perspective, it does not trigger an alert. From a compliance intelligence perspective, its presence in Singapore waters is significant.

The question is how much visual and navigational prominence to give shadow fleet vessels in the interface — given that their relevance is real but their legal status is ambiguous.

---

## Decision

Shadow fleet vessels receive **prominent, independent treatment** in the interface:

1. **Dedicated map filter toggle** — "Shadow Fleet only" checkbox in the overlay panel, separate from the "Sanctioned only" filter.
2. **Dedicated drawer tab** — "Shadow Fleet" tab in the side drawer, parallel to (and independent of) the "Sanctions" tab. Shadow fleet vessels appear here even when the Sanctions tab is empty.
3. **Badge overlay on map markers** — A distinct visual badge on the vessel's map pin, visible at any zoom level.

The `vessel.is_shadow_fleet` boolean flag is derived nightly from `vessel_topic` where `topic = 'mare.shadow'` and `valid_to IS NULL` (meaning the tag is currently active). The shadow fleet score component of the risk score is 100 if `is_shadow_fleet = true`, and 0 otherwise — the highest possible component value, equal to a confirmed sanctions match.

All shadow fleet displays include a contextual note explaining that shadow fleet status is derived from OpenSanctions topic tags and does not necessarily indicate a formal government sanctions designation.

---

## Alternatives Considered

1. **Show shadow fleet vessels only in the Sanctions tab with a different badge** — Single tab, clearer hierarchy. Rejected because mixing formally sanctioned vessels with shadow fleet vessels in a single list conflates two distinct concepts. A user scanning the Sanctions tab for confirmed sanctions entries would have to filter out the shadow fleet vessels. Separate tabs preserve the distinction.

2. **Show shadow fleet status only in the vessel detail panel (no map badge, no dedicated tab)** — Minimal prominence; relies on users drilling into individual vessels. Rejected because the value proposition of shadow fleet visibility is the ability to see which vessels in the current view are shadow fleet — a capability that only exists at the map and list level, not per-vessel detail. A user asking "are there any shadow fleet vessels in Eastern Anchorage right now?" needs to see that answer on the map.

3. **Exclude shadow fleet from the interface entirely (sanctions only)** — Clean compliance posture, no ambiguity. Rejected because the shadow fleet is a primary use case for maritime compliance monitoring in Singapore waters. Russian oil sanctions circumvention vessels transiting the Singapore Strait is exactly the kind of intelligence the platform is designed to surface. Omitting it would eliminate a core capability.

---

## Consequences

- **Enables:** Users can immediately see which visible vessels are shadow fleet tagged, without drilling into individual vessel panels; the Shadow Fleet tab remains populated and useful even when no vessels are formally sanctioned; shadow fleet vessels contribute maximum risk score, ensuring they appear at the top of the risk leaderboard.
- **Precludes:** Any possibility of treating shadow fleet and sanctions as interchangeable. The UI always distinguishes them, and the data model has separate flags and separate score components for each.
- **Costs:** An additional drawer tab to maintain. A nightly job (`refresh_shadow_fleet_flags`) to re-derive `vessel.is_shadow_fleet` from the topic table after each OpenSanctions pull. UI copy that accurately describes the OpenSanctions provenance without alarming users about non-formally-sanctioned vessels.
- **Reversibility:** 2 (easy). Shadow fleet treatment is a presentation layer decision. The underlying `vessel_topic` table and `is_shadow_fleet` flag exist regardless; removing the dedicated tab and badge is a frontend change.

---

## Plain-English Summary

The "shadow fleet" is a collection of older tankers operating in a legal gray zone — not necessarily named on any government sanctions list, but used specifically to move Russian oil in ways that circumvent Western sanctions. OpenSanctions tracks these vessels and tags them. A compliance dashboard focused on Singapore waters would be significantly less useful without surfacing these vessels prominently.

The decision was to give shadow fleet vessels their own map filter, their own drawer tab, and their own badge on the map — so they are always visible to a user scanning the interface, not buried in a detail panel. The tab stays populated even when no vessels are formally sanctioned, because the shadow fleet is worth monitoring regardless. Every shadow fleet display includes a clear note that this is an OpenSanctions tag, not a formal government sanctions designation — the distinction matters, and the interface preserves it.
