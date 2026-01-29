# Handoff: Known Issues in NSA Pipeline

**Date**: 2026-01-29
**Context**: Evaluation of 50-claim ground truth set

## Issue Summary

| Priority | Issue | Impact | Claims Affected | Status |
|----------|-------|--------|-----------------|--------|
| P0 | Deductible extraction wrong | Blocks all payouts | All | Investigating |
| P1 | Service compliance false failures | 9 false rejects | 9 | Needs investigation |
| P1 | Coverage categories too narrow | Under-covering items | Many | Needs policy review |
| P2 | REFER_TO_HUMAN overuse | No decision made | 21 | Partially fixed |

---

## P0: Deductible Extraction Wrong

### Symptom

Claim 64166 shows:
```json
"deductible_minimum": 30000.0,
"deductible_amount": 30000.0
```

Ground truth says deductible should be **376.65 CHF**.

### Impact

- Even when items are correctly marked as covered, the huge deductible makes `final_payout = 0`
- This is likely affecting ALL claims, not just 64166

### Where to Investigate

1. **Policy extraction** - Where is `excess_minimum` being read from?
   - Check `workspaces/nsa/claims/64166/claim_runs/clm_20260129_071613_4f1375/claim_facts.json`
   - Look for fields like `excess_minimum`, `deductible`, `franchise`

2. **Coverage analyzer** - Where does it get the deductible value?
   - Check `src/context_builder/coverage/analyzer.py`
   - Look for how `excess_minimum` is populated

3. **Policy document** - What does the actual guarantee say?
   - Check `data/09-Claims-Motor-NSA-2/64166/NSA_Guarantee_*.pdf`

### Suspected Root Cause

The value 30,000 might be:
- A max coverage limit being misread as deductible
- A field extraction error from the German/French policy
- A default value when extraction fails

---

## P1: Service Compliance False Failures

### Symptom

9 claims rejected with error like:
```
"Last service 859 days ago (exceeds 12-month limit)"
```

But these claims were APPROVED in ground truth.

### Example Claims

- 64166: Last service "2023-06-01", claim date "2025-10-07" → 859 days
- 64168: Last service "2020-01-10", claim date "2025-10-07" → 5+ years

### Questions to Answer

1. **Is the service date extraction correct?**
   - Check `claim_facts.json` for `last_service_date`
   - Check the actual Service.pdf document

2. **Is service compliance a hard or soft requirement?**
   - NSA approved these claims despite lapsed service
   - Maybe it's a flag for review, not a rejection reason?

### Where to Investigate

1. **Screening logic** - Is service compliance a hard fail?
   - Check `screening.json` for `is_hard_fail` flag on check 4b
   - Currently `is_hard_fail: false` but `requires_llm: true`

2. **Service extraction** - How are service dates being read?
   - Check the Service.pdf extraction
   - Look for multiple service entries that might be missed

### Potential Fixes

- Make service compliance a "flag for review" not a rejection trigger
- Improve service history extraction to find more recent entries
- Add logic to check if service was done at an authorized partner (which might waive requirement)

---

## P1: Coverage Categories Too Narrow

### Symptom

Claim 64166 coverage analysis shows only these categories as covered:
```json
"covered_categories": [
  "electric",
  "axle_drive",
  "steering",
  "brakes",
  "air_conditioning"
]
```

Repair items like "SYNC module" and "UNITE - PROCESSEUR CENTRAL" are marked not covered.

### Impact

- Only 181.83 CHF marked as covered
- Ground truth says ~1,506.52 CHF should be covered
- Most items getting "not_covered" verdict from LLM

### Example LLM Reasoning

```
"The repair line item 'UNITE - PROCESSEUR CENTRAL' does not match any of the
covered components listed under the policy categories. It appears to be a
central processing unit, which is not explicitly included in the policy coverage."
```

### Questions to Answer

1. **What categories does the NSA policy actually cover?**
   - Review the actual guarantee document
   - Are electronics/infotainment covered under certain plans?

2. **Is the policy-specific coverage scale being read correctly?**
   - Check how `covered_categories` is populated
   - Check `workspaces/nsa/config/assumptions.json` for category definitions

### Where to Investigate

1. **Coverage analyzer inputs** - Where do categories come from?
   - Check `coverage_analysis.json` → `inputs.covered_categories`
   - Trace back to policy extraction

2. **NSA guarantee spec** - What does extraction spec define?
   - Check `workspaces/nsa/config/extraction_specs/`

---

## P2: REFER_TO_HUMAN Overuse

### Symptom

In baseline run: 30/50 claims (60%) returned `REFER_TO_HUMAN`
In iteration 1: 21/50 claims still return `REFER_TO_HUMAN`

### Breakdown (Iteration 1)

| Category | Count |
|----------|-------|
| refer_should_deny:no_fails | 12 |
| refer_should_approve:no_fails | 9 |

### Root Causes Identified

1. **Shop authorization inconclusive** - Many shops not in authorized list
2. **Component coverage unknown** - Items not matching keyword/rule lookups
3. **LLM being too conservative** - Prefers to refer rather than decide

### Progress Made

- Added pattern matching for shop authorization (AMAG, BYmyCAR, etc.)
- Added LLM-based coverage analysis with reasoning
- Reduced REFER_TO_HUMAN from 30 to 21 claims

### Remaining Work

- Expand authorized shop patterns
- Improve coverage category matching
- Consider adjusting LLM prompt to be more decisive when checks pass

---

## Investigation Commands

### Check a specific claim's screening result
```bash
cat workspaces/nsa/claims/64166/claim_runs/clm_20260129_071613_4f1375/screening.json | python -m json.tool
```

### Check coverage analysis for a claim
```bash
cat workspaces/nsa/claims/64166/claim_runs/clm_20260129_071613_4f1375/coverage_analysis.json | python -m json.tool
```

### Find all claims with specific error
```python
import json
from pathlib import Path

# Find claims where deductible > 1000
for claim_dir in Path("workspaces/nsa/claims").iterdir():
    runs = sorted((claim_dir / "claim_runs").iterdir(), reverse=True) if (claim_dir / "claim_runs").exists() else []
    for run in runs[:1]:  # Latest only
        screening = run / "screening.json"
        if screening.exists():
            data = json.loads(screening.read_text())
            ded = data.get("payout", {}).get("deductible_amount", 0)
            if ded > 1000:
                print(f"{claim_dir.name}: deductible={ded}")
        break
```

### Compare ground truth vs pipeline for a claim
```python
import json
gt = json.load(open("data/08-NSA-Supporting-docs/claims_ground_truth.json"))
gt_claim = next(c for c in gt["claims"] if c["claim_id"] == "64166")
print(f"GT: {gt_claim['decision']}, amount={gt_claim['total_approved_amount']}, ded={gt_claim['deductible']}")
```

---

## Next Steps

1. **P0 First**: Investigate deductible extraction - this is blocking all accurate payouts
2. **Then P1**: Check if service dates are being extracted correctly
3. **Then P1**: Review actual NSA policy to understand true coverage categories
4. **Finally P2**: Tune the system to be more decisive (reduce REFER_TO_HUMAN)
