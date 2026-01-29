# Handoff: NSA Pipeline Evaluation Process

**Date**: 2026-01-29
**Status**: In Progress - Baseline established, first iteration complete

## Context

We are running an evaluation-driven development process to improve the accuracy of the NSA motor claims pipeline. The goal is to achieve high accuracy on automated claim decisions, especially for low-value claims.

## Ground Truth

- **Location**: `data/08-NSA-Supporting-docs/claims_ground_truth.json`
- **Claims**: 50 total (25 approved, 25 denied)
- **Source**: Decision letters from NSA (Claim_Decision_for_Claim_Number_*.pdf)
- **Fields**: claim_id, decision, total_approved_amount, deductible, currency, vehicle, date, denial_reason

## Data Sets

| Set | Location | Claims | Purpose |
|-----|----------|--------|---------|
| Development | `data/07-Claims-Motor-NSA/` | 4 (65128, 65157, 65196, 65258) | Original test claims, sanity check |
| Evaluation | `data/09-Claims-Motor-NSA-2/` | 50 | Primary evaluation set with ground truth |

**Note**: The 4 development claims are NOT in the ground truth. Keep them separate as regression tests.

## Evaluation Infrastructure

### Eval Script

**Location**: `scripts/eval_pipeline.py`

**Usage**:
```bash
python scripts/eval_pipeline.py
```

**What it does**:
1. Loads ground truth from `claims_ground_truth.json`
2. Finds latest assessment in `workspaces/nsa/claims/{claim_id}/claim_runs/*/assessment.json`
3. Compares decisions and amounts
4. Outputs Excel files and updates metrics history

**Output** (in `workspaces/nsa/eval/eval_YYYYMMDD_HHMMSS/`):
- `summary.xlsx` - High-level metrics
- `details.xlsx` - Per-claim breakdown
- `errors.xlsx` - Only mismatches
- `summary.json` - Programmatic access

### Tracking Files

| File | Purpose | Auto-updated? |
|------|---------|---------------|
| `workspaces/nsa/eval/metrics_history.json` | Machine-readable run history | Yes |
| `workspaces/nsa/eval/EVAL_LOG.md` | Human-readable findings log | Manual |

### Error Categories

The eval script categorizes errors automatically:

| Category | Meaning |
|----------|---------|
| `false_reject:service_compliance` | Approved claim wrongly rejected due to service check |
| `false_reject:component_coverage` | Approved claim wrongly rejected due to coverage check |
| `false_reject:policy_validity` | Approved claim wrongly rejected due to policy check |
| `false_reject:other` | Approved claim wrongly rejected, other reason |
| `false_approve` | Denied claim wrongly approved |
| `refer_should_approve:*` | Should have approved, but output REFER_TO_HUMAN |
| `refer_should_deny:*` | Should have denied, but output REFER_TO_HUMAN |
| `amount_mismatch` | Decision correct but amount differs by >5% |

## Evaluation Results So Far

### Baseline (2026-01-28) - LLM Only

- **Accuracy**: 18% (9/50)
- **Approved Correct**: 0/25 (100% false reject rate)
- **Denied Correct**: 9/25

**Root Causes**:
1. Coverage lookup returned "unknown" for all items (German keywords, French claims)
2. Shop authorization returned "inconclusive" for most shops
3. 60% of claims returned REFER_TO_HUMAN

### Iteration 1 (2026-01-29) - Screening + LLM Coverage

- **Accuracy**: 28% (14/50) - **+10%**
- **Approved Correct**: 2/25 (vs 0 before)
- **Denied Correct**: 12/25 (vs 9 before)

**What Changed**:
- Added deterministic screening stage
- Added LLM-based coverage analysis per line item
- Shop authorization now uses pattern matching

**New Issues Found**:
1. Deductible extraction wrong (30,000 CHF instead of ~400)
2. Coverage categories too restrictive
3. Service compliance still failing on old dates

## Pipeline Architecture (Current)

```
Input Claim
    ↓
┌─────────────────────────────────────────┐
│ SCREENING STAGE (Deterministic)         │
│ - Policy validity (dates, mileage)      │
│ - VIN consistency                       │
│ - Shop authorization (pattern match)    │
│ - Service compliance                    │
│ - Coverage analysis (rules + LLM)       │
│                                         │
│ Output: screening.json, coverage_analysis.json
└─────────────────────────────────────────┘
    ↓
    ├── Auto-reject if hard fail
    ↓
┌─────────────────────────────────────────┐
│ ASSESSMENT STAGE (LLM)                  │
│ - Receives screening context            │
│ - Makes final judgment                  │
│ - Calculates payout                     │
│                                         │
│ Output: assessment.json                 │
└─────────────────────────────────────────┘
```

## Key Files to Understand

| File | Purpose |
|------|---------|
| `src/context_builder/pipeline/claim_stages/assessment_processor.py` | Assessment stage with screening integration |
| `workspaces/nsa/config/assumptions.json` | Coverage lookup tables (keywords, part numbers, authorized shops) |
| `workspaces/nsa/config/enrichment/enricher.py` | NSA-specific enrichment logic |
| `src/context_builder/coverage/analyzer.py` | Coverage analysis engine (rules + keywords + LLM) |

## Claim Run Structure

Each processed claim produces:
```
workspaces/nsa/claims/{claim_id}/claim_runs/clm_YYYYMMDD_HHMMSS_*/
├── assessment.json          # Final decision
├── screening.json           # Deterministic checks result
├── coverage_analysis.json   # Per-item coverage decisions
├── claim_facts.json         # Aggregated facts
├── reconciliation_report.json
└── manifest.json
```

## How to Continue

1. **Run pipeline on all claims**:
   ```bash
   python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2
   ```

2. **Run evaluation**:
   ```bash
   python scripts/eval_pipeline.py
   ```

3. **Analyze errors**:
   - Open `workspaces/nsa/eval/eval_*/errors.xlsx`
   - Sort by `error_category`
   - Pick top category, investigate 2-3 claims manually

4. **Investigate a specific claim**:
   - Check `claim_runs/*/screening.json` for deterministic results
   - Check `claim_runs/*/coverage_analysis.json` for per-item coverage
   - Check `claim_runs/*/assessment.json` for final decision

5. **Update tracking**:
   - `metrics_history.json` updates automatically
   - Update `EVAL_LOG.md` with findings manually

## Related Documentation

- `docs/EVAL-pipeline-evaluation-guide.md` - Full evaluation framework
- `docs/HANDOFF-known-issues.md` - Current bugs and issues to fix
- `workspaces/nsa/eval/EVAL_LOG.md` - Detailed run-by-run findings
