# Prompt Fix Plan

**Date:** 2026-01-25
**Target:** `workspaces/nsa/config/prompts/claims_assessment.md`

---

## Fix Status

| Fix | Description | Status | Tokens Added |
|-----|-------------|--------|--------------|
| Fix 3 | VAT deduction for companies | ✅ DONE | +453 |
| Fix 2 | Assistance package detection | ✅ DONE | +441 |
| Fix 1 | Service history check (12-month rule) | ✅ DONE | +417 |

---

## Fixes Ready to Implement

### Fix 1: Service History Compliance Check

**Gap:** Prompt only checks if current repair shop is authorized, not whether historical maintenance is up to date.

**Decision:** Assume service must be performed at least once per year per manufacturer specs.

**Changes to prompt:**
- Rename Check 4 to "Service & Shop Compliance"
- Add sub-check 4a: Shop Authorization (existing)
- Add sub-check 4b: Service History Compliance (new)

**New check logic:**
```
Check 4b: Service History Compliance
- Review service_history entries
- Calculate time gaps between service entries
- If any gap > 12 months → FAIL (service overdue)
- If last service > 12 months before claim date → FAIL
- If service history is empty/missing → REFER_TO_HUMAN
```

**Estimated tokens:** +300

---

### Fix 2: Assistance Package Detection

**Gap:** Prompt doesn't handle replacement car / towing claims.

**Decision:** Add detection + warning, flag for human review (don't auto-calculate).

**Changes to prompt:**
- Add new section after Check 5 (before payout calculation)
- Scan line items for keywords: "Ersatzwagen", "replacement car", "towing", "Abschlepp", "remorquage", "véhicule de remplacement"

**New check logic:**
```
Check 5b: Assistance Package Items (WARNING)
- Scan line items for assistance-related keywords
- If detected:
  - Flag in output: "ASSISTANCE_ITEMS_DETECTED"
  - Note: "Replacement car/towing detected. Verify assistance package coverage separately."
  - DO NOT include these items in standard payout calculation
  - Add to recommendations: "Human review needed for assistance package items"
```

**Estimated tokens:** +200

---

### Fix 3: VAT Handling for Company Policyholders

**Gap:** If policyholder is a company, VAT should be deducted from payout.

**Changes to prompt:**
- Add to Check 6 (Payout Calculation) after deductible step
- Check if policyholder is a company (look for company indicators in facts)

**New logic in Check 6:**
```
Step 5: VAT Adjustment (if applicable)
- Check policyholder type:
  - Look for "company", "GmbH", "AG", "SA", "Sàrl", "Inc", "Ltd" in policyholder name
  - Or check if policy has "is_company: true" field
- If company policyholder:
  - Deduct VAT from final payout (typically 8.1% in Switzerland)
  - final_payout = final_payout / 1.081
  - Document: "VAT deducted (company policyholder)"
```

**Estimated tokens:** +250

---

## Fixes Pending Adjuster Input

| Gap | Status | Blocker |
|-----|--------|---------|
| Gap 4: Costly repair documentation | BLOCKED | Need adjuster to define "entire unit" criteria |
| Gap 5: Error memory verification | BLOCKED | Need adjuster to explain what this means |
| Gap 6: Part number research | NOT MVP | Need frequency data from adjuster |

---

## Implementation Order

1. **Fix 3 (VAT)** - Cleanest change, isolated to payout calculation
2. **Fix 2 (Assistance)** - Detection + warning only, low risk
3. **Fix 1 (Service History)** - Most complex, requires service_history parsing logic

---

## Token Budget

| Component | Original | After Fix 3 | After Fix 2 | After Fix 1 (Final) |
|-----------|----------|-------------|-------------|---------------------|
| Prompt template | 4,694 | 5,147 (+453) | 5,588 (+894) | 6,005 (+1,311) |
| Largest claim (65258) | 61,673 | 62,126 | 62,567 | 62,984 |

**Summary:** All 3 fixes added 1,311 tokens total. Still well within safe zone for 3/4 claims. Largest claim at ~63K remains in monitoring zone but acceptable.

---

## Next Steps

- [ ] Get adjuster answers for Gap 4, 5, 6
- [ ] Implement Fix 3 (VAT)
- [ ] Implement Fix 2 (Assistance detection)
- [ ] Implement Fix 1 (Service history)
- [ ] Test all 4 claims against updated prompt
- [ ] Compare AI decisions to adjuster decisions
