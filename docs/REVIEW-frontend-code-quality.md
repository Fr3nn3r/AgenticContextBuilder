# Frontend Code Review: Structure & Maintainability

**Date:** 2026-02-11
**Scope:** `ui/src/` — 183 files, ~50,661 lines

## Overall: Mixed — Good foundations, but several files have grown past the point of easy maintenance.

---

## 1. THE BIG PROBLEMS

### `ClaimsWorkbenchPage.tsx` (1,848 lines) — Needs splitting

This is the worst offender. It's a full application crammed into one file:
- **7 internal components** (`VerdictBadge`, `FactField`, `DecisionBanner`, `CostBreakdownTab`, `CoverageChecksTab`, `DocumentsTab`, `ClaimDetail`, `ClaimRow`, `SortHeader`)
- **6 helper functions** (`getFact`, `getFactValue`, `fmt`, `pct`, `formatCHF`, `componentLabel`, `clauseToQuestion`, `parseDate`)
- **Business logic mixed with presentation** — payout recalculation in `CostBreakdownTab` (lines 441-496) reimplements financial logic that should live in the backend
- Heavy use of `any` types throughout (`data: any`, `clause: any`, `item: any`) — defeats the purpose of TypeScript

**What to do:** Extract to `pages/ClaimsWorkbench/` directory with:
- `CostBreakdownTab.tsx`, `CoverageChecksTab.tsx`, `DocumentsTab.tsx`, `DecisionBanner.tsx`
- `ClaimDetail.tsx`, `ClaimRow.tsx`
- `helpers.ts` for `fmt`, `pct`, `formatCHF`, `parseDate`, `clauseToQuestion`
- `types.ts` for `TabId`, `ClaimVerdict`, `SortKey`, `EffectiveValues`, `VERDICT_CONFIG`

### `api/client.ts` (1,551 lines) — Monolith API file

Every API call in the entire app lives here. The file has **scattered imports** (line 131 imports types mid-file, line 1496 imports more types mid-file) which is a code smell.

**What to do:** Split by domain:
- `api/claims.ts` — claim CRUD, facts, runs
- `api/documents.ts` — doc retrieval, reviews, sources
- `api/pipeline.ts` — pipeline runs, batch operations
- `api/dashboard.ts` — dashboard-specific endpoints
- `api/decision.ts` — dossier, evaluation, denial clauses
- `api/client.ts` — keep only `fetchJson`, auth logic, and re-export everything for backward compat

### `types/index.ts` (1,575 lines) — Single type file

Same pattern. All types in one file makes navigation hard, but it's less urgent since types don't have runtime behavior.

**What to do:** Split by domain when convenient. Not a priority since type-only files are cheaper to maintain.

### `PipelineControlCenter.tsx` (1,221 lines) — Same pattern

Contains `NewBatchTab`, `BatchesTab`, `ConfigTab`, `StatusBadge`, `ProgressBar` all inline. The `NewBatchTab` alone takes 18 props (lines 139-181), which is a strong signal it should be its own file.

---

## 2. WHAT'S ACTUALLY GOOD

- **Shared component library** (`components/shared/`) — Well-organized: `StatusBadge`, `MetricCard`, `LoadingSkeleton`, `EmptyState`. Good reuse across pages.
- **ClaimExplorer directory** — 45 files in a well-structured directory with a barrel file. Components are reasonably sized. This is the model to follow.
- **Custom hooks** (`usePipelineData`, `usePipelineWebSocket`, `useAssessmentWebSocket`) — Proper separation of data fetching from rendering.
- **Context providers** — 4 focused contexts (Auth, Batch, Claims, Filter) — not over-engineered.
- **Route organization** — `routes.ts` as config + `AppRoutes.tsx` as renderer is clean.
- **`fetchJson` wrapper** — Centralized auth, error handling, 401 redirect. Solid.
- **Consistent styling** — Tailwind + `cn()` utility used consistently. Design token usage (`text-muted-foreground`, `bg-card`, `border-border`) is disciplined.

---

## 3. REACT BEST PRACTICES ASSESSMENT

| Rule | Status | Notes |
|------|--------|-------|
| **`async-parallel`** | GOOD | `Promise.all` used correctly (e.g., `ClaimDetail` line 1113) |
| **`bundle-barrel-imports`** | WATCH | Barrel files exist in every subdirectory. For Vite this is usually fine since it tree-shakes, but the `shared/index.ts` re-exports 40+ items |
| **`rerender-functional-setstate`** | GOOD | Functional setState used consistently (`setExpandedTypes(prev => ...)`, `setClaims(prev => prev.map(...))`) |
| **`rerender-memo`** | OK | `useMemo` used for derived data (filtering, sorting). No obvious missing memoizations |
| **`rerender-lazy-state-init`** | N/A | No expensive initial state |
| **`js-combine-iterations`** | MINOR | `ClaimsWorkbenchPage` iterates `claims` multiple times for filter + sort, but the dataset is small enough this doesn't matter |
| **`rendering-conditional-render`** | GOOD | Uses ternary operators, not `&&` with numbers |
| **`rerender-dependencies`** | GOOD | `useCallback` with proper dependency arrays throughout |

---

## 4. REAL CONCERNS (Pragmatic)

**`any` type abuse in ClaimsWorkbenchPage** — `data: any` is passed through 4 levels of components. This is the #1 maintainability risk. When the backend response shape changes, nothing catches it at compile time. At minimum, define a `WorkbenchData` interface.

**Client-side payout recalculation** (lines 441-496 of ClaimsWorkbenchPage) — This directly violates the CLAUDE.md "Single Source of Truth for Computed Values" rule. The "what-if" override math recomputes payout with VAT, deductible, and cap logic that should only live in `screener._calculate_payout()`. If the formula changes server-side, this will silently diverge.

**Mid-file imports in `client.ts`** (lines 131, 1496) — Indicates the file grew organically. Imports should be at the top.

**No error boundaries** — No `ErrorBoundary` components found. A crash in `ClaimDetail` will take down the entire page rather than just showing a fallback.

---

## 5. WHAT NOT TO DO

- **Don't add React.memo everywhere** — Components re-render on real data changes (claim expansion, tab switches). Memoizing would add complexity without measurable gain for this data size.
- **Don't introduce a state management library** — 4 contexts + local state is appropriate for this scale.
- **Don't split types/index.ts right now** — It's large but navigable with IDE search. Lower ROI than splitting the actual component files.
- **Don't refactor the shared barrel files** — They work fine with Vite's tree-shaking.

---

## 6. PRIORITY RANKING

| Priority | Action | Impact |
|----------|--------|--------|
| **1** | Split `ClaimsWorkbenchPage.tsx` into a directory | Biggest single file, hardest to maintain |
| **2** | Type the `WorkbenchData` response (kill `any`) | Prevents runtime bugs, enables IDE support |
| **3** | Split `api/client.ts` by domain | Easier to find and modify endpoints |
| **4** | Move payout what-if recalculation to a backend endpoint | Fixes SSOT violation |
| **5** | Split `PipelineControlCenter.tsx` into tab files | Same pattern as #1, smaller impact |
| **6** | Add `ErrorBoundary` around expandable sections | Prevents cascade failures |
