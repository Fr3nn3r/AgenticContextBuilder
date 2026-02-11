# Plan: Move Verdict Authority to Decision Stage

## Context

Claim 64297 shows REFER in the dashboard when ground truth expects APPROVE. Root cause: the LLM assessment prompt has a general "INCONCLUSIVE checks -> REFER_TO_HUMAN" rule that conflicts with its own soft-check exception for check 4b (service compliance). The Python overrides in `assessment_processor.py` only catch REJECT->APPROVE for soft checks, not REFER_TO_HUMAN.

The deeper issue: verdict logic is split between the LLM prompt (unreliable with conflicting rules) and Python overrides in the assessment processor. The decision engine — which already exists and is workspace-configurable — should be the single authority for the claim verdict.

## Design Principle

- **Assessment** evaluates checks, computes payout, detects fraud -> produces advisory `decision`
- **Decision engine** makes the authoritative verdict using check results + clause evaluations + business rules
- All verdict-related business logic (soft-check exceptions, zero-payout, REFER rules) moves to the decision engine

---

## Changes

### 1. DefaultDecisionEngine — derive verdict from assessment checks
**File**: `src/context_builder/pipeline/claim_stages/decision.py` (lines 131-174)

Currently returns hardcoded REFER ("No decision engine configured"). Change to derive a meaningful verdict from assessment check results when `processing_result` is available.

- Add `SOFT_CHECK_IDS: set = set()` class constant (empty in default; customer engines override)
- Add `_derive_verdict_from_assessment(processing_result)` method with logic:
  - Hard check FAIL -> DENY
  - Any INCONCLUSIVE -> REFER
  - Only soft checks failed -> APPROVE
  - APPROVE + zero payout -> DENY
  - No processing_result -> REFER (fallback, same as today)
- Update `evaluate()` to call the new method

### 2. Assessment Processor — remove verdict overrides
**File**: `src/context_builder/pipeline/claim_stages/assessment_processor.py`

Delete lines 331-411 (3 override blocks):
- Lines 331-372: soft-check REJECT->APPROVE override
- Lines 374-403: zero-payout APPROVE->REJECT override
- Lines 405-411: payout zeroing on REJECT

**Keep**: lines 320-329 (screening payout swap — this is payout authority, not verdict)
**Keep**: LLM `decision` field in response (advisory, for audit trail)
Add a clarifying comment that `decision` is advisory.

### 3. NSA Decision Engine — add REFER logic and moved overrides
**File**: `workspaces/nsa/config/decision/engine.py` (customer config)

Enhance `_determine_verdict()` (lines 1091-1165):
- Change signature: add `processing_result: Optional[Dict] = None` parameter
- Add `SOFT_CHECK_IDS = {"4b"}` class constant
- After hard-deny check (line 1136), add in order:
  1. **REFER rule**: if any assessment check is INCONCLUSIVE -> REFER (with check names in reason)
  2. **Soft-check protection**: if LLM said REJECT but only soft checks failed and no clause-level hard denials -> APPROVE
  3. **Zero-payout rule**: if no hard denials but final_payout <= 0 -> DENY
- Update call site at line 1292 to pass `processing_result`
- Bump `engine_version` from `"1.2.0"` to `"1.3.0"`

### 4. Assessment Prompt — simplify decision guidance
**File**: `workspaces/nsa/config/processing/assessment/prompt.md` (customer config)

Simplify the decision framework section (~lines 148-175):
- Mark the `decision` field as **advisory** (final verdict comes from decision engine)
- Remove the detailed REFER_TO_HUMAN trigger rules
- Keep the confidence scoring guidance (unchanged)
- Emphasize: focus on accurately resolving each check, not engineering the verdict

### 5. Eval Script — switch to dossier verdict
**File**: `scripts/eval_pipeline.py`

Currently reads `assessment.get("decision")` (line 197) for `pred_decision` and compares to ground truth. Does NOT read the decision dossier. After removing overrides from assessment.json, this would regress accuracy.

- Update `find_latest_assessment()` or `run_evaluation()` to ALSO load the latest `decision_dossier_v*.json`
- Use `dossier.get("claim_verdict")` as `pred_decision` (authoritative), fall back to `assessment.get("decision")` if no dossier
- `normalize_decision()` (line 92) already handles DENY->REJECTED and REFER->REFER_TO_HUMAN mapping
- Keep reading `payout` and `decision_rationale` from assessment.json (payout authority is screening, rationale is LLM)
- Update `categorize_error()` to use dossier verdict for error classification

### 6. Dashboard decision_match — switch to dossier verdict
**File**: `src/context_builder/api/services/dashboard.py`

Currently `decision_match` compares `assessment.get("decision")` (line 336/420) vs ground truth. Must switch to dossier verdict.

- Move `decision_match` computation after dossier loading (line 388-399)
- Compare `wb_verdict` (from dossier) to `gt_decision` (from ground truth) using `_normalize_decision()`
- Fall back to `assessment.decision` if no dossier
- `_normalize_decision()` (line 179) already handles DENY/REFER vocabulary differences

### 7. No frontend changes
- Frontend already uses `verdict ?? decision?.toUpperCase()` — prefers dossier verdict
- Dashboard service already returns both fields separately
- `ClaimAssessmentResult.decision` property already prefers dossier `claim_verdict`

---

## Test Changes

### Update existing tests

**`tests/unit/test_assessment_processor_screening.py`**:
- Remove `test_zero_payout_approve_overridden_to_reject` (line 743) — logic moves to decision engine
- Remove `test_zero_payout_override_updates_final_decision_check` (line 792) — same
- Add new tests verifying the overrides are NOT applied:
  - `test_approve_with_zero_payout_stays_approve` — assessment preserves LLM decision as-is
  - `test_reject_from_soft_check_stays_reject` — no override in assessment

**`tests/unit/test_decision_stage.py`**:
- Update `test_run_with_default_engine` (line 188):
  - Without `processing_result`: still returns REFER (no data to derive verdict)
  - Add new test with `processing_result` set: verify verdict is derived from checks
- Add tests for DefaultDecisionEngine verdict derivation:
  - All checks PASS + APPROVE -> APPROVE
  - Hard check FAIL -> DENY
  - INCONCLUSIVE check -> REFER
  - Zero payout -> DENY
  - REFER_TO_HUMAN from LLM -> REFER

### NSA engine tests (customer repo)
- Soft check 4b fail only -> APPROVE (not DENY)
- Hard check INCONCLUSIVE -> REFER
- Clause DENY takes precedence over assessment APPROVE
- Zero payout -> DENY

---

## Implementation Order

| Step | Repo | Files |
|------|------|-------|
| 1 | Core | `decision.py` — DefaultDecisionEngine verdict derivation |
| 2 | Core | `assessment_processor.py` — remove verdict overrides |
| 3 | Core | `scripts/eval_pipeline.py` — read dossier verdict for eval |
| 4 | Core | `dashboard.py` — switch `decision_match` to dossier verdict |
| 5 | Core | Test updates for steps 1-4 |
| 6 | Customer | `engine.py` — NSA REFER logic + moved overrides |
| 7 | Customer | `prompt.md` — simplify decision guidance |
| 8 | Customer | NSA engine tests |

Steps 1-5 are one atomic commit in this repo. Steps 6-8 are committed to the customer repo.

---

## Verification

1. `python -m pytest tests/unit/ --no-cov -q` — all tests pass
2. Re-run claim 64297: dossier should show REFER (mileage INCONCLUSIVE is a legitimate referral)
3. Re-run a clean APPROVE claim: dossier shows APPROVE, assessment `decision` also APPROVE
4. Test soft-check scenario: LLM rejects on 4b only -> dossier shows APPROVE
5. Test zero-payout scenario: LLM approves with zero payout -> dossier shows DENY
6. **Run full eval** (`/eval run`) — compare accuracy before/after to verify no regressions from verdict source switch
7. Verify dashboard `decision_match` uses dossier verdict for GT comparison

## Downstream Impact Summary

| Consumer | File | Currently reads | Must change to |
|----------|------|----------------|---------------|
| **Eval script** | `scripts/eval_pipeline.py:197` | `assessment.decision` | dossier `claim_verdict` (fall back to assessment) |
| **Dashboard decision_match** | `dashboard.py:420` | `assessment.decision` | dossier `claim_verdict` (fall back to assessment) |
| **Dashboard verdict badge** | `dashboard.py:394` | dossier `claim_verdict` | No change needed |
| **CLI assess output** | `claim_assessment.py:60` | dossier > assessment | No change needed |
| **Eval skill (/eval)** | `.claude/skills/eval/skill.md:36` | Docs say assessment.json = "final decision" | Update docs to clarify advisory vs authoritative |
| **Export** | `export.py` | Does not use verdicts | No change needed |
| **Extraction eval** | `pipeline/eval.py` | Does not use verdicts | No change needed |

## Backward Compatibility

- `DecisionEngine` protocol unchanged — `processing_result` already accepted as optional param
- `assessment.json` still contains `decision` field (now raw LLM output, no overrides)
- Old dossiers versioned (`decision_dossier_v{N}.json`) — no data loss on re-run
- Dashboard/frontend prefer dossier verdict already — no UI changes needed
- `_normalize_decision()` in both dashboard.py and eval_pipeline.py already handles DENY/REJECT and REFER/REFER_TO_HUMAN vocabulary differences
