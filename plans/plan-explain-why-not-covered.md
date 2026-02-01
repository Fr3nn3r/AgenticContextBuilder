# Feature Brief: "Explain WHY Not Covered"

**Priority**: P0 (CEO-confirmed)
**Origin**: Stefano (NSA) requested this twice in the Jan 27 meeting
**Status**: Ready for planning

---

## Business Context

When a claim has non-covered items, NSA adjusters must explain to the customer WHY each item isn't covered. Today this is manual: the adjuster looks up the policy, finds the relevant clause, and writes the explanation. This is time-consuming and inconsistent across the team.

Stefano's exact words: "the AI should learn to explain why specific parts, like liquids, are not covered by referencing terms or the contract, to efficiently answer common customer requests." He clarified that they need "reasons for non-covered parts related to the cost estimate, as part of the claim decision."

**This is TrueAim's highest-value feature right now.** It's the thing that makes adjusters say "I can't do my job without this." A payout calculator doesn't have that effect. A coverage explanation does, because it eliminates the most tedious part of the adjuster's daily work: explaining denials.

---

## What Exists Today

The coverage analyzer (`src/context_builder/coverage/analyzer.py`) already computes detailed per-item coverage decisions. Each line item gets:

| Field | Already exists | Example |
|---|---|---|
| `coverage_status` | Yes | `NOT_COVERED` |
| `match_reasoning` | Yes | `"Part 10503023 is 'Motoröl' in category 'consumables' which is not covered by this policy"` |
| `match_method` | Yes | `RULE`, `KEYWORD`, `PART_NUMBER`, `LLM` |
| `match_confidence` | Yes | `0.95` |
| `coverage_category` | Yes | `"consumables"`, `"engine"` |
| `matched_component` | Yes | `"motor_oil"` |

**Schema**: `src/context_builder/coverage/schemas.py` — `LineItemCoverage` model (line 32)

The reasoning data is already there. What's missing:

| Missing | Impact |
|---|---|
| Policy clause reference (e.g., "Section 4.2 Exclusions") | Adjuster can't point customer to the contract |
| Customer-facing language (current reasoning is technical/internal) | Can't copy-paste into customer emails |
| Grouping by exclusion reason (e.g., all consumables together) | Adjuster sees a wall of individual items, not categories |
| Link to the guarantee type's coverage scope | Can't explain "your BASIC policy covers X but not Y" |

---

## What "Done" Looks Like

### Output: A new section in the assessment output

For each claim, alongside the existing `coverage_analysis.json` and `assessment.json`, produce a structured **coverage explanation** that an adjuster can use directly.

### Concrete example of desired output

For a claim with 3 non-covered items on a BASIC guarantee:

```json
{
  "non_covered_explanations": [
    {
      "items": ["Motoröl 5W-40 (2.5L)", "Ölfilter"],
      "category": "consumables",
      "total_amount": 85.50,
      "explanation": "Oils, filters, and lubricants are classified as consumable maintenance items. These are excluded from all guarantee types under the general terms and conditions (Section 4.2 — Exclusions).",
      "policy_reference": "General Terms, Section 4.2",
      "match_confidence": 1.0
    },
    {
      "items": ["Turbolader-Kompressor"],
      "category": "turbo_components",
      "total_amount": 2340.00,
      "explanation": "Turbo and turbocharger components are only covered when the Turbo option is included in the guarantee. Your policy (BASIC) does not include the Turbo option.",
      "policy_reference": "Policy schedule, Option Turbo: Non couvert",
      "match_confidence": 0.95
    },
    {
      "items": ["Diagnose / Fehlerspeicher auslesen"],
      "category": "diagnostic_labor",
      "total_amount": 120.00,
      "explanation": "Standalone diagnostic work, error code reading, and system testing are not covered as they are classified as investigative labor rather than repair labor.",
      "policy_reference": "General Terms, Section 4.2",
      "match_confidence": 1.0
    }
  ],
  "summary": "3 items (CHF 2,545.50) are not covered. Consumable items and diagnostic labor are excluded under general terms. Turbo components require the Turbo option which is not included in your BASIC guarantee."
}
```

### What makes this useful for the adjuster

1. **Grouped by reason**, not listed per line item — "all consumables" is one explanation, not five
2. **References the policy** — "Section 4.2", "Option Turbo: Non couvert"
3. **Written in language an adjuster can use** — not internal system jargon
4. **Includes the financial impact** — the adjuster sees what amount is excluded per category
5. **Includes confidence** — if match_confidence < 0.8, the adjuster knows to double-check

---

## What the Developer Needs to Know

### Data sources available

1. **Coverage analysis results** — per-item `coverage_status`, `match_reasoning`, `match_method`, `coverage_category`, `matched_component` (already computed by the analyzer)

2. **Policy data** — extracted from the guarantee document:
   - Guarantee type (BASIC, COMFORT, etc.)
   - Options included/excluded (4x4, Turbo, Hybrid — as booleans)
   - Covered component systems (e.g., "Moteur: Couvert", "Option turbo: Non couvert")
   - Coverage scale (mileage tiers)
   - Max coverage amount

3. **Exclusion rules** — hardcoded in the rule engine and coverage config:
   - Consumables list (oil, filters, brake fluid, coolant, etc.)
   - Fee exclusions (disposal, environmental, rental car, cleaning)
   - Diagnostic labor exclusions
   - AdBlue/urea exclusion
   - These rules have implicit policy clause references (Section 4.2 of general terms)

4. **NSA API** (future) — `GET /v1/guarantees/{number}` provides guarantee type and option booleans. `GET /v1/guarantee-types` provides product definitions.

### Architecture constraints

- This is **customer-specific output** — the explanation templates, policy references, and language belong in `workspaces/nsa/config/`, not in `src/context_builder/`
- The core product should provide a **framework for generating explanations** (grouping, templating, policy reference lookup) — the actual explanation text and clause mappings are customer config
- Follow the existing pattern: core code in `src/`, customer config in workspace

### Exclusion categories to policy references (known mappings)

These are the mappings we already know. The adjuster session will validate and extend them:

| Exclusion category | Policy reference | Applies to |
|---|---|---|
| Consumables (oil, filters, fluids) | General Terms, Section 4.2 (Exclusions) | All guarantee types |
| Fees (disposal, environmental, rental) | General Terms, Section 4.2 (Exclusions) | All guarantee types |
| Diagnostic labor (standalone) | General Terms, Section 4.2 (Exclusions) | All guarantee types |
| AdBlue/urea system | General Terms, Section 4.2 (Exclusions) | All guarantee types |
| Turbo components (without Turbo option) | Policy schedule — "Option Turbo" | When optionTurbo = false |
| 4x4 components (without 4x4 option) | Policy schedule — "Option 4x4" | When option4x4 = false |
| Hybrid components (without Hybrid option) | Policy schedule — "Option Hybride" | When optionHybrid = false |
| Component not in guarantee type scope | Policy schedule — covered systems list | Varies by BASIC/COMFORT/etc. |

### What's NOT clear yet (adjuster session will answer)

- Exact wording adjusters use when explaining denials to customers
- Whether explanations should be in French, German, or both (claims are multilingual)
- Whether the explanation goes in the decision letter, an email, or both
- Whether there are standard templates NSA already uses
- Additional exclusion categories we haven't mapped

---

## Suggested Approach

1. **Add a `policy_reference` field to exclusion rules** — when the rule engine or keyword matcher marks something NOT_COVERED, tag it with the applicable policy section. This is a config addition, not a code change.

2. **Add a grouping/explanation generation step** after coverage analysis — takes the per-item results, groups by exclusion reason, generates human-readable explanations using templates.

3. **Store explanation templates in customer config** — e.g., `workspaces/nsa/config/coverage/explanation_templates.yaml` with templates per exclusion category and language.

4. **Add the explanation to the assessment output** — new field in `assessment.json` or as a sibling `coverage_explanations.json`.

5. **Keep it deterministic where possible** — for rule-based exclusions (consumables, fees, diagnostics), the explanation is a template fill. Only use LLM for edge cases where the exclusion reason isn't captured by rules.

---

## Acceptance Criteria

- [ ] Every NOT_COVERED item in a claim has an explanation that references the policy
- [ ] Items are grouped by exclusion reason (not listed individually)
- [ ] Explanation text is suitable for adjuster use (not internal jargon)
- [ ] Financial impact per exclusion group is shown
- [ ] Explanation templates are in customer config (not hardcoded in src/)
- [ ] Works for both French and German claims
- [ ] Confidence score is surfaced so adjusters can flag uncertain explanations
- [ ] Existing coverage analysis accuracy is not regressed (run eval after implementation)

---

## What This Is NOT

- This is NOT a customer-facing email generator (Stefano wants adjuster tooling, not automation of customer communication)
- This is NOT a payout calculator fix (amount_mismatch is a separate workstream)
- This is NOT an LLM chatbot feature (it's structured, deterministic explanations with LLM fallback)
- This does NOT require the NSA API integration (works with current document-based pipeline)

---

## References

- Meeting notes (Jan 27): Stefano's request at timestamps 00:53:28, 00:56:16, 00:58:27
- Coverage analyzer: `src/context_builder/coverage/analyzer.py`
- Coverage schemas: `src/context_builder/coverage/schemas.py`
- Rule engine: `src/context_builder/coverage/rule_engine.py`
- Assessment schema: `src/context_builder/schemas/assessment_response.py`
- Coverage config: `workspaces/nsa/config/coverage/nsa_coverage_config.yaml`
- Strategy doc: `docs/NSA-strategy-and-next-steps.md`
