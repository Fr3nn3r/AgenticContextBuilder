# Pipeline Evaluation Guide: NSA Motor Claims

This guide documents the evaluation-driven development process for improving the extraction and assessment pipeline accuracy.

## Overview

**Goal**: Build a scalable system that achieves high accuracy on insurance claim processing, especially for low-value claims where automation ROI is highest.

**Approach**: Run baseline → measure against ground truth → analyze errors → fix top issues → repeat

## Data Sets

| Set | Location | Claims | Purpose |
|-----|----------|--------|---------|
| Development | `data/datasets/nsa-motor-seed-v1/claims/` | 4 (65128, 65157, 65196, 65258) | Sanity check, known behavior |
| Evaluation | `data/datasets/nsa-motor-eval-v1/claims/` | 50 | Primary metrics, ground truth comparison |
| Ground Truth | `data/datasets/nsa-motor-eval-v1/ground_truth.json` | 50 | Expected outcomes |

### Ground Truth Schema

```json
{
  "claim_id": "64166",
  "decision": "APPROVED|DENIED",
  "total_approved_amount": 1506.52,
  "deductible": 376.65,
  "currency": "CHF",
  "vehicle": "FordFOCUS",
  "date": "08/10/2025",
  "denial_reason": "..." // for denied claims
}
```

### Ground Truth Statistics
- Total claims: 50
- Approved: 25 (50%)
- Denied: 25 (50%)
- Currency: CHF (all claims)

## Workspace Setup

The NSA workspace is located at `workspaces/nsa/` with this structure:

```
workspaces/nsa/
├── claims/           # Processed claim data
├── config/           # Extractors, prompts, specs (customer-specific)
├── eval/             # Evaluation results and reports
├── logs/             # Processing logs
├── registry/         # Truth store, indexes
└── runs/             # Pipeline run logs
```

## Evaluation Metrics

### Primary Metrics

1. **Decision Accuracy**: % of claims with correct APPROVED/DENIED decision
   - Target: 90%+ overall, 95%+ for low-value claims

2. **Amount Accuracy** (for approved claims):
   - Exact match rate
   - Within 5% tolerance rate
   - Mean absolute error

3. **Denial Reason Accuracy** (for denied claims):
   - Correct denial category identified
   - Key terms/parts mentioned

### Stratified Analysis

| Claim Value Tier | Amount Range | Target Accuracy | Rationale |
|------------------|--------------|-----------------|-----------|
| Low-value | < CHF 1,000 | 95%+ | High volume, automate aggressively |
| Medium | CHF 1,000 - 3,000 | 90%+ | Balance automation and review |
| High-value | > CHF 3,000 | 85%+ | Human review acceptable |

### Error Categories

Track every error by category to identify where to focus:

| Category | Description | Fix Approach |
|----------|-------------|--------------|
| **Extraction miss** | Required field not extracted | Improve extraction prompt/spec |
| **Extraction wrong** | Field extracted incorrectly | Add validation rules |
| **Assessment logic** | Correct data, wrong decision | Fix coverage rules |
| **Edge case** | Unusual document format | Add specific handling |
| **Ground truth error** | Label was incorrect | Fix ground truth |

## Step-by-Step Execution Plan

### Phase 1: Baseline Run (Do First)

1. **Verify workspace is active**
   ```bash
   # Check active workspace
   cat .contextbuilder/workspaces.json | grep active
   ```

2. **Run pipeline on evaluation set**
   ```bash
   python -m context_builder.cli pipeline data/datasets/nsa-motor-eval-v1/claims
   ```

3. **Save baseline results**
   - Results will be in `workspaces/nsa/claims/` and `workspaces/nsa/runs/`
   - Copy/tag this as "baseline" for comparison

### Phase 2: Run Evaluation

1. **Run evaluation command**
   ```bash
   python -m context_builder.cli eval run --run-id <baseline_run_id>
   ```

2. **Generate comparison report**
   - Compare pipeline output against `claims_ground_truth.json`
   - Calculate metrics per category

### Phase 3: Error Analysis

1. **Export errors to spreadsheet for analysis**
   - Claim ID, expected decision, actual decision, error category
   - For amount errors: expected vs actual, difference

2. **Categorize errors**
   - Group by error category (extraction miss, wrong, logic, etc.)
   - Count frequency per category

3. **Identify top failure modes**
   - Rank by frequency
   - Focus on top 3

### Phase 4: Iterative Improvement

For each iteration:

1. **Pick ONE failure mode to fix** (the most frequent)
2. **Implement fix** in extraction spec, prompt, or assessment logic
3. **Re-run pipeline** on evaluation set
4. **Re-run evaluation** to measure improvement
5. **Verify no regression** on development set (original 4 claims)
6. **Document** what changed and impact

### Phase 5: Holdout Validation

Keep 10 claims (20%) as holdout - don't look at them during development:
- Use for final validation
- Prevents overfitting to evaluation set

## File Locations

| File | Purpose |
|------|---------|
| `workspaces/nsa/eval/EVAL_LOG.md` | Human-readable log of all iterations with findings |
| `workspaces/nsa/eval/metrics_history.json` | Machine-readable metrics history (auto-updated) |
| `workspaces/nsa/eval/eval_YYYYMMDD_HHMMSS/` | Per-run output folder |
| `workspaces/nsa/eval/eval_*/summary.json` | Run metrics |
| `workspaces/nsa/eval/eval_*/details.xlsx` | Per-claim breakdown |
| `workspaces/nsa/eval/eval_*/errors.xlsx` | Only mismatches |

## Tracking Workflow

After each evaluation run:

1. **Automatic**: `metrics_history.json` is updated with metrics
2. **Manual**: Update `EVAL_LOG.md` with:
   - What you changed
   - What improved
   - New issues discovered
   - Next steps

## Evaluation Script

Run the evaluation script after processing claims:

```bash
python scripts/eval_pipeline.py
```

**Output** (in `workspaces/nsa/eval/eval_YYYYMMDD_HHMMSS/`):
- `summary.xlsx` - High-level metrics
- `details.xlsx` - Per-claim breakdown with all fields
- `errors.xlsx` - Only mismatches (focus your investigation here)
- `summary.json` - Metrics in JSON format for tracking over time

**Error Categories** (automatically assigned):
| Category | Meaning |
|----------|---------|
| `false_reject:service_compliance` | Approved claim wrongly rejected due to service check |
| `false_reject:component_coverage` | Approved claim wrongly rejected due to coverage check |
| `false_reject:policy_validity` | Approved claim wrongly rejected due to policy check |
| `false_reject:other` | Approved claim wrongly rejected, other reason |
| `false_approve` | Denied claim wrongly approved |
| `amount_mismatch` | Decision correct but amount differs by >5% |
| `not_processed` | Claim not yet processed by pipeline |

## Commands Reference

```bash
# Run full pipeline
python -m context_builder.cli pipeline data/datasets/nsa-motor-eval-v1/claims

# Run specific stages only
python -m context_builder.cli pipeline data/datasets/nsa-motor-eval-v1/claims --stages ingest,classify,extract

# Run assessment only (after extraction)
python -m context_builder.cli assess --claim-id <id>

# Dry run (preview without processing)
python -m context_builder.cli pipeline data/datasets/nsa-motor-eval-v1/claims --dry-run

# Run evaluation
python -m context_builder.cli eval run --run-id <run_id>

# Build indexes
python -m context_builder.cli index build
```

## Success Criteria

| Metric | Baseline | Target | Stretch |
|--------|----------|--------|---------|
| Overall decision accuracy | TBD | 90% | 95% |
| Low-value claim accuracy | TBD | 95% | 98% |
| Amount accuracy (within 5%) | TBD | 85% | 95% |
| Denial reason category match | TBD | 80% | 90% |

## Tracking Progress

After each iteration, record:

```json
{
  "iteration": 1,
  "date": "2026-01-28",
  "change_made": "Improved part name extraction for German documents",
  "decision_accuracy": 0.82,
  "amount_accuracy": 0.78,
  "errors_fixed": 4,
  "new_errors": 0,
  "notes": "..."
}
```

## Common Denial Reasons (from Ground Truth)

Analyzing the ground truth, common denial patterns:

1. **Part not covered** - "Die Garantie umfasst ausschliesslich die Teile, die im Vertrag aufgelistet sind"
2. **Policy expired/invalid** - "la police n'est pas valide" or mileage exceeded
3. **Software updates** - "Software Updates sind nicht über die Garantie abgedeckt"
4. **Specific parts excluded** - Headlights, control arms, water pump, AdBlue system, etc.

These patterns should inform assessment rule development.
