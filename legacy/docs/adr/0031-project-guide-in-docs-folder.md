# ADR 0031: Project Guide in Docs Folder

**Status:** Accepted
**Decided:** 2026-05-06
**Deciders:** Solo (Shawn Khattak)

---

## Context

The project already had deep documentation: an architecture plan, phase journey documents, ADRs, and a glossary. Those documents are useful, but they are not the quickest way for a new developer to understand how to run and modify the app. The repository needed one simple practical guide that explains the whole project at a working level.

The guide was first created at the repository root as `PROJECT_GUIDE.md`. That made it easy to find, but it also added another top-level documentation file alongside `README.md` and the long architecture plan. The user requested that the guide live in the docs folder.

---

## Decision

Store the simple project guide at:

```text
docs/PROJECT_GUIDE.md
```

Keep `README.md` short and link to the guide from the Architecture section. The deeper documents remain where they are:

- `oceansx-v2-architecture.md` for the full architecture plan
- `docs/journey/` for phase-by-phase narrative
- `docs/adr/` for formal decisions
- `docs/glossary.md` for definitions

---

## Alternatives Considered

1. **Keep the guide at the repository root** - Easy to discover, but rejected because the root already contains the README and architecture plan. Keeping practical docs under `docs/` is cleaner.

2. **Merge the guide into README** - Rejected because README should stay short. A 600-line operational guide would make the landing page harder to scan.

3. **Split the guide into many small docs** - Rejected for now because the goal is a simple single starting point. It can be split later if it grows too large.

4. **Move guide to `docs/PROJECT_GUIDE.md` and link from README (chosen)** - Keeps the root clean while preserving discoverability.

---

## Consequences

- **Enables:** One practical entry point for developers without bloating the README.
- **Precludes:** Treating README as the only source of onboarding information.
- **Costs:** Links must point to `docs/PROJECT_GUIDE.md`, not `PROJECT_GUIDE.md`.
- **Reversibility:** 5 (easy). The file can be moved again with only link updates.

---

## Plain-English Summary

The project now has a simple guide that explains how everything fits together. Instead of keeping that guide at the top level of the repository, it lives in the docs folder with the rest of the documentation.

The README stays short. It points readers to the project guide for day-to-day understanding, and to the architecture plan, journey, ADRs, and glossary when they need deeper background.
