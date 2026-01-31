# NSA Pipeline Evaluation Process

**Status**: 22 iterations complete, best accuracy **94%** (eval #21), latest **92%** (eval #22)

## Quick Start

```bash
# 1. Run pipeline on all 50 eval claims
python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2

# 2. Evaluate the LATEST assessment per claim (picks most recent claim_run)
python scripts/eval_pipeline.py

# 3. Evaluate a SPECIFIC claim run by ID
python scripts/eval_pipeline.py --run-id clm_20260130_095213_ecae7c

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

**Note**: The 4 development claims are NOT in the ground truth. Keep them separate.

## Non-Regression Claims

Verified claims are tracked in `workspaces/nsa/eval/regression_claims.json`. After pipeline changes, re-run these claims and confirm results still match expected decisions and payouts.

## Evaluation Infrastructure

### Eval Script

**Location**: `scripts/eval_pipeline.py`

**Usage**:
```bash
# Evaluate latest assessment per claim (default)
python scripts/eval_pipeline.py

# Evaluate a specific pipeline run
python scripts/eval_pipeline.py --run-id clm_20260130_095213_ecae7c
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
│   ├── regression_claims.json   # Verified claims for non-regression testing
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
| `workspaces/nsa/eval/regression_claims.json` | Verified claims for non-regression testing | Manual |
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
    "final_payout": 1506.54,
    "deductible": 376.64,
    ...
  },
  "data_gaps": [...],
  "fraud_indicators": [],
  "recommendations": [...]
}
```

## Evaluation Results History

### Full Run History

| # | Date | Eval ID | Accuracy | Appr OK | Deny OK | FRR | FAR | Top Error |
|---|------|---------|----------|---------|---------|-----|-----|-----------|
| 1 | 01-28 | eval_20260128_211247 | 18% | 0/25 | 9/25 | 100% | 64% | refer_should_approve (11) |
| 2 | 01-28 | eval_20260128_211424 | 18% | 0/25 | 9/25 | 100% | 64% | refer_should_approve (11) |
| 3 | 01-29 | eval_20260129_085909 | 28% | 2/25 | 12/25 | 92% | 52% | refer_should_deny (12) |
| 4 | 01-29 | eval_20260129_121209 | 30% | 6/25 | 9/25 | 76% | 64% | refer_should_approve (13) |
| 5 | 01-29 | eval_20260129_145932 | 36% | 8/25 | 10/25 | 68% | 60% | refer_should_deny (13) |
| 6 | 01-29 | eval_20260129_162838 | 62% | 19/25 | 12/25 | 24% | 52% | amount_mismatch (16) |
| 7 | 01-29 | eval_20260129_180748 | 48% | 13/25 | 11/25 | 48% | 56% | amount_mismatch (12) |
| 8 | 01-29 | eval_20260129_194743 | 68% | 16/25 | 18/25 | 36% | 28% | amount_mismatch (14) |
| 9 | 01-29 | eval_20260129_213944 | 56% | 4/25 | 24/25 | 84% | 4% | false_reject:component (18) |
| 10 | 01-29 | eval_20260129_225329 | 60% | 8/25 | 22/25 | 68% | 12% | false_reject:component (10) |
| 11 | 01-30 | eval_20260130_032512 | 60% | 16/25 | 14/25 | 36% | 44% | amount_mismatch (10) |
| 12 | 01-30 | eval_20260130_061455 | 66% | 13/25 | 20/25 | 48% | 20% | amount_mismatch (7) |
| 13 | 01-30 | eval_20260130_073431 | 76% | 16/25 | 22/25 | 36% | 12% | amount_mismatch (10) |
| 14 | 01-30 | eval_20260130_091345 | 58% | 12/25 | 16/25 | 52% | 36% | amount_mismatch (8) |
| 15 | 01-30 | eval_20260130_103240 | 68% | 19/25 | 15/25 | 24% | 40% | amount_mismatch (13) |
| 16–18 | 01-30 | (various) | 69–76% | — | — | — | — | amount_mismatch |
| 19 | 01-30 | eval_20260130_180826 | 92% | 22/26 | 24/24 | 15% | 0% | amount_mismatch (13) |
| 20 | 01-31 | eval_20260131_072810 | 80% | 25/26 | 15/24 | 4% | 38% | amount_mismatch (15) — regression from component_name |
| 21 | 01-31 | eval_20260131_104745 | **94%** | 23/26 | 24/24 | 12% | 0% | amount_mismatch (15) |

**FRR** = False Reject Rate, **FAR** = False Approve Rate

### Version Tags

Both repos are tagged on each eval for reproducibility.

| Eval | Accuracy | Main Repo Tag | Customer Repo Tag | Notes |
|------|----------|---------------|-------------------|-------|
| #13 | 76% | `eval-13-76pct` (b07dbc7) | `eval-13-76pct` (735b6c4) | Customer tag approximate — config not committed at eval time |
| #14 | 56% | `eval-14-56pct` (b07dbc7) | `eval-14-56pct` (ecca6ad) | Same code commit, different config |
| #15 | 68% | `eval-15-68pct` (8910dd3) | `eval-15-68pct` (4832281) | Reverted damage_date hard_fail, simplified assessment prompt |
| #16 | 69% | `eval-16-69pct` (eac6f20) | `eval-16-69pct` (9cf0f3f) | Keyword matching implementation |
| #17 | 72% | `eval-17-72pct` (de4b91c) | `eval-17-72pct` (a337e59) | Screener age-based coverage reduction |
| #18 | 76% | `eval-18-76pct` (c743193) | `eval-18-76pct` (e1a8c23) | Improved coverage analysis and keyword matching |
| #19 | **92%** | `eval-19-92pct` (fa41bdc) | `eval-19-92pct` (e1a8c23) | Best result. Same customer config as #18, code improvements. Renamed from eval-19-86pct. |
| #20 | 80% | `eval-20-80pct` (a9af7dc) | `eval-20-80pct` (a3fbd15) | Regression — component_name bypassed Stage 2.5 safety net. Renamed from eval-20-92pct. |
| #21 | **94%** | `eval-21-94pct` (e52e1ba) | `eval-21-94pct` (8300278) | New best. Stripped component_name, kept other config improvements, LLM max 35. |
| #22 | 92% | `eval-22-92pct` (59d16a4) | `eval-22-92pct` (7861d6a) | Refactored coverage analyzer: externalized config, primary repair on schema, null-primary reject logic. |

**Process**: After every future eval:
1. Sync customer config: `powershell -ExecutionPolicy Bypass -File "C:\Users\fbrun\Documents\GitHub\context-builder-nsa\copy-from-workspace.ps1"`
2. Commit + tag customer repo: `git -C <customer-repo> tag -a eval-NN-XXpct`
3. Commit + tag main repo: `git -C <main-repo> tag -a eval-NN-XXpct`
4. Record tags in the table above

### Best Result: eval_20260131_104745 (94%, eval #21)

- 47/50 correct (23 approved + 24 denied)
- FRR=11.5%, FAR=0% (zero false approves, perfect denial accuracy)
- Main issue: `amount_mismatch` (15) — correct decisions but wrong payout amounts
- Tagged as `eval-21-94pct` in both repos
- Changes from eval #19 (92%): stripped `component_name` from keyword mappings, added door lock/mirror keywords, `comfort_options` in labor categories, age-based reduction disabled, LLM max items bumped to 35
- This is the target to beat

### Previous Best: eval_20260130_180826 (92%, eval #19)

- 46/50 correct (22 approved + 24 denied)
- FRR=15.4%, FAR=0%
- Tagged as `eval-19-92pct`

### Key Patterns Across All Runs

1. **Approval accuracy and denial accuracy trade off** — improving one tends to regress the other
2. **`amount_mismatch` is persistent** — appears as #1 error in every run above 50% accuracy (payout calculation, not decision logic)
3. **`service_compliance` false rejects stuck at 2** — consistent across all runs, likely 2 specific claims (64168, 64659)
4. **REFER_TO_HUMAN** varies wildly (0-26 claims) depending on screening confidence thresholds
5. **`component_coverage` swings** — 1 to 18 depending on how strict the coverage rules are

## Pipeline Architecture

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

## Key Files

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
| `workspaces/nsa/eval/regression_claims.json` | Verified claims for non-regression testing |
| `workspaces/nsa/eval/EVAL_LOG.md` | Human analysis of findings per iteration |

## Standard Iteration Cycle

1. **Make code/config changes** to improve accuracy

2. **Run pipeline on all 50 eval claims**:
   ```bash
   python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2
   ```
   Check the run ID from the output or:
   ```bash
   ls workspaces/nsa/claim_runs/  # newest folder is the latest run
   ```

3. **Run evaluation for that specific run**:
   ```bash
   python scripts/eval_pipeline.py --run-id <claim_run_id>
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
   - Tag both repos (see Version Tags section)

## Current Priority Issues

| Priority | Issue | Impact | Claims | Status |
|----------|-------|--------|--------|--------|
| P0 | `amount_mismatch` (payout calculation) | Correct decisions with wrong amounts (14 claims) | Various | Persistent — #1 error since eval #6 |
| P1 | `false_reject:component_coverage` | Approved claims wrongly rejected (2 claims) | 64358, 65040 | Persistent — angle gearbox not in policy list, trunk ECU unresolvable |
| P1 | `refer_should_approve` | System refers instead of approving (1 claim) | 65055 | Persistent |
| P2 | `false_approve` | Denied claim wrongly approved (1 claim) | TBD | New in eval #22 (was 0 in #21) — investigate |
| P2 | `refer_should_deny` | System refers instead of denying (1 claim) | 64961 | New in eval #22 — 3 review-needed items cause uncertainty |
| ~~P1~~ | ~~`false_approve` (eval #20)~~ | ~~Denied claims wrongly approved (9)~~ | — | **Fixed** in eval #21 (component_name stripped) |

## Related Documentation

- `docs/EVAL-pipeline-evaluation-guide.md` — Full evaluation framework
- `docs/HANDOFF-known-issues.md` — Current bugs and issues to fix
- `workspaces/nsa/eval/EVAL_LOG.md` — Detailed run-by-run findings
- `workspaces/nsa/eval/regression_claims.json` — Verified claims for non-regression testing
