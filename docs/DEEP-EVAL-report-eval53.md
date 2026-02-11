# Deep Eval Report -- Eval #53 (run clm_20260210_210836_bcbde0)

**Date:** 2026-02-11
**Run ID:** `clm_20260210_210836_bcbde0`
**Eval ID:** `eval_20260211_100130`
**Decision accuracy:** 98% (49/50)
**Focus:** Overpayment cases -- items incorrectly identified as covered, resulting in amount mismatch in the policyholder's favor

## Overview

Of 16 amount_mismatch claims, **8 are overpayments** (system paid more than ground truth) totaling **CHF 3,764.72** in excess payouts. The remaining 8 are underpayments.

| Claim | Vehicle | GT | Predicted | Overpayment | % |
|-------|---------|-----|-----------|-------------|---|
| 64792 | Peugeot 3008 | 520.68 | 2,793.84 | +2,273.16 | +437% |
| 64297 | Subaru Impreza | 74.00 | 409.96 | +335.96 | +454% |
| 65150 | Audi A8 | 1,841.25 | 2,245.26 | +404.01 | +22% |
| 65056 | Audi A4 | 3,600.00 | 3,891.60 | +291.60 | +8% |
| 64535 | Range Rover Evoque | 914.20 | 1,189.08 | +274.88 | +30% |
| 64386 | Jeep Grand Cherokee | 2,429.46 | 2,703.84 | +274.38 | +11% |
| 65055 | Ford Fiesta | 910.15 | 1,098.43 | +188.28 | +21% |
| 64978 | Mitsubishi ASX | 24.98 | 37.53 | +12.55 | +50% |

---

## Part 1: Individual Claim Analysis

### Claim 64792 -- Peugeot 3008 (+CHF 2,273.16 / +437%)

**The worst overpayment.** GT approved only CHF 49.65 in parts and CHF 570.78 in labor. System covered CHF 1,460 gross in parts and CHF 5,719 gross in labor.

**Root causes:**
- **Struck-through items invisible to system.** The GT adjuster crossed out most line items on the physical invoice. The system cannot detect struck-through markup on scanned documents, so it treated all extracted items as coverage candidates.
- **Massive parts over-coverage:** System covered ~CHF 1,410 more in gross parts than GT (including HITZESCHILD TURBOLADER, HOHLSCHRAUBE, VERSCHLUSSST ZYLINDERBLOCK, BUNDMUTTER, OELDAMPFENTOELER, and most of the KOLBEN set). GT explicitly denied "DICHTUNG ZYLINDERBLOCKSTOPFEN" at CHF 0.
- **Massive labor over-coverage:** System covered CHF 5,719 in piston replacement labor; GT only approved CHF 571.
- **Deductible on wrong base:** System computed CHF 310.43 vs GT CHF 150.00.

**Financial impact:** +CHF 564 parts over-coverage + CHF 2,059 labor over-coverage - CHF 160 deductible offset = ~CHF 2,273.

---

### Claim 64297 -- Subaru Impreza 1.5R (+CHF 335.96 / +454%)

**Root causes:**
- **Wrong reimbursement rate (100% instead of 40%).** The vehicle is 18.5 years old. GT notes state "Des 8 ans 40%". The system recognized the age threshold (`age_threshold_years: 8`) but applied 100% coverage instead of 40%. This is a **bug in the coverage percent lookup** -- the system failed to apply the km/age-based degradation.
- **Parts over-coverage:** System covered CHF 358 vs GT CHF 143.20 (adjuster reduced the throttle body amount).
- **Labor over-coverage:** System covered CHF 160 vs GT CHF 64 (adjuster reduced labor).

**Financial impact:** The wrong rate accounts for ~93% of the overpayment (+CHF 311). Parts/labor over-coverage adds the remaining ~CHF 25.

---

### Claim 65150 -- Audi A8 60 TFSI e (+CHF 404.01 / +22%)

**Root causes:**
- **`primary_repair_boost` too aggressive.** The LLM correctly identified "GFS/GEFUEHRTE FUNKTION #2" (CHF 196.80) as standalone diagnostic labor that should NOT be covered. The system's automatic promotion rule overrode this correct assessment.
- **Labor over-coverage:** System covered CHF 861 in labor vs GT CHF 442.80. The excess of CHF 418.20 corresponds exactly to GFS/GEFUEHRTE FUNKTION #1 (CHF 295.20) + RUECKSPIEGEL AUS- U.EINGEBAUT (CHF 123.00) -- both were struck through by the GT adjuster.
- **Deductible difference:** System CHF 249.47 vs GT CHF 204.60 (partially offsets overpayment by CHF 44.87).
- Parts coverage was nearly correct (CHF 1,446.80 vs GT CHF 1,449.75).

---

### Claim 65056 -- Audi A4 2.0 TDI (+CHF 291.60 / +8%)

**Root cause: Deductible/cap interaction bug.**
- Both system and GT hit the max coverage cap of CHF 4,000. Individual coverage decisions are not the direct cause.
- GT correctly computes: cap(4,000) - 10%(4,000) = CHF 3,600.
- System produces CHF 3,891.60 because the deductible appears to be computed on a different base than the capped amount. The system shows deductible CHF 432.40 but after_deductible CHF 3,891.60, which implies a pre-deductible amount of CHF 4,324 (not the capped CHF 4,000).
- **Bug:** The deductible should be computed on the capped amount, not on a pre-cap or intermediate value.

---

### Claim 64535 -- Range Rover Evoque (+CHF 274.88 / +30%)

**A complex case with offsetting errors:**
- **False positive parts coverage:** System covered Tube cylindre 1-4 (CHF 276.24 total) via part number lookup (LR012751-54 mapped to "cylinder_liner"). GT adjuster struck these through -- they should NOT have been covered.
- **False negative parts coverage:** System missed "Couvercle" (LR022304, CHF 664.20 -- the oil separator cover). The LLM couldn't identify "Couvercle" (Cover) as a covered component because the description was too vague. GT approved this part.
- **Diagnostic labor incorrectly covered:** System covered CHF 562.50 in diagnostic labor via `labor_follows_parts` promotion. GT only approved CHF 400 (replacement labor only, not diagnostic).
- **Missing VAT deduction:** GT notes state CHF 86.20 in VAT is not reimbursable. System did not apply this (`vat_adjusted: false`).

**Net:** +276 false positive parts + 563 false positive labor + 86 VAT - 664 missed part = +CHF 275 overpayment.

---

### Claim 64386 -- Jeep Grand Cherokee CRD (+CHF 274.38 / +11%)

**Root cause: Labor for excluded part incorrectly covered.**
- System correctly excluded "DISPOSITIF DE COM-" (CHF 796.25 part) as not covered.
- But then the LLM matched labor "REMPLACEMENT MODULE DE COMMANDE TRANS." (CHF 282.00) to `automatic_transmission` category, covering it independently.
- This labor is for replacing the DISPOSITIF DE COM- part that was already excluded. The system failed to link the labor back to the excluded part.
- Deductible difference (CHF 300.43 vs GT CHF 269.95) partially offsets.

---

### Claim 65055 -- Ford Fiesta (+CHF 188.28 / +21%)

**Root causes:**
- **Timing belt labor promoted despite excluded part.** The timing belt part (code 213040, CHF 342.02) was correctly excluded. But the labor with the same code (CHF 1,120.00) was promoted via `labor_follows_parts` using "repair_context_keyword" matching "chaine de distribution" to engine. At 40% rate, this adds CHF 448 incorrectly.
- **Deductible difference:** System CHF 150 vs GT CHF 101.15 (partially offsets by CHF 48.85).

---

### Claim 64978 -- Mitsubishi ASX (+CHF 12.55 / +50%)

**Root cause: struck-through item (same as claims 64792, 65150, 64535).**
- **"Effacement des codes" labor (CHF 29.00) incorrectly covered.** GT excludes this as a struck-through item. At 40% rate = CHF 11.60 excess, plus VAT on that excess (CHF 0.94) = CHF 12.54 total overpayment.
- ~~**Payout arithmetic bug.**~~ **CORRECTION:** The original report claimed `173.48 - 150.00 = 23.48, not 37.53` and called this a CHF 14.05 arithmetic error. This was a misread of the formula. The payout pipeline adds VAT (8.1%) before the deductible: `subtotal_with_vat = 173.48 + 14.05 = 187.53`, then `187.53 - 150.00 = 37.53`. The CHF 14.05 "error" is the VAT amount, correctly applied. The entire overpayment is explained by the struck-through "Effacement des codes" item.

---

## Part 2: Systemic Root Causes (ranked by financial impact)

### 1. Struck-through items invisible to system (~CHF 2,300+)

**Claims:** 64792, 65150, 64535, 64978 (64978 was originally misattributed to a payout arithmetic bug -- see correction)

The system cannot detect when a human adjuster crosses out line items on scanned invoices. All extracted items are treated as valid coverage candidates. This is the single largest source of overpayment.

**Impact:** This is the dominant cause of the CHF 2,273 overpayment on claim 64792 alone.

### 2. `labor_follows_parts` / `primary_repair_boost` too aggressive (~CHF 1,700+)

**Claims:** 64386, 65055, 65150, 64535

The automatic promotion rules override correct LLM exclusion decisions:
- **64386:** Labor for a part the system itself excluded (DISPOSITIF DE COM-) was promoted because the LLM matched it to a generic category
- **65055:** Timing belt labor promoted despite the timing belt part being explicitly excluded
- **65150:** LLM correctly identified diagnostic labor as non-covered, but `primary_repair_boost` overrode the decision
- **64535:** Diagnostic labor promoted via `labor_follows_parts` when GT only approved replacement labor

**Fix needed:** The promotion heuristics must check whether the *specific part* the labor relates to is covered, not just whether *any part in the same category* is covered.

### 3. Wrong reimbursement rate / coverage percent lookup (~CHF 310)

**Claims:** 64297

The system applied 100% coverage instead of the age-based 40% rate, despite recognizing the age threshold. The km/age degradation schedule from the policy was not applied.

### 4. Deductible/cap interaction bug (CHF 291.60)

**Claims:** 65056

When the max coverage cap is applied, the deductible should be computed on the capped amount. The system computes it on a different (larger) base, resulting in an inconsistent payout.

### 5. Missing VAT deduction logic (CHF 86.20)

**Claims:** 64535

The system does not detect or apply VAT non-reimbursability rules noted in GT coverage notes. `vat_adjusted` is always false.

### ~~6. Payout arithmetic bug (CHF 14.05)~~ RETRACTED

**Claims:** 64978

~~`after_coverage - deductible != after_deductible`. The subtraction is incorrect.~~

**Correction:** No arithmetic bug exists. The formula adds VAT (8.1%) between `capped_amount` and the deductible step: `subtotal_with_vat (187.53) - deductible (150.00) = 37.53`. The CHF 14.05 difference is the VAT amount, not a calculation error. The overpayment on this claim is entirely due to the struck-through "Effacement des codes" item (root cause #1).

---

## Part 3: Priority Fixes

| Priority | Issue | Est. Impact | Claims Affected |
|----------|-------|-------------|-----------------|
| **P0** | `labor_follows_parts` / `primary_repair_boost` promotes labor for excluded parts | ~CHF 1,700 overpayment | 64386, 65055, 65150, 64535 |
| **P0** | Deductible/cap interaction -- compute deductible on capped amount | CHF 292 overpayment | 65056 |
| **P1** | Coverage percent lookup -- apply age/km degradation schedule | CHF 310 overpayment | 64297 |
| ~~P1~~ | ~~Payout arithmetic~~ RETRACTED -- no bug, CHF 14.05 is the VAT step (see correction) | ~~CHF 14~~ | ~~64978~~ |
| **P2** | VAT deduction handling from coverage notes | CHF 86 overpayment | 64535 |
| **P2** | Struck-through item detection (hard problem -- requires OCR/visual analysis of scanned invoices) | CHF 2,300+ overpayment | 64792, 65150, 64535 |

**P0 items are code bugs that can be fixed immediately. P1 items require config/logic changes. P2 items require new capabilities.**
