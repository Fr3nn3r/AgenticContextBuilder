# Claim Facts Coverage Analysis

**Date**: 2026-01-24
**Claims Analyzed**: 65128, 65157, 65196, 65258

## Purpose

This analysis evaluates whether the extracted claim facts (JSON) contain sufficient information to replicate an adjuster's thought process and decision-making.

---

## Summary: Can Adjuster Thought Process Be Replicated?

| Claim | Verdict | Key Gap |
|-------|---------|---------|
| **65128** | **NO** | Missing defective component identification (trunk lock) |
| **65157** | **PARTIAL** | Missing sale date for retroactive warranty detection |
| **65196** | **PARTIAL** | Missing line item details and component-level coverage mapping |
| **65258** | **PARTIAL** | Missing service compliance details and owner/policyholder match |

---

## Detailed Analysis by Claim

### Claim 65128

**Adjuster's Decision**: REJECT - trunk lock not covered by warranty

**Key Reasoning Points**:
- Check if defective component is in policy scope of coverage
- Trunk lock identified as the defective component
- Trunk lock NOT in covered components list
- No further examination needed since rejection is clear

**Fact Coverage**:
| Reasoning Point | Supported? | Notes |
|-----------------|------------|-------|
| Policy scope of coverage | PARTIAL | Covered components listed but not all exclusions |
| Trunk lock is defective component | NO | JSON does not identify specific component repaired |
| Policy details (limits, excess) | YES | All present |
| Cost estimate totals | YES | Present |
| Vehicle identification | YES | VIN, plate, make/model present |

**Missing Information**:
1. Defective component identification (trunk lock)
2. Part numbers from cost estimate
3. Detailed line item descriptions

**Verdict**: **NO** - Cannot replicate. The critical determination (trunk lock not covered) requires knowing what component was repaired, which is not in the JSON.

---

### Claim 65157

**Adjuster's Decision**: REJECT - damage occurred before warranty start date

**Key Reasoning Points**:
- Coverage check for defective component
- Mileage limit check (no limit in this case)
- VIN and policyholder verification
- Service history compliance
- Error memory analysis
- Detected warranty start (31.12.2025) BEFORE sale date (07.01.2026) - retroactive purchase
- Contacted policyholder who confirmed damage occurred 29.12.2025
- Damage occurred before warranty start → rejection

**Fact Coverage**:
| Reasoning Point | Supported? | Notes |
|-----------------|------------|-------|
| Coverage scope | YES | Covered/excluded components present |
| VIN verification | YES | Consistent across documents |
| Policyholder match | YES | Name matches across documents |
| Service history | YES | 3 entries, mobility guarantee active |
| Error codes | YES | 6 codes with descriptions |
| Warranty start date | YES | 31.12.2025 |
| Sale date | NO | NOT PRESENT - adjuster notes 07.01.2026 |
| Damage date | YES | 29.12.25 from customer communication |

**Missing Information**:
1. **Sale date (07.01.2026)** - Critical for detecting retroactive warranty
2. Policy mileage limit indicator (binary yes/no)
3. Explicit claim report date

**Verdict**: **PARTIAL** - Final rejection logic CAN be derived (damage date < warranty start), but the intermediate reasoning about retroactive warranty purchase cannot be replicated without sale date.

---

### Claim 65196

**Adjuster's Decision**: APPROVE with adjustments (mileage scale, VAT deduction for company)

**Key Reasoning Points**:
- Component coverage check (central hydraulic valve for height control)
- Part identification from cost estimate
- Mileage limit check
- VIN and policyholder verification
- Service history compliance
- Cost estimate processing (remove excluded items)
- Assistance package limits (CHF 100/day, CHF 1,000/event max)
- Mileage-based coverage scale application
- VAT deduction for company policyholders

**Fact Coverage**:
| Reasoning Point | Supported? | Notes |
|-----------------|------------|-------|
| Component coverage | PARTIAL | "Suspension: 6 parts" but no specific parts listed |
| Part identification | NO | Line items summarized, not itemized |
| Mileage check | YES | 74,359 km present |
| VIN match | YES | Consistent across documents |
| Policyholder match | YES | EM Haustechnik GmbH |
| Service compliance | PARTIAL | 5 entries but no overdue status |
| Assistance limits | YES | Exact figures match |
| Coverage scale | YES | Percentages by km range |
| Company VAT rule | PARTIAL | GmbH identifiable but rule not flagged |

**Missing Information**:
1. Specific line item details (part names, numbers)
2. Explicit coverage mapping for specific parts
3. Service compliance status (current/overdue)
4. Business logic rules (VAT for companies, exclusions)

**Verdict**: **PARTIAL** - Most verification steps possible, but component-level coverage decisions and line item evaluation cannot be replicated.

---

### Claim 65258

**Adjuster's Decision**: APPROVE with max coverage cap (CHF 5,000) and 10% deductible

**Key Reasoning Points**:
- Component coverage (cylinder head)
- Mileage limit check
- VIN and policyholder/owner verification
- Service history compliance
- Cost estimate processing
- Assistance package check
- Maximum coverage application (CHF 5,000 incl. VAT)
- Deductible calculation (10% → CHF 4,500 payout)
- VAT treatment for companies
- Documentation requirements (delivery note, photos)

**Fact Coverage**:
| Reasoning Point | Supported? | Notes |
|-----------------|------------|-------|
| Cylinder head coverage | PARTIAL | "Engine: 30 parts" but no specific parts |
| Mileage check | YES | Coverage scale and odometer present |
| VIN match | YES | All VINs match |
| Policyholder identity | PARTIAL | Name present but owner not extracted |
| Service compliance | PARTIAL | 1 entry but no compliance details |
| Max coverage | YES | CHF 5,000 |
| Deductible | YES | 10%, min CHF 150 |
| Cost estimate totals | YES | All amounts present |
| Assistance coverage | YES | "Not covered" |
| Policyholder entity type | NO | Not extracted |

**Missing Information**:
1. Explicit cylinder head in covered components
2. Vehicle owner name from registration
3. Service dates and mileage at service
4. Policyholder entity type (individual/company)
5. Line item coverage categorization
6. Applicable coverage percentage tier

**Verdict**: **PARTIAL** - 60-70% of information present. Cannot verify service compliance, owner match, or component-level coverage.

---

## Common Missing Information Patterns

Across all 4 claims, these data gaps prevent full replication of adjuster reasoning:

### 1. Line Item Details (All 4 Claims)
Cost estimate summaries show counts (e.g., "5 items: 3 labor, 1 parts, 1 fees") but not specific parts/components being repaired. Adjusters need part names and part numbers to make coverage decisions.

### 2. Component-Level Coverage Mapping (All 4 Claims)
Policy facts show aggregated counts (e.g., "Engine: 30 parts", "Suspension: 6 parts") but don't list specific covered parts. Adjusters must match claimed parts against covered parts list.

### 3. Service Compliance Status (65196, 65258)
Whether service intervals are current per manufacturer specifications is a coverage requirement. JSON shows entry counts but not whether maintenance is up-to-date or overdue.

### 4. Policyholder/Owner Verification (65258)
Vehicle owner name from registration document not extracted, preventing verification that owner matches policyholder.

### 5. Sale Date (65157)
Critical for detecting retroactive warranty purchases (warranty start before vehicle sale).

---

## Recommendations

To enable full replication of adjuster reasoning, the extraction pipeline should be enhanced:

### High Priority

1. **Extract itemized line items from cost estimates**
   - Part names and descriptions
   - Part numbers
   - Individual amounts (labor, parts, fees)
   - This is critical for coverage determination

2. **Extract explicit covered parts list from policy**
   - Not just category counts ("Engine: 30 parts")
   - Full list of specific covered parts per category
   - Enable programmatic coverage matching

3. **Add service compliance status**
   - Last service date and mileage
   - Next service due date/mileage
   - Explicit current/overdue indicator

### Medium Priority

4. **Add sale date extraction**
   - From purchase agreement or dealer documentation
   - Required for retroactive warranty detection

5. **Extract vehicle owner name from registration**
   - Required for owner/policyholder match verification

6. **Add policyholder entity type**
   - Individual vs. company
   - Affects VAT treatment in claim calculations

### Lower Priority

7. **Compute applicable coverage tier**
   - Based on incremental mileage since policy start
   - Output which percentage (40%/60%/80%) applies

8. **Flag business rules**
   - VAT non-reimbursable for companies
   - Specific exclusion triggers

---

## Conclusion

Current extraction captures policy metadata, coverage limits, and document verification data well. The primary gap is **detailed line item extraction** from cost estimates and **component-level coverage mapping** from policies. These are essential for the core adjuster workflow of matching claimed repairs against covered components.

Implementing the high-priority recommendations would move fact coverage from PARTIAL to near-complete for most claims.
