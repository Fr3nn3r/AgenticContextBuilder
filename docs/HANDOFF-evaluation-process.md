# Handoff: NSA Pipeline Evaluation Process

**Date**: 2026-01-30
**Status**: In Progress - 12 iterations complete, best accuracy 68%, current 60%

## Context

We are running an evaluation-driven development process to improve the accuracy of the NSA motor claims pipeline. The goal is to achieve high accuracy on automated claim decisions, especially for low-value claims.

## Quick Start (Copy-Paste Commands)

```bash
# 1. Run pipeline on all 50 eval claims
python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2

# 2. Evaluate the LATEST assessment per claim (picks most recent claim_run)
python scripts/eval_pipeline.py

# 3. Evaluate a SPECIFIC claim run by ID
python scripts/eval_pipeline.py --run-id clm_20260129_220857_ed62f2

# 4. Find available claim run IDs (batch runs)
ls workspaces/nsa/claim_runs/

# 5. View evaluation history (machine-readable)
cat workspaces/nsa/eval/metrics_history.json

# 6. Open the latest eval results
ls workspaces/nsa/eval/  # find latest eval_YYYYMMDD_HHMMSS folder
# then open summary.json, details.xlsx, errors.xlsx inside it
```

**Dependencies**: `pip install pandas openpyxl` (required by eval script)

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
# Evaluate latest assessment per claim (default)
python scripts/eval_pipeline.py

# Evaluate a specific pipeline run
python scripts/eval_pipeline.py --run-id clm_20260129_220857_ed62f2
```

**IMPORTANT**: Without `--run-id`, the script picks each claim's most recent `assessment.json`. If you've run the pipeline multiple times, older and newer assessments may mix. Always use `--run-id` when evaluating a specific pipeline run to get consistent results.

**What it does**:
1. Loads ground truth from `claims_ground_truth.json`
2. For each of the 50 ground-truth claims, finds `assessment.json` in `workspaces/nsa/claims/{claim_id}/claim_runs/{run_id}/`
3. Compares predicted decision (APPROVE/REJECT/REFER_TO_HUMAN) against ground truth
4. Compares payout amounts for approved claims (±5% tolerance)
5. Categorizes each error type
6. Outputs Excel files + JSON summary
7. Appends metrics to `metrics_history.json` automatically

**Output** (saved to `workspaces/nsa/eval/eval_YYYYMMDD_HHMMSS/`):

| File | Contents |
|------|----------|
| `summary.json` | Machine-readable metrics (accuracy, error counts, rates) |
| `summary.xlsx` | Same metrics formatted for humans |
| `details.xlsx` | Per-claim breakdown: gt vs predicted decision, amounts, error category |
| `errors.xlsx` | Subset of details.xlsx showing only mismatched claims |

### Directory Structure

```
workspaces/nsa/
├── claims/{claim_id}/claim_runs/{run_id}/   # Per-claim assessment outputs
│   ├── assessment.json          # Final decision + payout + checks
│   ├── screening.json           # Deterministic checks result
│   ├── coverage_analysis.json   # Per-item coverage decisions
│   ├── claim_facts.json         # Aggregated facts from extractions
│   ├── reconciliation_report.json
│   └── manifest.json            # Run metadata
│
├── claim_runs/{run_id}/                     # Batch run metadata
│   ├── manifest.json            # Start/end time, command, claim count, decision distribution
│   ├── summary.json             # Decision distribution (APPROVE/REJECT/REFER counts)
│   ├── logs/                    # Per-claim processing logs
│   └── .complete                # Marker file indicating run finished
│
├── eval/                                    # All evaluation results
│   ├── metrics_history.json     # Append-only history of all eval runs (auto-updated)
│   ├── EVAL_LOG.md              # Human-written findings log (manual updates)
│   └── eval_YYYYMMDD_HHMMSS/   # One folder per evaluation
│       ├── summary.json
│       ├── summary.xlsx
│       ├── details.xlsx
│       └── errors.xlsx
│
└── config/                                  # Customer config (GITIGNORED - use customer repo)
    ├── assumptions.json         # Coverage lookup tables, authorized shops
    ├── extractors/              # Extraction configs per doc type
    ├── extraction_specs/        # Field specs per doc type
    ├── prompts/                 # LLM prompt templates
    ├── enrichment/enricher.py   # NSA-specific enrichment logic
    └── scripts/eval_assessment.py  # Alternate eval for 4 dev claims only
```

### Tracking Files

| File | Purpose | Auto-updated? |
|------|---------|---------------|
| `workspaces/nsa/eval/metrics_history.json` | Machine-readable history of all eval runs | Yes (by eval script) |
| `workspaces/nsa/eval/EVAL_LOG.md` | Human-readable findings, root cause analysis | Manual |
| `workspaces/nsa/claim_runs/{run_id}/manifest.json` | Batch run metadata (timing, claim count, decisions) | Yes (by pipeline) |

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

### Assessment JSON Schema

Each `assessment.json` contains:
```json
{
  "assessment_method": "llm",
  "claim_id": "64166",
  "decision": "APPROVE",              // APPROVE | REJECT | REFER_TO_HUMAN
  "decision_rationale": "...",
  "confidence_score": 0.95,
  "checks": [
    {
      "check_name": "policy_validity",  // policy_validity | service_compliance | component_coverage | vehicle_id_consistency
      "result": "PASS",                 // PASS | FAIL | INCONCLUSIVE
      "details": "...",
      "evidence_refs": [...]
    }
  ],
  "payout": {
    "final_payout": 1854.30,
    "deductible": 376.65,
    ...
  },
  "data_gaps": [...],
  "fraud_indicators": [],
  "recommendations": [...]
}
```

## Evaluation Results History

### Full Run History (12 evaluations)

| # | Date | Eval ID | Claim Run | Accuracy | Appr OK | Deny OK | FRR | FAR | Top Error |
|---|------|---------|-----------|----------|---------|---------|-----|-----|-----------|
| 1 | 01-28 | eval_20260128_211247 | (baseline) | **18%** | 0/25 | 9/25 | 100% | 64% | refer_should_approve (11) |
| 2 | 01-28 | eval_20260128_211424 | (same, fixed categories) | 18% | 0/25 | 9/25 | 100% | 64% | refer_should_approve (11) |
| 3 | 01-29 | eval_20260129_085909 | clm_..._cf2356 | **28%** | 2/25 | 12/25 | 92% | 52% | refer_should_deny (12) |
| 4 | 01-29 | eval_20260129_121209 | - | **30%** | 6/25 | 9/25 | 76% | 64% | refer_should_approve (13) |
| 5 | 01-29 | eval_20260129_145932 | - | **36%** | 8/25 | 10/25 | 68% | 60% | refer_should_deny (13) |
| 6 | 01-29 | eval_20260129_162838 | - | **62%** | 19/25 | 12/25 | 24% | 52% | amount_mismatch (16) |
| 7 | 01-29 | eval_20260129_180748 | - | 48% | 13/25 | 11/25 | 48% | 56% | amount_mismatch (12) |
| 8 | 01-29 | eval_20260129_194743 | - | **68%** | 16/25 | 18/25 | 36% | 28% | amount_mismatch (14) |
| 9 | 01-29 | eval_20260129_213944 | clm_..._8fbdd5 | 56% | 4/25 | 24/25 | 84% | 4% | false_reject:component (18) |
| 10 | 01-29 | eval_20260129_225329 | clm_..._ed62f2? | 60% | 8/25 | 22/25 | 68% | 12% | false_reject:component (10) |
| 11 | 01-30 | eval_20260130_032512 | clm_20260129_220857_ed62f2 | **60%** | 16/25 | 14/25 | 36% | 44% | amount_mismatch (10) |

**FRR** = False Reject Rate, **FAR** = False Approve Rate

**Note**: Runs 10 and 11 both report 60% accuracy but have very different profiles. Run 10 used `--run-id` unspecified (latest per claim, potentially mixed), while run 11 used `--run-id clm_20260129_220857_ed62f2` for consistency.

### Best Result: eval_20260129_194743 (68%)

- 34/50 correct (16 approved + 18 denied)
- Balanced: FRR=36%, FAR=28%
- Main issue: `amount_mismatch` (14) - correct decisions but wrong payout amounts
- This is the target to beat

### Latest Result: eval_20260130_032512 (60%) — Run `clm_20260129_220857_ed62f2`

- 30/50 correct (16 approved + 14 denied)
- Good on approvals (16/25, same as best), weak on denials (14/25 vs 18/25 best)
- FRR=36% (good), FAR=44% (regression - too permissive on denials)

**Error breakdown**:
| Error | Count | Trend vs Best |
|-------|-------|---------------|
| `amount_mismatch` | 10 | Improved (was 14) |
| `refer_should_deny:no_fails` | 7 | Worse (was 5) |
| `refer_should_approve:no_fails` | 5 | Worse (was 1) |
| `false_approve` | 4 | Worse (was 2) |
| `false_reject:service_compliance` | 2 | Same |
| `false_reject:component_coverage` | 1 | Improved (was 5) |
| `false_reject:policy_validity` | 1 | Same |

### Key Patterns Across All Runs

1. **Approval accuracy and denial accuracy trade off** - improving one tends to regress the other
2. **`amount_mismatch` is persistent** - appears as #1 error in every run above 50% accuracy (payout calculation, not decision logic)
3. **`service_compliance` false rejects stuck at 2** - consistent across all runs, likely 2 specific claims
4. **REFER_TO_HUMAN** varies wildly (0-26 claims) depending on screening confidence thresholds
5. **`component_coverage` swings** - 1 to 18 depending on how strict the coverage rules are

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
| `scripts/eval_pipeline.py` | **Evaluation script** — compares assessments to ground truth |
| `src/context_builder/pipeline/claim_stages/assessment_processor.py` | Assessment stage with screening integration |
| `src/context_builder/coverage/analyzer.py` | Coverage analysis engine (rules + keywords + LLM) |
| `src/context_builder/api/services/claim_assessment.py` | `ClaimAssessmentService` — orchestrates reconciliation → screening → assessment |
| `src/context_builder/api/services/reconciliation.py` | Fact aggregation and conflict detection |
| `workspaces/nsa/config/assumptions.json` | Coverage lookup tables (keywords, part numbers, authorized shops) |
| `workspaces/nsa/config/enrichment/enricher.py` | NSA-specific enrichment logic |
| `data/08-NSA-Supporting-docs/claims_ground_truth.json` | Ground truth (50 claims) |
| `workspaces/nsa/eval/metrics_history.json` | All eval metrics over time |
| `workspaces/nsa/eval/EVAL_LOG.md` | Human analysis of findings per iteration |

## How to Continue

### Standard Iteration Cycle

1. **Make code/config changes** to improve accuracy

2. **Run pipeline on all 50 eval claims**:
   ```bash
   python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2
   ```
   This creates a new claim run (e.g., `clm_20260130_143000_abc123`). Check the run ID from the output or:
   ```bash
   ls workspaces/nsa/claim_runs/  # newest folder is the latest run
   ```

3. **Run evaluation for that specific run**:
   ```bash
   python scripts/eval_pipeline.py --run-id clm_20260130_143000_abc123
   ```

4. **Check results**:
   - Console output shows summary
   - `workspaces/nsa/eval/eval_*/summary.json` for metrics
   - `workspaces/nsa/eval/eval_*/errors.xlsx` for per-claim error analysis

5. **Compare with previous runs**:
   - Read `workspaces/nsa/eval/metrics_history.json` — the latest entry is appended automatically
   - Compare `decision_accuracy`, `false_reject_rate`, `false_approve_rate` with prior entries

6. **Investigate errors** (pick top error category from `errors.xlsx`):
   ```
   workspaces/nsa/claims/{claim_id}/claim_runs/{run_id}/screening.json       # deterministic checks
   workspaces/nsa/claims/{claim_id}/claim_runs/{run_id}/coverage_analysis.json # per-item coverage
   workspaces/nsa/claims/{claim_id}/claim_runs/{run_id}/assessment.json       # final decision + rationale
   ```

7. **Update tracking**:
   - `metrics_history.json` updates automatically
   - Update `EVAL_LOG.md` with your findings manually

### Current Priority Issues

| Priority | Issue | Impact | Evidence |
|----------|-------|--------|----------|
| P0 | `amount_mismatch` (10 claims) | Correct decision but wrong payout — blocks amount accuracy | Persistent across all runs >50% |
| P1 | `false_approve` (4 claims) | Denied claims wrongly approved — FAR=44% | Regression from best run (FAR=28%) |
| P1 | `refer_should_deny` (7 claims) | System refers instead of denying — indecisive | No failed checks to trigger rejection |
| P2 | `refer_should_approve` (5 claims) | System refers instead of approving | No failed checks but won't commit |
| P3 | `false_reject:service_compliance` (2 claims) | Approved claims rejected for service dates | Stuck at 2 across all runs |

## Related Documentation

- `docs/EVAL-pipeline-evaluation-guide.md` - Full evaluation framework
- `docs/HANDOFF-known-issues.md` - Current bugs and issues to fix
- `workspaces/nsa/eval/EVAL_LOG.md` - Detailed run-by-run findings
- `workspaces/nsa/config/scripts/eval_assessment.py` - Alternate eval script for 4 dev claims only (not the main eval)
