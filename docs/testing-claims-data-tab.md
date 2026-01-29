# Handoff: Claims Data (Reconciliation) Tab Testing

## What Was Implemented

A new **"Data" tab** was added to the ClaimExplorer showing reconciliation results:
- Claim run version selector (dropdown to switch between reconciliation versions)
- Gate status card (pass/warn/fail with metrics and reasons)
- Conflicts list (expandable, with source document links)
- All aggregated facts grouped by document type

## Files Changed

### Backend
- `src/context_builder/api/routers/claims.py` - Added 2 new endpoints (lines 629-688)

### Frontend
- `ui/src/types/index.ts` - Added 4 new interfaces (lines 876-920)
- `ui/src/api/client.ts` - Added 3 new API functions (lines 130-172)
- `ui/src/components/ClaimExplorer/ClaimRunSelector.tsx` - **NEW**
- `ui/src/components/ClaimExplorer/ReconciliationStatusCard.tsx` - **NEW**
- `ui/src/components/ClaimExplorer/ConflictsList.tsx` - **NEW**
- `ui/src/components/ClaimExplorer/ClaimDataTab.tsx` - **NEW**
- `ui/src/components/ClaimExplorer/ClaimSummaryTab.tsx` - Added Data tab integration

## Testing Instructions

### 1. Backend API Tests
```bash
# Start backend
uvicorn context_builder.api.main:app --reload --port 8000

# Test endpoints (replace with actual claim_id and claim_run_id from your workspace)
curl http://localhost:8000/api/claims/{claim_id}/claim-runs
curl http://localhost:8000/api/claims/{claim_id}/claim-runs/{claim_run_id}/facts
curl http://localhost:8000/api/claims/{claim_id}/claim-runs/{claim_run_id}/reconciliation-report
```

### 2. Frontend Tests
```bash
cd ui && npm run dev
```

Navigate to: `http://localhost:5173` → Claims → Select a claim → Click **"Data"** tab

### 3. Test Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| Claim with no runs | Shows "No Claim Runs" message |
| Claim with runs, no report | Shows run selector, "No reconciliation report" message |
| Claim with full data | Shows gate status, conflicts (if any), all facts |
| Switch claim runs | Data reloads for selected run |
| Click "View" on conflict | Opens document slide panel |
| Click fact with provenance | Opens document at source location |
| Gate status = pass | Green card with checkmark |
| Gate status = warn | Amber card with warning icon |
| Gate status = fail | Red card with X icon |

### 4. Visual Checks
- [ ] Data tab icon (Database) appears in tab bar
- [ ] Claim run selector shows formatted timestamps
- [ ] Gate status card shows metrics (conflicts, missing critical, facts, coverage %)
- [ ] Conflicts are expandable with selected value highlighted in blue
- [ ] Facts are grouped by doc_type with collapsible sections
- [ ] Dark mode styling works correctly

### 5. Edge Cases
- Claim with 0 facts but has reconciliation report
- Claim run with conflicts but 100% coverage
- Very long fact values (should truncate)
- Multiple claim runs (selector should list all, newest first)

## Data Requirements

For full testing, you need a workspace with:
1. At least one claim that has been through the reconciliation pipeline
2. Claim runs stored in `claims/{claim_id}/claim_runs/{claim_run_id}/`
3. Files: `manifest.json`, `claim_facts.json`, `reconciliation_report.json`

If no test data exists, run:
```bash
python -m context_builder.cli pipeline <input_claims_folder>
```

## Known Limitations
- Read-only UI (no actions/edits)
- Conflicts only show doc_id in source, not full provenance path
- Facts panel uses simplified grouping (by doc_type only)
