# Assessment Improvements Implementation Plan

**Date:** 2026-01-25
**Status:** Planning
**Goal:** Make claims assessment production-grade by eliminating hallucination risks and adding deterministic lookups

---

## Overview

Create `assumptions.json` as a controlled configuration file containing:
1. **Part → System mapping** - Deterministic lookup to eliminate LLM guessing
2. **Authorized partners list** - Known dealers/repair shops
3. **Business rules** - Configurable policy defaults

This file becomes the "source of truth" that both extraction and assessment reference.

---

## Phase 1: Create assumptions.json Structure

### File Location
```
workspaces/nsa/config/assumptions.json
```

### Schema

```json
{
  "schema_version": "assumptions_v1",
  "updated_at": "2026-01-25T00:00:00Z",
  "updated_by": "human",

  "part_system_mapping": {
    "_description": "Maps part descriptions/numbers to covered systems",
    "_lookup_order": ["part_number", "description_keyword"],

    "by_part_number": {
      "8W0616887": {"system": "suspension", "component": "height_control_valve", "covered": true},
      "G 052731A2": {"system": "consumables", "component": "hydraulic_oil", "covered": true}
    },

    "by_keyword": {
      "ventil": {"system": "suspension", "note": "Confirm context - could be engine valve"},
      "zylinderkopf": {"system": "engine", "component": "cylinder_head", "covered": true},
      "getriebe": {"system": "transmission", "covered": true},
      "kupplung": {"system": "transmission", "component": "clutch", "covered": false, "reason": "wear_part"},
      "serrure": {"system": "body", "component": "lock", "covered": false, "reason": "accessory"},
      "schloss": {"system": "body", "component": "lock", "covered": false, "reason": "accessory"},
      "bremse": {"system": "brakes", "covered": false, "reason": "wear_part"},
      "reifen": {"system": "tires", "covered": false, "reason": "wear_part"}
    }
  },

  "authorized_partners": {
    "_description": "Known authorized repair partners",
    "_default_if_unknown": "REFER_TO_HUMAN",

    "by_name": {
      "AMAG": {"authorized": true, "regions": ["CH"]},
      "AMAG Bern Wankdorf": {"authorized": true},
      "AMAG Automobiles et Moteurs SA": {"authorized": true},
      "Kestenholz Automobil AG": {"authorized": true}
    },

    "by_pattern": [
      {"pattern": "AMAG.*", "authorized": true},
      {"pattern": ".*Audi Service Partner.*", "authorized": true}
    ]
  },

  "business_rules": {
    "_description": "Configurable business policy defaults",

    "unknown_authorization": {
      "action": "REFER_TO_HUMAN",
      "reason": "Shop authorization status could not be verified"
    },

    "unknown_part_coverage": {
      "action": "REFER_TO_HUMAN",
      "reason": "Part not found in coverage lookup table"
    },

    "missing_damage_date": {
      "action": "REFER_TO_HUMAN",
      "reason": "Cannot verify damage occurred within policy period"
    },

    "payout_near_max_coverage": {
      "threshold_percent": 90,
      "action": "use_max_coverage",
      "reason": "Adjuster policy: close claim at max to prevent follow-ups"
    }
  },

  "coverage_tiers": {
    "_description": "Standard mileage-based coverage percentages",
    "default": [
      {"max_km": 50000, "parts_percent": 80, "labor_percent": 100},
      {"max_km": 80000, "parts_percent": 60, "labor_percent": 100},
      {"max_km": 110000, "parts_percent": 40, "labor_percent": 100},
      {"max_km": 999999, "parts_percent": 20, "labor_percent": 100}
    ]
  },

  "excluded_items": {
    "_description": "Items never covered regardless of part mapping",
    "categories": ["rental_fee", "towing_fee", "environmental_fee"],
    "keywords": ["ERSATZFAHRZEUG", "MIETWAGEN", "ENTSORGUNG", "ABSCHLEPP"]
  }
}
```

---

## Phase 2: Update Assessment Script

### Changes to `run_assessment.py`

```python
def load_assumptions() -> dict:
    """Load assumptions.json from workspace config."""
    workspace_path = get_active_workspace_path()
    assumptions_path = workspace_path / "config" / "assumptions.json"

    if not assumptions_path.exists():
        logger.warning(f"No assumptions.json found at {assumptions_path}")
        return {}

    with open(assumptions_path, "r", encoding="utf-8") as f:
        return json.load(f)


def enrich_claim_facts(claim_facts: dict, assumptions: dict) -> dict:
    """
    Pre-process claim facts using assumptions lookup.
    Adds deterministic coverage flags before sending to LLM.
    """
    enriched = claim_facts.copy()

    # Enrich line items with coverage info
    if "line_items" in enriched.get("structured_data", {}):
        for item in enriched["structured_data"]["line_items"]:
            coverage = lookup_part_coverage(item, assumptions)
            item["_coverage_lookup"] = coverage

    # Enrich repair shop authorization
    shop_name = get_fact_value(enriched, "garage_name")
    if shop_name:
        auth = lookup_authorization(shop_name, assumptions)
        enriched["_shop_authorization_lookup"] = auth

    return enriched


def lookup_part_coverage(item: dict, assumptions: dict) -> dict:
    """Lookup part coverage from assumptions."""
    mapping = assumptions.get("part_system_mapping", {})

    # Try part number first
    part_num = item.get("item_code", "")
    if part_num in mapping.get("by_part_number", {}):
        result = mapping["by_part_number"][part_num].copy()
        result["lookup_method"] = "part_number"
        return result

    # Try keyword matching
    desc = item.get("description", "").lower()
    for keyword, info in mapping.get("by_keyword", {}).items():
        if keyword in desc:
            result = info.copy()
            result["lookup_method"] = "keyword"
            result["matched_keyword"] = keyword
            return result

    # Not found
    return {
        "lookup_method": "not_found",
        "covered": None,
        "action": assumptions.get("business_rules", {}).get("unknown_part_coverage", {}).get("action", "REFER_TO_HUMAN")
    }
```

---

## Phase 3: Update Prompt

### Add Assumptions Context Section

Add to `claims_assessment.md` before the user message:

```markdown
## Assumptions & Lookup Tables

The following lookup results have been pre-computed from the controlled assumptions file.
Use these results directly - DO NOT override or guess different values.

### Line Item Coverage (from assumptions.json)

Each line item in the claim facts includes a `_coverage_lookup` field:
- `covered: true` → Item is covered, include in payout
- `covered: false` → Item is NOT covered, exclude from payout
- `covered: null` → Unknown, apply `unknown_part_coverage` rule (typically REFER_TO_HUMAN)

**CRITICAL:** If `lookup_method` is "not_found", you MUST use the `action` field (usually REFER_TO_HUMAN).
Do NOT attempt to infer coverage from part descriptions.

### Shop Authorization (from assumptions.json)

The claim facts include `_shop_authorization_lookup`:
- `authorized: true` → Shop is verified authorized
- `authorized: false` → Shop is explicitly NOT authorized
- `authorized: null` → Unknown, apply `unknown_authorization` rule (REFER_TO_HUMAN)

**CRITICAL:** If authorization is unknown, do NOT assume authorized. Follow the action field.
```

### Update Check 5 (Component Coverage)

```markdown
### Check 5: Component Coverage

**Use the pre-computed `_coverage_lookup` field on each line item.**

Do NOT:
- Research part numbers
- Infer coverage from descriptions
- Guess system mappings

Do:
- Read the `_coverage_lookup.covered` field
- If `covered: null`, check the `action` field and follow it
- Sum covered vs non-covered amounts

**Example line item with lookup:**
```json
{
  "description": "VENTIL",
  "item_code": "8W0616887",
  "total_price": 1766.90,
  "_coverage_lookup": {
    "lookup_method": "part_number",
    "system": "suspension",
    "component": "height_control_valve",
    "covered": true
  }
}
```
Result: PASS - Part is covered per lookup table.

**Example with unknown part:**
```json
{
  "description": "SPEZIALWERKZEUG",
  "total_price": 50.00,
  "_coverage_lookup": {
    "lookup_method": "not_found",
    "covered": null,
    "action": "REFER_TO_HUMAN"
  }
}
```
Result: INCONCLUSIVE - Unknown part requires human review.
```

---

## Phase 4: Update Evaluation

### Add Stricter Scoring Option

```python
# In eval_assessment.py

EVAL_MODES = {
    "lenient": {
        # Current behavior
        "refer_as_reject": True,  # REFER_TO_HUMAN counts as REJECT
    },
    "strict": {
        # Production behavior
        "refer_as_reject": False,  # REFER_TO_HUMAN is its own category
        "require_exact_payout": True,  # Payout must match within 1%
    }
}

def evaluate_claim(claim_id: str, assessment: dict, ground_truth: dict, mode: str = "lenient"):
    config = EVAL_MODES[mode]
    # ... apply config to evaluation logic
```

### Add Confusion Matrix

```python
def compute_confusion_matrix(results: list) -> dict:
    """Compute confusion matrix for decisions."""
    matrix = {
        "APPROVE": {"APPROVE": 0, "REJECT": 0, "REFER_TO_HUMAN": 0},
        "REJECT": {"APPROVE": 0, "REJECT": 0, "REFER_TO_HUMAN": 0},
    }

    for r in results:
        expected = r["expected_decision"]
        actual = r["ai_decision"]
        if expected in matrix and actual in matrix[expected]:
            matrix[expected][actual] += 1

    return matrix
```

---

## Phase 5: Output Validation

### Add JSON Schema

```python
# In run_assessment.py

ASSESSMENT_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "claim_id", "decision", "confidence_score", "checks", "payout"],
    "properties": {
        "decision": {"enum": ["APPROVE", "REJECT", "REFER_TO_HUMAN"]},
        "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
        "payout": {
            "type": "object",
            "required": ["final_payout", "currency"],
            "properties": {
                "final_payout": {"type": "number", "minimum": 0}
            }
        }
    }
}

def validate_assessment(assessment: dict) -> tuple[bool, list[str]]:
    """Validate assessment against schema."""
    from jsonschema import validate, ValidationError

    errors = []
    try:
        validate(assessment, ASSESSMENT_SCHEMA)
    except ValidationError as e:
        errors.append(str(e))

    # Business logic validation
    if assessment.get("decision") in ("REJECT", "REFER_TO_HUMAN"):
        if assessment.get("payout", {}).get("final_payout", 0) > 0:
            errors.append("Rejected claims must have final_payout = 0")

    return len(errors) == 0, errors
```

---

## Implementation Order

### Sprint 1 (Core - 2-3 days)

| Task | File | Effort |
|------|------|--------|
| Create assumptions.json with initial mappings | `config/assumptions.json` | 2h |
| Add `load_assumptions()` function | `run_assessment.py` | 1h |
| Add `enrich_claim_facts()` function | `run_assessment.py` | 3h |
| Update prompt Check 5 to use lookups | `claims_assessment.md` | 2h |
| Update prompt Check 4 to use shop lookup | `claims_assessment.md` | 1h |
| Test with all 4 claims | - | 2h |

### Sprint 2 (Hardening - 1-2 days)

| Task | File | Effort |
|------|------|--------|
| Add JSON schema validation | `run_assessment.py` | 2h |
| Enforce payout=0 for REJECT | `run_assessment.py` | 1h |
| Add confusion matrix to eval | `eval_assessment.py` | 2h |
| Add strict eval mode | `eval_assessment.py` | 2h |

### Sprint 3 (Polish - 1 day)

| Task | File | Effort |
|------|------|--------|
| Add assumptions version to assessment output | `run_assessment.py` | 1h |
| Log when lookup falls back to REFER_TO_HUMAN | `run_assessment.py` | 1h |
| Document assumptions.json format | `docs/` | 2h |

---

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| Part coverage hallucination risk | HIGH | ELIMINATED |
| Unknown authorization handling | Assumes approved | REFER_TO_HUMAN |
| Output validation | None | Schema-enforced |
| Eval transparency | Accuracy only | Confusion matrix |
| Reproducibility | LLM-dependent | Deterministic lookups |

---

## Files Changed

```
workspaces/nsa/config/
├── assumptions.json           # NEW - Lookup tables
└── prompts/
    └── claims_assessment.md   # UPDATED - Use lookups

scripts/
├── run_assessment.py          # UPDATED - Load & enrich
└── eval_assessment.py         # UPDATED - Confusion matrix

docs/
├── ASSESSMENT_IMPROVEMENTS_PLAN.md  # This file
└── ASSUMPTIONS_FORMAT.md            # NEW - Schema docs
```

---

## Rollback Plan

If issues arise:
1. Remove `enrich_claim_facts()` call in `run_assessment.py`
2. Prompt falls back to original behavior (LLM inference)
3. Assumptions file is ignored but preserved

The changes are additive - original behavior is preserved if enrichment is disabled.
