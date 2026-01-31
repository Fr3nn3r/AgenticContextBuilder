# Refactor: Coverage Primary Component Determination

**Status:** PLANNED
**Created:** 2026-01-31
**Context:** Eval #21 (94%) — 2 of 3 decision errors are false rejects caused by flawed primary component selection in the screener. A third claim (65055) is already correctly referred.

## Problem Statement

The screener's check #5 (`_check_5_component_coverage`) selects a "primary component" from the claim's line items and hard-rejects the claim if that component isn't covered. The selection logic is flawed:

1. **It only considers `item_type == "parts"`** — but in many repair invoices the actual component identity is embedded in labor descriptions, not in a parts line.
2. **Consumables win by default** — e.g., claim 64358 has HALDEXOEL (oil, 83 CHF) as the highest-value parts item. The real repair (angle gearbox, 460 CHF) is labor.
3. **The repair-group override requires `matched_component`** — which is `None` since we stripped `component_name` from keyword mappings in eval #21 to fix false approves.
4. **Customer-specific vocabulary is hardcoded in core** — `COMPONENT_SYNONYMS` (60+ entries), `CATEGORY_ALIASES`, `REPAIR_CONTEXT_KEYWORDS` are all in `src/context_builder/coverage/analyzer.py`.

### Evidence: Claims Affected

| Claim | GT | Pipeline | Issue |
|-------|----|----------|-------|
| 64358 | APPROVED (439 CHF) | REJECT | HALDEXOEL (consumable) picked as primary; real repair is WINKELGETRIEBE (angle gearbox) in labor |
| 65040 | APPROVED (1,522 CHF) | REJECT | CALCULATEUR DE COFFRE (trunk ECU) not in policy list; LLM matched at 0.85 but hard-failed |
| 65055 | APPROVED (910 CHF) | REFER | Already correctly referred — no fix needed |

## Design

### Principle: Move primary component determination from screener to analyzer

The coverage analyzer already has all the context needed (line items, repair context from labor, policy parts list, LLM results). The screener should consume a claim-level verdict, not reimplement coverage logic with less information.

### Three-tier determination

```
Tier 1: Deterministic (no LLM cost)
  → If any line item is COVERED, that's the primary component
  → Skip consumables/exclusions when selecting among parts items
  → Use repair context from labor descriptions as fallback

Tier 2: LLM fallback (one focused call, ~$0.01)
  → When all items are NOT_COVERED or consumables
  → Ask: "Given these line items, what is the primary component being repaired?"
  → Validate answer against policy's covered components

Tier 3: Refer to human
  → When LLM can't determine, or confidence is below threshold
  → Return UNCERTAIN verdict → screener marks INCONCLUSIVE → no auto-reject
```

### Externalize customer-specific vocabulary

Move hardcoded dictionaries from core code to customer config YAML, following the existing `nsa_keyword_mappings.yaml` pattern.

## Implementation Steps

### Step 1: Create `nsa_component_config.yaml` in customer config

**New file:** `workspaces/nsa/config/coverage/nsa_component_config.yaml`
**Also committed to:** `C:\Users\fbrun\Documents\GitHub\context-builder-nsa\coverage\nsa_component_config.yaml`

Move these from `analyzer.py` into this YAML:

```yaml
# Component synonyms: maps component type to multilingual search terms
# Used by _is_component_in_policy_list() to match components against policy
component_synonyms:
  oil_cooler: ["ölkühler", "oelkuehler", "refroidisseur d'huile", "oil cooler"]
  timing_belt: ["zahnriemen", "courroie de distribution", "courroie crantée"]
  # ... (all ~60 entries from COMPONENT_SYNONYMS, lines 51-162)

# Category aliases: equivalent coverage category names
# Used by _is_system_covered() for cross-referencing
category_aliases:
  axle_drive: ["four_wd", "differential"]
  four_wd: ["axle_drive", "differential"]
  electrical_system: ["electronics", "electric"]
  electronics: ["electrical_system", "electric"]

# Repair context keywords: labor description patterns → (component, category)
# Used by _extract_repair_context() to identify primary repair from labor text
repair_context_keywords:
  ölkühler: { component: "oil_cooler", category: "engine" }
  wasserpumpe: { component: "water_pump", category: "engine" }
  turbolader: { component: "turbocharger", category: "turbo_supercharger" }
  winkelgetriebe: { component: "angle_gearbox", category: "axle_drive" }
  kardanwelle: { component: "drive_shaft", category: "axle_drive" }
  haldex: { component: "haldex_coupling", category: "axle_drive" }
  # ... expand with more German/French terms

# Distribution assembly catch-all components
distribution_catch_all_components:
  - timing_belt
  - timing_chain
  - timing_gear
  - chain_tensioner
  - chain_guide
  - belt_tensioner
  - idler_pulley
  - tensioner_pulley
  - pulley
  - timing_bolt
  - timing_belt_kit

distribution_catch_all_keywords:
  - "ensemble de distribution"
  - "distribution"
```

### Step 2: Load component config in analyzer

**File:** `src/context_builder/coverage/analyzer.py`

**Changes:**

a) Add a `ComponentConfig` dataclass (similar to `AnalyzerConfig`):

```python
@dataclass
class ComponentConfig:
    """Customer-specific component vocabulary, loaded from YAML."""
    component_synonyms: Dict[str, List[str]]
    category_aliases: Dict[str, List[str]]
    repair_context_keywords: Dict[str, Dict[str, str]]  # keyword → {component, category}
    distribution_catch_all_components: Set[str]
    distribution_catch_all_keywords: List[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentConfig":
        ...

    @classmethod
    def default(cls) -> "ComponentConfig":
        """Empty defaults — no customer-specific vocabulary."""
        return cls(
            component_synonyms={},
            category_aliases={},
            repair_context_keywords={},
            distribution_catch_all_components=set(),
            distribution_catch_all_keywords=[],
        )
```

b) Update `CoverageAnalyzer.__init__()` to accept `ComponentConfig`.

c) Update `CoverageAnalyzer.from_config_path()` to load `nsa_component_config.yaml` using the existing `_find_sibling()` pattern:

```python
# Load component config from sibling file
component_file = _find_sibling(config_path, "*_component_config.yaml")
if component_file:
    with open(component_file, "r", encoding="utf-8") as f:
        component_data = yaml.safe_load(f) or {}
    component_config = ComponentConfig.from_dict(component_data)
else:
    component_config = ComponentConfig.default()
```

d) Replace all references to the hardcoded constants (`COMPONENT_SYNONYMS`, `CATEGORY_ALIASES`, `REPAIR_CONTEXT_KEYWORDS`, `DISTRIBUTION_CATCH_ALL_*`) with `self.component_config.<field>`.

e) Remove the hardcoded constants (lines 51-216) from `analyzer.py`.

### Step 3: Add `PrimaryRepairResult` to coverage schemas

**File:** `src/context_builder/coverage/schemas.py`

```python
class PrimaryRepairResult(BaseModel):
    """Claim-level primary repair determination."""
    component: Optional[str] = None          # e.g., "angle_gearbox"
    category: Optional[str] = None           # e.g., "axle_drive"
    description: Optional[str] = None        # Original text, e.g., "Winkelgetriebe aus/einbau"
    is_covered: Optional[bool] = None        # True/False/None (uncertain)
    confidence: float = 0.0                  # 0.0-1.0
    determination_method: str = "none"       # "covered_item" | "repair_context" | "llm" | "none"
    source_item_index: Optional[int] = None  # Index into line_items that identified this
```

Add to `CoverageAnalysisResult`:

```python
class CoverageAnalysisResult(BaseModel):
    ...
    primary_repair: Optional[PrimaryRepairResult] = Field(
        None, description="Claim-level primary repair determination"
    )
```

### Step 4: Implement primary repair determination in analyzer

**File:** `src/context_builder/coverage/analyzer.py`

Add a new method `_determine_primary_repair()` called at the end of `analyze()`, after all line items are processed:

```python
def _determine_primary_repair(
    self,
    line_items: List[LineItemCoverage],
    covered_components: Dict[str, List[str]],
    repair_context: RepairContext,
    claim_id: str,
) -> PrimaryRepairResult:
    """Determine the claim's primary repair component.

    Three-tier approach:
    1. Deterministic: highest-value COVERED item (parts preferred, then labor)
    2. Repair context: if all parts are consumables, use labor description context
    3. LLM fallback: ask LLM to identify primary repair from line items
    """
```

**Tier 1 logic:**
```python
# 1a: Find highest-value COVERED parts item
covered_parts = [
    item for item in line_items
    if item.coverage_status == CoverageStatus.COVERED
    and item.item_type == "parts"
]
if covered_parts:
    best = max(covered_parts, key=lambda x: x.total_price or 0)
    return PrimaryRepairResult(
        component=best.matched_component,
        category=best.coverage_category,
        description=best.description,
        is_covered=True,
        confidence=best.match_confidence,
        determination_method="covered_item",
    )

# 1b: Find highest-value COVERED item (any type)
covered_any = [
    item for item in line_items
    if item.coverage_status == CoverageStatus.COVERED
]
if covered_any:
    best = max(covered_any, key=lambda x: x.total_price or 0)
    return PrimaryRepairResult(...)
```

**Tier 2 logic:**
```python
# 2: Use repair context from labor descriptions
if repair_context and repair_context.primary_component:
    return PrimaryRepairResult(
        component=repair_context.primary_component,
        category=repair_context.primary_category,
        description=repair_context.source_description,
        is_covered=repair_context.is_covered,
        confidence=0.80,  # repair context is reliable when it matches
        determination_method="repair_context",
    )
```

**Tier 3 logic (LLM fallback):**
```python
# 3: LLM determination — only when tiers 1-2 fail
#    Single focused call: "What is the primary component being repaired?"
if self.config.use_llm_fallback and self.llm_matcher:
    llm_result = self._llm_determine_primary_repair(
        line_items, covered_components, claim_id
    )
    if llm_result:
        return llm_result

# 4: Uncertain — return None-ish result → screener will REFER
return PrimaryRepairResult(
    determination_method="none",
    confidence=0.0,
)
```

**New method for LLM primary repair:**

```python
def _llm_determine_primary_repair(
    self,
    line_items: List[LineItemCoverage],
    covered_components: Dict[str, List[str]],
    claim_id: str,
) -> Optional[PrimaryRepairResult]:
    """Ask LLM to identify the primary repair component from all line items."""
    # Build a summary of all line items
    items_text = "\n".join(
        f"- {item.description} ({item.item_type}, {item.total_price} CHF)"
        for item in line_items
    )
    # Use existing LLM infrastructure with a focused prompt
    # Prompt: "Given these repair invoice items, identify the primary
    #          component being repaired and its category."
    # Response: {component, category, confidence, reasoning}
    ...
```

**LLM prompt for this call** — create new prompt template:

**New file:** `workspaces/nsa/config/coverage/prompts/nsa_primary_repair.md`

```markdown
---
name: nsa_primary_repair
model: gpt-4o
temperature: 0.0
max_tokens: 256
---
system:
You are an automotive insurance claims analyst. Given the line items from a
repair invoice, identify the PRIMARY COMPONENT being repaired or replaced.

Ignore consumables (oil, fluids, seals, gaskets, screws, bolts) and diagnostic
labor. Focus on the actual mechanical/electrical component being serviced.

Respond in JSON: {"component": "...", "category": "...", "confidence": 0.0-1.0, "reasoning": "..."}

Categories: engine, mechanical_transmission, automatic_transmission, chassis,
suspension, brakes, steering, electrical_system, air_conditioning,
cooling_system, electronics, fuel_system, axle_drive, exhaust, comfort_options

user:
Line items:
{{ items_text }}

Covered categories in this policy: {{ covered_categories }}
```

### Step 5: Wire up in `analyze()` method

**File:** `src/context_builder/coverage/analyzer.py`
**Location:** End of `analyze()` method, after all post-processing (after line ~1738)

```python
# Determine primary repair (claim-level)
primary_repair = self._determine_primary_repair(
    all_items, covered_components, repair_context, claim_id
)

# Build result
result = CoverageAnalysisResult(
    ...
    primary_repair=primary_repair,
)
```

### Step 6: Simplify screener check #5

**File:** `workspaces/nsa/config/screening/screener.py`
**Method:** `_check_5_component_coverage()` (lines 844-1014)

Replace the entire primary component selection and evaluation logic with:

```python
def _check_5_component_coverage(
    self, coverage_result: Optional[CoverageAnalysisResult]
) -> ScreeningCheck:
    if coverage_result is None:
        return ScreeningCheck(
            check_id="5", check_name="component_coverage",
            verdict=CheckVerdict.SKIPPED,
            reason="No coverage analysis available",
            is_hard_fail=True,
        )

    summary = coverage_result.summary
    evidence = {
        "items_covered": summary.items_covered,
        "items_not_covered": summary.items_not_covered,
        "items_review_needed": summary.items_review_needed,
        "total_covered_before_excess": summary.total_covered_before_excess,
    }

    primary = coverage_result.primary_repair

    if primary is None or primary.determination_method == "none":
        evidence["primary_determination"] = "unable_to_determine"
        return ScreeningCheck(
            check_id="5", check_name="component_coverage",
            verdict=CheckVerdict.INCONCLUSIVE,
            reason="Could not determine primary repair component — refer to human",
            evidence=evidence,
            is_hard_fail=True,
            requires_llm=False,  # Already tried LLM in analyzer
        )

    evidence["primary_component"] = primary.component
    evidence["primary_category"] = primary.category
    evidence["primary_description"] = primary.description
    evidence["primary_confidence"] = primary.confidence
    evidence["primary_method"] = primary.determination_method

    if primary.is_covered is True:
        return ScreeningCheck(
            check_id="5", check_name="component_coverage",
            verdict=CheckVerdict.PASS,
            reason=f"Primary repair '{primary.description}' is covered ({primary.category})",
            evidence=evidence,
            is_hard_fail=True,
        )

    if primary.is_covered is False and primary.confidence >= 0.80:
        return ScreeningCheck(
            check_id="5", check_name="component_coverage",
            verdict=CheckVerdict.FAIL,
            reason=f"Primary repair '{primary.description}' is not covered",
            evidence=evidence,
            is_hard_fail=True,
        )

    # Uncertain or low confidence → refer
    return ScreeningCheck(
        check_id="5", check_name="component_coverage",
        verdict=CheckVerdict.INCONCLUSIVE,
        reason=f"Primary repair '{primary.description}' coverage uncertain (confidence={primary.confidence:.2f})",
        evidence=evidence,
        is_hard_fail=True,
        requires_llm=False,
    )
```

**Lines to remove:** ~871-1014 (the entire primary selection + evaluation block).
**Lines to keep:** The SKIPPED/null checks at the start and the REVIEW_NEEDED handler.

### Step 7: Update sync scripts

**File:** `C:\Users\fbrun\Documents\GitHub\context-builder-nsa\copy-from-workspace.ps1`

The `coverage/*.yaml` pattern is already covered by the existing sync rule. Verify that `nsa_component_config.yaml` gets picked up (it should, since `coverage/*.yaml` is already synced).

**File:** `C:\Users\fbrun\Documents\GitHub\context-builder-nsa\sync-to-workspace.ps1`

Verify that `coverage/` is synced TO workspace as well. If not, add it.

### Step 8: Update tests

**Unit tests to update:**

| Test file | What to change |
|-----------|---------------|
| `tests/unit/test_nsa_screener.py` (lines 1093-1225) | Update check #5 tests to provide `CoverageAnalysisResult` with `primary_repair` field instead of testing internal selection logic |
| `tests/unit/test_coverage_analyzer.py` | Add tests for `_determine_primary_repair()` — all three tiers |
| `tests/unit/test_keyword_matcher.py` | No change needed |

**New test cases for `_determine_primary_repair()`:**

1. Covered parts item exists → returns it (tier 1)
2. Only covered labor item → returns it (tier 1)
3. All parts are consumables, labor has repair context → returns repair context (tier 2)
4. All items NOT_COVERED, no repair context → LLM fallback (tier 3)
5. LLM fallback also uncertain → returns `determination_method="none"` → screener refers

**Test case for claim 64358 specifically:**
- Parts: HALDEXOEL (not covered), repair kit (not covered), seal (not covered)
- Labor: "Winkelgetriebe aus/einbau" (covered under axle_drive)
- Expected: Tier 1 picks the labor item since it's COVERED

**Test case for claim 65040 specifically:**
- Parts: CALCULATEUR DE COFFRE (not covered, LLM confidence 0.85)
- Labor: REMPLACEMENT DU CALCULATEUR (not covered)
- Expected: Tier 3 LLM determines "trunk control unit" → policy check → not covered → screener FAILs (correct denial) OR refers if we want to be safe

### Step 9: Run eval and validate

After implementation:

```bash
# Run pipeline on existing claims
python -m context_builder.cli pipeline <input> --force

# Run eval
python scripts/eval_pipeline.py --run-id <new_run_id>

# Compare with eval #21 (94%)
# Target: maintain 94%+ accuracy, convert false rejects to refers
```

**Expected outcomes:**
- Claim 64358: REFER or APPROVE (was: REJECT) — improvement
- Claim 65040: REFER or correct REJECT (was: incorrect REJECT) — improvement or neutral
- Claim 65055: REFER (unchanged)
- All 24 correct denials: unchanged
- All 23 correct approvals: unchanged

## File Map

### Core repo (`AgenticContextBuilder`)

| File | Action | Lines affected |
|------|--------|---------------|
| `src/context_builder/coverage/analyzer.py` | MODIFY | Remove lines 51-216 (hardcoded constants); add `ComponentConfig` dataclass; add `_determine_primary_repair()` method; update `from_config_path()` to load component config; update `analyze()` to call primary repair and attach to result |
| `src/context_builder/coverage/schemas.py` | MODIFY | Add `PrimaryRepairResult` model; add `primary_repair` field to `CoverageAnalysisResult` |
| `tests/unit/test_nsa_screener.py` | MODIFY | Update check #5 test cases |
| `tests/unit/test_coverage_analyzer.py` | MODIFY | Add `_determine_primary_repair()` tests |

### Customer repo (`context-builder-nsa`)

| File | Action |
|------|--------|
| `coverage/nsa_component_config.yaml` | CREATE — contains COMPONENT_SYNONYMS, CATEGORY_ALIASES, REPAIR_CONTEXT_KEYWORDS |
| `coverage/prompts/nsa_primary_repair.md` | CREATE — LLM prompt for tier 3 fallback |
| `screening/screener.py` | MODIFY — simplify `_check_5_component_coverage()` to consume `primary_repair` |

### Workspace (synced from customer repo)

| File | Action |
|------|--------|
| `workspaces/nsa/config/coverage/nsa_component_config.yaml` | Synced from customer repo |
| `workspaces/nsa/config/coverage/prompts/nsa_primary_repair.md` | Synced from customer repo |
| `workspaces/nsa/config/screening/screener.py` | Synced from customer repo |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing hardcoded constants breaks existing tests | Tests fail | Update tests to load from YAML or inject ComponentConfig in test fixtures |
| LLM fallback adds cost per claim | ~$0.01 per claim that hits tier 3 | Only fires when tiers 1-2 fail; `llm_max_items` already caps total LLM spend |
| Primary repair determination changes approval rate | Could increase false approves | Tier 3 defaults to REFER (not approve); only tier 1 (deterministic) auto-approves |
| `copy-from-workspace.ps1` doesn't pick up new YAML | Config not synced to customer repo | Verify `coverage/*.yaml` glob already covers new file |
| Schema change breaks existing coverage_analysis.json | Old results missing `primary_repair` | Field is `Optional` with default `None` — backward compatible |

## Definition of Done

- [ ] `COMPONENT_SYNONYMS`, `CATEGORY_ALIASES`, `REPAIR_CONTEXT_KEYWORDS` moved to `nsa_component_config.yaml`
- [ ] `ComponentConfig` loaded via `_find_sibling()` pattern in `from_config_path()`
- [ ] `PrimaryRepairResult` added to `CoverageAnalysisResult` schema
- [ ] `_determine_primary_repair()` implements all three tiers
- [ ] `nsa_primary_repair.md` prompt template created
- [ ] Screener check #5 simplified to consume `primary_repair`
- [ ] All existing tests pass (with necessary updates)
- [ ] New test cases for primary repair determination
- [ ] Eval accuracy >= 94% (no regressions)
- [ ] Claims 64358 and 65040 are REFER or correct
- [ ] Customer repo committed and synced
- [ ] Tagged as `eval-22-*`

## Dependency Order

```
Step 1 (config YAML)
  → Step 2 (load in analyzer)
    → Step 3 (schema)
      → Step 4 (implement determination)
        → Step 5 (wire up in analyze())
          → Step 6 (simplify screener)
            → Step 7 (sync scripts)
              → Step 8 (tests)
                → Step 9 (eval)
```

Steps 1-3 can be done in parallel. Steps 4-5 depend on 1-3. Step 6 depends on 3 (schema). Steps 7-8 can happen in parallel after 6. Step 9 is last.
