---
name: eval
description: Run and analyze NSA pipeline evaluations. Use /eval run, /eval investigate <claim_id>, /eval compare, /eval deep, or /eval tag <number> <accuracy>.
argument-hint: "[run|investigate|compare|deep|tag] [args...]"
allowed-tools: Read, Grep, Glob, Bash(python *), Bash(ls *), Bash(git tag *), Bash(git -C *), Bash(powershell *), Task
---

# NSA Pipeline Evaluation

You are helping run and analyze pipeline evaluations for 50 NSA motor insurance claims.

**Action requested**: $ARGUMENTS

## Commands by action

### `/eval run` — Run pipeline + evaluate

1. Run the pipeline on all 50 eval claims:
   ```
   python -m context_builder.cli pipeline data/datasets/nsa-motor-eval-v1/claims
   ```
2. Note the claim run ID from output (or check `ls workspaces/nsa/claim_runs/` for newest folder)
3. Run evaluation for that specific run:
   ```
   python scripts/eval_pipeline.py --run-id <claim_run_id>
   ```
4. Read the summary from the eval output folder in `workspaces/nsa/eval/eval_*/summary.json`
5. Compare with previous runs by reading `workspaces/nsa/eval/metrics_history.json` (latest entry is appended automatically)
6. Report: accuracy, approvals correct, denials correct, FRR, FAR, top error category, and comparison vs previous run

### `/eval investigate <claim_id>` — Debug a specific claim

Find and analyze these files for the claim (use the most recent claim run):
- `workspaces/nsa/claims/<claim_id>/claim_runs/<run_id>/screening.json` — deterministic check results
- `workspaces/nsa/claims/<claim_id>/claim_runs/<run_id>/coverage_analysis.json` — per-item coverage decisions
- `workspaces/nsa/claims/<claim_id>/claim_runs/<run_id>/assessment.json` — final decision + rationale
- `workspaces/nsa/claims/<claim_id>/claim_runs/<run_id>/claim_facts.json` — aggregated facts

Cross-reference against ground truth in `data/datasets/nsa-motor-eval-v1/ground_truth.json`.

Report: what the system decided vs what was expected, which check caused the error, and what specifically went wrong.

### `/eval compare` — Compare recent eval runs

Read `workspaces/nsa/eval/metrics_history.json` and present:
- Last 5 eval runs side by side
- Accuracy trend, FRR trend, FAR trend
- Which error categories improved/regressed
- Current best result and what to beat

### `/eval deep` — Deep eval: compare system explanations vs ground truth

A deep eval goes beyond accuracy metrics. It compares the system's **detailed reasoning** against the ground truth for every claim — checking whether the system got the right answer for the right reason, and where payment calculations diverge.

**Procedure:**

1. **Find the latest eval run** from `workspaces/nsa/eval/metrics_history.json` (last entry)
2. **Read the eval details** from the eval's `details.xlsx` using Python/openpyxl:
   ```python
   python -c "import openpyxl; wb = openpyxl.load_workbook('workspaces/nsa/eval/<eval_id>/details.xlsx'); ws = wb.active; rows = list(ws.iter_rows(values_only=True)); [print('|'.join(str(x) for x in r)) for r in rows]"
   ```
   The details.xlsx contains: claim_id, gt_decision, pred_decision, decision_match, gt_amount, pred_amount, amount_diff, amount_diff_pct, gt_deductible, pred_deductible, deductible_match, error_category, failed_checks, decision_rationale, gt_denial_reason, gt_vehicle, run_id
3. **Read the ground truth** from `data/datasets/nsa-motor-eval-v1/ground_truth.json`
4. **Launch 2 subagents in parallel** (use the Task tool):
   - **Agent 1: Denied claims analysis** — For each denied claim, read `assessment.json` and `coverage_analysis.json` from the claim run. Compare the system's rejection reason (failed checks, rationale) vs the ground truth's `denial_reason`. Focus on: (a) claims where system rejected for a different reason than GT, (b) false approves — what went wrong, (c) whether the system correctly identified the specific uncovered component.
   - **Agent 2: Approved claims payment analysis** — For each approved claim with >5% amount mismatch, read `assessment.json` and `coverage_analysis.json`. Compare system's payout calculation (parts, labor, deductible, reimbursement rate) vs GT amounts. Identify patterns: over-aggressive labor exclusion, rate formula mismatch, component classification errors, null coverage_percent, etc.
5. **Compile the report** from both agents' findings into `docs/DEEP-EVAL-report-eval<N>.md` with sections:
   - Part 1: Denied claims explanation comparison (matching reasons, differing reasons, false approves)
   - Part 2: Approved claims payment comparison (within tolerance, mismatches with root causes, patterns)
   - Part 3: Priority fixes (ranked by financial impact and severity)

**Key paths for deep eval:**
- Assessment files: `workspaces/nsa/claims/{claim_id}/claim_runs/{run_id}/assessment.json`
- Coverage analysis: `workspaces/nsa/claims/{claim_id}/claim_runs/{run_id}/coverage_analysis.json`
- Screening results: `workspaces/nsa/claims/{claim_id}/claim_runs/{run_id}/screening.json`
- Previous deep eval reports: `docs/DEEP-EVAL-report-eval*.md`

### `/eval tag <number> <accuracy>` — Tag repos after eval

Execute the post-eval tagging process:
1. Sync customer config:
   ```
   powershell -ExecutionPolicy Bypass -File "C:\Users\fbrun\Documents\GitHub\context-builder-nsa\copy-from-workspace.ps1"
   ```
2. Commit and tag customer repo:
   ```
   git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" add -A
   git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" commit -m "eval-<number>: <accuracy>pct accuracy"
   git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" tag -a eval-<number>-<accuracy>pct -m "Eval <number>: <accuracy>% accuracy"
   ```
3. Tag main repo:
   ```
   git tag -a eval-<number>-<accuracy>pct -m "Eval <number>: <accuracy>% accuracy"
   ```
4. Remind user to update the Version Tags table in `docs/EVAL-process.md`

### `/eval` (no args) — Show status

Read `workspaces/nsa/eval/metrics_history.json` and report:
- Total evals run
- Best accuracy and which eval
- Latest accuracy and which eval
- Top recurring error category

## Error categories reference

| Category | Meaning |
|----------|---------|
| `false_reject:service_compliance` | Approved claim wrongly rejected — service check |
| `false_reject:component_coverage` | Approved claim wrongly rejected — coverage check |
| `false_reject:policy_validity` | Approved claim wrongly rejected — policy check |
| `false_approve` | Denied claim wrongly approved |
| `refer_should_approve:*` | Should approve, got REFER_TO_HUMAN |
| `refer_should_deny:*` | Should deny, got REFER_TO_HUMAN |
| `amount_mismatch` | Decision correct, payout amount wrong (>5% tolerance) |

## Key paths

| What | Path |
|------|------|
| Ground truth | `data/datasets/nsa-motor-eval-v1/ground_truth.json` |
| Eval script | `scripts/eval_pipeline.py` |
| Metrics history | `workspaces/nsa/eval/metrics_history.json` |
| Regression claims | `workspaces/nsa/eval/regression_claims.json` |
| Eval log | `workspaces/nsa/eval/EVAL_LOG.md` |
| Full eval docs | `docs/EVAL-process.md` |
| Claim assessments | `workspaces/nsa/claims/{claim_id}/claim_runs/{run_id}/assessment.json` |
| Batch run manifests | `workspaces/nsa/claim_runs/{run_id}/manifest.json` |
| Dataset registry | `data/datasets/registry.yaml` |
| Eval claim docs | `data/datasets/nsa-motor-eval-v1/claims/` |
| Customer config repo | `C:\Users\fbrun\Documents\GitHub\context-builder-nsa` |

## Important notes

- **Always use `--run-id`** when evaluating. Without it, the script picks each claim's most recent assessment, which may mix results from different pipeline runs.
- **Dependencies**: `pip install pandas openpyxl` (required by eval script)
- The 4 development claims in `data/datasets/nsa-motor-seed-v1/claims/` are NOT in the ground truth — don't mix them up.
- `amount_mismatch` is the persistent #1 error above 50% accuracy — it's payout calculation, not decision logic.
- Best result so far: **100%** (eval #35). Current target: maintain 96%+ while fixing amount_mismatch.
- Deep eval reports are saved to `docs/DEEP-EVAL-report-eval<N>.md`.
