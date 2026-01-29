# Plan: Two-Phase Assessment (Screening + LLM)

**Status:** Draft (revised)
**Created:** 2026-01-28
**Revised:** 2026-01-28
**Author:** Claude + User

## Problem Statement

The current assessment system sends all claims to the LLM for evaluation, even when deterministic rules can definitively reject a claim. This leads to:

1. **Unnecessary LLM costs** for obvious rejections (expired policy, mileage exceeded)
2. **Potential calculation errors** - LLM doing arithmetic it can get wrong
3. **Inconsistent decisions** - deterministic checks should have deterministic outcomes
4. **Wasted tokens** - prompt includes payout calculation steps that are pure math

Additionally, **coverage determination is duplicated**: the enrichment stage adds `_coverage_lookup` per line item, and the assessment LLM re-evaluates coverage in Check 5. The new coverage analysis module (`coverage/`) provides a more accurate three-tier approach (rules + keywords + LLM) that should be the single source of truth.

## Solution Overview

Reduce from four potential stages (enrichment, coverage, screening, assessment) to **two clean stages**:

1. **Screening Phase** (Deterministic + Coverage)
   - Run coverage analysis (rules + keywords + LLM fallback)
   - Run all deterministic checks (policy dates, mileage, VIN, shop auth)
   - Calculate payout using deterministic math
   - Auto-reject if hard fail conditions met

2. **Assessment Phase** (LLM)
   - Only called if screening doesn't auto-reject
   - Receives pre-computed screening results
   - Focuses on fraud detection, ambiguous cases, final judgment
   - Simplified prompt (~40% token reduction)

### Key Principles

- **Never auto-approve** - all approvals require LLM judgment
- **Can auto-reject** - deterministic failures don't need LLM
- **Same output format** - `assessment.json` structure unchanged
- **Audit trail** - screening results saved separately for traceability
- **No duplicate work** - coverage determined once, payout calculated once

### What Gets Merged

The previous draft had four stages: Enrichment → Coverage → Screening → Assessment. This revision merges the first three into one **Screening** stage:

| Old Stage | Disposition |
|-----------|-------------|
| **Enrichment** (coverage lookups, shop auth) | Merged INTO screening |
| **Coverage Analysis** (`coverage/analyzer.py`) | Called BY screening for line item coverage |
| **Screening** (deterministic checks, payout) | Absorbs enrichment + uses coverage results |
| **Assessment** (LLM) | Unchanged |

The `coverage/` module (`rule_engine.py`, `keyword_matcher.py`, `llm_matcher.py`, `analyzer.py`) remains as a library. Screening calls it rather than it being a standalone pipeline step.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        ClaimAssessmentService                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────┐   ┌─────────────────────────────────┐               │
│  │Reconcile   │──▶│          Screening              │               │
│  │            │   │                                  │               │
│  └────────────┘   │  ┌───────────────────────────┐  │               │
│        │          │  │ Coverage Analysis          │  │               │
│        ▼          │  │ (rules→keywords→LLM)      │  │               │
│  claim_facts.json │  └───────────────────────────┘  │               │
│                   │  ┌───────────────────────────┐  │               │
│                   │  │ Deterministic Checks       │  │               │
│                   │  │ (policy, mileage, VIN,    │  │               │
│                   │  │  shop auth, service hist)  │  │               │
│                   │  └───────────────────────────┘  │               │
│                   │  ┌───────────────────────────┐  │               │
│                   │  │ Payout Calculation         │  │               │
│                   │  │ (deterministic math)       │  │               │
│                   │  └───────────────────────────┘  │               │
│                   │  ┌───────────────────────────┐  │               │
│                   │  │ Auto-Reject Evaluation     │  │               │
│                   │  └───────────────────────────┘  │               │
│                   └──────────────┬──────────────────┘               │
│                                  │                                   │
│                                  ▼                                   │
│                            screening.json                            │
│                       + coverage_analysis.json                       │
│                                  │                                   │
│                            ┌─────┴─────┐                            │
│                            │ HARD FAIL? │                            │
│                            └─────┬─────┘                            │
│                           Yes    │    No                             │
│                            ▼     │     ▼                             │
│                     Auto-REJECT  │  ┌────────────┐                  │
│                     (skip LLM)   │  │ Assessment │                  │
│                                  │  │ (LLM)      │                  │
│                                  │  └────────────┘                  │
│                                  │         │                         │
│                                  │         ▼                         │
│                                  │   assessment.json                 │
└──────────────────────────────────┴───────────────────────────────────┘
```

## Screening Stage Responsibilities

The screening stage is the single deterministic pre-processing step. It runs four sub-steps in order:

### Sub-step 1: Coverage Analysis

Uses the existing `coverage/` module to determine per-line-item coverage:

```python
from context_builder.coverage.analyzer import CoverageAnalyzer

# Three-tier matching:
# 1. Rule engine (fees, exclusions, consumables) → confidence 1.0
# 2. Keyword matcher (German automotive terms) → confidence 0.70-0.90
# 3. LLM fallback (ambiguous items only) → confidence 0.60-0.85
```

Output: `coverage_analysis.json` (already implemented, reused as-is)

**Replaces:** Enrichment's `_coverage_lookup` per line item. The coverage analysis is more accurate because it uses rules and keyword matching before falling back to LLM, rather than the enrichment's simple lookup-table approach.

### Sub-step 2: Deterministic Checks

| Check | What | Detection | Hard Fail? |
|-------|------|-----------|------------|
| 1 Policy Validity | Date comparison | `claim_date` outside `start_date`/`end_date` | Yes |
| 1b Damage Date | Date comparison (clear cases only) | `damage_date` < `policy_start` | Yes (clear cases) |
| 2 VIN Consistency | String comparison | VIN mismatch across documents | No (flag) |
| 2b Owner Match | Fuzzy string match | Owner vs policyholder mismatch | No (flag) |
| 3 Mileage | Numeric comparison | `odometer` > `km_limited_to` | Yes |
| 4a Shop Auth | Lookup | Shop not in authorized list | No (flag) |
| 4b Service Compliance | Date gap analysis | Service interval > 12 months | No (flag) |
| 5 Component Coverage | From coverage analysis | Primary component `not_covered` | Yes |
| 5b Assistance Items | Keyword detection | Rental car, towing in items | No (exclude from payout) |

### Sub-step 3: Payout Calculation

```
Step 1: Sum from coverage analysis
  - covered_total = SUM(coverage_analysis.line_items WHERE status = "covered" → covered_amount)
  - not_covered_total = SUM(WHERE status = "not_covered" → total_price)

Step 2: Coverage percentage already applied
  - coverage_analysis already applies coverage_percent from coverage_scale
  - No need to re-apply

Step 3: Apply max coverage cap
  - IF covered_total > max_coverage THEN capped = max_coverage
  - ELSE capped = covered_total

Step 4: Apply deductible
  - deductible = MAX(capped × excess_percent, excess_minimum)
  - after_deductible = capped - deductible

Step 5: VAT adjustment (company only)
  - IF policyholder is company THEN final = after_deductible / 1.081
  - ELSE final = after_deductible
```

**Note:** The coverage analysis already calculates a preliminary `total_payable`. The screening payout calculation refines this by adding max coverage cap and VAT adjustment, which are policy-level concerns the coverage module doesn't handle.

### Sub-step 4: Auto-Reject Evaluation

Check if any hard-fail condition was triggered. If yes, produce a REJECT assessment without calling the LLM.

## What the LLM Still Handles

The LLM assessment receives `screening.json` and `coverage_analysis.json` and focuses on:

| Check | Why LLM? |
|-------|----------|
| **1b Damage Date (ambiguous)** | Requires reasoning about conflicting dates, partial info |
| **2/2b VIN/Owner (flagged)** | Screening flags mismatches; LLM judges severity |
| **Fraud indicators** | Pattern recognition across documents |
| **Final judgment** | Approve vs refer-to-human weighing all factors |

The LLM does NOT:
- Re-evaluate line item coverage (use screening results)
- Calculate payout (use screening calculation)
- Check policy dates or mileage (already deterministic)

## Hard Fail Conditions (Auto-Reject)

| Condition | Check | Detection |
|-----------|-------|-----------|
| Policy expired (dates) | Check 1 | `claim_date` outside `start_date`/`end_date` |
| Mileage exceeded | Check 3 | `odometer` > `km_limited_to` |
| Primary repair not covered | Check 5 | Coverage analysis: primary component = `not_covered` |
| Pre-existing damage (clear) | Check 1b | `damage_date` < `policy_start` (unambiguous only) |
| Missing critical data | All | No policy dates, no VIN, no claim date |

## Checks Summary

| Check | Deterministic? | Can Hard Fail? | Needs LLM? |
|-------|---------------|----------------|------------|
| 1 Policy Validity | Yes | Yes | No |
| 1b Damage Date | Partial | Yes (clear) | Yes (ambiguous) |
| 2 VIN Consistency | Yes | No | If flagged |
| 2b Owner Match | Yes | No | If flagged |
| 3 Mileage | Yes | Yes | No |
| 4a Shop Auth | Yes | No | No |
| 4b Service Compliance | Yes | No | No |
| 5 Component Coverage | Yes (via coverage analysis) | Yes | No |
| 5b Assistance Items | Yes | No | No |
| 6 Payout | Yes | N/A | No |
| 7 Final Decision | No | N/A | Yes |

## File Structure

```
src/context_builder/
├── coverage/                       # EXISTS: coverage analysis library
│   ├── schemas.py                  #   LineItemCoverage, CoverageAnalysisResult
│   ├── rule_engine.py              #   Deterministic rules (fees, exclusions)
│   ├── keyword_matcher.py          #   German keyword → category mapping
│   ├── llm_matcher.py              #   LLM fallback for ambiguous items
│   └── analyzer.py                 #   Orchestrates the three matchers
│
├── schemas/
│   ├── screening.py                # NEW: ScreeningResult, ScreeningCheck, PayoutCalculation
│   └── assessment_response.py      # UPDATE: add assessment_method field
│
├── pipeline/claim_stages/
│   ├── screening.py                # NEW: ScreeningStage (coverage + checks + payout)
│   ├── enrichment.py               # DEPRECATE: replaced by screening
│   └── assessment_processor.py     # UPDATE: receive screening results, skip auto-rejects
│
└── api/services/
    └── claim_assessment.py         # UPDATE: reconcile → screen → assess

workspaces/nsa/config/
├── coverage/                       # EXISTS: coverage analysis config
│   ├── nsa_coverage_config.yaml    #   Rules, keyword thresholds, LLM settings
│   ├── nsa_keyword_mappings.yaml   #   German term → category mappings
│   └── prompts/nsa_coverage.md     #   LLM prompt for ambiguous items
├── screening/
│   └── rules.yaml                  # NEW: hard-fail rules, thresholds
└── prompts/
    └── claims_assessment.md        # UPDATE: simplify, reference screening results
```

## Schema Definitions

### ScreeningResult

```python
class CheckVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    SKIPPED = "SKIPPED"

class ScreeningCheck(BaseModel):
    check_id: str  # "1", "1b", "2", "2b", "3", "4a", "4b", "5", "5b"
    check_name: str
    verdict: CheckVerdict
    reason: str
    evidence: Dict[str, Any] = {}
    is_hard_fail: bool = False
    requires_llm: bool = False  # Flags for LLM to review

class PayoutCalculation(BaseModel):
    # From coverage analysis
    parts_covered: float       # Covered parts (after coverage %)
    labor_covered: float       # Covered labor
    not_covered_total: float   # Total not covered

    # Policy-level adjustments
    coverage_percent: float
    max_coverage: Optional[float]
    max_coverage_applied: bool
    capped_amount: float

    # Deductible
    deductible_percent: float
    deductible_minimum: float
    deductible_amount: float
    after_deductible: float

    # VAT
    policyholder_type: Literal["individual", "company"]
    vat_adjusted: bool
    vat_deduction: float

    # Final
    final_payout: float
    currency: str = "CHF"

class ScreeningResult(BaseModel):
    schema_version: str = "screening_v1"
    claim_id: str
    screening_timestamp: str

    # Check verdicts
    checks: List[ScreeningCheck]
    checks_passed: int = 0
    checks_failed: int = 0
    checks_inconclusive: int = 0
    checks_for_llm: List[str] = []  # Check IDs that need LLM review

    # Coverage analysis reference
    coverage_analysis_ref: Optional[str] = None  # Path to coverage_analysis.json

    # Payout
    payout: Optional[PayoutCalculation] = None
    payout_error: Optional[str] = None

    # Auto-reject
    auto_reject: bool = False
    auto_reject_reason: Optional[str] = None
    hard_fails: List[str] = []  # Check IDs that hard-failed
```

### Screening Rules Config

```yaml
# workspaces/nsa/config/screening/rules.yaml
schema_version: screening_rules_v1

hard_fail_checks:
  policy_expired: true
  mileage_exceeded: true
  primary_not_covered: true
  missing_critical_data: true
  pre_existing_damage: true  # Only clear/unambiguous cases

critical_fields:
  - start_date
  - end_date
  - vehicle_vin
  - odometer_km

unknown_coverage_threshold:
  max_unknown_percent: 50
  action_if_exceeded: REFER_TO_HUMAN

service_compliance:
  max_gap_months: 12
  require_authorized_for_history: false
```

## Prompt Changes

### Current Prompt Issues

1. **Payout calculation (lines 319-395)** - 100% deterministic, LLM shouldn't do this
2. **Coverage evaluation (Check 5)** - already done by coverage analysis
3. **Check instructions are verbose** - many checks are now pre-computed
4. **~630 lines total** - significant token cost

### Proposed Changes

1. **Remove payout calculation** - reference `screening.payout`
2. **Remove coverage evaluation** - reference `coverage_analysis.json`
3. **Simplify deterministic checks** - "verify screening result" instead of full instructions
4. **Keep fraud detection (1b ambiguous)** - this needs LLM reasoning
5. **Keep final judgment (7)** - this needs LLM
6. **Add screening context** - inject screening results into prompt

### Estimated Reduction

- Current: ~630 lines, ~15K tokens
- After: ~300-350 lines, ~8-10K tokens
- Token savings: ~40-50%

## Implementation Phases

### Phase 1: Schemas (Small)

| Task | Description | File |
|------|-------------|------|
| 1.1 | Create screening schema | `schemas/screening.py` |
| 1.2 | Add `assessment_method` field to AssessmentResponse | `schemas/assessment_response.py` |

### Phase 2: Screening Stage (Large)

| Task | Description | File |
|------|-------------|------|
| 2.1 | Create `ScreeningStage` class | `pipeline/claim_stages/screening.py` |
| 2.2 | Implement deterministic checks (1, 2, 2b, 3, 4a, 4b, 5, 5b) | `pipeline/claim_stages/screening.py` |
| 2.3 | Implement payout calculation using coverage analysis results | `pipeline/claim_stages/screening.py` |
| 2.4 | Implement auto-reject evaluation | `pipeline/claim_stages/screening.py` |
| 2.5 | Create rules config | `config/screening/rules.yaml` |

Screening calls `coverage/analyzer.py` internally - no new coverage code needed.

### Phase 3: Assessment Updates (Medium)

| Task | Description | File |
|------|-------------|------|
| 3.1 | Update AssessmentProcessor to accept screening results | `pipeline/claim_stages/assessment_processor.py` |
| 3.2 | Handle auto-reject (skip LLM, produce assessment.json from screening) | `pipeline/claim_stages/assessment_processor.py` |
| 3.3 | Simplify prompt, reference screening | `config/prompts/claims_assessment.md` |

### Phase 4: Orchestration (Medium)

| Task | Description | File |
|------|-------------|------|
| 4.1 | Update `ClaimAssessmentService.assess()` | `api/services/claim_assessment.py` |
| 4.2 | Replace enrichment call with screening call | `api/services/claim_assessment.py` |
| 4.3 | Update `ClaimContext` to carry screening results | `pipeline/claim_stages/context.py` |

### Phase 5: Testing (Medium)

| Task | Description | File |
|------|-------------|------|
| 5.1 | Unit tests for screening checks | `tests/unit/test_screening.py` |
| 5.2 | Unit tests for payout calculation | `tests/unit/test_screening_payout.py` |
| 5.3 | Integration test: auto-reject flow | `tests/integration/test_assessment_flow.py` |
| 5.4 | Integration test: LLM assessment flow | `tests/integration/test_assessment_flow.py` |

### Phase 6: Cleanup (Small)

| Task | Description | File |
|------|-------------|------|
| 6.1 | Deprecate enrichment stage | `pipeline/claim_stages/enrichment.py` |
| 6.2 | Remove standalone `coverage analyze` CLI (optional, may keep for debugging) | `cli.py` |

## Testing Strategy

### Unit Tests

```python
class TestScreeningStage:
    # Coverage integration
    def test_coverage_analysis_runs(self):
        """Screening runs coverage analysis and produces coverage_analysis.json."""

    # Hard-fail checks
    def test_policy_expired_hard_fail(self):
        """Claim outside policy period should auto-reject."""

    def test_mileage_exceeded_hard_fail(self):
        """Odometer > km_limited_to should auto-reject."""

    def test_primary_not_covered_hard_fail(self):
        """Primary repair component not covered should auto-reject."""

    def test_clear_pre_existing_damage_hard_fail(self):
        """Unambiguous damage date before policy should auto-reject."""

    # Non-hard-fail checks
    def test_vin_mismatch_flags_for_review(self):
        """VIN mismatch should flag for LLM but not auto-reject."""

    def test_shop_not_authorized_flags(self):
        """Unauthorized shop should flag but not auto-reject."""

    def test_all_checks_pass_no_auto_reject(self):
        """When all checks pass, should NOT auto-reject."""

    # Payout
    def test_payout_calculation_basic(self):
        """Verify payout from coverage analysis totals."""

    def test_payout_with_max_coverage_cap(self):
        """Payout should cap at max_coverage."""

    def test_payout_company_vat_adjustment(self):
        """Company policyholders should have VAT deducted."""

    def test_payout_uses_coverage_analysis_amounts(self):
        """Payout should use covered_amount from coverage analysis, not re-calculate."""
```

### Integration Tests

```python
def test_auto_reject_flow():
    """Full flow: reconcile → screen (auto-reject) → no LLM call."""

def test_llm_assessment_flow():
    """Full flow: reconcile → screen → LLM assessment."""

def test_screening_produces_both_files():
    """Screening writes both screening.json and coverage_analysis.json."""
```

## Expected Benefits

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| LLM calls for obvious rejections | 100% | 0% | -100% |
| Prompt tokens (when LLM called) | ~15K | ~8-10K | -40% |
| Payout calculation accuracy | LLM-dependent | Deterministic | Guaranteed |
| Coverage accuracy | Simple lookup | Rules + keywords + LLM | Better |
| Pipeline stages | 3 (enrich + assess LLM) | 2 (screen + assess LLM) | Simpler |
| Duplicate coverage logic | Enrichment + LLM Check 5 | Coverage analysis only | Eliminated |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Auto-reject false positives | Conservative hard-fail list, never auto-approve |
| Missing edge cases | LLM still handles ambiguous cases and INCONCLUSIVE checks |
| Config drift | Version schema, include in claim_run snapshot |
| Regression in accuracy | A/B test: run old pipeline in parallel before cutover |
| Coverage analysis LLM errors | LLM only used for ambiguous items; rule/keyword matches are deterministic |

## Open Questions (Updated)

1. ~~Should we add a "confidence threshold" for screening decisions?~~ **Resolved:** Coverage analysis already has confidence thresholds; screening checks are binary pass/fail.
2. **How do we handle partial data?** Checks that can't run due to missing data → verdict `SKIPPED`. If a critical field is missing → hard fail via `missing_critical_data`.
3. **Should screening results be shown in the UI?** Yes, eventually. But not blocking for initial implementation.
4. **Keep `coverage analyze` CLI command?** Useful for debugging. Keep it but document that `assess` runs coverage internally.

## Related Documents

- `docs/PLAN-coverage-analysis.md` - Coverage analysis implementation plan
- `docs/PLAN-json-only-assessment.md` - Structured output implementation
- `workspaces/nsa/config/prompts/claims_assessment.md` - Current prompt
- `workspaces/nsa/config/coverage/nsa_coverage_config.yaml` - Coverage analysis config

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-28 | Claude + User | Initial draft |
| 2026-01-28 | Claude + User | Revised: merged enrichment + coverage analysis into screening; eliminated duplicate stages |
