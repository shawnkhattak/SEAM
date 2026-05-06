# Architecture Decision Records

ADRs document significant architectural choices made during the SEAM build. They are append-only — never delete or retroactively modify a decision record.

## Template

```markdown
# ADR-NNNN: Title

**Date:** YYYY-MM-DD  
**Status:** Accepted | Superseded by ADR-XXXX | Deprecated  
**Deciders:** [role or name]

## Context
What problem or situation prompted this decision?

## Decision
What was decided and why was this option chosen over alternatives?

## Consequences
What becomes easier or harder as a result of this choice?
```

## Index

| ADR | Title | Status |
|-----|-------|--------|
| 0001 | Sanctions auto-confirm only on IMO-exact match | Accepted |
| 0002 | Field-level provenance via vessel_particular_fact | Accepted |
| 0003 | Admin-configurable API keys via app_config + Fernet | Accepted |
| 0004 | Vessel detail as bottom sheet, not right drawer | Accepted |
| 0005 | Journal/ADR browsing in admin dashboard, not map toolbar | Accepted |
