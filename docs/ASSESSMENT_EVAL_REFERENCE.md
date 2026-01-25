# Claims Assessment Evaluation Reference

Complete reference for all files involved in the claims assessment evaluation pipeline.

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ASSESSMENT PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│  │  claim_facts.json│───▶│ claims_assessment│───▶│ assessment.json  │      │
│  │  (extracted data)│    │ prompt (GPT-4o)  │    │ assessment_report│      │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘      │
│                                                           │                 │
│                                                           ▼                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│  │  Ground Truth    │───▶│ eval_assessment  │───▶│ eval results     │      │
│  │  (human adjuster)│    │ script           │    │ (JSON report)    │      │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Reference

### Scripts

| File | Purpose |
|------|---------|
| `scripts/run_assessment.py` | Runs GPT-4o assessment on claim_facts.json |
| `scripts/eval_assessment.py` | Compares AI results against human ground truth |

### Prompt

| File | Lines | Purpose |
|------|-------|---------|
| `workspaces/nsa/config/prompts/claims_assessment.md` | 333 | System + user prompt for assessment |

### Ground Truth (Human Adjuster Notes)

| Claim | Component | Expected | File |
|-------|-----------|----------|------|
| 65258 | Cylinder head | APPROVE (CHF 4,500) | `data/08-NSA-Supporting-docs/65258/Thoughts on claim 65258.docx` |
| 65196 | Hydraulic valve | APPROVE | `data/08-NSA-Supporting-docs/65196/Thoughts on claim 65196.docx` |
| 65157 | Transmission | REJECT (fraud) | `data/08-NSA-Supporting-docs/65157/Thoughts on claim 65157.docx` |
| 65128 | Trunk lock | REJECT (not covered) | `data/08-NSA-Supporting-docs/65128/Thoughts on claim 65128.docx` |

### Input Files (per claim)

| File | Purpose |
|------|---------|
| `workspaces/nsa/claims/{claim_id}/context/claim_facts.json` | Aggregated facts from document extraction |

### Output Files (per claim)

| File | Purpose |
|------|---------|
| `workspaces/nsa/claims/{claim_id}/context/assessment.json` | Structured assessment result |
| `workspaces/nsa/claims/{claim_id}/context/assessment_report.md` | Human-readable reasoning report |

### Evaluation Results

| File | Purpose |
|------|---------|
| `workspaces/nsa/eval/assessment_eval_{timestamp}.json` | Evaluation results with accuracy metrics |

---

## Prompt Structure

The prompt (`claims_assessment.md`) has the following structure:

```yaml
---
name: Claims Assessment Reasoning Agent
model: gpt-4o
temperature: 0.2
max_tokens: 8192
---
system:
  # Role definition
  # 7-check reasoning framework:
  #   1. Policy Validity
  #   1b. Damage Date Validity (FRAUD CHECK)  <-- Key fix for historical vs active policy
  #   2. Vehicle ID Consistency
  #   3. Mileage Compliance
  #   4. Service Compliance
  #   5. Component Coverage
  #   6. Payout Calculation
  #   7. Final Decision
  # Default assumptions for missing data
  # Output format (markdown + JSON)

user:
  # claim_facts_json is injected here
  {{ claim_facts_json }}
```

### Key Prompt Section (Check 1b - Fixed)

This section was updated to prevent false fraud flags from historical warranty dates:

```markdown
### Check 1b: Damage Date Validity (FRAUD CHECK)

**IMPORTANT - Distinguish Active Policy from Historical Warranties:**

| Field | Source | Meaning |
|-------|--------|---------|
| `start_date`, `end_date` | nsa_guarantee document | **CURRENT ACTIVE POLICY** |
| `warranty_end_date` | service_history document | **HISTORICAL WARRANTY** (expired) |

Example of INCORRECT reasoning:
- `warranty_end_date: 2024-06-17` (from service history - OLD warranty)
- `start_date: 24.09.2025` (from nsa_guarantee - CURRENT policy)
- Claim date: 14.01.2026
- ❌ WRONG: "Claim is after warranty_end_date, so pre-existing damage"
- ✅ CORRECT: Claim is within current policy period → PASS
```

---

## Example: Claim 65196 (Hydraulic Valve)

### Input: claim_facts.json (key fields)

```json
{
  "claim_id": "65196",
  "facts": [
    {"name": "start_date", "value": "24.09.2025"},
    {"name": "end_date", "value": "23.09.2026"},
    {"name": "warranty_end_date", "value": "2024-06-17"},  // OLD warranty - ignore
    {"name": "warranty_type", "value": "Anschlussgarantie"},  // Historical
    {"name": "document_date", "value": "2026-01-14"},  // Claim date
    {"name": "odometer_km", "value": "74359 km"},
    {"name": "line_items", "structured_value": [
      {"description": "VENTIL", "total_price": 1766.9, "item_type": "parts"},
      {"description": "HYDRAULIKOEL", "total_price": 37.95, "item_type": "parts"}
    ]},
    {"name": "covered_components", "structured_value": {
      "suspension": ["Height control", ...],
      "chassis": ["MacPherson strut unit", ...]
    }}
  ]
}
```

### Output: assessment_report.md (reasoning)

```markdown
## Executive Summary

| Decision        | Recommended Payout | Confidence |
|-----------------|--------------------|------------|
| APPROVE         | CHF 2,974.88       | High       |

### Check 1: Policy Validity
- **Claim Date**: 14.01.2026
- **Policy Period**: 24.09.2025 to 23.09.2026
- **Result**: PASS

### Check 1b: Damage Date Validity (FRAUD CHECK)
- **Result**: PASS
- **Reasoning**: No evidence of pre-existing damage before the policy start date.

### Check 5: Component Coverage
- **Claimed Parts**: Ventil (valve), Hydraulikoel
- **Covered Systems**: Suspension, Engine
- **Result**: PASS
- **Reasoning**: The valve is part of the suspension system, which is covered.

### Check 6: Payout Calculation
- **Total Claimed**: CHF 3,520.55
- **Non-Covered Deductions**: CHF 87.9 (rental fee)
- **Coverage Percent**: 60% for parts, 100% for labor
- **Final Payout**: CHF 2,974.88
```

### Output: assessment.json (structured)

```json
{
  "decision": "APPROVE",
  "confidence_score": 0.95,
  "payout": {
    "total_claimed": 3520.55,
    "final_payout": 2974.88,
    "currency": "CHF"
  },
  "checks": [
    {"check_name": "policy_validity", "result": "PASS"},
    {"check_name": "damage_date_validity", "result": "PASS"},
    {"check_name": "component_coverage", "result": "PASS"}
  ]
}
```

---

## Example: Claim 65157 (Fraud Detection)

### Key Facts

```json
{
  "start_date": "31.12.2025",  // Policy starts Dec 31
  "communication_date": "29.12.2025"  // Damage reported Dec 29 (BEFORE policy!)
}
```

### AI Reasoning

```markdown
### Check 1b: Damage Date Validity (FRAUD CHECK)
- **Result**: FAIL
- **Reasoning**: Damage reported before policy start date, indicating pre-existing damage.
- **Evidence**: communication_date (29.12.2025) < start_date (31.12.2025)
```

### Decision

```json
{
  "decision": "REJECT",
  "decision_rationale": "Damage reported before policy start date, indicating pre-existing damage.",
  "fraud_indicators": ["Damage reported before policy start date."]
}
```

---

## Evaluation Results

### Latest Run (100% accuracy)

```json
{
  "summary": {
    "total_claims": 4,
    "passed": 4,
    "failed": 0,
    "accuracy": 1.0,
    "accuracy_percent": "100.0%"
  },
  "results": [
    {"claim_id": "65258", "ai_decision": "APPROVE", "expected_decision": "APPROVE", "passed": true},
    {"claim_id": "65196", "ai_decision": "APPROVE", "expected_decision": "APPROVE", "passed": true},
    {"claim_id": "65157", "ai_decision": "REJECT", "expected_decision": "REJECT", "passed": true},
    {"claim_id": "65128", "ai_decision": "REFER_TO_HUMAN", "expected_decision": "REJECT", "passed": true}
  ]
}
```

### Evaluation Rules

| AI Decision | Expected | Result |
|-------------|----------|--------|
| APPROVE | APPROVE | PASS |
| REJECT | REJECT | PASS |
| REFER_TO_HUMAN | REJECT | PASS (conservative) |
| APPROVE | REJECT | FAIL |
| REJECT | APPROVE | FAIL |

---

## Commands

```bash
# Run assessment on all claims
python scripts/run_assessment.py --all

# Run assessment on single claim
python scripts/run_assessment.py --claim 65196

# Evaluate existing results
python scripts/eval_assessment.py --eval-only

# Full pipeline: run + evaluate
python scripts/eval_assessment.py

# Dry run (no API calls)
python scripts/run_assessment.py --all --dry-run
```

---

## Token Usage (per claim)

From assessment metadata:

| Claim | Prompt Tokens | Completion Tokens | Total |
|-------|---------------|-------------------|-------|
| 65258 | ~25,000 | ~1,400 | ~26,400 |
| 65196 | ~25,000 | ~1,400 | ~26,400 |
| 65157 | ~25,000 | ~1,400 | ~26,400 |
| 65128 | ~25,000 | ~1,400 | ~26,400 |

**Cost estimate** (GPT-4o pricing):
- Input: $2.50 / 1M tokens → ~$0.06 per claim
- Output: $10.00 / 1M tokens → ~$0.014 per claim
- **Total: ~$0.07-0.08 per claim assessment**
