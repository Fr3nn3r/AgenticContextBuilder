# UI Test Plan (Unit + E2E)

Purpose: protect critical user flows, catch regressions early, and give you confidence in releases.
Scope: React UI under `ui/`.

## Test Strategy Overview
- **Unit/Component tests**: fast checks for component behavior, rendering, and state changes. Use existing `ui/src/components/__tests__`.
- **E2E tests**: real user flows in a browser with a running backend (or stubbed API). Use Playwright config already in `ui/`.
- **Risk-based focus**: prioritize the flows that are easiest to break and hardest to notice.

## Critical User Flows (E2E Priority)
These are the “must work” flows where regressions are most costly.

1) **New Claim → Upload → Run Pipeline**
- Steps:
  - Open `/claims/new`
  - Create a new claim
  - Upload 1–2 documents
  - Start pipeline
  - Verify progress updates
  - Verify completion state and "View in Claims Review" link works
- Risks covered:
  - Upload failures, pipeline start failure, websocket status issues

2) **Batches → Extraction Overview**
- Steps:
  - Open `/batches`
  - Select a batch
  - Verify summary stats render
  - Verify coverage progress bars
  - Verify doc type scoreboard populates
- Risks covered:
  - Missing/incorrect insights, broken layout, data mapping issues

3) **Batch → Claims Table → Expand Claim → Open Doc**
- Steps:
  - Open `/batches/:id/claims`
  - Expand a claim
  - Open a document
  - Verify review route loads
- Risks covered:
  - Claim list filtering, navigation, doc loading

4) **Document Review (Classification + Field Review)**
- Steps:
  - Open `/batches/:id/documents`
  - Select a document
  - Verify classification panel loads
  - Label a field and save
  - Verify auto-advance to next doc
- Risks covered:
  - Saving, classification overrides, label state persistence

5) **Claim Review (Single Claim)**
- Steps:
  - Open `/claims/:claimId/review`
  - Navigate docs, edit a truth value, save
  - Verify status updates (labeled/unlabeled)
- Risks covered:
  - Data sync issues, state corruption, navigation bugs

6) **Pipeline Control Center**
- Steps:
  - Open `/pipeline`
  - Start a batch (if allowed)
  - Cancel a running batch
  - Delete a batch
  - Verify status badges map correctly
- Risks covered:
  - Status mapping, actions wiring, stale data

## Component/Unit Tests (High Value)
Focus on behavior that breaks easily but is hard to spot.

1) **ClaimsTable**
- Filters:
  - Gate status filters (PASS/WARN/FAIL)
  - Unlabeled filter
  - Search filtering
- Sorting:
  - Sorting by claim ID, doc count, gate status
- Expand behavior:
  - Expands only one claim at a time
  - Shows “Review next unlabeled” button only when needed

2) **FieldsTable**
- Labeling actions:
  - Confirm extracted value
  - Set manual truth value
  - Mark unverifiable
  - Edit truth value
- Evidence click calls `onQuoteClick` with correct args
- Optional field toggle behavior

3) **DocumentViewer**
- Tab availability (text/pdf/image)
- Highlight behavior (quote + page change triggers)
- Azure DI lazy load (only fetch when needed)

4) **PipelineControlCenter**
- Status mapping (cancelled ≠ failed)
- Batch filtering (status + needs attention)
- Default prompt config selection (uses effect)

5) **NewClaimPage**
- Claim creation + removal
- Upload state + progress handling
- “Run Pipeline” disabled/enabled correctly

## E2E Test Coverage Matrix (Sample)
| Flow | Route | Key assertions |
| --- | --- | --- |
| New claim upload | `/claims/new` | Upload works, run starts, progress updates |
| Batch summary | `/batches/:id` | Metrics render, progress bars visible |
| Claims review list | `/batches/:id/claims` | filters + expand works |
| Document review | `/batches/:id/documents` | select doc, save, auto-advance |
| Claim review | `/claims/:id/review` | doc nav + save works |
| Pipeline control | `/pipeline` | start/cancel/delete, status labels |

## Test Data & Environment
- **Minimum dataset** for reliable tests:
  - 1 batch with 2 claims
  - 4–6 docs total
  - At least one doc with extraction + labels
  - At least one doc without extraction
  - At least one doc with gate WARN/FAIL
- **Blindspot**: E2E tests fail if backend data changes. Use seeded test data or snapshots.
- **Recommendation**: add a “test fixtures” mode in backend (or load data from `examples/`).

## Suggested Playwright E2E Setup
- Run `uvicorn` backend + `npm run dev` frontend
- Use Playwright tests under `ui/e2e/`
- Keep tests deterministic:
  - Use known test data or mock API responses
  - Avoid relying on timing (use `await expect` for UI states)

## Blindspots to Watch (Common UI Gaps)
- **Accessibility**: clickable rows aren’t focusable by keyboard
- **Race conditions**: fast clicks cause stale data to render
- **Empty states**: new runs without data render “garbled” placeholders
- **Status mapping**: cancelled vs failed vs partial
- **Encoding issues**: check for hidden invalid characters in UI strings
- **Performance**: many API calls in lists (DocumentReview)

## Open Questions (Please Answer)
1) Do you want E2E tests to run against a **live backend** or a **mock/stubbed API**?
2) Do you have **stable test data** you can seed, or should we build a fixture loader?
3) Which flow is **most critical** for your team (top 1–2)?
4) Any **browser targets** beyond Chromium (Firefox, WebKit)?
5) Do you want **accessibility checks** (a11y) included in CI?

