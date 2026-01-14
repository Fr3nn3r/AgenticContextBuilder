# SOLID Refactor Plan (Frontend)

Goal: improve SOLID compliance without breaking features. Keep changes small and incremental.

## Plan (Low Risk, Incremental)

1) Create dedicated data hooks (SRP, DIP)
- New files:
  - `ui/src/hooks/useClaimsData.ts`
  - `ui/src/hooks/useDocumentReviewData.ts`
- Move data fetching, filtering, and selection state out of:
  - `ui/src/App.tsx`
  - `ui/src/components/DocumentReview.tsx`
- Result: pages become mostly UI.

2) Split large pages into smaller components (SRP, ISP)
- Break `ui/src/components/DocumentReview.tsx` into:
  - `ui/src/components/document-review/DocumentListPanel.tsx`
  - `ui/src/components/document-review/DocumentViewerPanel.tsx`
  - `ui/src/components/document-review/FieldsPanel.tsx`
- Extract a `ClaimsView` container from `ui/src/App.tsx`:
  - `ui/src/components/claims/ClaimsView.tsx`

3) Reduce prop surface (ISP)
- Remove unused props from:
  - `ui/src/components/ClaimsTable.tsx`
  - `ui/src/components/DocumentReview.tsx`
- Update parents accordingly.

4) Centralize domain mappings (OCP)
- Move hard-coded mappings out of UI:
  - `fieldDisplayNames`
  - `expectedFieldsByDocType`
- New file:
  - `ui/src/lib/fieldConfig.ts`

5) Add a small API service interface (DIP)
- New file:
  - `ui/src/api/service.ts`
- Hooks depend on this interface, not raw API calls.
- Easier to mock for tests.

6) Add targeted tests (regression safety)
- Add tests for:
  - Claim filters (especially "Has FAIL docs" and "Has unlabeled docs")
  - Document selection and data load
  - Cancelled status mapping

## Suggested Order to Implement
1) Data hooks
2) Component splits
3) Prop cleanup
4) Config extraction
5) API service interface
6) Tests

