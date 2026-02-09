# Plan: Claims Workbench (Stefano's Primary Screen)

## Context

NSA claims adjuster Stefano needs a primary work screen that mirrors his mental model from the NSA Garantie system. The current Decision Dossier page is a power-user audit tool; Stefano needs a **Claims Workbench** that follows his explicitly stated information hierarchy:

```
1. DECISION  ->  2. WHY  ->  3. MAIN PART  ->  4. COSTS  ->  5. AUTO DETAILS  ->  6. DOCUMENTS
```

## Design Decisions

- **Entry point**: Claims list first (like NSA system), drill into detail
- **Replaces**: Decision Dossier page (fold clause audit into Clauses tab)
- **First mock scope**: Claim detail view only (list comes later)
- **Data**: Real data from seed claims (64166, 64168, 64288, 64297)
- **Cost breakdown**: Three groups (Parts | Labor | Other/Fees)
- **Screen name**: "Claims Workbench" (sidebar: "Workbench")
- **Mock format**: Real React page wired to API

## Capabilities & Acceptance Criteria

### P0 - Above the fold (immediate visibility)

| # | Capability | Acceptance Criteria |
|---|-----------|---------------------|
| C1 | Decision verdict | APPROVE/DENY/REFER as large colored badge |
| C2 | Reason | 1-2 sentence explanation under verdict |
| C3 | Main component | Primary repair part name |
| C4 | Cost summary | Requested -> Approved -> Payable |
| C5 | Conflict count | Warning badge (hidden if zero) |
| C6 | Claim header | Claim #, Policy, Vehicle, Mileage, Garage, Date |

### P0 - One click access (tabs)

| # | Capability | Acceptance Criteria |
|---|-----------|---------------------|
| C7 | Cost breakdown | Parts/Labor/Fees groups, Requested vs Approved, subtotals, tax, deductible, payable |
| C8 | Exclusion reasons | Each excluded item shows reason + denial clause reference |
| C9 | Assumptions tab | YES/NO questions for tier 2/3 clauses, missing data highlighted, re-evaluate button |
| C10 | Clauses tab | All 27 clauses, PASS/FAIL, YES/NO, missing data highlighted |
| C11 | Screening tab | Raw screening checks with verdict and reason |
| C12 | Documents tab | List of source documents |

### P1 - Second iteration

| # | Capability | Acceptance Criteria |
|---|-----------|---------------------|
| C13 | Override decision | Button with justification, logged for audit |
| C14 | Version history | Dropdown of past dossier versions |
| C15 | Claims list | Entry point with search, sort, filters |

### P2 - Later

| # | Capability | Acceptance Criteria |
|---|-----------|---------------------|
| C16 | Response generator | Template with policy citations |
| C17 | Conflict resolution | Select correct value, add note |
| C18 | Ancillary work detection | Flag main vs related work |

## Data Sources

Single API endpoint: `GET /api/claims/{claim_id}/workbench`

Returns aggregated:
- `facts` - claim_facts.json (vehicle, policy, odometer, line items)
- `screening` - screening.json (checks with PASS/FAIL/SKIPPED)
- `coverage` - coverage_analysis.json (line items with coverage status)
- `dossier` - decision_dossier_v1.json (clause evaluations, assumptions, verdict)
- `assessment` - assessment.json (LLM assessment)
- `documents` - list of files in docs/

## Source Documents

- Feedback session summary: `data/08-NSA-Supporting-docs/Aufzeichnung 2026-02-06 113007_feedback_summary.md`
- Capabilities analysis: `data/08-NSA-Supporting-docs/Aufzeichnung 2026-02-06_capabilities_analysis.md`
- Customer feedback: `docs/customer-feedback-2026-02.md`
- NSA system screenshot: Stefano's current Claims screen
