# Holdout Evaluation Report — NSA Motor v2

**Date:** 2026-02-03
**Dataset:** nsa-motor-holdout (30 claims, 15 approved / 15 denied)
**Run ID:** `clm_20260203_104511_52f826`
**Workspace:** nsa-holdout

---

## 1. Summary

| Metric | Value |
|--------|-------|
| **Decision Accuracy** | **76.7% (23/30)** |
| Approved correct | 11 / 15 |
| Denied correct | 12 / 15 |
| False Reject Rate | 26.7% |
| False Approve Rate | 20.0% |
| Amount accuracy (within 5%) | 27.3% (3/11 approved-correct claims) |

### Error Breakdown

| Category | Count | Claims |
|----------|-------|--------|
| Amount mismatch (correct decision, wrong payout) | 8 | 64687, 64873, 64942, 65010, 65044, 65316, 65345, 65356 |
| False approve (should deny, system approved) | 2 | 64827, 64943 |
| False reject — component coverage | 2 | 64868, 65352 |
| False reject — policy validity | 1 | 64887 |
| Refer should approve (VIN issue) | 1 | 64846 |
| Refer should deny (data gap) | 1 | 64877 |

---

## 2. Decision Errors — Detailed Analysis

### 2.1 False Approvals

---

#### Claim 64827 — Land Rover RR Sport 4.4

| | Ground Truth | System |
|---|---|---|
| **Decision** | DENIED | APPROVE |
| **Reason** | Hoses are explicitly excluded from the contract | All checks passed; primary repair "Bolzen" covered under engine |
| **Payout** | CHF 0 | CHF 187.64 |

**Evidence trail:**

The system **correctly extracted** the policy's excluded components from the guarantee document. The extracted `excluded_components` include:

```
comfort_options:
  - Dichtungen
  - Verschlusszapfen
  - Schläuche              <-- hoses explicitly excluded
  - Versorgungsleitungen
  - Metall- oder Gummileitungen
  - elektrische Leitungen
  - Simmerring
  - Isolationsgummi
```

The coverage analyzer also **correctly classified** the hose as NOT_COVERED:

| Line Item | Code | Price | Coverage Status | Reasoning |
|-----------|------|-------|-----------------|-----------|
| Schlauch (hose) | LR066536 | CHF 79.00 | NOT_COVERED | "Hoses are explicitly listed as excluded under comfort_options" |
| Bolzen (bolt) | LR033655 | CHF 3.70 | COVERED | "Bolzen listed as covered under engine category" |

Despite the hose being correctly flagged as excluded, the screening decision was APPROVE. The reason is a **design gap in Check 5 (component coverage)**:

- The primary repair determination selects the highest-value **covered** item: Bolzen at CHF 3.70
- Check 5 evaluates only whether the primary repair is covered: Bolzen is covered → PASS
- The excluded hose at CHF 79.00 (the actual main repair) is silently absorbed into the payout reduction — it contributes CHF 0 to the covered total, but does not trigger a rejection

**Root cause — screening logic gap:** Check 5 only validates the primary covered component. It does not check whether the actual highest-value repair item is an explicitly excluded component. When an excluded item is the main repair and a minor covered part (CHF 3.70 bolt) anchors the approval, the system incorrectly approves.

**The fix:** If the highest-value line item in the claim appears in `excluded_components`, Check 5 should FAIL or REFER — regardless of whether a minor covered part exists. The excluded-components data is already extracted and available; it just isn't used in the decision logic.

---

#### Claim 64943 — Mini Mini (JCW R57)

| | Ground Truth | System |
|---|---|---|
| **Decision** | DENIED | APPROVE |
| **Reason** | Malfunction caused by a non-insured part — no liability | All checks passed; turbo covered under turbo_supercharger |
| **Payout** | CHF 0 | CHF 1,929.10 |

**Evidence trail:**

The cost estimate contains 30 line items totalling CHF 14,160.47. The system's coverage analysis:

| Item Category | Count | Total CHF | Coverage Status |
|---------------|-------|-----------|-----------------|
| Abgasturbolader (turbocharger) | 1 | 2,597.59 | COVERED (part number match, 95% confidence) |
| Anbausatz Turbolader (turbo kit) | 1 | 400.89 | COVERED (LLM, 85% confidence) |
| Fasteners/bolts (engine hardware) | 14 | 305.24 | COVERED (ancillary to covered repair) |
| Triebwerk (complete engine assembly) | 1 | 7,982.19 | NOT_COVERED (complete assembly, not specific part) |
| Zweimassenschwungrad (dual-mass flywheel) | 1 | 1,573.08 | NOT_COVERED (not in covered list) |
| Kupplungsteile (clutch parts) | 1 | 620.75 | NOT_COVERED (wear-and-tear item) |
| Dichtungen/gaskets | 6 | 516.08 | NOT_COVERED (explicitly excluded) |
| Other uncovered parts | 5 | 163.64 | NOT_COVERED |

The turbocharger IS a covered component under the policy. The system correctly identified it and approved at 60% reimbursement rate (age-adjusted from 70% due to vehicle being 13.78 years old). All screening checks passed.

However, the ground truth denial states: **"No liability exists when the malfunction is caused by a non-insured part."** This is a causal exclusion — the turbo failure was triggered by a failure in a non-covered component (likely the engine assembly or clutch). The cost estimate's scope (full engine replacement + turbo + clutch + flywheel) strongly suggests cascading damage from a root failure in the engine or clutch.

**Root cause — missing causal-chain analysis:** The system evaluates each component independently: "Is the turbo covered? Yes. Is the clutch covered? No." But the policy clause requires evaluating causation: "Was the turbo failure caused by a non-covered part?" The system has no mechanism for this determination. The invoice itself provides evidence (engine + turbo replaced together implies common failure), but the system does not reason about repair scope patterns.

**Difficulty of fix:** Hard. This requires either (a) an explicit causation flag from the documents (e.g., an expert report stating root cause), or (b) heuristic reasoning about invoice composition (e.g., "when the total non-covered amount exceeds 75% of the invoice and includes the engine assembly, the covered turbo is likely collateral damage"). Option (b) is fragile and error-prone.

---

### 2.2 False Rejections

---

#### Claim 64868 — Mercedes C 43 AMG 4Matic Speedshift TCT 9G

| | Ground Truth | System |
|---|---|---|
| **Decision** | APPROVED (CHF 793.70) | REJECT (auto-reject) |
| **Failed Check** | — | Check 5: component coverage hard fail |
| **Payout** | CHF 793.70 | CHF 0.00 |

**Evidence trail:**

The claim involves a panoramic sunroof repair. The cost estimate contains 12 line items:

| Line Item | Code | Type | Price | Coverage | Reasoning |
|-----------|------|------|-------|----------|-----------|
| BORDENTZSPANNUNG (voltage maintenance) | 54-0650-00 | labor | 23.50 | NOT_COVERED | Diagnostic labor — rule-excluded (pattern: DIAGNOSE) |
| FENSTER EINSTELLEN (window adjust) | 00-0000-99 | labor | 70.50 | NOT_COVERED | Calibration labor — rule-excluded (pattern: EINSTELLEN) |
| KURZTEST (short test) | 54-1011-00 | labor | 47.00 | NOT_COVERED | Diagnostic labor |
| SCHIEBEDACH PRUEFEN (sunroof check) | 77-0640-00 | labor | 70.50 | NOT_COVERED | Diagnostic labor |
| FUEHRUNGSSCHIENEN ERNEUERN (guide rails) | 77-7002-00 | labor | 658.00 | NOT_COVERED | No covered component match |
| ANTRIEBSKABEL SONNENROLLO (sunshade cable) | 77-7060-00 | labor | 399.50 | NOT_COVERED | Sunshade not in covered list |
| EINKLEMMSCHUTZ (anti-pinch learning) | 77-1248-00 | labor | 23.50 | NOT_COVERED | Calibration procedure |
| TUERVERKLEIDUNG (door panel) | 72-6405-00 | labor | 94.00 | NOT_COVERED | Door panel not covered |
| **MOTOR SCHIEBEDACHANTRIEB (sunroof motor)** | **77-6995-00** | **labor** | **235.00** | **NOT_COVERED** | **Matched to Schiebedachmotor (covered!) but DEMOTED: "no_anchor" — no other covered parts** |
| FUEHRUNGSROHR (guide tube) | A205 780 97 00 | parts | 234.00 | NOT_COVERED | Category "body" — not covered |
| **DACHMECHANIK (roof mechanism)** | **A205 780 01 75** | **parts** | **413.00** | **NOT_COVERED** | **Category "body" — not covered. Selected as PRIMARY REPAIR (highest-value part)** |
| **GETRIEBEMOTOR (gearbox motor)** | **A205 906 41 04** | **parts** | **450.00** | **NOT_COVERED** | **LLM classified at 0.70 confidence — "does not match specific component"** |

Three critical failures occurred:

1. **Part A205 906 41 04 (GETRIEBEMOTOR) was not matched by part-number lookup.** This part IS in the assumptions database mapped to `electrical_system/roof_motor`. The part-number matcher should have identified it as a covered electrical system component. Instead, it fell through to the LLM, which classified it as not covered with low confidence (0.70). This is the highest-value item at CHF 450 — if matched correctly, it would have been the primary repair and the claim would have been approved.

2. **The sunroof motor labor (77-6995-00) was correctly identified** as matching the covered `Schiebedachmotor` component in the electrical_system category. However, it was then **demoted** by the `_demote_labor_without_covered_parts` logic because no parts were covered. The demotion is logically correct given that the parts matching failed — but the parts matching should not have failed.

3. **DACHMECHANIK was selected as primary repair** (highest-value part at CHF 413) and classified under "body" (not covered). This triggered a hard fail on Check 5 and auto-rejection.

**The correct outcome:** Part A205 906 41 04 should match to `electrical_system/roof_motor` via the parts database. This makes it the primary repair (CHF 450 > CHF 413 DACHMECHANIK). With a covered primary repair in electrical_system, the sunroof motor labor (CHF 235) would be promoted instead of demoted. The guide rails labor (CHF 658) and other related labor would also be candidates for promotion.

**Root cause — part-number matching failure:** The part `A205 906 41 04` exists in `assumptions.json` under `part_system_mapping.by_part_number` mapped to `electrical_system/roof_motor`, but the coverage analyzer's part-number lookup did not match it. This could be a normalization issue (spacing, dashes) or a lookup-ordering issue where the item was consumed by an earlier matching stage. The entire cascade of failures (labor demotion, wrong primary repair, hard fail) stems from this single part-number miss.

---

#### Claim 65352 — BMW X3 xDrive 48V 20d M Sport Edition Steptronic

| | Ground Truth | System |
|---|---|---|
| **Decision** | APPROVED (CHF 180.00) | REJECT (auto-reject) |
| **Failed Check** | — | Check 5: component coverage hard fail |
| **Payout** | CHF 180.00 | CHF 0.00 |

**Evidence trail:**

The claim contains 3 line items:

| Line Item | Code | Type | Price | Coverage | Match Method | Reasoning |
|-----------|------|------|-------|----------|-------------|-----------|
| Partikelsensor | 0281008468 | parts | 211.00 | NOT_COVERED | part_number (0.95) | Part identified as "Particulate matter sensor for DPF monitoring (Bosch)". **Component NOT in policy's exhaust parts list** |
| Arbeit Partikelsensor prüfen und ersetzen | — | labor | 119.00 | NOT_COVERED | LLM (0.90) | Labor for sensor replacement — no covered part to anchor |
| FA Fehler auslesen/löschen | — | labor | 25.00 | NOT_COVERED | LLM (0.80) | Diagnostic labor (fault code read/clear) — demoted, no anchor |

The policy's exhaust system category covers only **2 components**:
- Katalysator (catalytic converter)
- Lambda-Sonde (oxygen sensor)

The system correctly identified that the Partikelsensor (particulate/DPF sensor) is NOT in this list. The part-number lookup confirmed the match to a Bosch DPF sensor (0281008468) and the system metadata explicitly states: *"Component 'particle_filter_sensor' not found in policy's exhaust parts list (2 parts)."*

**However**, the ground truth shows NSA approved this claim at CHF 180.00 (CHF 330 total - CHF 150 deductible). This means NSA considered the Partikelsensor a covered sub-component of the exhaust system despite it not being explicitly listed.

**Root cause — policy interpretation gap:** The system applies strict matching: if a component is not in the policy's explicit list for its category, it is not covered. NSA's adjuster applied a more lenient interpretation: the DPF sensor is a functional part of the exhaust system, and the exhaust category is covered, so the sensor is covered by extension. This matches the "tiered matching" principle in the LLM coverage prompt (sub-component of a covered category → COVERED at medium confidence), but the **deterministic screening bypasses the LLM** and hard-fails with 0.95 confidence before the LLM tier can apply.

**The fix:** Either (a) add `Partikelsensor`/`DPF-Sensor` to the exhaust covered components in the policy configuration, or (b) lower the confidence of the deterministic "not in explicit list" verdict below the hard-fail threshold so the LLM's tiered matching can evaluate sub-component status.

---

#### Claim 64887 — Land Rover Discovery 3.0 Si6 HSE Luxury

| | Ground Truth | System |
|---|---|---|
| **Decision** | APPROVED (CHF 1,906.02) | REJECT (auto-reject) |
| **Failed Check** | — | Check 1: policy validity hard fail |
| **Payout** | CHF 1,906.02 | CHF 0.00 |

**Evidence trail:**

The policy dates extracted from the guarantee document:

| Field | Value |
|-------|-------|
| Policy number | 575385 |
| Guarantee start | 2024-09-09 |
| Guarantee end | **2025-09-08** |
| Claim date | **2025-11-19** |
| Days after expiry | **71 days** |

Check 1 (policy_validity) correctly determined that the claim date falls 71 days after the policy expiration. This is a hard fail, triggering auto-rejection.

If the claim were within the policy period, the coverage analysis shows a valid payout:

| Category | Details |
|----------|---------|
| Primary repair | Längslenker vorne links (front longitudinal control arm) — suspension, COVERED |
| Items covered | 10 (suspension labor + parts at 100% rate) |
| Items not covered | 8 (brake discs/pads, hood insulation, storage compartment) |
| Covered subtotal | CHF 3,077.40 |
| Deductible (10%) | CHF 332.67 |
| Payable after deductible | CHF 2,994.00 |

The ground truth shows NSA approved this claim at CHF 1,906.02, implying the policy was renewed beyond the extracted end date (2025-09-08). The renewal document is not present in the claim file.

**Root cause — missing document:** The system correctly applies the policy validity rule based on available documents. The guarantee document shows expiry on 2025-09-08, and the claim on 2025-11-19 is clearly outside that period. NSA approved it because they have access to internal records confirming a renewal — the system does not. This is a data completeness issue that cannot be fixed without obtaining the renewal document.

---

### 2.3 Referral Errors

---

#### Claim 64846 — Volkswagen Golf 2.0 TSI GTI Clubsport DSG

| | Ground Truth | System |
|---|---|---|
| **Decision** | APPROVED (CHF 321.05) | REFER_TO_HUMAN |
| **Reason** | — | VIN inconsistency detected between documents |
| **Payout** | CHF 321.05 | CHF 1,318.95 (conditional on verification) |

**Evidence trail:**

The screening detected a VIN conflict:
- VIN 1: `WVWZZZAUZHW146216` — Volkswagen prefix (WVW), found in both the cost estimate and the NSA guarantee document
- VIN 2: `WAUZZZF24KN016070` — **Audi prefix** (WAU), source document unknown

Both primary claim documents (cost estimate and guarantee) consistently report the same VIN (`WVWZZZAUZHW146216`). The second VIN (`WAUZZZF24KN016070`) appears to originate from a third document in the claim file, possibly an unrelated vehicle's paperwork that was inadvertently included.

All other screening checks passed:

| Check | Verdict | Details |
|-------|---------|---------|
| Policy validity | PASS | 2025-12-11 within 2025-11-22 to 2026-11-21 |
| Mileage | PASS | 107,251 km within 126,500 km limit |
| Shop authorization | PASS | AMAG (authorized, exact name match) |
| Service compliance | PASS | Last service 311 days ago, 3 services on record |
| Component coverage | PASS | Primary: CACHE (timing chain cover), engine category, covered |

The coverage analysis identified 13 covered items and 9 not-covered items, with a payout of CHF 1,318.95 at 80% reimbursement rate. Note the payout amount differs significantly from the GT (CHF 321.05 vs CHF 1,318.95), indicating that even if the decision were corrected, the amount would still be wrong — the system covers substantially more items than NSA approved.

**Root cause — spurious VIN from unrelated document:** The VIN extraction pulled a second VIN from a document that does not belong to this vehicle. The system conservatively referred the claim because VIN conflicts are a legitimate fraud indicator. Improving document-level VIN attribution — tagging each extracted VIN with the specific document and page it came from, and weighting VINs from the guarantee/cost estimate higher than those from ancillary documents — would allow the system to distinguish genuine conflicts from extraction noise.

---

#### Claim 64877 — Volkswagen T6 Kombi 2.0 4M

| | Ground Truth | System |
|---|---|---|
| **Decision** | DENIED (non-payment lapse) | REFER_TO_HUMAN |
| **Reason** | Guarantee automatically lapses due to non-payment of premium | Insufficient data for any determination |

**Evidence trail:**

The claim file contains only **one document**: a vehicle registration certificate (Fahrzeugzulassungsurkunde / FZA.pdf). No policy document, no cost estimate, no repair invoice, no expert report.

Extracted data from the single document:

| Field | Value |
|-------|-------|
| Vehicle | VW T6 Kombi 2.0 4M |
| VIN | WV2ZZZ7HZH053452 |
| License plate | LU 198 434 |
| Registration date | 28.10.2016 |
| Registration expiry | 22.08.2025 |

All screening checks were skipped due to missing data:

| Check | Verdict | Reason |
|-------|---------|--------|
| Policy enforcement | SKIPPED | No policy number available |
| Policy validity | SKIPPED | No policy dates |
| Damage date | SKIPPED | No damage date |
| VIN consistency | PASS | Only 1 VIN from 1 document — no conflict possible |
| Mileage | SKIPPED | No odometer reading |
| Shop authorization | SKIPPED | No garage name |
| Service compliance | SKIPPED | No service history |
| Component coverage | SKIPPED | No coverage analysis performed |

With 9 of 10 checks skipped and zero hard fails, the system correctly referred the claim for human review — it had no basis for either approval or denial.

**Root cause — document completeness:** The ground truth denial is based on a premium non-payment lapse, which is internal to NSA's policy management system and not visible in any claim document. Even with a complete set of claim documents, this denial reason would not be detectable by the system. The system's REFER decision is defensible — it acknowledged it lacked sufficient data. The classification as an "error" reflects a limitation of the evaluation framework: REFER is treated as wrong when the expected answer is DENY, even though REFER is a reasonable outcome given the available information.

---

## 3. Amount Mismatches

All 8 claims below were decided correctly (APPROVE = APPROVE) but the calculated payout differs from the ground truth by more than 5%.

| Claim | Vehicle | GT Amount | System Amount | Difference | Diff % |
|-------|---------|-----------|---------------|------------|--------|
| 64687 | BMW 335i xDrive | 2,566.99 | 2,334.96 | -232.03 | -9.0% |
| 64873 | Audi Q5 2.0 TFSI | 3,415.56 | 3,948.38 | +532.82 | +15.6% |
| 64942 | Audi A6 Avant | 502.05 | 438.71 | -63.34 | -12.6% |
| 65010 | BMW X3 xDrive30i | 673.79 | 839.94 | +166.15 | +24.7% |
| 65044 | Seat Leon ST Cupra | 863.15 | 251.27 | -611.88 | -70.9% |
| 65316 | Mercedes GLA 45 AMG | 366.42 | 336.23 | -30.19 | -8.2% |
| 65345 | Peugeot Partner 1.6 HDi | 958.42 | 1,019.59 | +61.17 | +6.4% |
| 65356 | Land Rover Range Rover | 162.05 | 126.90 | -35.15 | -21.7% |

### Payout Calculation Details

| Claim | System Covered | System Rate | System Deductible | GT Deductible | GT Rate |
|-------|---------------|-------------|-------------------|---------------|---------|
| 64687 | 4,447.53 (cap 4,000) | 60% | 259.44 | 285.20 | 60% |
| 64873 | 4,058.36 | 100% | 438.71 | 379.50 | n/a |
| 64942 | 1,361.50 | 40% | 150.00 | 150.00 | 40% |
| 65010 | 1,831.52 | 50% | 150.00 | 150.00 | 50% |
| 65044 | 928.00 | 40% | 150.00 | 95.90 | 40% |
| 65316 | 1,124.50 | 40% | 150.00 | 150.00 | 40% |
| 65345 | 1,545.64 | 70% | 150.00 | 150.00 | 80% |
| 65356 | 640.39 | 40% | 150.00 | 150.00 | 40% |

### Pattern Analysis

**Overpayment (+):** Claims 64873, 65010, 65345 — the system covers more line items than NSA approved. This typically happens when the system includes labor or ancillary items that NSA's adjuster struck from the approved list (e.g., "Les postes supprimés ne sont pas couverts"). The system does not have visibility into which specific line items NSA crossed out.

**Underpayment (-):** Claims 64687, 64942, 65044, 65316, 65356 — the system covers fewer items or applies different rates. Key drivers:

- **65044 (-70.9%):** The largest mismatch. GT approved CHF 863.15 (parts 260 + labor 627.20 at 40%). The system only covered CHF 928 of items, suggesting most labor was not linked to the covered repair. The GT approved significantly more labor than the system recognized.
- **64687 (-9.0%):** Max coverage cap of CHF 4,000 was applied by the system. The deductible calculation differs (259.44 vs 285.20), suggesting the deductible base calculation differs between the system formula and NSA's formula.
- **65345 (+6.4%):** The system applied a 70% reimbursement rate while the GT data suggests 80%. This may be an age-based rate degradation (the policy notes "Dès 8 ans 70%") that the system applied but NSA did not, or vice versa.

**Common root causes for amount mismatches:**
1. **Line-item selection:** NSA adjusters manually strike specific line items from the cost estimate. The system does not have access to the marked-up estimate and must infer coverage from component matching.
2. **Deductible formula:** The deductible base (before or after rate reduction, before or after VAT) may differ between the system and NSA's internal calculation.
3. **Labor association:** Some claims have labor items that the system cannot link to covered parts, resulting in underpayment.

---

## 4. Correctly Processed Claims (23/30)

The system correctly decided 23 of 30 claims. Of the 15 denied claims, 12 were correctly identified with matching denial reasons (component not covered, wear parts excluded, mileage exceedance, etc.). Of the 15 approved claims, 11 were correctly approved, though 8 have payout amounts outside the 5% tolerance.

**Correct denials (12/15):** 64808, 64822, 64843, 64844, 64862, 64867, 64870, 64871, 64880, 64883, 64896, 64945

**Correct approvals (11/15):** 64687, 64823, 64873, 64942, 65010, 65037, 65044, 65316, 65318, 65345, 65356

**Correct approvals within 5% amount tolerance (3/11):** 64823, 65037, 65318

---

## 5. Error Classification Summary

| # | Classification | Claim(s) | Fixable | Priority |
|---|----------------|----------|---------|----------|
| 1 | False approve — excluded component not checked in decision | 64827 | Yes | **HIGH** — design gap in Check 5 |
| 2 | False approve — causal exclusion (root-cause denial) | 64943 | Hard | LOW — requires causal reasoning |
| 3 | False reject — part-number lookup failure (sunroof motor) | 64868 | Yes | **HIGH** — part exists in DB, matching failed |
| 4 | False reject — sub-component not in explicit policy list | 65352 | Yes | MEDIUM — policy interpretation gap |
| 5 | False reject — missing renewal document | 64887 | No | N/A — data completeness issue |
| 6 | Refer should approve — spurious VIN from unrelated document | 64846 | Partially | MEDIUM — VIN attribution improvement |
| 7 | Refer should deny — extraction failure, no data | 64877 | No | N/A — document quality issue |

---

## 6. Recommended Next Steps

**High priority (fixes 2 errors, prevents systematic false approvals):**

1. **Add excluded-component check to Check 5 decision logic.** When the highest-value line item is an explicitly excluded component, Check 5 should FAIL even if a minor covered part exists. The excluded_components data is already extracted — it just needs to be used in the screening verdict. (Fixes 64827; prevents similar false approvals.)

2. **Investigate part-number lookup failure for A205 906 41 04.** This part is in `assumptions.json` mapped to `electrical_system/roof_motor` but was not matched by the part-number stage. Debug the normalization/lookup path. (Fixes 64868; the entire cascade of failures — labor demotion, wrong primary repair, hard fail — stems from this one missed match.)

**Medium priority:**

3. **Add Partikelsensor/DPF-Sensor as a covered exhaust sub-component** in the policy configuration, or lower the deterministic confidence below the hard-fail threshold so the LLM's tiered matching can evaluate sub-component status. (Fixes 65352.)

4. **Improve VIN document attribution** — weight VINs from guarantee/cost estimate documents higher than those from ancillary documents. (Partially fixes 64846.)

5. **Investigate deductible formula alignment** with NSA's actual calculation (deductible base before vs after rate reduction) to improve amount accuracy. (Improves 64687, 65044, and potentially others.)

**Not fixable by the system:**

6. Claim 64887: Missing renewal document — data completeness issue outside system control.
7. Claim 64877: Insufficient documents + internal policy lapse info — not available in claim files.
8. Claim 64943: Causal exclusion reasoning — requires understanding failure chains, beyond current capability.
