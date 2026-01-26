# Assessment History Tab - Fix Plan

## Problem Summary

After running a re-assessment:
1. The History tab doesn't show previous assessments
2. Badge shows "2" assessments but the list is empty or shows wrong data
3. The "Assessment Complete" card shows 0 tokens (separate issue with WebSocket)

## Root Cause Analysis

### Issue 1: Field Name Mismatch (Primary Issue)

The backend returns different field names than what the frontend expects:

| Backend Returns | Frontend Expects |
|-----------------|------------------|
| `id` | `run_id` |
| `checks_passed` | `pass_count` |
| `checks_total` | `check_count` |
| (not returned) | `fail_count` |

**Backend code** (`assessment.py:390-402`):
```python
history.append({
    "id": entry.get("id"),                    # Wrong name
    "timestamp": entry.get("timestamp"),
    "decision": entry.get("decision"),
    "confidence_score": confidence,
    "checks_passed": checks_passed,           # Wrong name
    "checks_total": checks_total,             # Wrong name
    "assumption_count": assumption_count,
    "is_current": entry.get("is_current", False),
})
```

**Frontend expects** (`ClaimHistoryTab.tsx:8-18`):
```typescript
export interface AssessmentHistoryEntry {
  run_id: string;           // Expected name
  timestamp: string;
  decision: AssessmentDecision;
  confidence_score: number;
  check_count: number;      // Expected name
  pass_count: number;       // Expected name
  fail_count: number;       // Expected name (calculated)
  assumption_count: number;
  is_current: boolean;
}
```

### Issue 2: History Doesn't Auto-Refresh After Re-run

In `ClaimSummaryTab.tsx`, after a re-run completes:
- `handleRefreshAssessment()` is called (refreshes assessment data)
- But `history` is NOT refreshed
- User must manually navigate away and back to see updated history

### Issue 3: Progress Card Shows 0 Tokens

The WebSocket progress card shows "0 Input tokens / 0 Output tokens" - this is a separate issue with the WebSocket not receiving token counts during the assessment run.

---

## Implementation Steps

### Step 1: Fix Backend Field Names

**File:** `src/context_builder/api/services/assessment.py`

Change the `get_assessment_history()` method to return frontend-compatible field names:

```python
# Lines 390-402: Change field names
history.append({
    "run_id": entry.get("id"),                              # Renamed
    "timestamp": entry.get("timestamp"),
    "decision": entry.get("decision"),
    "confidence_score": confidence,
    "check_count": checks_total,                            # Renamed
    "pass_count": checks_passed,                            # Renamed
    "fail_count": checks_total - checks_passed,             # Added
    "assumption_count": assumption_count,
    "is_current": entry.get("is_current", False),
})

# Lines 410-426: Also fix the fallback single-entry case
return [
    {
        "run_id": None,                                     # Renamed
        "timestamp": assessment.get("assessed_at"),
        "decision": assessment.get("decision"),
        "confidence_score": assessment.get("confidence_score"),
        "check_count": len(assessment.get("checks", [])),   # Renamed
        "pass_count": sum(...),                             # Renamed
        "fail_count": checks_total - checks_passed,         # Added
        "assumption_count": len(assessment.get("assumptions", [])),
        "is_current": True,
    }
]
```

### Step 2: Add History Refresh Callback

**File:** `ui/src/components/ClaimExplorer/ClaimSummaryTab.tsx`

1. Create a `handleRefreshHistory` callback similar to `handleRefreshAssessment`
2. Pass it to `ClaimAssessmentTab` as a new prop `onRefreshHistory`

```typescript
// Add after handleRefreshAssessment
const handleRefreshHistory = useCallback(async () => {
  setHistoryLoading(true);
  setHistoryError(null);
  try {
    const data = await getAssessmentHistory(claim.claim_id);
    setHistory(data);
  } catch (err) {
    console.warn("History refresh error:", err);
    setHistoryError(err instanceof Error ? err.message : "Failed to load history");
    setHistory([]);
  } finally {
    setHistoryLoading(false);
  }
}, [claim.claim_id]);

// In ClaimAssessmentTab usage, add:
onRefreshHistory={handleRefreshHistory}
```

**File:** `ui/src/components/ClaimExplorer/ClaimAssessmentTab.tsx`

1. Add `onRefreshHistory?: () => Promise<void>` to props interface
2. Call `onRefreshHistory()` in `handleViewResult` and `handleDismissProgress`

```typescript
// Props interface
interface ClaimAssessmentTabProps {
  // ... existing props
  onRefreshHistory?: () => Promise<void>;
}

// In handleViewResult
const handleViewResult = useCallback(() => {
  reset();
  if (onRefreshAssessment) {
    onRefreshAssessment();
  }
  if (onRefreshHistory) {
    onRefreshHistory();
  }
}, [reset, onRefreshAssessment, onRefreshHistory]);

// In handleDismissProgress
const handleDismissProgress = useCallback(() => {
  reset();
  if (progress.status === "completed") {
    if (onRefreshAssessment) onRefreshAssessment();
    if (onRefreshHistory) onRefreshHistory();
  }
}, [reset, progress.status, onRefreshAssessment, onRefreshHistory]);
```

---

## Files to Modify

| File | Change |
|------|--------|
| `src/context_builder/api/services/assessment.py` | Fix field names in `get_assessment_history()` |
| `ui/src/components/ClaimExplorer/ClaimSummaryTab.tsx` | Add `handleRefreshHistory` callback, pass to child |
| `ui/src/components/ClaimExplorer/ClaimAssessmentTab.tsx` | Add `onRefreshHistory` prop, call on completion |

---

## Verification Steps

1. **Backend Test:**
   ```bash
   curl http://localhost:8000/api/claims/CLM-65196/assessment/history | jq
   ```
   Should return fields: `run_id`, `check_count`, `pass_count`, `fail_count`

2. **Frontend Test:**
   - Run an assessment
   - Click "View Result"
   - Navigate to History tab
   - Should see all previous assessment runs with correct data

3. **TypeScript Compilation:**
   ```bash
   cd ui && npx tsc --noEmit
   ```

---

## Out of Scope (Token Count Issue)

The "0 Input tokens / 0 Output tokens" shown in the progress card is a separate issue:
- WebSocket receives progress updates but token counts are not being populated
- This requires investigating the pipeline's token tracking
- Will be addressed in a separate fix
