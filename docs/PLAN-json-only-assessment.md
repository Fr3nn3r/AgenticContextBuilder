# Implementation Plan: JSON-Only Structured Assessment Output

## Problem Statement

The current assessment prompt asks for markdown report FIRST, then JSON. The LLM:
1. Writes full markdown report (consumes tokens)
2. Gets "tired" and truncates the JSON structure
3. Result: Only 2 of 10 checks appear in JSON, even though all 10 were reasoned in markdown

**Evidence from logs:**
- Markdown has all 10 checks: 1, 1b, 2, 2b, 3, 4, 5, 5b, 6, 7
- JSON only has 2 checks: 1, 2b
- `response_format` was `None` in the logged call

## Solution

Remove markdown requirement entirely. Use JSON-only output with OpenAI structured outputs (JSON schema) to guarantee complete responses.

## Implementation Steps

### Step 1: Define JSON Schema for Assessment Response

**File:** `src/context_builder/schemas/assessment_response.py` (NEW)

Create a Pydantic model that defines the complete assessment structure:

```python
class CheckResult(BaseModel):
    check_number: str  # "1", "1b", "2", etc.
    check_name: str
    result: Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_CHECKED"]
    details: str
    evidence_refs: List[str]

class PayoutCalculation(BaseModel):
    total_claimed: float
    non_covered_deductions: float
    covered_subtotal: float
    coverage_percent: int
    after_coverage: float
    max_coverage_applied: bool
    capped_amount: Optional[float]
    deductible: float
    after_deductible: float
    vat_adjusted: bool
    vat_deduction: float
    policyholder_type: Literal["individual", "company"]
    final_payout: float
    currency: str = "CHF"

class AssessmentResponse(BaseModel):
    schema_version: str = "claims_assessment_v2"
    claim_id: str
    assessment_timestamp: str
    decision: Literal["APPROVE", "REJECT", "REFER_TO_HUMAN"]
    decision_rationale: str
    confidence_score: float  # 0.0 to 1.0
    checks: List[CheckResult]  # Should have 7+ entries
    payout: PayoutCalculation
    assumptions: List[AssumptionMade]
    fraud_indicators: List[str]
    recommendations: List[str]
```

**Key:** The `checks` list will be enforced by the schema - no more truncation.

---

### Step 2: Update Assessment Prompt

**File:** `workspaces/nsa/config/processing/assessment/prompt.md`

**Changes:**

1. **Remove PART 1 (Markdown Report)** - Delete lines 458-464

2. **Update Output Format section** to:
```markdown
## Output Format

You MUST respond with a single JSON object (no markdown, no explanation outside JSON).

Your response will be validated against a strict schema. ALL fields are required.

CRITICAL: The `checks` array MUST contain ALL checks you performed:
- Check 1: policy_validity
- Check 1b: damage_date_validity
- Check 2: vehicle_id_consistency
- Check 2b: owner_policyholder_match
- Check 3: mileage_compliance
- Check 4a: shop_authorization
- Check 4b: service_compliance
- Check 5: component_coverage
- Check 5b: assistance_package_items
- Check 6: payout_calculation
- Check 7: final_decision

Do NOT omit any checks. If a check cannot be performed, set result to "NOT_CHECKED" with explanation.
```

3. **Bump version** in frontmatter: `version: "2.0.0"`

---

### Step 3: Update Assessment Processor

**File:** `src/context_builder/pipeline/claim_stages/assessment_processor.py`

**Changes:**

1. **Import the schema:**
```python
from context_builder.schemas.assessment_response import AssessmentResponse
```

2. **Update `_call_with_retry` to use structured outputs:**
```python
response = self._audited_client.chat_completions_create(
    model=model,
    messages=messages,
    temperature=temperature,
    max_tokens=max_tokens,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "assessment_response",
            "strict": True,
            "schema": AssessmentResponse.model_json_schema()
        }
    },
)
```

3. **Add validation after parsing:**
```python
result = json.loads(content)

# Validate with Pydantic
validated = AssessmentResponse.model_validate(result)

# Ensure minimum checks
if len(validated.checks) < 7:
    raise ValueError(
        f"Incomplete assessment: only {len(validated.checks)} checks, expected 7+"
    )

return validated.model_dump()
```

---

### Step 4: Update LLM Audit Logging

**File:** `src/context_builder/services/llm_audit.py`

Ensure `response_format` is always logged (already done based on code review).

---

### Step 5: Test the Changes

1. **Unit test:** Create test for `AssessmentResponse` schema validation
2. **Integration test:** Run assessment on claim 65196 and verify all checks present
3. **Verify logs:** Confirm `response_format` shows the schema

---

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `src/context_builder/schemas/assessment_response.py` | CREATE | Pydantic models for structured output |
| `workspaces/nsa/config/processing/assessment/prompt.md` | MODIFY | Remove markdown, update format instructions |
| `src/context_builder/pipeline/claim_stages/assessment_processor.py` | MODIFY | Use JSON schema in response_format |
| `tests/unit/test_assessment_response.py` | CREATE | Schema validation tests |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Azure OpenAI may not support `json_schema` mode | Fall back to `json_object` with Pydantic validation post-response |
| Schema too strict, causes failures | Add Optional fields where appropriate, use sensible defaults |
| Existing assessments incompatible | Schema version bump (v1 → v2) allows coexistence |

---

## Rollback Plan

If issues arise:
1. Revert `prompt.md` to previous version (git revert)
2. Remove `response_format` schema requirement
3. Keep Pydantic validation as optional warning, not error

---

## Success Criteria

1. All assessments have 7+ checks in JSON output
2. No more markdown in LLM responses
3. `response_format` logged for all assessment calls
4. Claim 65196 re-assessment shows all 10 checks

---

## Estimated Changes

- **New code:** ~150 lines (schema + tests)
- **Modified code:** ~50 lines (processor + prompt)
- **Risk level:** Medium (prompt change affects LLM behavior)
