---
name: eval
description: Run and analyze NSA pipeline evaluations. Use /eval run, /eval investigate <claim_id>, /eval compare, or /eval tag <number> <accuracy>.
argument-hint: "[run|investigate|compare|tag] [args...]"
allowed-tools: Read, Grep, Glob, Bash(python *), Bash(ls *), Bash(git tag *), Bash(git -C *), Bash(powershell *)
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
- Best result so far: **76%** (eval #13). That's the target to beat.
