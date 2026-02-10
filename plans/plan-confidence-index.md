# Plan: Composite Confidence Index (CCI) — Phase 1 & 2

## Context

Every pipeline stage already produces confidence signals (field confidence, quality gates, match scores, conflict counts, etc.) but these are isolated silos. The final Decision Dossier has no confidence score. Claims that reach payout=0 due to bad upstream data aren't flagged early. We need a composite metric that aggregates data-quality signals into a single, traceable confidence index.

**Phase 1** instruments (collects raw signals from existing stage outputs).
**Phase 2** computes the composite score and stores it in the decision dossier + a separate breakdown file.

---

## New Files (7)

### 1. `src/context_builder/schemas/confidence.py` — Pydantic models

| Model | Purpose |
|-------|---------|
| `ConfidenceBand` | Enum: `high` (>=0.80), `moderate` (>=0.55), `low` (<0.55) |
| `SignalSnapshot` | Single raw signal: `signal_name`, `raw_value`, `normalized_value` (0-1), `source_stage`, `description` |
| `ComponentScore` | One of 5 components: `component`, `score` (0-1), `weight`, `weighted_contribution`, `signals_used: List[SignalSnapshot]`, `notes` |
| `ConfidenceIndex` | Compact model for dossier embedding: `composite_score`, `band`, `components: Dict[str, float]` |
| `ConfidenceSummary` | Full breakdown: `schema_version`, `claim_id`, `claim_run_id`, `composite_score`, `band`, `component_scores`, `weights_used`, `signals_collected`, `stages_available`, `stages_missing`, `flags: List[str]` |

### 2. `src/context_builder/confidence/__init__.py` — Package exports

Exports `ConfidenceCollector`, `ConfidenceScorer`, `ConfidenceStage`.

### 3. `src/context_builder/confidence/collector.py` — Signal collection

Reads upstream results (dicts already on context + JSON from disk). Produces `List[SignalSnapshot]`.

**Signals collected (21 total):**

| Signal | Source | Normalization |
|--------|--------|---------------|
| **Extraction (5)** | Loaded from extraction JSON files on disk | |
| `extraction.avg_field_confidence` | mean of `fields[*].confidence` across docs | Already 0-1 |
| `extraction.avg_doc_type_confidence` | mean of `doc.doc_type_confidence` across docs | Already 0-1 |
| `extraction.quality_gate_pass_rate` | fraction of docs with `quality_gate.status == "pass"` | Ratio 0-1 |
| `extraction.provenance_match_rate` | fraction of fields with `match_quality` in {exact, case_insensitive, normalized} | Ratio 0-1 |
| `extraction.verified_evidence_rate` | fraction of fields with `has_verified_evidence == True` | Ratio 0-1 |
| **Reconciliation (4)** | From `reconciliation_report` dict | |
| `reconciliation.provenance_coverage` | `gate.provenance_coverage` | Already 0-1 |
| `reconciliation.critical_facts_rate` | `len(critical_facts_present) / len(critical_facts_spec)` | Ratio 0-1 |
| `reconciliation.conflict_rate` | `1.0 - conflict_count / max(fact_count, 1)` | Inverted ratio |
| `reconciliation.gate_status_score` | pass=1.0, warn=0.5, fail=0.0 | Map |
| **Coverage (4)** | From `coverage_analysis` dict (loaded from disk) | |
| `coverage.avg_match_confidence` | amount-weighted mean of `line_items[*].match_confidence` by `total_price` | Weighted 0-1 |
| `coverage.review_needed_rate` | `1.0 - items_review_needed / max(total_items, 1)` | Inverted ratio |
| `coverage.method_diversity` | `len(distinct match_methods) / 5` | Ratio 0-1 |
| `coverage.primary_repair_confidence` | `primary_repair.confidence` (0.0 if None) | Already 0-1 |
| **Screening (3)** | From `screening_result` dict | |
| `screening.pass_rate` | `checks_passed / max(total_checks, 1)` | Ratio 0-1 |
| `screening.inconclusive_rate` | `1.0 - checks_inconclusive / max(total_checks, 1)` | Inverted ratio |
| `screening.hard_fail_clarity` | `1.0 if no hard_fails else 0.0` — note: hard fails = high clarity for DENY, but signal is about data quality not verdict | Binary |
| **Assessment (3)** | From `processing_result` dict | |
| `assessment.confidence_score` | `confidence_score` | Already 0-1 |
| `assessment.data_gap_penalty` | `1.0 - (HIGH*0.15 + MED*0.08 + LOW*0.03)`, clamped [0,1] | Inverted penalty |
| `assessment.fraud_indicator_penalty` | `1.0 - (high*0.20 + med*0.10 + low*0.05)`, clamped [0,1] | Inverted penalty |
| **Decision (2)** | From `decision_result` dict | |
| `decision.tier1_ratio` | fraction of clause_evaluations with `evaluability_tier == 1` | Ratio 0-1 |
| `decision.assumption_reliance` | `1.0 - unresolved / max(total_assumptions, 1)`, clamped [0,1] | Inverted ratio |

### 4. `src/context_builder/confidence/scorer.py` — Score computation

**Component formulas** (arithmetic mean of component signals):

| Component | Weight | Signals |
|-----------|--------|---------|
| `document_quality` | 0.25 | 5 extraction signals |
| `data_completeness` | 0.20 | reconciliation.provenance_coverage, reconciliation.critical_facts_rate, assessment.data_gap_penalty |
| `consistency` | 0.20 | reconciliation.conflict_rate, reconciliation.gate_status_score |
| `coverage_reliability` | 0.20 | 4 coverage signals |
| `decision_clarity` | 0.15 | screening.pass_rate, screening.inconclusive_rate, screening.hard_fail_clarity, decision.tier1_ratio, decision.assumption_reliance, assessment.fraud_indicator_penalty |

**Composite**: `CCI = sum(score * weight) / sum(active_weights)` — if a component has 0 signals, its weight redistributes.

**Bands**: HIGH >= 0.80, MODERATE >= 0.55, LOW < 0.55.

### 5. `src/context_builder/confidence/stage.py` — ConfidenceStage

Implements `ClaimStage` protocol. Runs after `DecisionStage`:
1. Loads extraction results from disk (scans `docs/*/extraction/*/`)
2. Loads coverage_analysis from claim_run dir
3. Reads reconciliation_report from context (or disk fallback)
4. Builds `ConfidenceCollector`, calls `collect_all()`
5. Optionally loads custom weights from `{workspace}/config/confidence/weights.yaml`
6. Builds `ConfidenceScorer`, calls `compute()`
7. Writes `confidence_summary.json` to claim_run dir
8. Patches `decision_dossier_v{N}.json` with `confidence_index` field
9. Non-fatal: exceptions logged, pipeline continues

### 6. `tests/unit/test_confidence_collector.py` — 13 tests
### 7. `tests/unit/test_confidence_scorer.py` — 12 tests
### 8. `tests/unit/test_confidence_stage.py` — 8 tests

---

## Existing Files Modified (5)

### 1. `src/context_builder/schemas/decision_dossier.py`
Add optional field to `DecisionDossier`:
```python
confidence_index: Optional[ConfidenceIndex] = Field(
    default=None,
    description="Composite Confidence Index computed after decision stage",
)
```
Backward-compatible (Optional, default None). Uses `TYPE_CHECKING` guard to avoid circular import.

### 2. `src/context_builder/pipeline/claim_stages/context.py`
- Add `confidence_ms: int = 0` to `ClaimStageTimings`
- Add `run_confidence: bool = True` to `ClaimStageConfig`

### 3. `src/context_builder/pipeline/claim_stages/__init__.py`
- Import `ConfidenceStage` from `context_builder.confidence.stage`
- Add to `__all__`

### 4. `src/context_builder/api/services/assessment_runner.py`
Add `ConfidenceStage()` after `DecisionStage()` in the stages list (line 92-98):
```python
stages = [
    ReconciliationStage(),
    EnrichmentStage(),
    ScreeningStage(),
    ProcessingStage(),
    DecisionStage(),
    ConfidenceStage(),  # <-- NEW
]
```

### 5. `src/context_builder/schemas/__init__.py`
Export `ConfidenceBand`, `ConfidenceIndex`, `ConfidenceSummary` from confidence.py.

---

## NOT Modified (Important)

- **No changes to any existing stage** (reconciliation, screening, processing, decision)
- **No changes to the CLI `assess` command** — the CLI uses `ClaimAssessmentService` which doesn't run DecisionStage. CCI via CLI will be a follow-up after wiring DecisionStage into the CLI path.
- **No changes to the NSA decision engine** (customer config)
- **No changes to extraction, classification, or coverage** code

---

## Implementation Sequence

1. Create `schemas/confidence.py` (models only, no dependencies)
2. Create `confidence/__init__.py`
3. Create `confidence/collector.py` + `tests/unit/test_confidence_collector.py`
4. Create `confidence/scorer.py` + `tests/unit/test_confidence_scorer.py`
5. Modify `context.py` (add timing + config fields)
6. Modify `decision_dossier.py` (add optional confidence_index field)
7. Modify `schemas/__init__.py` (add exports)
8. Create `confidence/stage.py` + `tests/unit/test_confidence_stage.py`
9. Modify `claim_stages/__init__.py` (import ConfidenceStage)
10. Modify `assessment_runner.py` (add ConfidenceStage to stages list)
11. Run full test suite to verify no regressions

---

## Verification

```bash
# Unit tests (new)
python -m pytest tests/unit/test_confidence_collector.py tests/unit/test_confidence_scorer.py tests/unit/test_confidence_stage.py -v --tb=short --no-cov

# Full test suite (regression check)
python -m pytest tests/unit/ --no-cov -q

# Manual E2E (on a real claim via API)
# 1. Start backend: uvicorn context_builder.api.main:app --reload --port 8000
# 2. Trigger assessment via API (creates decision dossier + confidence)
# 3. Inspect: {workspace}/claims/{claim_id}/claim_runs/{run_id}/confidence_summary.json
# 4. Inspect: decision_dossier_v{N}.json should now contain confidence_index field
```

---

## Phase 3: Calibration (Future)

- Collect CCI scores across holdout evaluation set
- Compare CCI bands to adjuster accept/override rates
- Tune default weights to minimize divergence (CCI predicts when adjusters change the decision)
- Add `python -m context_builder.cli confidence calibrate --run-id <id>` that reads all `confidence_summary.json` files from a batch run and produces calibration stats (distribution by band, correlation with adjuster overrides)
- Store calibrated weights in workspace config, track drift over time

## Phase 4: Routing (Future)

- Use CCI band to drive workflow routing:
  - **HIGH** (>= 0.80): straight-through processing, minimal human review
  - **MODERATE** (0.55-0.80): route to standard adjuster with dossier
  - **LOW** (< 0.55): route to senior adjuster with detailed breakdown + flags
  - **INSUFFICIENT** (optional sub-band < 0.30): don't decide, request more documents
- Add routing rules to workspace config (per-customer thresholds)
- Early exit: if CCI after reconciliation < threshold, skip expensive LLM assessment call
- Expose CCI in Claims Workbench UI (badge/color indicator on claim cards)
- API endpoint `GET /api/claims/{claim_id}/confidence` for summary
- Add CCI to compliance decision record audit trail
