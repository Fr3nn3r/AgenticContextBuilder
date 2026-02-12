# Repair Context LLM Validation — Analysis & Plan

**Date:** 2026-02-12
**Trigger:** Claim 64168 false denial (should be APPROVE, 333.69 CHF)
**Status:** Eval data validated — pattern is systemic but selective

---

## Eval Data Validation (50 claims)

### Headline Numbers

| Metric | Value |
|--------|-------|
| Total claims analyzed | ~50 |
| Claims with keyword-then-demoted items | **19** (38%) |
| Total CHF lost from demotions (all claims) | **CHF 26,698** |
| False rejects (GT=APPROVED) with this pattern | **6** |
| CHF lost in false rejects only | **CHF 3,252** |

### The 6 False Reject Cases (GT=APPROVED, items keyword-covered then demoted)

| Claim | GT Amount | Our Amount | Lost CHF | What Got Demoted | Would Fix Help? |
|-------|-----------|------------|----------|-----------------|-----------------|
| **64168** | 333.69 | **0.00** (DENY) | 660.00 | Labor "Olkuhler" demoted (no anchor) because "Gehause, Olfilter" denied by LLM | **YES** — part IS the oil cooler |
| **64288** | 4,141.02 | 3,990.21 | 365.59 | "Injecteur d'huile" (oil injector) denied — but it's part of timing chain repair | **YES** — part is for the covered repair |
| **64358** | 439.27 | 435.28 | 299.00 | "Olverlust Getriebe lokalisieren" (diagnostic labor) + oil for axle drive | No — diagnostic labor + consumable oil, correctly denied |
| **64792** | 520.68 | 668.78 | 199.30 | "Zuendkerze" (spark plugs) + "Ausgangsstutzen Einspritzpumpe" (injection pump nozzle) | No — spark plugs are consumables, fuel system not covered |
| **65055** | 910.15 | 11.76 | 1,500.32 | "Courroie crantee/chaine de distribution" (timing belt/chain) | No — timing belt is **explicitly excluded** in policy |
| **65056** | 3,600.00 | 6,996.95 | 228.00 | "Softwareupdate Motor" (software update/calibration) | No — diagnostic/calibration labor, correctly denied |

### Key Insight

**2 out of 6 false rejects** (64168, 64288) are genuine repair-context-association issues where the LLM denied a part that IS for the covered repair. The other 4 were correctly denied (consumables, excluded components, diagnostic labor).

This means the repair association step must be **selective** — it needs to:
- Promote "Gehause, Olfilter" when it's clearly the oil cooler replacement part (YES)
- Promote "Injecteur d'huile" when it's part of the timing chain repair (YES)
- NOT promote spark plugs, timing belts, oil, or diagnostic labor (these are genuinely not covered)

**The LLM CAN make this distinction** when given the full cost estimate context — that's exactly the kind of nuanced judgment it's good at. The current failure is that the LLM evaluates each part in isolation.

### Monetary Impact If Fixed

- Claim 64168: flips from DENY to APPROVE (+333.69 CHF, fixes false reject)
- Claim 64288: increases payout from 3,990.21 to ~4,141 CHF (+150 CHF, closer to GT)
- Other 4 claims: correctly unchanged (LLM should still deny those items)
- **Net: fixes 1 complete false reject, improves 1 amount accuracy**

### Broader Pattern Data (all 50 claims)

| Pattern | Count | Description |
|---------|-------|-------------|
| Keyword initially covered then demoted | **19** (38%) | Broadest: any item keyword-matched then overridden |
| `demoted_no_anchor` | **7** | Labor demoted because no covered parts exist |
| Keyword LABOR + LLM-denied PARTS | **4** | Exact repair-association pattern |
| primary_repair.is_covered=false but repair_context.is_covered=true | **2** | Direct conflict signal |
| Verdict disagreements with GT | **6** | 1 false reject (64168), 5 false approves |

The keyword-then-demotion is **correct in most cases** — the LLM catches false keyword matches like "MOTORENOEL" (engine oil, consumable) that keyword-matched "MOTOR" (engine). The dangerous failure mode is specifically when the LLM misclassifies the **primary repair part**, causing a cascading denial.

### Risk Assessment

- **Today**: 1 false reject (64168), 1 underpayment (64288)
- **Going forward**: the failure mode (LLM misclassifying primary repair parts) is systemic and will recur on new claims with catalog-vs-policy name mismatches
- **Safety**: the repair_context already has the correct answer — the fix uses it as a safety net

---

## Problem Statement

The coverage analyzer evaluates each line item **independently**. When a garage uses a catalog part name that differs from the policy component name, the LLM misclassifies the part as not covered — even when the labor description clearly identifies a covered repair.

### Claim 64168 Case Study

**NSA Decision:** APPROVE (333.69 CHF)
**Pipeline Decision:** DENY (0.00 CHF)

| Source | Labor line | Parts line |
|--------|-----------|------------|
| Garage cost estimate (KV.pdf) | "Olkuhler defekt / undicht aus /einbauen ersetzen" (660.00) | **"Gehause, Olfilter"** (458.60) |
| NSA decision letter | Same (660.00 -> 264.00) | **"Olkuhler"** (458.60 -> 183.44) |

NSA renamed the part from "Gehause, Olfilter" to "Olkuhler" in their decision — they understood the part IS the oil cooler, just listed under a different catalog name. On the Range Rover 4.4L diesel, the oil cooler and oil filter housing are an integrated assembly.

**This was NOT an adjuster judgment call** — it was contextual reading of the full cost estimate.

### Why The Pipeline Fails

1. **LLM evaluates "Gehause, Olfilter" in isolation** -> concludes "oil filter housing = consumable = NOT_COVERED"
2. The LLM receives repair context ("Olkuhler defekt...") but **dismisses it**: "the specific part in question is unrelated to the oil cooler"
3. **Parts NOT_COVERED** -> labor demoted (no anchor) -> everything denied

### Current Architecture (coverage analyzer stages)

```
Stage 1:  Rule Engine (deterministic exclusions: fees, cleaning, etc.)
Stage 1.5: Part Number Lookup
Stage 2:  Keyword Matcher (German terms -> categories)
Stage 2+: Labor Component Extraction (repair context)
Stage 2.5: Policy List Verification
Stage 3:  LLM Fallback (per-item, independent evaluation)
Post-LLM: Labor promotion/demotion, Primary repair determination
```

Key post-LLM functions:
- `_promote_parts_for_covered_repair()` (analyzer.py:1709-1793) — should rescue but fails because LLM returns `coverage_category: null`
- `_demote_labor_without_covered_parts()` (analyzer.py:1795-1857) — demotes labor when no parts are covered

---

## Proposed Solution: Repair Association LLM Step

### Concept

Add a single **repair association** LLM call per claim (not per item) that evaluates denied parts in the context of the full cost estimate and covered repair.

### When It Fires (generic trigger)

All three conditions must be true:
1. A covered repair context exists (labor matched a covered component via keyword, confirmed in policy list)
2. At least one parts item was denied by the LLM (match_method=LLM, coverage_status=NOT_COVERED)
3. The denied part was NOT caught by a deterministic exclusion (rule engine exclusions like REINIGUNG, fee items stay final)

### What The LLM Sees

One call with full context:

```
You are reviewing a vehicle repair cost estimate for insurance coverage.

PRIMARY REPAIR IDENTIFIED:
- Component: Olkuhler (oil cooler)
- Category: engine
- Status: COVERED (confirmed in policy parts list)
- Labor description: "Olkuhler defekt / undicht aus /einbauen ersetzen"

POLICY COVERED PARTS (engine category):
Kolben, Zylinderbuchsen, Kurbelwelle, Olpumpe, Olkuhler, ... [full list]

FULL COST ESTIMATE LINE ITEMS:
1. [LABOR] "Olkuhler defekt / undicht aus /einbauen ersetzen" - 660.00 CHF - COVERED (keyword match)
2. [PARTS] "Gehause, Olfilter" - 458.60 CHF - NOT_COVERED (LLM: consumable)
3. [PARTS] "Klein- und Reinigungsmaterial" - 25.00 CHF - NOT_COVERED (rule: exclusion pattern)
4. [FEE]   "Transportkostenanteil" - -18.00 CHF - NOT_COVERED (rule: fee)

QUESTION: For each parts item marked NOT_COVERED by the LLM (item 2), determine:
Is this part the replacement component for the identified primary repair, or is it
genuinely unrelated (consumable, ancillary, different repair)?

Consider:
- Garages often use manufacturer catalog names that differ from policy terminology
- A single cost estimate typically describes one coherent repair
- The part's price and context relative to the labor should inform your judgment
```

### Expected LLM Response (JSON)

```json
{
  "items": [
    {
      "description": "Gehause, Olfilter",
      "is_repair_component": true,
      "confidence": 0.90,
      "reasoning": "The cost estimate describes an oil cooler replacement. 'Gehause, Olfilter' (oil filter housing) at 458.60 CHF is the only material part and matches the repair context. On this vehicle, the oil cooler is integrated into the oil filter housing assembly. This is the replacement component for the covered oil cooler repair, not a consumable oil filter.",
      "associated_repair_component": "Olkuhler",
      "associated_category": "engine"
    }
  ]
}
```

### Where It Slots In (pipeline order)

```
... existing stages 1-3 ...
Stage 3:   LLM Fallback (per-item)
NEW STEP:  Repair Association Validation (per-claim, one LLM call)
           -> Overrides LLM NOT_COVERED -> COVERED for validated parts
           -> Adds decision_trace step: "repair_association_validation"
Post-LLM:  Labor promotion/demotion (now works because parts are covered)
```

### Why This Generalizes

1. **Input is the full cost estimate** — not one item in isolation
2. **Question is about association** — "is this part for this repair?" — not about specific part names
3. **Works for any component** — turbos, transmissions, water pumps, anything where catalog vs. policy names diverge
4. **Preserves denials where appropriate** — cleaning materials, transport fees, genuinely unrelated parts stay denied
5. **One LLM call per claim** — bounded cost
6. **Only fires when needed** — no covered repair context = no extra call

### What It Replaces

The hardcoded `_promote_parts_for_covered_repair()` function becomes the fallback; the LLM-based validation becomes the primary mechanism. Eventually the hardcoded function can be removed.

---

## Validation Needed

**Before building:** Check eval data to quantify how many claims have this pattern:
- Covered labor (keyword match) + denied parts (LLM) in the same repair context
- This tells us if the fix is high-value (systemic gap) or one-off

---

## Key Files

| File | Purpose |
|------|---------|
| `src/context_builder/coverage/analyzer.py` | Main orchestrator, all matching stages |
| `src/context_builder/coverage/llm_matcher.py` | LLM call logic, prompt building |
| `workspaces/nsa/config/coverage/prompts/nsa_coverage.md` | Coverage LLM prompt template |
| `workspaces/nsa/config/coverage/prompts/nsa_primary_repair.md` | Primary repair prompt |
| `src/context_builder/coverage/schemas.py` | LineItemCoverage, CoverageStatus, TraceStep |

## Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `analyze()` | analyzer.py:2654-3096 | Main entry, orchestrates all stages |
| `_extract_repair_context()` | analyzer.py:410-509 | Extracts repair component from labor lines |
| `_promote_parts_for_covered_repair()` | analyzer.py:1709-1793 | Current hardcoded promotion (broken for null category) |
| `_demote_labor_without_covered_parts()` | analyzer.py:1795-1857 | Demotes labor when no parts covered |
| `LLMMatcher._match_single()` | llm_matcher.py:286-472 | Per-item LLM classification |
| `LLMMatcher._build_prompt_messages()` | llm_matcher.py:118-210 | Prompt construction |
