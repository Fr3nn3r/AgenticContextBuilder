# Frontend Code Review (Maintainability + Best Practices)

Date: 2026-01-25

## Findings (ordered by severity)

- High: Route metadata is duplicated across routing, sidebar, and page-title logic; this will drift as routes evolve. You currently maintain route lists in `ui/src/AppRoutes.tsx:30`, view/title mapping in `ui/src/App.tsx:15`, and nav items in `ui/src/components/Sidebar.tsx:7`. This violates SRP and increases change risk.
- High: API client is a 1,100+ line monolith with mixed domains and mid-file imports, making it hard to reason about and merge. It centralizes everything in `ui/src/api/client.ts:1` and even injects imports mid-file around `ui/src/api/client.ts:490`, which is non-idiomatic and signals feature coupling.
- Medium: The type system is a monolith as well, spanning many domains in a single file (`ui/src/types/index.ts:3`, `ui/src/types/index.ts:643`, `ui/src/types/index.ts:823`). This reduces discoverability, increases compile noise, and makes types harder to reuse safely by feature.
- Medium: App-level loading/error for claims blocks unrelated pages. `ui/src/App.tsx:12` and `ui/src/App.tsx:94` gate most screens on claims state, so a claims fetch failure makes templates/pipeline/admin look broken even if those APIs are fine.
- Medium: `ClaimsTable` mixes data concerns, filtering UI, sorting, expansion, and navigation in one large component, and `showAllClaims` bypasses filters while still rendering the filter UI (`ui/src/components/ClaimsTable.tsx:23`, `ui/src/components/ClaimsTable.tsx:42`). It also uses a single global `docs` list from context, so expanding another claim can momentarily show stale docs for the previous claim.
- Low: Auth responsibilities are bundled into context state + API calls + permission rules, and token access is duplicated in both auth and API layers (`ui/src/context/AuthContext.tsx:37`, `ui/src/context/AuthContext.tsx:65`, `ui/src/context/AuthContext.tsx:197`, `ui/src/api/client.ts:19`). This makes testing and reuse harder and is a DIP/SRP smell.

## Open questions / assumptions

- Should “All Claims” still support filtering? If yes, the current `showAllClaims` behavior likely contradicts the UI intent.
- Are routes expected to evolve frequently (new pages, feature flags)? If so, a central route config becomes high-leverage quickly.
- Is there a plan to swap auth mechanisms? If yes, decoupling storage + permission policy now will pay off.

## Pragmatic improvement plan (no over-engineering)

1. Centralize route metadata into a single `routes.ts` (path, title, nav label/icon, auth screen, layout), then derive `AppRoutes`, `Sidebar`, and `getPageTitle` from it. This is the highest ROI refactor and fixes the SRP/Open-Closed issues.
2. Split `ui/src/api/client.ts` into feature modules (`api/claims.ts`, `api/pipeline.ts`, `api/compliance.ts`, etc.) and extract a tiny `api/http.ts` for `fetchJson` + auth header logic. Re-export from `api/index.ts` to keep imports simple.
3. Split `ui/src/types/index.ts` into feature-scoped types (mirror the API modules). Keep a `types/index.ts` barrel that re-exports for convenience.
4. Localize loading/error to the screens that actually depend on the data (e.g., claims pages), and avoid app-shell gating in `App.tsx`. This will make unrelated pages resilient.
5. Break `ClaimsTable` into: `ClaimsFilters`, `ClaimsTableView`, `ClaimRow`, and a `useClaimsTable` hook for sorting/expansion. If “All Claims” should be filterable, reuse the same filter logic in a pure selector function.
