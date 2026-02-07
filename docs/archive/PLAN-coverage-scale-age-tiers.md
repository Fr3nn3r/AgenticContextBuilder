# Plan: Extract Per-Tier Age-Adjusted Coverage Rates from Policy

**Status**: Ready for implementation
**Priority**: High (affects 15/50 eval claims via amount_mismatch)
**Estimated impact**: Fixes 2-4 false-reject underpayments + removes incorrect override on policies without age rules

---

## Problem

The system applies a **hardcoded blanket** `age_threshold_years=8, age_coverage_percent=40%` override to all policies when the vehicle is 8+ years old. This is wrong because:

1. **Some policies have per-tier age rates** (e.g., 80%/60%/40% per km tier, not a flat 40%)
2. **Some policies have NO age rule at all** — the override should not be applied
3. **The age threshold itself (8 years) could vary** by policy type in the future

### Evidence from Policy Audit (10 claims, 8 guarantee types)

| Policy Type | Has Age Column? | Age Rates | Age Threshold |
|-------------|----------------|-----------|---------------|
| BASIC 15 (FR) | **YES** | 80% / 60% / 40% per tier | "Dès 8 ans" |
| BASIC 10 (DE) | **YES** | 80% / 60% / 40% per tier | "Fahrzeuge ab 8 Jahre" |
| GLOBAL 12 (DE) | **YES** | 70% / 60% / 50% / 40% per tier | "Fahrzeuge ab 8 Jahre" |
| GLOBAL 12 plus (DE) | **YES** | 70% / 60% / 50% / 40% per tier | "Fahrzeuge ab 8 Jahre" |
| NSA Basic 150 - New (FR) | **NO** | — | — |
| NSA Basic 180 (V7) - New | **NO** | — | — |
| Best - New (FR) | **NO** | — | — |
| Best 05 - New 2J (DE) | **NO** | — | — |
| Elite Platinum - New (FR) | **NO** | — | — |
| L Large (DE) | **NO** | — | — |

### Pattern in dual-column policies

The age rate is consistently **10 percentage points lower** than the normal rate at each tier:

**BASIC policies (3 tiers: 50k/80k/110k):**
| Km Tier | Normal | Age 8+ |
|---------|--------|--------|
| 50,000 | 90% | 80% |
| 80,000 | 70% | 60% |
| 110,000 | 50% | 40% |

**GLOBAL policies (4 tiers: 100k/120k/140k/160k):**
| Km Tier | Normal | Age 8+ |
|---------|--------|--------|
| 100,000 | 80% | 70% |
| 120,000 | 70% | 60% |
| 140,000 | 60% | 50% |
| 160,000 | 50% | 40% |

### Impact on eval claims

| Claim | Policy | Km | Age | Blanket 40% | Correct Rate | GT Amount | System Amount |
|-------|--------|-----|-----|-------------|-------------|-----------|---------------|
| CLM-64836 | GLOBAL 12 plus | 20,012 | 10.4y | 40% | ~80-90% (below 100k, age-adjusted) | 2,995.41 | 646.72 |
| CLM-64535 | GLOBAL 12 | 23,635 | 11.7y | 40% | ~80-90% (below 100k, age-adjusted) | 914.20 | 142.41 |
| CLM-65040 | Elite Platinum | 25,622 | 10.8y | 40% | 100% (NO age rule in policy!) | 1,522.03 | 0.00 |

---

## Solution

Make the age-adjusted rate **policy-driven**: extract it from the guarantee document, store it per tier, and use it during screening. If the policy has no age column, no age adjustment is applied.

---

## Implementation Steps

### Step 1: Update LLM extraction prompt for coverage_scale

**File:** `src/context_builder/prompts/nsa_guarantee_components.md`

Update the `## Coverage Scale` section (lines 39-43) and the JSON example (lines 59-63) to capture both columns plus the age threshold.

**Current prompt (lines 39-43):**
```markdown
## Coverage Scale
Also extract the parts/labor coverage scale (usually at the end of the components section):
- Format: km threshold to coverage percentage
- Example: "ab 50'000 Km zu 80%" means threshold 50000, coverage 80%
```

**New prompt:**
```markdown
## Coverage Scale
Also extract the parts/labor coverage scale (usually at the end of the components section):
- Format: km threshold to coverage percentage, with optional age-adjusted rate
- Example: "ab 50'000 Km zu 90% (Fahrzeuge ab 8 Jahre 80%)" means threshold 50000, coverage 90%, age_coverage 80%, age_threshold 8
- Example: "A partir de 50 000 Km = 90% (Dès 8 ans 80%)" means the same in French
- If there is NO age-adjusted rate mentioned, set age_coverage_percent to null
- The age threshold (e.g., 8 in "ab 8 Jahre" or "Dès 8 ans") should be extracted as age_threshold_years
- All tiers in a single policy use the same age threshold — extract it once
```

**Current JSON example (lines 59-63):**
```json
"coverage_scale": [
    {"km_threshold": 50000, "coverage_percent": 80},
    {"km_threshold": 80000, "coverage_percent": 60},
    {"km_threshold": 110000, "coverage_percent": 40}
]
```

**New JSON example:**
```json
"coverage_scale": {
    "age_threshold_years": 8,
    "tiers": [
        {"km_threshold": 50000, "coverage_percent": 90, "age_coverage_percent": 80},
        {"km_threshold": 80000, "coverage_percent": 70, "age_coverage_percent": 60},
        {"km_threshold": 110000, "coverage_percent": 50, "age_coverage_percent": 40}
    ]
}
```

When NO age column is present in the policy:
```json
"coverage_scale": {
    "age_threshold_years": null,
    "tiers": [
        {"km_threshold": 100000, "coverage_percent": 80, "age_coverage_percent": null},
        {"km_threshold": 120000, "coverage_percent": 70, "age_coverage_percent": null},
        {"km_threshold": 140000, "coverage_percent": 60, "age_coverage_percent": null},
        {"km_threshold": 160000, "coverage_percent": 40, "age_coverage_percent": null}
    ]
}
```

Also update the `## Important Rules` section (line 72):
```markdown
5. For coverage_scale, extract all threshold/percentage pairs. If the policy includes
   age-adjusted rates (e.g., "Dès 8 ans 80%" or "Fahrzeuge ab 8 Jahre 80%"),
   include them as age_coverage_percent. Extract the age threshold (typically 8).
   If no age column exists, set age_coverage_percent to null and age_threshold_years to null.
```

### Step 2: Handle backward compatibility for coverage_scale format

The coverage_scale is stored as `structured_value` in claim_facts. Old extractions use:
```json
[{"km_threshold": 50000, "coverage_percent": 90}, ...]
```

New extractions will use:
```json
{"age_threshold_years": 8, "tiers": [{"km_threshold": 50000, "coverage_percent": 90, "age_coverage_percent": 80}, ...]}
```

**Every consumer of coverage_scale must handle both formats.** Add a normalizer function.

**File:** `src/context_builder/coverage/analyzer.py` (new helper, near top of file)

```python
def _normalize_coverage_scale(raw_scale) -> Tuple[Optional[int], Optional[List[Dict[str, Any]]]]:
    """Normalize coverage_scale from either old or new format.

    Old format: [{"km_threshold": 50000, "coverage_percent": 90}, ...]
    New format: {"age_threshold_years": 8, "tiers": [{"km_threshold": 50000, "coverage_percent": 90, "age_coverage_percent": 80}, ...]}

    Returns:
        Tuple of (age_threshold_years, tiers_list)
        age_threshold_years is None if not present (old format or policy without age rule)
    """
    if isinstance(raw_scale, list):
        # Old format — no age data
        return None, raw_scale
    elif isinstance(raw_scale, dict):
        age_threshold = raw_scale.get("age_threshold_years")
        tiers = raw_scale.get("tiers", [])
        return age_threshold, tiers
    return None, None
```

### Step 3: Update `_determine_coverage_percent` in analyzer.py

**File:** `src/context_builder/coverage/analyzer.py`, lines 362-435

Replace the current blanket age override with per-tier age-adjusted rates.

**Current signature:**
```python
def _determine_coverage_percent(
    self,
    vehicle_km: Optional[int],
    coverage_scale: Optional[List[Dict[str, Any]]],
    vehicle_age_years: Optional[float] = None,
    age_threshold_years: Optional[int] = None,
    age_coverage_percent: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float]]:
```

**New signature:**
```python
def _determine_coverage_percent(
    self,
    vehicle_km: Optional[int],
    coverage_scale: Optional[List[Dict[str, Any]]],
    vehicle_age_years: Optional[float] = None,
    age_threshold_years: Optional[int] = None,
) -> Tuple[Optional[float], Optional[float]]:
```

Remove `age_coverage_percent` parameter (the flat 40%). Instead, read `age_coverage_percent` from the matching tier in the scale.

**New logic:**
```python
# Sort tiers by km_threshold ascending
sorted_scale = sorted(coverage_scale, key=lambda x: x.get("km_threshold", 0))

# Find the applicable tier
first_threshold = sorted_scale[0].get("km_threshold", 0)
if vehicle_km < first_threshold:
    mileage_percent = 100.0
    tier_age_percent = None  # Below first tier — no age rate defined
else:
    applicable_tier = sorted_scale[0]
    for tier in sorted_scale:
        if vehicle_km >= tier.get("km_threshold", 0):
            applicable_tier = tier
        else:
            break
    mileage_percent = applicable_tier.get("coverage_percent")
    tier_age_percent = applicable_tier.get("age_coverage_percent")  # NEW: per-tier

# Apply age-based reduction using PER-TIER age rate
effective_percent = mileage_percent
if (
    vehicle_age_years is not None
    and age_threshold_years is not None
    and vehicle_age_years >= age_threshold_years
    and tier_age_percent is not None  # Only if policy has age column
):
    effective_percent = tier_age_percent
    logger.info(
        f"Age-based coverage reduction: vehicle is {vehicle_age_years:.1f} years old "
        f"(>= {age_threshold_years}), using tier age rate {tier_age_percent}% "
        f"instead of {mileage_percent}%"
    )
```

**Edge case — below first tier with age > threshold:**
When vehicle km is below the first tier (100% coverage normally), and the vehicle is 8+ years old:
- If the policy has age rates, extrapolate: the pattern is consistently -10 percentage points, so below-first-tier would be ~90%.
- **Conservative approach**: leave at 100% for below-first-tier since no explicit rate is defined.
- **Better approach**: check if the `-10pp` pattern holds across all tiers, and if so, apply 90% below first tier. But this adds complexity. Start with conservative (100%) and validate against ground truth.

### Step 4: Update callers to pass normalized scale

#### 4a. Screener (pipeline path)

**File:** `workspaces/nsa/config/screening/screener.py`, lines 349-387

**Current code (lines 372-387):**
```python
analyzer = self._get_analyzer()
return analyzer.analyze(
    ...
    coverage_scale=coverage_scale,
    ...
    vehicle_age_years=vehicle_age_years,
    age_threshold_years=8,          # HARDCODED — REMOVE
    age_coverage_percent=40.0,      # HARDCODED — REMOVE
    ...
)
```

**New code:**
```python
# Normalize coverage_scale (handles old list format + new dict format)
age_threshold_years, coverage_tiers = _normalize_coverage_scale(coverage_scale)

analyzer = self._get_analyzer()
return analyzer.analyze(
    ...
    coverage_scale=coverage_tiers,
    ...
    vehicle_age_years=vehicle_age_years,
    age_threshold_years=age_threshold_years,  # From policy extraction (None if no age rule)
    ...
)
```

Remove `age_coverage_percent=40.0` from the call entirely.

#### 4b. Coverage Analysis Service (API path)

**File:** `src/context_builder/api/services/coverage_analysis.py`, lines 395-427

The `_get_age_coverage_params` method currently returns hardcoded defaults. This method should be removed or simplified, since age params now come from the extracted coverage_scale.

**Remove** `_get_age_coverage_params` method entirely. Wherever it's called, replace with `_normalize_coverage_scale(coverage_scale)`.

### Step 5: Update `CoverageInputs` schema

**File:** `src/context_builder/coverage/schemas.py`, lines 94-121

Remove `age_coverage_percent` field (the flat value is gone). Keep `age_threshold_years` (now sourced from extraction).

```python
class CoverageInputs(BaseModel):
    vehicle_km: Optional[int] = Field(None, description="Vehicle odometer reading in km")
    vehicle_age_years: Optional[float] = Field(
        None, description="Vehicle age in years"
    )
    coverage_percent: Optional[float] = Field(
        None, description="Coverage percentage from mileage scale (before age adjustment)"
    )
    coverage_percent_effective: Optional[float] = Field(
        None, description="Effective coverage percent after per-tier age adjustment"
    )
    age_threshold_years: Optional[int] = Field(
        None, description="Age threshold from policy (e.g., 8 from 'Dès 8 ans'). Null if policy has no age rule."
    )
    # REMOVED: age_coverage_percent (was flat 40%, now per-tier from extraction)
    excess_percent: Optional[float] = Field(None)
    excess_minimum: Optional[float] = Field(None)
    covered_categories: List[str] = Field(default_factory=list)
```

### Step 6: Update `analyze()` method signature

**File:** `src/context_builder/coverage/analyzer.py`, lines 1453-1489

Remove `age_coverage_percent` parameter from `analyze()`. Update the `CoverageInputs` construction (lines 1765-1775) to not include the removed field.

### Step 7: Clean up assumptions.json

**File:** `workspaces/nsa/config/assumptions.json`, lines 1617-1622

The `coverage` section currently has disabled age override:
```json
"coverage": {
    "age_threshold_years": null,
    "age_coverage_percent": null,
    "_note": "NSA policies use mileage bands only. Age-based reduction disabled."
}
```

Update to reflect the new approach:
```json
"coverage": {
    "_note": "Age-based coverage reduction is now extracted per-tier from the guarantee document. No hardcoded override."
}
```

### Step 8: Update/add tests

**Files:** `tests/unit/test_coverage_analyzer.py` or new test file

Add tests for:
1. **New format parsing**: `_normalize_coverage_scale` handles both old list and new dict format
2. **Per-tier age lookup**: vehicle at 75k km with BASIC policy (8+ years) gets 60% (not 40%)
3. **No age rule**: vehicle at 75k km with Best policy (8+ years) gets mileage-based rate (no age adjustment)
4. **Below first tier**: vehicle at 20k km with GLOBAL policy (8+ years) gets 100% (conservative) or 90% (extrapolated)
5. **Backward compat**: old-format coverage_scale (list of dicts) still works, with no age adjustment

---

## Files to Change (Summary)

| File | Change | Lines |
|------|--------|-------|
| `src/context_builder/prompts/nsa_guarantee_components.md` | Update extraction prompt for dual-column scale | 39-43, 59-63, 72 |
| `src/context_builder/coverage/analyzer.py` | Add `_normalize_coverage_scale`, rewrite `_determine_coverage_percent`, update `analyze()` signature | 362-435, 1453-1489, 1765-1775 |
| `src/context_builder/coverage/schemas.py` | Remove `age_coverage_percent` from `CoverageInputs` | 107-112 |
| `workspaces/nsa/config/screening/screener.py` | Remove hardcoded age params, use extracted values | 372-387 |
| `src/context_builder/api/services/coverage_analysis.py` | Remove `_get_age_coverage_params`, use extracted values | 395-427 |
| `workspaces/nsa/config/assumptions.json` | Update coverage note | 1617-1622 |
| `tests/unit/test_coverage_analyzer.py` | Add tests for new format + per-tier age logic | new tests |

---

## Validation

After implementation:
1. Re-run pipeline: `python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2`
2. Run eval: `python scripts/eval_pipeline.py --run-id <new_run_id>`
3. Specifically check:
   - **CLM-64297** (BASIC 15, 155k km, 18y) — should still get 40% (regression test)
   - **CLM-64836** (GLOBAL 12 plus, 20k km, 10y) — should get ~100% or 90% (was 40%)
   - **CLM-64535** (GLOBAL 12, 24k km, 12y) — should get ~100% or 90% (was 40%)
   - **CLM-65040** (Elite Platinum, 26k km, 11y) — should get 100% (no age rule in policy)
   - **CLM-64168** (NSA Basic 180 V7, 173k km, 10y) — should get 40% from mileage tier (no age column, no override)

---

## Risk & Rollback

- **Risk**: LLM may not reliably extract `age_coverage_percent` from all policies. Mitigation: the new format treats `null` as "no age rule" which is safe (no override applied).
- **Risk**: Old extractions in existing claim_runs won't have the new format. Mitigation: `_normalize_coverage_scale` handles the old list format gracefully.
- **Rollback**: Revert the prompt change and restore the hardcoded 8/40 values in screener.py.
