# Frontend Code Review (January 14, 2026)

This review focuses on the React + TypeScript UI in `ui/`. It highlights the most important issues first, and explains them in simple language. Each item includes a file + line reference so you can jump to the exact spot.

## Findings (Highest Impact First)

### 1) Claim filters do not match the UI options (filters look broken)
- Where: `ui/src/App.tsx:103`, `ui/src/App.tsx:108`, `ui/src/components/ClaimsTable.tsx:159`, `ui/src/components/ClaimsTable.tsx:171`
- What happens: The UI offers filters like "Has FAIL docs" and "Has unlabeled docs", but the filtering code compares against `c.status` and `c.lob`. Those values never equal `has_fail`, `has_warn`, `all_pass`, or `has_unlabeled`, so the filters mostly do nothing.
- Why this matters: Users select filters and see no change, which feels like the app is broken.
- Simple fix: Update the filter logic in `App.tsx` to use the data you actually want to filter on (for example, `gate_fail_count > 0` for "Has FAIL docs", and `labeled_count < doc_count` for "Has unlabeled docs").

### 2) Cancelled pipeline runs are shown as failed
- Where: `ui/src/components/PipelineControlCenter.tsx:27`, `ui/src/components/PipelineControlCenter.tsx:33`
- What happens: A run with status `cancelled` is mapped to `failed`, so the UI shows the wrong state.
- Why this matters: It confuses users and hides the real reason the run stopped.
- Simple fix: Map `cancelled` to `cancelled` (not `failed`) and use the `CANCELLED` badge you already defined.

### 3) Garbled characters appear in the UI (text looks corrupted)
- Where:
  - `ui/src/components/FieldsTable.tsx:231`, `ui/src/components/FieldsTable.tsx:235`, `ui/src/components/FieldsTable.tsx:362`
  - `ui/src/components/ExtractionPage.tsx:134`, `ui/src/components/ExtractionPage.tsx:151`, `ui/src/components/ExtractionPage.tsx:354`
  - `ui/src/components/PipelineControlCenter.tsx:235`, `ui/src/components/PipelineControlCenter.tsx:714`, `ui/src/components/PipelineControlCenter.tsx:817`
- What happens: Strings like `ƒ?""` and `Aú` show up in the UI instead of normal text (likely from encoding or copy/paste).
- Why this matters: It looks unprofessional and makes the interface harder to read.
- Simple fix: Replace those strings with normal ASCII (for example, use `"-"` or `"N/A"` and `"·"` -> `"·"` is still non-ASCII; use `" - "` or `" / "` if you want to stay ASCII-only).

### 4) `useMemo` is used for side effects (can lead to confusing behavior)
- Where: `ui/src/components/PipelineControlCenter.tsx:898`
- What happens: `useMemo` is used to set state (`setPromptConfig`). `useMemo` is meant for pure calculations, not for running side effects.
- Why this matters: It makes the component harder to reason about and can cause subtle bugs in React.
- Simple fix: Replace this `useMemo` with `useEffect`.

### 5) Time filter in Batches tab is not wired up
- Where: `ui/src/components/PipelineControlCenter.tsx:428`, `ui/src/components/PipelineControlCenter.tsx:431`
- What happens: The UI lets you select "Last 24 hours / 7 days / 30 days", but the filter is never applied.
- Why this matters: Users think they are filtering the list, but nothing changes.
- Simple fix: Apply `timeFilter` inside `filteredBatches` or remove the control until it is implemented.

### 6) Race condition when selecting claims can show the wrong documents
- Where: `ui/src/App.tsx:176`, `ui/src/components/ClaimsTable.tsx:271`
- What happens: If a user clicks claims quickly, the slower network response can overwrite the document list for the most recently selected claim.
- Why this matters: The UI can show documents for the wrong claim, which is confusing and risky for review work.
- Simple fix: Track the active claim ID when the request starts, and only apply results if it still matches the active claim.

### 7) Keyboard accessibility issues (clickable rows are not focusable)
- Where:
  - `ui/src/components/ClaimsTable.tsx:271`
  - `ui/src/components/DocumentReview.tsx:591`
- What happens: Rows are clickable but not keyboard-focusable, so keyboard users cannot use them.
- Why this matters: It blocks accessibility and can fail basic a11y checks.
- Simple fix: Use real buttons/links or add `role="button"` + `tabIndex={0}` + key handlers.

### 8) Many per-claim API calls when loading document review
- Where: `ui/src/components/DocumentReview.tsx:107`
- What happens: The UI requests `listDocs` for every claim to find docs with extraction. This can create a lot of network calls for large runs.
- Why this matters: Performance slows down as the run size grows.
- Simple fix: Ask the backend for a single API that returns docs with extraction status, or return `has_extraction` directly in the classification list.

## Smaller Issues / Nice-to-Haves
- `ui/src/api/client.ts`: `fetchJson` always calls `response.json()` even for empty responses (204). This can throw. Consider checking `response.status === 204` and returning `null` or a default object.
- `ui/src/components/DocumentViewer.tsx`: `setTimeout` calls in the highlight logic have no cleanup. In practice it is likely fine, but it can cause small memory leaks if switching docs rapidly.

## Tests & Coverage Gaps (UI)
- There are tests in `ui/src/components/__tests__`, but high-impact flows like claim filtering, batch status mapping, and document list selection do not appear to be covered.
- Recommended: add tests for:
  - Claim filters (including "Has FAIL docs" and "Has unlabeled docs")
  - Batch status mapping (cancelled should not appear as failed)
  - Document selection race (verify docs list matches selected claim)

## Suggested Next Steps (Simple)
1) Fix claim filters in `App.tsx` so the UI filters actually work.
2) Fix cancelled run mapping and remove garbled characters.
3) Add a small guard to prevent stale doc lists when selecting claims quickly.
4) Replace the `useMemo` side effect with `useEffect`.
5) Decide whether to implement or remove the time filter.

