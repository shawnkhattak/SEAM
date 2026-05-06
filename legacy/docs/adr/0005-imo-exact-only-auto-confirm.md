# ADR 0005: IMO-Exact Matches Only for Auto-Confirmation

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

When the OpenSanctions Watcher agent processes the daily sanctions download, it must decide whether a vessel in our database is the same entity as a vessel on a sanctions list. This matching can be done by several methods:

- **IMO exact match:** The vessel's IMO number in our database matches the IMO number recorded in the OpenSanctions data. IMO numbers are permanent seven-digit identifiers assigned for the life of a vessel; they do not change with name changes, flag changes, or ownership transfers.
- **Name + flag fuzzy match:** The vessel's current name and flag state are similar (but not necessarily identical) to a name and flag on the sanctions list. Owners deliberately give vessels similar names; flags change regularly; transliteration from other alphabets produces variants.
- **Name fuzzy match only:** Similar name, flag not considered.
- **Organizational linkage:** A vessel's registered owner, operator, or beneficial owner organization is linked in the OpenSanctions graph to a sanctioned entity.

The question is: which of these methods should be allowed to produce an auto-confirmed sanctions match — one that appears in the live production interface without human review?

The stakes are high in both directions. A false positive (marking a legitimate vessel as sanctioned when it is not) could damage the reputation of the system and mislead users making compliance decisions. A false negative (missing a genuinely sanctioned vessel) defeats the purpose of the feature. The answer is not to optimize a single threshold — it is to choose the method whose reliability is categorically different from the others.

---

## Decision

**Only IMO-exact matches auto-confirm to the production `sanctions_match` table.** All other match methods — regardless of confidence score — are routed to the admin review queue and require explicit human approval before appearing in the production interface.

This rule is hardcoded in `services/sanctions_matcher.py` with a check that cannot be overridden by configuration or agent decision. The Security Reviewer Build Swarm agent has this check on its mandatory review checklist. Violations block the PR.

---

## Alternatives Considered

1. **Auto-confirm all matches above a confidence threshold (e.g., 90%)** — Single pipeline, no review queue overhead. Rejected because confidence scores for fuzzy name matching are not calibrated against a ground truth set of sanctions false-positive rates. A 90% confidence in fuzzy name matching does not mean 90% precision in a maritime compliance context. Vessel names are recycled, transliterated, and deliberately varied. The false positive rate at any reasonable confidence threshold is unknown and potentially high.

2. **Auto-confirm IMO exact and name+flag matches** — IMO exact is definitive; name+flag is strong corroborating evidence. Rejected because flag states change, and a vessel can carry a name previously used by a different vessel. The combination is much stronger than name alone but is still not equivalent to IMO exact. A single incorrectly flagged vessel appearing in the production interface is not an acceptable risk for a compliance tool.

3. **Route all matches to the admin review queue (no auto-confirm at all)** — Maximum safety; no false positives possible in production. Rejected because IMO-exact matches are definitionally reliable — the IMO number is designed to be a permanent, unique vessel identifier. Requiring human review for IMO-exact matches adds friction with no safety benefit. The review queue would quickly become a burden rather than a safety mechanism.

---

## Consequences

- **Enables:** Production sanctions matches that are definitionally reliable; a clean separation between "confirmed" and "pending" states in the UI; an audit trail of every human approval decision; suppression of repeated false-positive proposals for 30 days after rejection.
- **Precludes:** Any possibility of a fuzzy-matched or organizationally-linked vessel appearing as confirmed-sanctioned without human review, regardless of confidence score.
- **Costs:** Admin review queue requires ongoing human attention. Vessels that should be flagged by name or organizational linkage will appear in the pending queue rather than the production interface until reviewed. For a single-user portfolio project, this is manageable — the daily batch produces a bounded number of new candidates.
- **Reversibility:** 2 (easy to relax, dangerous to do so). The hardcoded check in `sanctions_matcher.py` is a single conditional. Removing it is technically trivial but requires a deliberate decision, a new ADR, and Security Reviewer sign-off — which is exactly the point of hardcoding it.

---

## Plain-English Summary

Sanctions data is uniquely high-stakes. If the system incorrectly labels a vessel as sanctioned when it is not, the consequences range from embarrassing to misleading for anyone using the tool to make real compliance decisions. The safest match method is also the most definitive: if a vessel's permanent IMO number exactly matches a number on a sanctions list, there is no ambiguity — they are the same vessel.

All other matching approaches — comparing vessel names, checking whether the owner is connected to a sanctioned company — involve judgment calls and fuzzy comparisons that can and do produce false positives. Rather than attempt to tune a confidence threshold that cannot be validated, OceansX V2 routes every non-IMO-exact match to a review queue where a human confirms or rejects it before anything appears in the production interface. This check is built into the code in a way that cannot be quietly overridden. It is the single most important safety constraint in the system.
