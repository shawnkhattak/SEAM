# ADR 0030: SEAM Dashboard as Primary UI Shell

**Status:** Accepted
**Decided:** 2026-05-06
**Deciders:** Solo (Shawn Khattak)

---

## Context

The working app had a technically functional frontend, but the visual system was split. The main map, drawers, vessel details, admin views, risk badges, and search panels used a mix of older dark OceansX styling and newer SEAM dashboard styling. This caused overlapping menus, inconsistent colors, and hard-to-read panels. A standalone "SEAM Dashboard template" existed and captured the desired product direction, but it used mock data and a self-contained HTML/React structure.

The project needed the template's visual language without losing the existing live API-backed behavior.

---

## Decision

Adopt SEAM (Singapore Entity Analytics for Maritime) as the primary UI shell for both the public map dashboard and the admin dashboard.

The template is used as visual direction only. The production frontend remains the Vite/React app in `frontend/src`, with existing API clients, React Query data flows, Zustand UI state, Leaflet map components, and admin endpoints preserved.

Implementation choices:

- Keep `/` as the live map dashboard and `/admin` as the admin dashboard.
- Replace the old dark map shell with SEAM glass header, toolbar, status pill, light map treatment, and matching panels.
- Restyle existing drawers instead of replacing them with template mock drawers.
- Keep one active left-side panel at a time to prevent menu overlap.
- Rebuild the admin shell to match the template's glass header, sidebar, cards, tables, and chart palette.
- Add shared CSS utilities for admin cards, admin tables, navigation, animation, and SEAM glass components.

---

## Alternatives Considered

1. **Drop the template directly into the app** - Fastest visually, but rejected because the template contains mock data, inline scripts, and a separate architecture that would bypass the existing backend and frontend data flows.

2. **Keep the existing UI and only fix obvious bugs** - Lower risk, but rejected because it would leave the product with no coherent visual identity and would not satisfy the SEAM dashboard direction.

3. **Create a brand-new design system package** - Cleaner long term, but too much scope for this phase. The current app is small enough that shared CSS classes in `frontend/src/styles/index.css` are sufficient.

4. **Adopt SEAM styling inside the existing React app (chosen)** - Preserves live features while giving the app one coherent product shell.

---

## Consequences

- **Enables:** A consistent SEAM product identity across map and admin surfaces while keeping live vessel, risk, sanctions, news, search, journal, and admin features connected to real APIs.
- **Precludes:** Treating the standalone HTML template as a production source of truth. Future UI changes should happen in React components and shared CSS.
- **Costs:** Some visual styling remains component-level until a fuller design-system extraction is justified. Developers must keep new panels aligned with the SEAM classes.
- **Reversibility:** 3 (moderate). The app still uses existing component boundaries, but many components now assume SEAM CSS tokens and classes.

---

## Plain-English Summary

The app had working features, but the screens did not feel like one product. Some panels were dark, some were light, and some menus overlapped. The SEAM dashboard template showed the right direction, but it was only a mockup.

The decision was to keep the real app and real data connections, then apply the SEAM dashboard style to those real components. The result is one consistent dashboard for both the map and admin screens without replacing working backend integrations with mock template data.
