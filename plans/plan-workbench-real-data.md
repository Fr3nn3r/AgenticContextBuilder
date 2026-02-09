# Plan: Connect Claims Workbench to Real Data

## Problem

The Claims Workbench currently loads ALL claims via `getDashboardClaims()` and then tries to enrich each one with workbench data. Most claims don't have a decision trail (no `decision_dossier_v*.json`), so they show empty/incomplete data. We need to:

1. **Only show claims with complete decision trails** (dossier exists)
2. **Load data efficiently** — don't pre-load workbench data for every claim serially
3. **Ensure clause data quality** — `clause_text` and `assumption_question` are populated correctly

## Current Data Flow

```
Frontend                          Backend
─────────                         ─────────
getDashboardClaims() ──────────→  DashboardService.list_claims()
  returns ALL claims                iterates every claim folder
                                    loads latest assessment.json

For EACH claim (serial):
getWorkbenchData(id) ──────────→  DecisionDossierService.get_workbench_data()
  enriches table columns            reads facts, screening, coverage, assessment, dossier
                                    returns null if no claim_runs or no dossier
```

**Problems:**
- Pre-loads workbench data for all 50+ claims serially (slow, most fail)
- No way to know upfront which claims have dossiers
- Claims without decision trails show as empty rows

## Solution

### Step 1: Add `has_decision_dossier` flag to Dashboard claims endpoint

**File:** `src/context_builder/api/services/dashboard.py`

In `list_claims()`, after finding the latest assessment, check if a `decision_dossier_v*.json` file exists in the same claim run directory:

```python
# After line ~261 (after getting assessment and claim_run_id)
has_dossier = False
if claim_run_id:
    run_dir = claim_dir / "claim_runs" / claim_run_id
    has_dossier = bool(list(run_dir.glob("decision_dossier_v*.json")))
```

Add `"has_decision_dossier": has_dossier` to the results dict (line ~354).

**Why not a separate endpoint?** The dashboard service already iterates all claims and has the claim_run_id. Checking one glob per claim is trivial overhead.

### Step 2: Add TypeScript type for the new flag

**File:** `ui/src/types/index.ts`

Add `has_decision_dossier?: boolean` to `DashboardClaim` interface.

### Step 3: Filter workbench to only show claims with decision trails

**File:** `ui/src/pages/ClaimsWorkbenchPage.tsx`

In `loadClaims()`, filter the result:

```typescript
const list = await getDashboardClaims();
setClaims(list.filter(c => c.has_decision_dossier));
```

In the pre-load enrichment `useEffect`, only pre-load for claims that have dossiers (they all will now, since we filtered). Also batch the requests with `Promise.allSettled` instead of serial loop for better performance:

```typescript
useEffect(() => {
  if (claims.length === 0) return;
  let cancelled = false;

  async function preload() {
    const results = await Promise.allSettled(
      claims.map(c => getWorkbenchData(c.claim_id))
    );
    if (cancelled) return;
    const cache: Record<string, WorkbenchEnrichment> = {};
    results.forEach((r, i) => {
      if (r.status === "fulfilled" && r.value) {
        cache[claims[i].claim_id] = buildEnrichment(r.value);
      }
    });
    setEnrichmentCache(cache);
  }

  preload();
  return () => { cancelled = true; };
}, [claims]);
```

### Step 4: Verify clause data quality in denial_clauses.json

**File:** `workspaces/nsa/config/decision/denial_clauses.json` (customer config)

**Status:** Already good. Checked the file — clauses have:
- `text`: Full policy text (e.g., "There is no obligation to pay benefits if the damage was caused by...")
- `assumption_question`: Full sentence questions where applicable (e.g., "Is the failed component covered by the policy?")
- Some clauses have `assumption_question: null` — these are tier 1 (deterministic, no assumption needed) or tier 3 preamble clauses. This is correct behavior.

No changes needed here.

### Step 5: Verify confidence scoring is correct end-to-end

**Status:** Already fixed in the frontend. The issue was:
- `assessment.json` stores `confidence_score` as 0-1 (e.g., 0.85)
- `dashboard.py` converts to 0-100 for `DashboardClaim.confidence`
- `get_workbench_data()` returns raw assessment, so `assessment.confidence_score` is 0-1
- Frontend `buildEnrichment()` now normalizes: `rawConf <= 1 ? Math.round(rawConf * 100) : rawConf`

No further changes needed.

## Files Modified

| File | Action | Lines |
|------|--------|-------|
| `src/context_builder/api/services/dashboard.py` | **MODIFY** — add `has_decision_dossier` check | ~5 lines |
| `ui/src/types/index.ts` | **MODIFY** — add field to `DashboardClaim` | 1 line |
| `ui/src/pages/ClaimsWorkbenchPage.tsx` | **MODIFY** — filter claims + parallel preload | ~15 lines |

## Testing

1. **Backend unit test:** Verify `list_claims()` returns `has_decision_dossier: true` for claims with dossier files and `false` for claims without
2. **Frontend manual:** Navigate to Workbench, verify only claims with decision trails appear
3. **No regressions:** Run full test suite to ensure dashboard endpoint changes don't break existing tests

## Estimated Impact

- 3 files, ~20 lines of changes
- No new endpoints or services
- No breaking changes to existing API (additive field)
