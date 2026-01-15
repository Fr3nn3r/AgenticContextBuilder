# E2E Test Suite Issues Report

**Date:** 2026-01-14
**Initial Test Results:** 61 passed, 12 failed, 5 skipped, 4 did not run
**Final Status:** ✅ **77 passed, 5 skipped**

## Summary

All issues have been **resolved**:
- ✅ Tab rename ("Benchmark" → "Metrics") - all tests passing
- ✅ Metrics page tabs - tests updated and passing
- ✅ Doc strip labeled indicator - now passing
- ✅ Document labeling flow - fixed mock routes and selectors
- ✅ Visual regression - snapshot updated

## Fixes Applied

### 1. Mock API Route Patterns (`e2e/utils/mock-api.ts`)
Updated glob patterns to regex patterns to properly match URLs with query parameters:
- `/api/classification/docs?run_id=...` → `/\/api\/classification\/docs(\?.*)?$/`
- `/api/claims/:claimId/docs?run_id=...` → `/\/api\/claims\/[^/]+\/docs(\?.*)?$/`
- `/api/classification/stats?run_id=...` → `/\/api\/classification\/stats(\?.*)?$/`

### 2. Document Labeling Test Selectors (`e2e/tests/document-labeling.spec.ts`)
- Added explicit wait for documents to load
- Changed overly broad `div` selector to specific `.p-3` class selector
- Fixed selected row selector from escaped Tailwind classes to simpler `.border-l-2.border-accent`

### 3. Visual Regression Snapshot
- Updated `insights-chromium-win32.png` baseline to match current Metrics page UI

---

## Skipped Tests (5 tests)

The following tests in `claims-table.spec.ts` remain skipped:
- `should display claims list`
- `should have search input`
- `should expand claim to show documents`
- `should navigate to review when clicking document`
- `should filter claims by search`

These tests were intentionally skipped and should be reviewed to determine if they should be re-enabled or removed.

---

## Historical Issues (Resolved)

### Issue #1: Benchmark Tab Renamed to Metrics (9 tests) - RESOLVED

### Root Cause
The `BatchSubNav.tsx` component was refactored to rename the "Benchmark" tab to "Metrics":

**Current implementation (`ui/src/components/shared/BatchSubNav.tsx:10-16`):**
```typescript
const tabs: { id: BatchTab; label: string; path: string }[] = [
  { id: "overview", label: "Overview", path: "" },
  { id: "documents", label: "Documents", path: "/documents" },
  { id: "classification", label: "Classification", path: "/classification" },
  { id: "claims", label: "Claims", path: "/claims" },
  { id: "metrics", label: "Metrics", path: "/metrics" },  // Was "benchmark"
];
```

The tab now generates `data-testid="batch-tab-metrics"` instead of `batch-tab-benchmark`.

**App.tsx has a redirect** (`ui/src/App.tsx:402-405`):
```typescript
{/* Redirect old benchmark URL to new metrics */}
<Route
  path=":batchId/benchmark"
  element={<Navigate to="../metrics" replace />}
/>
```

### Affected Tests

| Test File | Test Name | Line |
|-----------|-----------|------|
| `batch-selector.spec.ts` | batch context persists across tab navigation | 44 |
| `batch-selector.spec.ts` | batch context header shows batch metadata | 75 |
| `batch-selector.spec.ts` | switching batch updates display | 86 |
| `batch-selector.spec.ts` | KPI cards are visible | 102 |
| `batch-selector.spec.ts` | tabs are visible and clickable | 114 |
| `insights-run-scope.spec.ts` | displays correct KPIs for small batch | 16 |
| `navigation.spec.ts` | should navigate between batch workspace tabs | 87 |
| `smoke.spec.ts` | batch workspace displays context bar and tabs | 31 |
| `smoke.spec.ts` | batch workspace tabs navigate correctly | 94 |
| `visual.spec.ts` | Calibration Insights layout | 51 |

### Files Requiring Updates

1. **`e2e/pages/insights.page.ts`** - Line 29:
   ```typescript
   // Change:
   await this.page.getByTestId("batch-tab-benchmark").click();
   // To:
   await this.page.getByTestId("batch-tab-metrics").click();
   ```
   Also update `gotoWithBatch()` route on line 34 from `/benchmark` to `/metrics`.

2. **`e2e/tests/batch-selector.spec.ts`** - Lines 62, 63:
   - Change `batch-tab-benchmark` → `batch-tab-metrics`
   - Change URL regex `/benchmark/` → `/metrics/`

3. **`e2e/tests/insights-run-scope.spec.ts`** - Multiple lines (20, 35, 54, 75, 101):
   - Change `batch-tab-benchmark` → `batch-tab-metrics`

4. **`e2e/tests/navigation.spec.ts`** - Lines 107-108:
   - Change `batch-tab-benchmark` → `batch-tab-metrics`
   - Change URL regex `/benchmark/` → `/metrics/`

5. **`e2e/tests/smoke.spec.ts`** - Lines 47, 103-104:
   - Change `batch-tab-benchmark` → `batch-tab-metrics`
   - Change URL regex `/benchmark/` → `/metrics/`

6. **`e2e/tests/visual.spec.ts`** - Line 55:
   - Change `batch-tab-benchmark` → `batch-tab-metrics`

---

## Issue #2: Labeled Status Indicator (1 test)

### Test
`claim-review.spec.ts:121` - "doc strip shows labeled status indicator"

### Failure
```
Error: locator.isVisible: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('svg.text-green-500')
```

### Analysis
The test expects a green checkmark SVG (`svg.text-green-500`) to indicate labeled status on documents:

**Test code (`e2e/tests/claim-review.spec.ts:127-134`):**
```typescript
const docWithLabels = review.docStripItems.filter({
  hasText: "police_report",
});
await expect(docWithLabels).toBeVisible();

// The labeled doc should have a checkmark
const checkmark = docWithLabels.locator("svg.text-green-500");
await expect(checkmark).toBeVisible();
```

**Fixture has the data** (`e2e/fixtures/claim-review.json:37-38`):
```json
{
  "doc_id": "doc_002",
  "doc_type": "police_report",
  "has_labels": true,
  ...
}
```

### Possible Causes
1. The component may have changed how it renders the labeled status indicator (different icon class, different element type)
2. The styling class may have changed from `text-green-500` to something else
3. The labeled indicator may be conditionally rendered based on additional state

### Investigation Needed
Review the doc strip item component in `ClaimReview.tsx` or related component to verify how `has_labels: true` is rendered visually.

---

## Issue #3: Document Labeling Flow (1 test)

### Test
`document-labeling.spec.ts:9` - "labels a document and auto-advances to next pending"

### Failure
```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: /confirm/i })
```

### Analysis
The test expects a "Confirm" button to appear after clicking on a field:

**Test code (`e2e/tests/document-labeling.spec.ts:19-21`):**
```typescript
// Expand a field and confirm it to enable Save
await page.getByText("Date Of Loss", { exact: true }).click();
await page.getByRole("button", { name: /confirm/i }).click();
```

### Possible Causes
1. The field labeling UX may have changed - "Confirm" button may no longer exist
2. The field expansion interaction may have changed
3. Field labeling may now use a different workflow (inline editing, modal, etc.)

### Investigation Needed
Review the `FieldsTable.tsx` component to understand the current field labeling interaction pattern.

---

## Skipped Tests (5 tests)

The following tests in `claims-table.spec.ts` are skipped (marked with `-`):
- `should display claims list` (line 15)
- `should have search input` (line 25)
- `should expand claim to show documents` (line 32)
- `should navigate to review when clicking document` (line 43)
- `should filter claims by search` (line 53)

These tests were likely skipped intentionally (using `test.skip()`) and should be reviewed to determine if they should be re-enabled or removed.

---

## Recommended Fix Order

1. **High Priority - Tab Rename (9 tests)**
   - Single search-and-replace operation across 6 files
   - Changes: `batch-tab-benchmark` → `batch-tab-metrics`, `/benchmark` → `/metrics`

2. **Medium Priority - Labeled Status Indicator (1 test)**
   - Investigate component changes
   - Update test selector to match current implementation

3. **Medium Priority - Document Labeling Flow (1 test)**
   - Investigate field labeling UX changes
   - Update test to match current workflow

4. **Low Priority - Skipped Tests (5 tests)**
   - Review why tests are skipped
   - Re-enable or remove as appropriate

---

## Quick Fix Commands

For the benchmark→metrics rename, run these sed commands (or use IDE find-replace):

```bash
# In e2e/ directory
find . -name "*.ts" -exec sed -i 's/batch-tab-benchmark/batch-tab-metrics/g' {} \;
find . -name "*.ts" -exec sed -i 's/\/benchmark/\/metrics/g' {} \;
```

**Note:** Manual review recommended after automated replacement to ensure URL patterns don't break other things.
