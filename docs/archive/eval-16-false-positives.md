# Eval 20 — False Approve Analysis (80% regression)

**Eval**: eval_20260131_072810 | **Claim run**: clm_20260130_185438_34465c | **Accuracy**: 80% (40/50)
**Previous best**: eval_20260130_180826 | **Claim run**: clm_20260130_161951_eb350b | **Accuracy**: 92% (46/50)

## Root Cause

The regression was caused by **both a code change and config changes** between the 92% and 80% runs. The code change was the primary cause; the config changes were secondary.

### Primary: Code change in `_is_component_in_policy_list` (analyzer.py)

Commit `a9af7dc` changed the return value of `_is_component_in_policy_list` when synonyms exist but don't match the policy parts list:

- **92% code** (`fa41bdc`): returns `False` (not in list)
- **80% code** (`a9af7dc`): returns `None` (uncertain) in non-strict mode

This broke the **Stage 2.5 keyword verification** safety net (`analyzer.py:1546-1606`). The verification step checks keyword-matched items against the policy's parts list before accepting them as covered:

```
Line 1565: if is_in_list is False:     → demote to LLM ✓
Line 1579: elif is_in_list is None:    → demote only if no matched_component
Line 1594: else:                       → keep as covered
```

With the code change:
- **92%**: `False` → line 1565 → item demoted to LLM → LLM correctly says "not covered"
- **80%**: `None` → line 1594 (else) → item **stays as "covered"** because it has a `matched_component` from the keyword matcher

All 9 false approves went through this path. The keyword matcher correctly flagged the category ("engine"), but the safety net that should have caught non-listed parts was bypassed.

### Secondary: Config changes in customer repo (`e1a8c23` → `a3fbd15`)

**`assumptions.json`**:
1. Added 2 part number mappings (`4N1857409J` mirror, `4N1837015B` door lock)
2. Reclassified `schloss` from `body/accessory` → `electrical_system/door_lock`
3. Added `coverage` section with `age_threshold_years: null` (explicitly disabled age-based reduction)

**`coverage/nsa_keyword_mappings.yaml`**:
1. Added `comfort_options` to `labor_coverage_categories` (labor for comfort items now covered)
2. Added `component_name` fields to all 13 categories + new keywords (door lock, mirror terms)

These config changes alone would not have caused the regression — the Stage 2.5 policy list verification would have caught the mismatched items and demoted them to LLM. It was the code change that disabled the safety net.

## False Approve Claims (9)

All 9 involve parts **not on the covered parts list** that got keyword-matched to a covered category and bypassed the policy list verification.

| Claim | Pred Amount | Uncovered Part | Keyword Match Issue |
|-------|-----------|----------------|---------------------|
| 65002 | 362.12 | NOx sensors, wiring harness, ECU | Emissions parts mapped to "engine" |
| 65021 | 191.13 | Heating valve, cooling system | `VENTIL` keyword too broad |
| 65029 | 463.27 | Ad-Blue system, Ad-Blue injector | `EINSPRITZ` matched AdBlue injector to "engine" |
| 65113 | 3,496.20 | High-pressure pump + consequential damage | Pump keyword mapped to "engine" |
| 65190 | 238.90 | Water pump | Pump keyword mapped to covered category |
| 65211 | 451.86 | Sealing sleeves/gaskets | French claim, gaskets not covered |
| 65276 | 170.00 | EGR recirculation valve | `EGR` mapped to "engine" via "leerlaufstellmotor" |
| 65288 | 1,587.69 | EGR module | Same EGR keyword issue |
| 65306 | 194.84 | EGR valve cooler | Same EGR keyword issue |

## Detailed Example: Claim 65029 (Ad-Blue injector)

**92% run** (policy list returns `False`):
- Keyword matcher: `VENTIL` → "engine" (0.88 confidence)
- Stage 2.5: `_is_component_in_policy_list` returns `False` → **demoted to LLM**
- LLM: "Ventil Klemmschelle is a valve clamp, not an engine valve. AdBlue injector is emissions, not fuel injection." → `not_covered`
- Screening check 5: FAIL → **auto-reject**

**80% run** (policy list returns `None`):
- Keyword matcher: `VENTIL` → "engine" (0.88 confidence)
- Stage 2.5: `_is_component_in_policy_list` returns `None` → has `matched_component` → **kept as covered**
- LLM never called for this item
- Screening check 5: PASS → LLM assessment rubber-stamps **APPROVE**

## Resolution

1. Reverted main repo code to `fa41bdc` (commit `5b4785d`)
2. Reverted customer repo config to `e1a8c23` (commit `c316f79`)
3. Synced workspace config from customer repo
4. Re-run confirmed 92% accuracy (claim run `clm_20260131_065503_4e3b0a`)
5. Renamed tags: `eval-19-86pct` → `eval-19-92pct`, `eval-20-92pct` → `eval-20-80pct`

## Lessons

1. **The `None` vs `False` distinction in `_is_component_in_policy_list` is safety-critical.** Returning `None` (uncertain) instead of `False` (not found) bypasses the demotion path in Stage 2.5. Any future changes to this function must preserve `False` for "synonyms exist but don't match".
2. **Config changes should be tested independently from code changes.** The config and code were changed together, making it hard to attribute the regression.
3. **The keyword matcher needs a tighter safety net.** Even with the fix, broad keywords like `VENTIL`, `EINSPRITZ`, and `EGR` will continue to match items they shouldn't. Consider exclusion keywords for emissions parts (EGR, AdBlue, NOx, SCR) and requiring compound matches for ambiguous terms.
