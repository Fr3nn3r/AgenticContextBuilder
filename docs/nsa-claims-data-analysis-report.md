# NSA Motor Guarantee — Claims Data Analysis

**Insights from 84 claims across 3 datasets**

Date: February 2026
Data period: October 2025 – January 2026

---

## 1. Portfolio at a Glance

| Metric | Value |
|--------|-------|
| Claims analyzed | 84 |
| Decision split | 42 approved (50%) / 42 denied (50%) |
| Total approved payout | CHF 60,885 |
| Average approved payout | CHF 1,450 |
| Median approved payout | CHF 949 |
| Vehicle brands represented | 23 |
| Top 4 brands (VW, Mercedes, BMW, Audi) | 45 claims (54% of volume) |
| Languages | DE (43), FR (39), IT (2) |
| Unique garages | 79 across 81 claims with garage data |
| Date range | 8 Oct 2025 – 30 Jan 2026 |

---

## 2. Decision Patterns — Why Claims Get Denied

Across the 42 denied claims, a single root cause dominates: **"part not covered by the policy"** accounts for 76% of all denials. This is a deterministic, lookup-based check — the garage submits a claim for a component, the component is checked against the policy's coverage list, and the claim is rejected because the part is not listed.

### Denial category breakdown

| Denial Category | Count | % of Denials |
|-----------------|------:|-------------:|
| Part not covered | 32 | 76% |
| Policy not valid / expired | 4 | 10% |
| Consequential / root-cause damage | 4 | 10% |
| Wear parts excluded | 1 | 2% |
| Mileage exclusion | 1 | 2% |

### Top denied systems

When the specific parts mentioned in denial reasons are grouped by vehicle system, the following pattern emerges:

| System | Denial Mentions |
|--------|----------------:|
| Electronics / Software | 10 |
| Emissions (EGR, AdBlue, DPF) | 8 |
| Seals & Gaskets | 8 |
| Engine / Powertrain | 8 |
| Cooling / Heating | 5 |
| Chassis / Steering | 4 |
| Body / Exterior | 2 |
| Wear parts | 2 |
| Hybrid / EV | 2 |

The most frequently denied individual components include software updates, gaskets/seals, EGR valves, control arms, wiring harnesses, engine control units, AdBlue systems, timing belts, and water pumps.

The data suggests that a significant portion of denied claims could be identified earlier in the process, before they require manual adjuster review. The "part not covered" check is inherently rule-based — it compares a submitted component against a defined coverage list, with no judgment call required.

---

## 3. Financial Profile — Where the Money Goes

### Approved payout distribution

All 42 approved claims have payout data. The distribution is right-skewed, with most claims falling in the CHF 500–2,000 range.

| Statistic | Value |
|-----------|------:|
| Mean payout | CHF 1,450 |
| Median payout | CHF 949 |
| Minimum | CHF 25 |
| Maximum | CHF 4,500 |
| 25th percentile | CHF 531 |
| 75th percentile | CHF 2,275 |

### Parts vs. labor split

Of the 38 approved claims with itemized cost data:

| Component | Total | Share |
|-----------|------:|------:|
| Parts | CHF 30,998 | 60% |
| Labor | CHF 20,695 | 40% |
| **Combined** | **CHF 51,694** | **100%** |

Average parts cost per claim: CHF 816. Average labor cost per claim: CHF 545.

### Deductible structure

The deductible across 41 approved claims with deductible data:

- **CHF 150** is the most common deductible, appearing in 20 of 41 claims (49%)
- Mean deductible: CHF 208
- Range: CHF 0 – CHF 500

### Reimbursement tiers

23 of 42 approved claims carry a mileage-dependent reimbursement rate that reduces the payout based on vehicle mileage. The remaining 19 claims either have 100% coverage or no degradation clause.

| Reimbursement Rate | Claims |
|-------------------:|-------:|
| 40% | 10 |
| 50% | 1 |
| 60% | 5 |
| 70% | 3 |
| 80% | 3 |
| 90% | 1 |

The 40% tier is the most common among claims with mileage-dependent reimbursement, indicating a portfolio with a meaningful share of high-mileage vehicles.

The financial structure of approved claims follows predictable patterns — standardized deductibles, formulaic reimbursement rates, and verifiable parts/labor splits. These characteristics lend themselves well to structured verification.

---

## 4. Brand & Garage Landscape

### Brand volume and approval rates

German premium brands dominate the portfolio. The top 4 brands account for 54% of all claims.

| Brand | Claims | Approved | Denied | Approval Rate | Total Payout (CHF) |
|-------|-------:|---------:|-------:|--------------:|--------------------:|
| Volkswagen | 16 | 5 | 11 | 31% | 2,955 |
| Mercedes | 14 | 8 | 6 | 57% | 16,831 |
| Audi | 8 | 5 | 3 | 63% | 11,048 |
| BMW | 7 | 5 | 2 | 71% | 5,264 |
| Land Rover | 7 | 5 | 2 | 71% | 7,457 |
| Peugeot | 6 | 2 | 4 | 33% | 1,479 |
| Ford | 4 | 3 | 1 | 75% | 3,897 |
| Mini | 3 | 0 | 3 | 0% | — |
| Porsche | 2 | 0 | 2 | 0% | — |
| Jeep | 2 | 2 | 0 | 100% | 2,686 |
| Seat | 2 | 1 | 1 | 50% | 863 |
| Cupra | 2 | 0 | 2 | 0% | — |

*Remaining 11 brands each have 1 claim.*

Volkswagen stands out with the highest volume (16 claims) but the lowest approval rate among high-volume brands (31%). This is driven primarily by "part not covered" denials (7 of 11) and "policy expired" denials (4 of 11). No other brand shows the "policy expired" pattern — this appears to be Volkswagen-specific in this dataset.

Mercedes generates the highest total payout (CHF 16,831) with 8 approved claims and an above-average approval rate of 57%.

There are no significant brand-specific denial *reason* patterns beyond Volkswagen's expired policies — "part not covered" is the dominant denial reason across all brands.

### Garage landscape

The garage network is overwhelmingly independent: 57 of 81 claims with garage data come from independent shops. Organized chains and OEM dealerships make up the remainder.

| Garage Type | Claims | Approval Rate |
|-------------|-------:|--------------:|
| Independent | 57 | 47% |
| AMAG | 7 | 86% |
| Emil Frey | 6 | 50% |
| Mercedes-Benz (OEM) | 5 | 60% |
| BYMYCAR | 3 | 33% |

79 unique garages submitted across 81 claims — nearly every claim comes from a different shop. Only 2 garages submitted more than once (Autorama AG and Garage du Chateau d'en Bas, each with 2 claims).

Claims originate from cities across Switzerland, with the highest concentrations in Sion (4), Bern (3), and Wetzikon (3).

---

## 5. Operational Observations

### Language distribution

| Language | Claims | Approved | Denied | Approval Rate |
|----------|-------:|---------:|-------:|--------------:|
| German (DE) | 43 | 21 | 22 | 49% |
| French (FR) | 39 | 21 | 18 | 54% |
| Italian (IT) | 2 | 0 | 2 | 0% |

German and French claims show comparable approval rates (49% vs. 54%) — there is no meaningful language bias in decisions. Average approved payouts are nearly identical: CHF 1,449 (DE) vs. CHF 1,451 (FR).

Italian claims appear for the first time in the eval-v2 dataset (2 claims, both denied). While too small a sample for conclusions, it may signal emerging activity in the Italian-speaking market.

Bilingual processing (DE/FR) is a baseline requirement for any operational tooling.

### Document completeness

Each claim submission averages 4.9 documents. The core document types and their presence rates:

| Document Type | Present in | % of Claims |
|---------------|------------|------------:|
| Vehicle registration (FZA) | 84 / 84 | 100% |
| Policy / guarantee | 84 / 84 | 100% |
| Cost estimate (KV) | 83 / 84 | 99% |
| Service book | 71 / 84 | 85% |
| Mileage proof (KM) | 56 / 84 | 67% |
| Photos | 10 / 84 | 12% |
| Diagnostic reports | 10 / 84 | 12% |

Cost estimates are present in virtually all claims (99%), and policy documents are now present in 100% of claims. Service books accompany 85% of submissions. Mileage proof (67%) and diagnostic reports (12%) are less consistently included.

### Temporal patterns

| Month | Approved | Denied | Total |
|-------|----------|--------|-------|
| Oct 2025 | 7 | 0 | 7 |
| Nov 2025 | 4 | 0 | 4 |
| Dec 2025 | 14 | 17 | 31 |
| Jan 2026 | 17 | 25 | 42 |

Volume increases significantly in December 2025 and January 2026. The early months (Oct–Nov) contain only approved claims — this reflects the composition of the eval-v1 dataset, which was enriched first with approved claims. The December–January spike includes the full decision spectrum and likely reflects both natural volume growth and the addition of eval-v2 data.

---

## 6. Opportunities the Data Suggests

### 1. Early-stage claim screening

The dominance of "part not covered" denials (76% of all denials) suggests that a pre-check at the point of claim submission — cross-referencing the claimed part against the policy's coverage list — could surface likely denials before they enter the manual review queue. This check is deterministic and does not require judgment: a part is either on the coverage list or it is not.

### 2. Coverage verification support

For approved claims, the financial structure follows highly patterned logic: standardized deductibles (CHF 150 in nearly half of cases), formulaic mileage-dependent reimbursement tiers (40%–90%), and verifiable parts/labor cost breakdowns. These patterns lend themselves well to automated verification — confirming that the math matches the policy terms.

### 3. Garage guidance

The frequently-denied parts list — emissions systems (EGR, AdBlue, DPF), electronics and software, seals and gaskets — represents an opportunity to provide garages with clearer upfront visibility into what their customer's policy covers. Reducing "part not covered" submissions at the source would decrease processing friction for both garages and adjusters.

### 4. Product intelligence

The gap between what garages submit and what policies cover — especially in emissions systems, electronics, and seals — reveals where customer expectations diverge from product coverage. This pattern data is potentially useful for future product design conversations: understanding which components generate the most claim friction can inform coverage list evolution.

---

## 7. Data Notes & Methodology

### Datasets

| Dataset | Claims | Period | Notes |
|---------|-------:|--------|-------|
| seed-v1 | 4 | Jan 2026 | Initial development set with full ground truth |
| eval-v1 | 50 | Oct 2025 – Jan 2026 | Primary evaluation set |
| eval-v2 | 30 | Dec 2025 – Jan 2026 | Extended set with enriched metadata from provenance PDFs |

### Enrichment

The eval-v2 dataset includes additional metadata fields (vehicle details, garage information, coverage notes, reimbursement rates) extracted from the original claim PDFs. Earlier datasets have sparser metadata in some fields.

### Known limitations

- **Sample size**: 84 claims is sufficient for pattern identification but too small for statistically robust subgroup analysis (e.g., brand-specific denial rates for low-volume brands)
- **Single customer**: All data comes from NSA Motor Guarantee — patterns may not generalize to other warranty products
- **Short time window**: 4 months of data (Oct 2025 – Jan 2026) — seasonal effects cannot be assessed
- **Denial reason classification**: Free-text denial reasons in German and French were programmatically categorized; automated classification covers ~86% of cases, with 14% requiring manual review
- **Part extraction**: Specific denied parts were extracted via pattern matching on denial reason text — some denials reference parts not captured by the extraction patterns

### Reference

The full interactive analysis with visualizations is available in the project notebook: `analysis/claims_eda.ipynb`
