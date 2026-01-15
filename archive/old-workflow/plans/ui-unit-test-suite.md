# UI Unit Test Suite Implementation Plan

## Goal
Establish a complete, maintainable UI unit test suite for `ui/` using Vitest, focusing on core logic, rendering states, and critical user flows without over-engineering.

## Scope
- Unit tests for UI logic, utilities, and component behavior.
- Mock API boundaries; avoid real network calls.
- Keep e2e tests (Playwright) as-is, but ensure unit tests cover core UI logic.

## Assumptions
- Vitest is already wired in `ui/package.json` and `ui/vite.config.ts`.
- TypeScript build must remain clean.
- Prefer minimal mocking and stable fixtures.

## Test Strategy
1. **Utilities / Pure Logic (highest ROI)**
   - `ui/src/lib/utils.ts` (`cn`)
   - Mapping helpers (if added later) for status, labels, or UI state logic.
2. **API Client Layer**
   - `ui/src/api/client.ts` request composition and response handling (mock fetch).
3. **Core Components (shallow-ish render + key behavior)**
   - `FieldsTable`: label state transitions, progress counts, optional fields toggle.
   - `DocumentViewer` / `PageViewer`: render states and highlight behaviors (mock PDF/Image internals).
   - `RunSelector`: selection callbacks and derived label text.
4. **Page Components (minimal smoke tests)**
   - `DocReview`, `ClaimReview`, `DocumentReview` basic render + loading/error states.
   - Avoid full flows that are better suited for e2e.

## Implementation Steps
1. **Define test harness utilities**
   - Add helpers for creating mock `DocPayload`, `ExtractionResult`, `FieldLabel`.
   - Add helper for mock `fetch` (API client).
2. **Unit tests for pure utilities**
   - Extend `ui/src/lib/__tests__/utils.test.ts` as needed.
3. **API client tests**
   - Create `ui/src/api/__tests__/client.test.ts` with fetch mocking.
4. **Component tests: core**
   - `FieldsTable` tests:
     - renders fields with correct labels/status.
     - triggers `onConfirm`, `onUnverifiable`, `onEditTruth`.
     - respects `showOptionalFields`.
5. **Component tests: viewer + selectors**
   - `RunSelector`: correct options + onChange.
   - `DocumentViewer` basic rendering without requiring PDF runtime (mock children).
6. **Page component smoke tests**
   - `DocReview` renders loading/error state.
   - `ClaimReview` renders header + doc list when data is present.
   - `DocumentReview` renders empty state when no run selected.
7. **CI/Docs updates**
   - Document test commands in `README.md` or `ui/README.md` if present.

## Deliverables
- Test helpers in `ui/src/test/` or `ui/src/__tests__/helpers/`.
- Unit tests in `ui/src/**/__tests__/*.test.ts(x)`.
- Documentation entry for `npm run test` (unit) vs `npm run test:e2e`.

## Non-goals
- Full e2e coverage (handled by Playwright).
- Snapshot-heavy testing.
- Full DOM/visual regression coverage.

## Validation
- `cd ui && npm run test`
- Ensure tests run fast (<5s locally) and avoid flakiness.
