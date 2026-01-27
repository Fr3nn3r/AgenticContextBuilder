# Design: Claim-Level Runs and Provenance

**Date:** 2026-01-26
**Status:** Draft - Awaiting Architecture Decision

## Problem Statement

The current reconciliation implementation has a conceptual gap:

1. **Extraction is run-based** - Each extraction run produces outputs per document, stored under `runs/{run_id}/`
2. **Reconciliation is claim-based** - But it references a single run_id, which is misleading
3. **Missing provenance** - We don't track which extraction run produced each reconciled fact
4. **No claim-level history** - Reconciliation outputs overwrite previous versions

### Current Confusion

```
"Reconciliation uses run_id X"
    → But reconciliation COULD pick facts from multiple extraction runs
    → The run_id is just "which extractions to consider", not "the run that produced this"
```

## Key Insight

**Aggregation IS Reconciliation** - They're the same concept:
- Take multiple document extractions → produce unified claim facts
- Detect conflicts (same fact, different values across docs)
- Select best value (highest confidence, most recent, etc.)

**Evaluation is separate** - Comparing against ground truth, not summarizing gate results.

## Current Architecture

```
workspaces/{workspace}/
├── claims/{claim_id}/
│   ├── docs/{doc_id}/              # Raw documents + metadata
│   ├── runs/{run_id}/              # Extraction runs (doc-level)
│   │   └── extraction/{doc_id}.json
│   └── context/                    # Claim-level outputs (NO VERSIONING)
│       ├── claim_facts.json        # Reconciled facts
│       └── reconciliation_report.json
└── runs/{run_id}/                  # Global run metadata
```

### Current FactProvenance Schema

```python
class FactProvenance(BaseModel):
    doc_id: str                    # Which document
    page: Optional[int]            # Which page
    text_quote: Optional[str]      # Evidence text
    char_start: Optional[int]      # Character offset
    char_end: Optional[int]
    # extraction_run_id: MISSING   # Which extraction run?
```

### Current Limitations

| Issue | Impact |
|-------|--------|
| No per-field extraction run tracking | Can't trace "where did this value come from?" |
| Single claim_facts.json per claim | History lost on re-reconciliation |
| No claim-level run concept | Can't version or compare reconciliation outputs |
| Reconciliation tied to one extraction run | Can't pick best facts across multiple runs |

---

## Proposed Solution: Two Levels

### Level 1: Per-Field Extraction Provenance (Minimal Path)

Add `extraction_run_id` to track which extraction run produced each fact.

```python
class FactProvenance(BaseModel):
    doc_id: str
    extraction_run_id: str         # NEW: "run_20260124_221046_7cc77c7"
    page: Optional[int]
    text_quote: Optional[str]
    char_start: Optional[int]
    char_end: Optional[int]
```

**Example claim_facts.json:**
```json
{
  "facts": [
    {
      "name": "policy_number",
      "value": "POL-2024-12345",
      "confidence": 0.95,
      "selected_from": {
        "doc_id": "abc123",
        "extraction_run_id": "run_20260124_221046",
        "page": 1,
        "text_quote": "Policy Number: POL-2024-12345"
      }
    },
    {
      "name": "claim_date",
      "value": "2026-01-15",
      "confidence": 0.88,
      "selected_from": {
        "doc_id": "def456",
        "extraction_run_id": "run_20260125_103000",  // Different run!
        "page": 2,
        "text_quote": "Date of Claim: 15/01/2026"
      }
    }
  ]
}
```

### Level 2: Claim-Level Runs (Full Path)

Introduce versioned claim-level processing, analogous to extraction runs.

```
claims/{claim_id}/
├── docs/
├── runs/                           # Extraction runs (existing)
│   ├── run_20260124_.../extraction/
│   └── run_20260125_.../extraction/
├── claim_runs/                     # NEW: Claim-level runs
│   ├── clm_20260126_143000/
│   │   ├── manifest.json           # What inputs, what version, what config
│   │   ├── claim_facts.json
│   │   ├── reconciliation_report.json
│   │   ├── enrichment_result.json  # Future stage
│   │   └── assessment.json         # Processing output
│   └── clm_20260126_150000/        # Another run (different config/version)
│       └── ...
└── context/                        # Points to "current" claim_run
    └── current_claim_run.json      # {"claim_run_id": "clm_20260126_150000"}
```

**Claim Run Manifest:**
```json
{
  "claim_run_id": "clm_20260126_143000",
  "created_at": "2026-01-26T14:30:00Z",
  "extraction_runs_considered": [
    "run_20260124_221046",
    "run_20260125_103000"
  ],
  "reconciliation_version": "1.2.0",
  "enrichment_version": "1.0.0",
  "processing_version": "2.1.0",
  "config": {
    "conflict_resolution": "highest_confidence",
    "processing_type": "assessment"
  }
}
```

---

## Impact Analysis

### Minimal Path (Level 1 Only)

**Scope of Changes:**

| Component | Change Required |
|-----------|-----------------|
| `schemas/claim_facts.py` | Add `extraction_run_id` to `FactProvenance` |
| `api/services/aggregation.py` | Populate `extraction_run_id` when building facts |
| `api/services/reconciliation.py` | Track which runs were considered |
| Frontend | Display provenance in fact details |

**Effort:** ~2-4 hours

**What You Get:**
- Full traceability per fact
- Can debug "where did this value come from?"
- Audit trail for compliance

**What You Don't Get:**
- No history of previous reconciliations
- Can't compare reconciliation outputs across versions
- Still overwrites claim_facts.json

**Migration:**
- Existing claim_facts.json files would have `extraction_run_id: null`
- New reconciliations would populate it
- Backward compatible

---

### Full Path (Level 1 + Level 2)

**Scope of Changes:**

| Component | Change Required |
|-----------|-----------------|
| `schemas/claim_facts.py` | Add `extraction_run_id` to `FactProvenance` |
| `schemas/claim_run.py` | NEW: Claim run manifest schema |
| `storage/filesystem.py` | Add claim_runs directory handling |
| `api/services/aggregation.py` | Write to claim_runs/, populate run_id |
| `api/services/reconciliation.py` | Create claim run, write manifest |
| `pipeline/claim_stages/` | All stages write to claim_run folder |
| `api/routers/claims.py` | Endpoints to list/get claim runs |
| Frontend | Claim run selector, history view |
| CLI | `--claim-run-id` parameter |

**Effort:** ~2-3 days

**What You Get:**
- Everything from Minimal, plus:
- Full history of claim-level processing
- Can compare reconciliations (different configs, versions)
- Can rollback to previous claim run
- Clear versioning for enrichment and processing stages
- Parallel to extraction run concept (consistency)

**What You Don't Get:**
- Adds complexity
- More storage (but claim_facts.json is small)
- Need to manage "current" pointer

**Migration:**
- Create `claim_runs/` directory structure
- Move existing `context/*.json` to a new claim run
- Set that as current
- Or: leave `context/` as legacy, new reconciliations use claim_runs/

---

## Decision Matrix

| Factor | Minimal | Full |
|--------|---------|------|
| Effort | ~4 hours | ~2-3 days |
| Traceability | Per-field | Per-field + per-run |
| History | None | Full |
| Compare versions | No | Yes |
| Rollback | No | Yes |
| Storage impact | None | Minimal (~10KB per claim run) |
| Code complexity | Low | Medium |
| Conceptual clarity | Better | Best |
| Future-proof | Partial | Yes |

---

## Recommendation

**Start with Minimal, design for Full.**

1. Implement Level 1 now (per-field extraction_run_id)
2. Design the claim_runs/ structure but don't implement yet
3. When we need history/versioning, implement Level 2

**Rationale:**
- Level 1 solves the immediate provenance problem
- Level 2 is additive (doesn't require rework of Level 1)
- We learn more about actual needs before committing to full structure

---

## Questions for Decision

1. **Do we need claim-level history now?**
   - If yes → Full path
   - If "eventually" → Minimal now, Full later

2. **Will reconciliation span multiple extraction runs?**
   - If yes → Level 1 is essential (must track which run per fact)
   - Current code only uses one run, but schema should support multiple

3. **Is the claim_runs/ structure the right model?**
   - Alternative: Single file with version history embedded
   - Alternative: Git-style versioning

4. **What about the "summary" we called "eval"?**
   - Rename `reconcile-eval` to `reconcile-summary`?
   - True eval should compare against ground truth

---

## Appendix: Terminology Cleanup

| Current Term | Proposed Term | Meaning |
|--------------|---------------|---------|
| Aggregation | Reconciliation | Combine doc extractions → claim facts |
| Reconciliation | (same) | Aggregation + conflict detection + gate |
| reconcile-eval | reconcile-summary | Aggregate gate stats across claims |
| Evaluation | Evaluation | Compare against ground truth |
| run (extraction) | extraction_run | Doc-level extraction batch |
| (missing) | claim_run | Claim-level processing batch |
