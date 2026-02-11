# Eval #48 Error Analysis

**Eval ID**: `eval_20260211_174507`
**Claim Run**: `clm_20260211_162539_654ce3`
**Date**: 2026-02-11

## Results

| Dataset | Accuracy | Approved | Denied | FRR | FAR |
|---------|----------|----------|--------|-----|-----|
| eval-v1 (50 claims) | **92.0%** (46/50) | 21/24 | 24/25 | 12.5% | 4.0% |
| seed-v1 (4 claims) | **100%** (4/4) | 2/2 | 2/2 | 0% | 0% |
| **Combined (54)** | **92.6%** (50/54) | 23/26 | 26/27 | 11.5% | 3.7% |

Amount mismatches: 13 eval + 1 seed = 14 total.

## Comparison vs Previous Run (eval #47: 98%)

| Metric | Eval #47 | Eval #48 | Delta |
|--------|----------|----------|-------|
| Decision accuracy | 98% (49/50) | 92% (46/50) | **-6%** |
| False reject rate | 4% | 12.5% | +8.5% |
| False approve rate | 0% | 4% | +4% |
| Amount mismatches | 13 | 13 | same |

Regression of 3 additional errors (1 false_reject:component_coverage reappeared, 1 false_reject:service_compliance reappeared, 1 false_approve reappeared).

---

## Error 1: Claim 64354 -- false_reject:service_compliance

**System: REJECT | Ground Truth: APPROVED (CHF 939.98)**

### What happened

The system correctly identified service compliance as a **soft** failure (29.9 months since last service, 2.49x above interval). The assessment explicitly states: "the only failure was a soft check (service compliance), which does not block approval."

Despite this, the system rejected the claim because the **coverage analysis drastically undercounted** the covered amount. Only CHF 63.83 labor was marked as covered, which falls below the CHF 150 deductible, producing a zero-payout automatic REJECT.

### Root cause

Key parts were marked `component_not_in_list`:
- **BETAETIGUNG** (gear selector actuator): CHF 372.80 -- not in policy parts list
- **ARRETIERUNG** (locking mechanism): CHF 18.50 -- not in policy parts list

The ground truth approved CHF 1,008.33 (parts + labor) after excluding only antenna and software update.

### Classification

The eval script categorized this as "service_compliance" but the real failure is **coverage under-counting**. The service compliance check worked correctly (soft fail, non-blocking).

---

## Error 2: Claim 64358 -- false_reject:component_coverage

**System: REJECT | Ground Truth: APPROVED (CHF 439.27)**

### What happened

Primary line item "OLVERLUST GETRIEBE LOKALISIEREN" (transmission oil loss diagnosis, CHF 230) was mapped to `transmission` via part number 99999700, then rejected because `transmission` is not in the `mechanical_transmission` exhaustive parts list (which contains only 5 specific parts: Ritzel, Schaltgabeln, Schiebemuffe, Antriebswelle, Hauptwelle).

All CHF 1,221.79 was marked not covered. Payout: CHF 0.

### Root cause

The exhaustive parts list check is **too strict for diagnostic/localization labor**. The policy covers transmission work at 60% after 80k km, but the system rejects diagnostic labor that isn't a named replacement part. "Localize oil loss" is legitimate covered work on a covered system.

Secondary issue: multiple other items (transmission seal, angle gearbox labor, Haldex oil) were also wrongly excluded.

---

## Error 3: Claim 65040 -- false_reject:component_coverage

**System: REJECT | Ground Truth: APPROVED (CHF 1,522.03)**

### What happened

The trunk control unit (CALCULATEUR DE COFFRE, CHF 1,164.80) was marked `component_not_in_list` under `electrical_system`. Additionally, diagnostic labor ("RECHERCHE DE PANNE SUR SYSTEME DE COFFRE") was excluded by the blanket regex `RECHERCHE.*PANNE`.

All CHF 2,147.23 was marked not covered. Payout: CHF 0.

### Root cause

Two issues:
1. **Trunk control unit (calculateur) missing from electrical system parts list.** The ground truth covers it; the system doesn't recognize it.
2. **`RECHERCHE.*PANNE` non-covered labor rule is too broad.** It blanket-excludes all diagnostic labor, even when diagnosing a covered component. The ground truth notes: "Fault diagnosis and recycling are not covered" -- but parts + coding/adaptation labor ARE covered (CHF 1,522.03 after deductible).

---

## Error 4: Claim 65113 -- false_approve

**System: APPROVE (CHF 20.04) | Ground Truth: DENIED**

### What happened

The claim is fundamentally about a **Hochdruckpumpe** (high-pressure pump, CHF 1,894) and injectors (CHF 3,108) which total CHF 5,002. These are correctly excluded from coverage. However, the system found ONE tiny covered item -- a Profildichtung (gasket, CHF 42.24) -- and approved the claim based on that.

After deductible, the payout was only CHF 20.04 on an CHF 11,901 claim.

### Ground truth denial reason

> "Die Garantie umfasst ausschliesslich die Teile, die im Vertrag aufgelistet sind. Die Hochdruckpumpe und die daraus resultierenden Folgeschaeden sind nicht von der Garantie Abgedeckt."

(The high-pressure pump and resulting consequential damage are not covered.)

### Root cause

The system's approval logic only checks "at least one covered item exists," not whether coverage is **material**. When 96.7% of the claim amount is excluded and the covered amount is CHF 42.24 (0.35% of total), the system should deny or escalate -- not approve for a trivial CHF 20.04 payout.

Additionally, the LLM labor relevance check incorrectly promoted CHF 140.40 of high-pressure rail labor as related to the gasket repair, inflating the covered total.

---

## Pattern Summary

| # | Claim | Error Type | Root Cause | Fix Area |
|---|-------|------------|------------|----------|
| 1 | 64354 | false_reject (service_compliance) | Actuator/locking parts missing from parts list | Customer config: parts lists |
| 2 | 64358 | false_reject (component_coverage) | Diagnostic labor rejected by exhaustive parts check | Coverage logic: labor vs parts distinction |
| 3 | 65040 | false_reject (component_coverage) | Trunk ECU missing + overly broad RECHERCHE.*PANNE exclusion | Config (parts list) + labor rule scoping |
| 4 | 65113 | false_approve | No minimum-coverage materiality threshold | Screening logic: add materiality guard |

### Themes

**False rejects (3 claims):** Exhaustive parts lists are too narrow. They work well for named replacement parts but fail for:
- Diagnostic/localization labor on covered systems (64358)
- Control units not explicitly listed (65040)
- Actuators and locking mechanisms in covered categories (64354)

**False approve (1 claim):** Missing **materiality guard** -- the system should deny (or escalate) when covered amount is negligible relative to total claim value. A CHF 20 payout on an CHF 11,900 claim is not a meaningful approval.

### Recommended Fixes

1. **Add materiality check to screening**: If covered_amount / total_claimed < threshold (e.g., 5%), flag as DENY or REFER. Prevents trivial-coverage false approvals.
2. **Expand parts lists** for electrical_system (trunk ECU) and mechanical categories (actuators, locking mechanisms).
3. **Scope the `RECHERCHE.*PANNE` exclusion**: Only exclude diagnostic labor when the diagnosed component is itself not covered. If the component is covered, diagnostic labor should be covered.
4. **Distinguish diagnostic labor from replacement parts** in the exhaustive parts list check. Diagnostic labor on a covered system should not require the labor type to be in the parts list.
