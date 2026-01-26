# Evaluation Dashboard Gates Plan

**Date:** 2026-01-26
**Owner:** Platform

## Goals

1) Surface document-level quality gate health alongside assessment accuracy.
2) Add a claim-level reconciliation gate view to catch missing/conflicting facts before assessment.
3) Track decision accuracy and payout deltas against ground truth.
4) Keep the Evaluation page usable with minimal new UI complexity.

## Current State (Summary)

- Evaluation UI: `ui/src/components/evaluation/EvaluationPage.tsx`
  - Only the Assessment tab is exposed.
  - Assessment view: `ui/src/components/assessment/AssessmentEvalView.tsx`.
- Assessment eval data source: `/api/assessment/evals/latest`.
- Document pipeline already emits quality gates in extraction results.
- Claim reconciliation exists as a stage stub (facts are loaded), but no formal gate output.

## Recommendation: UI Structure

### Keep a Single Top-Level Tab (Assessment)
Avoid adding more top-level tabs. Instead, add **secondary sections** inside the Assessment tab:

1) **Assessment Quality** (existing, plus payout deltas)
2) **Document Quality Gate** (new)
3) **Claim Reconciliation Gate** (new)

This avoids tab sprawl while keeping the evaluation story coherent.

If navigation becomes crowded later, add a light secondary toggle inside Assessment:
- `Assessment Quality` | `Doc Quality Gate` | `Claim Reconciliation Gate`

## Document Quality Gate: What to Show

### KPI Cards
- Docs evaluated
- Gate pass rate
- Gate warn rate
- Gate fail rate
- Missing required fields rate

### Breakdown Tables
- **By Doc Type**: pass/warn/fail counts, top missing fields
- **Top Failure Reasons**: rule name and frequency
- **Problem Documents**: doc_id, claim_id, doc_type, gate status, missing fields

### Useful Interactions
- Filter by run_id
- Filter by doc_type
- Drill into a document (link to `/docs/:id`)

## Claim Reconciliation Gate: What to Show

### KPI Cards
- Claims evaluated
- Gate pass rate
- Missing critical facts (avg per claim)
- Conflict rate (critical facts with multiple conflicting values)
- Provenance coverage (critical facts with evidence)
- Facts size (token or field count) distribution

### Breakdown Tables
- **Problem Claims**: claim_id, status, missing facts, conflict count, facts size, last run_id
- **Top Missing Facts**: fact name and frequency
- **Top Conflicts**: fact name and conflict patterns

### Useful Interactions
- Filter by run_id
- Drill into claim (`/claims/explorer?claim=...`)

## Assessment Quality: Add Payout Deltas

Add payout accuracy metrics to the Assessment Quality section:

### KPI Cards
- Decision accuracy (existing)
- Payout MAE (absolute mean error)
- Payout MAPE (percentage mean error)
- Overpay rate (% claims where predicted > actual)
- Underpay rate (% claims where predicted < actual)

### Per-Claim Table Additions
- Expected payout
- Predicted payout
- Delta (absolute)
- Delta (%)
- Error type (over/under/match)

## Data Model Changes

### 1) Document Quality Gate Summary
Aggregate extraction quality gates into a run-scoped summary.

Suggested data shape:
```json
{
  "run_id": "run_...",
  "summary": {
    "docs_total": 120,
    "pass_count": 85,
    "warn_count": 25,
    "fail_count": 10,
    "missing_required_rate": 0.18
  },
  "by_doc_type": [
    {
      "doc_type": "insurance_policy",
      "pass": 10,
      "warn": 2,
      "fail": 1,
      "top_missing_fields": ["policy_number", "start_date"]
    }
  ],
  "top_reasons": [
    {"rule": "missing_required_fields", "count": 21}
  ],
  "problem_docs": [
    {
      "doc_id": "doc_123",
      "claim_id": "65196",
      "doc_type": "invoice",
      "status": "fail",
      "missing_fields": ["line_items"],
      "run_id": "run_..."
    }
  ]
}
```

### 2) Claim Reconciliation Gate Summary
Create a new gate output at claim level.

Proposed new artifact per claim:
`workspaces/<ws>/claims/<claim_id>/context/reconciliation_report.json`

Suggested data shape:
```json
{
  "claim_id": "65196",
  "status": "warn",
  "missing_critical_facts": ["policy_end_date"],
  "conflicts": [
    {"fact": "odometer_km", "values": ["74200", "74410"]}
  ],
  "provenance_coverage": 0.92,
  "fact_count": 185,
  "estimated_tokens": 21000,
  "run_id": "run_..."
}
```

Aggregate into a run-scoped summary for the dashboard:
```json
{
  "run_id": "run_...",
  "summary": {
    "claims_total": 40,
    "pass_count": 28,
    "warn_count": 9,
    "fail_count": 3,
    "avg_missing_critical": 1.3,
    "avg_conflicts": 0.4,
    "avg_provenance": 0.91
  },
  "top_missing_facts": [
    {"fact": "coverage_scale", "count": 6}
  ],
  "top_conflicts": [
    {"fact": "claim_date", "count": 4}
  ],
  "problem_claims": [
    {"claim_id": "65258", "status": "fail", "missing_critical": 3, "conflicts": 2, "fact_count": 420}
  ]
}
```

### 3) Assessment Eval With Payout Deltas
Extend the existing assessment eval file to include payout stats.

Suggested additions:
```json
{
  "summary": {
    "payout_mae": 420.12,
    "payout_mape": 0.18,
    "overpay_rate": 0.12,
    "underpay_rate": 0.22
  },
  "results": [
    {
      "claim_id": "65196",
      "predicted_payout": 2974.88,
      "expected_payout": 3120.00,
      "payout_delta": -145.12,
      "payout_delta_pct": -0.046
    }
  ]
}
```

## API Additions

Minimal approach (lowest surface area): extend `/api/assessment/evals/latest` to return:
- `doc_quality_gate_summary`
- `reconciliation_gate_summary`
- `payout_metrics`

Alternative (clean separation): add endpoints
- `GET /api/quality-gates/docs/latest`
- `GET /api/quality-gates/claims/latest`

## Implementation Plan (Pragmatic)

Phase 1: Backend Artifacts
1) Define reconciliation gate output format and write `reconciliation_report.json` during claim reconciliation.
2) Add aggregation scripts to produce:
   - `eval/doc_quality_gate_eval_<ts>.json`
   - `eval/reconciliation_gate_eval_<ts>.json`
3) Extend assessment eval output to include payout deltas.

Phase 2: API
4) Extend `AssessmentService.get_latest_evaluation()` to load the latest gate summaries (or new endpoints).

Phase 3: UI
5) In `AssessmentEvalView`, add two sections:
   - Document Quality Gate
   - Claim Reconciliation Gate
6) Add payout delta columns + metrics to existing assessment table and KPI row.

Phase 4: QA
7) Validate with 4 existing claims and confirm:
   - Gate summaries render with partial data.
   - Links to claim/doc work.
   - No break when eval data missing (fallback to empty state).

## Gate Definitions (Initial Defaults)

Document Quality Gate
- PASS: all required fields present, confidence >= threshold
- WARN: missing non-critical fields or low confidence
- FAIL: missing required fields

Claim Reconciliation Gate
- PASS: no missing critical facts, no conflicts
- WARN: <= 2 missing critical facts or conflicts
- FAIL: > 2 missing critical facts or conflicts

Token Size (for reconciliation)
- WARN if estimated tokens > 40K
- FAIL if estimated tokens > 60K

## Open Questions

1) Should reconciliation gate be blocking (stop assessment) or advisory only?
2) Should payout deltas be strict (match exact) or allow tolerance bands?
3) How do we treat REFER_TO_HUMAN in payout delta metrics (exclude or treat as zero)?
