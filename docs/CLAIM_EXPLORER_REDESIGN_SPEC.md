# Claim Explorer Redesign Specification

## Problem Statement

The current Claim Explorer screen has fundamental usability and design problems:

1. **Action buttons are meaningless** - Refer/Approve/Reject buttons do nothing; they're not connected to any workflow
2. **Wrong default view** - Starts on "Facts" tab when an Overview should be the landing page
3. **Facts lack structure and provenance** - No clear connection between extracted values and source documents
4. **Checks are disconnected from facts** - Assessment checks appear unrelated to the extracted data
5. **Assumptions are buried** - Critical risk signals are hidden at the bottom of Assessment tab
6. **No clear decision workflow** - User cannot see what's blocking a decision or what needs attention

## Design Principles

Per `docs/UI_CAPABILITIES.md` and `docs/ASSESSMENT_FEEDBACK.md`:

- **Evidence-first**: Every check must show explicit evidence with document/page provenance
- **Assumptions as risk signals**: Surface assumption count and critical flags prominently
- **Hard gate on evidence**: PASS requires explicit provenance-linked evidence; otherwise INCONCLUSIVE
- **Auditability**: Every decision traceable to source; raw + normalized values side-by-side
- **Missing evidence = blocker**: Visually flag missing critical evidence

---

## Tab Structure (Redesigned)

| Tab | Purpose | Default? |
|-----|---------|----------|
| **Overview** | Decision summary + attention items | YES |
| **Facts** | Structured extracted data with provenance | |
| **Evidence** | Checks with linked facts and source docs | |
| **Assumptions** | First-class assumptions table | |
| **History** | Assessment run history | |

Remove the generic "Assessment" tab - split its content into Overview, Evidence, and Assumptions.

---

## Tab 1: Overview (Default Landing Page)

**Purpose**: At-a-glance decision readiness. What needs attention before a decision can be made?

### Layout (60/40 split)

#### Left Column (60%)

**1. Decision Readiness Card**
```
+----------------------------------------------------------+
|  DECISION READINESS                                       |
|                                                           |
|  [=============================----] 78% Ready            |
|                                                           |
|  Blocking Issues (2):                                     |
|  - Incident Date: Missing from all documents              |
|  - Mileage: Conflicting values across documents           |
|                                                           |
|  High-Impact Assumptions (1):                             |
|  - Labor rate assumed $95/hr (regional average)           |
+----------------------------------------------------------+
```

- Progress bar showing % of required checks with evidence
- List of blocking issues (missing critical evidence)
- Count and summary of high-impact assumptions

**2. Key Metrics Row**
```
+----------+----------+----------+----------+----------+
| CHECKS   | PASSED   | FAILED   | UNKNOWN  | ASSUMPT. |
|   7      |   5      |   1      |   1      |   3      |
+----------+----------+----------+----------+----------+
```

**3. Quick Facts Summary**
Compact 2-column grid showing only the most critical identifiers:
- Vehicle: Make/Model + VIN + Plate
- Policy: Number + Holder
- Dates: Incident Date + Coverage Period
- Amounts: Claimed Amount + Coverage Limit

Each value shows a provenance indicator (green dot = sourced, yellow = assumed, red = missing).

**4. Attention Items List**
Prioritized list of items needing human attention:
```
1. [!] Repair cost 30% above regional median - Review estimate
2. [?] 8-month gap in service records - Verify mileage
3. [?] No incident date found - Request from claimant
```

#### Right Column (40%)

**5. Documents Quick View**
- Compact list of documents with extraction status badges
- Click to open document in new tab

**6. Actions Panel**

Replace the current meaningless buttons with a workflow-aware action panel:

```
+----------------------------------------------------------+
|  CLAIM ACTIONS                                            |
|                                                           |
|  [Refer to Human]  <- Always available                    |
|                                                           |
|  -- Decision requires: --                                 |
|  [ ] All critical facts extracted                         |
|  [ ] No high-impact assumptions                           |
|  [ ] No failed checks                                     |
|                                                           |
|  [Approve] [Reject]  <- Disabled until ready              |
|                                                           |
|  Reason (required): [___________________________]         |
+----------------------------------------------------------+
```

**Key changes**:
- Approve/Reject disabled until prerequisites met
- Checklist shows what's blocking the decision
- Reason field required for any action
- "Refer to Human" always available (the safe default)
- Actions create audit log entries

---

## Tab 2: Facts (Structured Data with Provenance)

**Purpose**: Show all extracted facts organized by category, with clear provenance and normalization.

### Layout

#### Fact Cards by Category

Group facts into logical sections:

**Vehicle Information**
```
+----------------------------------------------------------+
| VEHICLE                                        3 sources  |
+----------------------------------------------------------+
| Field          | Value           | Source    | Confidence |
|----------------|-----------------|-----------|------------|
| Make           | Cupra           | FZA.pdf:1 | High       |
| Model          | Formentor       | FZA.pdf:1 | High       |
| VIN            | VSS ZZZ KMZ...  | FZA.pdf:1 | High       |
| License Plate  | VS 147831       | FZA.pdf:1 | High       |
| First Reg.     | 2023-06-15      | FZA.pdf:1 | High       |
|                | (15.06.2023)    | raw value |            |
| Mileage        | 52,100 km       | KV.pdf:1  | Medium     |
|                | (52100)         | raw value |            |
+----------------------------------------------------------+
```

**Key improvements**:
- Show **normalized AND raw** values for dates/numbers
- Show **source document** with page number (clickable)
- Show **confidence** level
- Multiple sources for same field? Show conflicts

**Policy & Coverage**
```
+----------------------------------------------------------+
| POLICY & COVERAGE                              2 sources  |
+----------------------------------------------------------+
| Policy Number  | 590223          | NSA_...pdf:1 | High   |
| Holder         | Cruz Morais P.  | NSA_...pdf:1 | High   |
| Coverage Start | 2023-06-01      | NSA_...pdf:3 | High   |
| Coverage End   | 2026-06-01      | NSA_...pdf:3 | High   |
+----------------------------------------------------------+
| COVERED COMPONENTS                                        |
| +--------+  +--------+  +--------+                        |
| | TURBO  |  | ENGINE |  | TRANS. |   Mechanical coverage |
| +--------+  +--------+  +--------+                        |
|                                                           |
| Max Coverage: CHF 4,000.00 (Engine)                       |
+----------------------------------------------------------+
```

**Claimed Amounts**
```
+----------------------------------------------------------+
| CLAIMED AMOUNTS                                           |
+----------------------------------------------------------+
| Line Item      | Amount   | Covered? | Source            |
|----------------|----------|----------|-------------------|
| Part: Turbo    | CHF 2100 | Yes      | KV.pdf:1          |
| Labor          | CHF 850  | Yes      | KV.pdf:1          |
| Diagnostic     | CHF 120  | Yes      | Service.pdf:2     |
|----------------|----------|----------|-------------------|
| TOTAL CLAIMED  | CHF 3070 |          |                   |
+----------------------------------------------------------+
```

**Dates & Timeline**
```
+----------------------------------------------------------+
| TIMELINE                                                  |
+----------------------------------------------------------+
| Event             | Date       | Source     | Status     |
|-------------------|------------|------------|------------|
| Policy Start      | 2023-06-01 | NSA:3      | OK         |
| First Registration| 2023-06-15 | FZA:1      | OK         |
| Last Service      | 2024-09-12 | Service:2  | OK         |
| Incident Date     | --         | --         | MISSING    |
| Claim Date        | 2025-01-14 | KV:1       | OK         |
| Policy End        | 2026-06-01 | NSA:3      | OK         |
+----------------------------------------------------------+
```

Visually highlight missing critical dates.

---

## Tab 3: Evidence (Checks Linked to Facts)

**Purpose**: Show each assessment check with the specific facts and documents that support or contradict it.

### Layout

Each check is an expandable card:

```
+----------------------------------------------------------+
| [PASS] Check 1: Policy Active at Incident Date            |
+----------------------------------------------------------+
| FACTS USED:                                               |
| - Policy Start: 2023-06-01 (NSA_Guarantee.pdf:3)          |
| - Policy End: 2026-06-01 (NSA_Guarantee.pdf:3)            |
| - Incident Date: MISSING                                  |
|                                                           |
| EVIDENCE:                                                 |
| [View] NSA_Guarantee.pdf, page 3                          |
|                                                           |
| REASONING:                                                |
| Policy coverage period verified. Incident date not found  |
| in any document - defaulted to claim submission date.     |
|                                                           |
| ASSUMPTION MADE:                                          |
| [!] Assumed incident occurred on claim date (2025-01-14)  |
|     Impact: MEDIUM - may affect coverage validation       |
+----------------------------------------------------------+
```

```
+----------------------------------------------------------+
| [FAIL] Check 4: Repair Costs Within Threshold             |
+----------------------------------------------------------+
| FACTS USED:                                               |
| - Claimed Amount: CHF 3,070 (KV.pdf:1)                    |
| - Regional Median: CHF 2,500 (system data)                |
|                                                           |
| EVIDENCE:                                                 |
| [View] KV.pdf, page 1 - Cost estimate                     |
|                                                           |
| REASONING:                                                |
| Repair estimate CHF 3,070 is 23% above regional median    |
| of CHF 2,500 for comparable turbo replacements.           |
|                                                           |
| REQUIRED ACTION:                                          |
| - Request itemized parts list with OEM part numbers       |
| - Verify repair shop certification                        |
+----------------------------------------------------------+
```

**Key improvement**: Each check explicitly lists:
1. Which facts it evaluated
2. Where those facts came from (provenance)
3. What reasoning was applied
4. What assumptions were made (if any)
5. What action is needed (if failing/inconclusive)

---

## Tab 4: Assumptions (First-Class Risk Signals)

**Purpose**: Dedicated view for all assumptions made during assessment. This is a key routing/escalation signal.

### Layout

**Summary Banner**
```
+----------------------------------------------------------+
|  ASSUMPTIONS SUMMARY                                      |
|                                                           |
|  Total: 3    Critical: 1    Affecting Decision: YES       |
|                                                           |
|  [!] This claim cannot be auto-approved due to critical   |
|      assumptions. Refer to human reviewer.                |
+----------------------------------------------------------+
```

**Assumptions Table**
```
+-------------------------------------------------------------------+
| #  | Check        | Field       | Assumed    | Impact | Reason    |
|----|--------------|-------------|------------|--------|-----------|
| 4  | Cost Check   | labor_rate  | CHF 95/hr  | HIGH   | Not spec. |
| 5  | Mileage      | service_gap | Normal use | MEDIUM | 8mo gap   |
| 1  | Policy Check | incident_dt | Claim date | MEDIUM | Missing   |
+-------------------------------------------------------------------+
```

**For each assumption, expandable detail**:
- Which document(s) were searched
- What value would be needed
- What the business impact is
- Suggested resolution (e.g., "Request incident report from claimant")

---

## Tab 5: History (unchanged)

Keep the existing history tab showing past assessment runs with their decisions and metrics.

---

## Component Hierarchy

```
ClaimExplorer
  ClaimTree (left sidebar)
  ClaimSummaryTab (main content area)
    ClaimContextBar (top bar with claim ID, status)
    TabNavigation [Overview, Facts, Evidence, Assumptions, History]

    OverviewTab (NEW - default)
      DecisionReadinessCard (NEW)
      KeyMetricsRow (NEW)
      QuickFactsSummary (NEW)
      AttentionItemsList (NEW)
      DocumentsQuickView
      ActionsPanel (NEW - replaces dumb buttons)

    FactsTab (redesigned)
      FactCategoryCard (vehicle, policy, amounts, timeline)
        FactRow (value, normalized, raw, source, confidence)

    EvidenceTab (NEW - replaces Assessment checks section)
      CheckEvidenceCard (per check)
        LinkedFacts
        SourceDocuments
        Reasoning
        AssumptionsMade
        RequiredActions

    AssumptionsTab (NEW - promoted from Assessment)
      AssumptionsSummaryBanner
      AssumptionsTable
        AssumptionDetail

    HistoryTab (unchanged)
```

---

## Data Requirements

### API Changes Needed

**1. Enhanced Facts Response**
```typescript
interface FactWithProvenance {
  name: string;
  value: string | number | null;
  normalized_value?: string | number;  // NEW: normalized form
  raw_value?: string;                  // NEW: original extracted text
  confidence: 'high' | 'medium' | 'low';
  source: {
    doc_id: string;
    doc_type: string;
    page: number;
    char_start: number;
    char_end: number;
  };
  conflicts?: FactWithProvenance[];    // NEW: conflicting values from other docs
}
```

**2. Enhanced Check Response**
```typescript
interface CheckWithEvidence {
  check_number: number;
  check_name: string;
  result: 'PASS' | 'FAIL' | 'INCONCLUSIVE';
  facts_used: {                        // NEW: explicit fact linkage
    fact_name: string;
    value: string | null;
    source_doc: string;
    is_missing: boolean;
  }[];
  evidence_docs: {                     // NEW: structured evidence
    doc_id: string;
    page: number;
    relevance: string;
  }[];
  reasoning: string;
  assumptions_made: string[];          // NEW: link to assumption IDs
  required_actions?: string[];         // NEW: for failing checks
}
```

**3. Decision Readiness Response**
```typescript
interface DecisionReadiness {
  readiness_pct: number;               // 0-100
  blocking_issues: {
    type: 'missing_evidence' | 'conflict' | 'failed_check';
    description: string;
    fact_or_check: string;
  }[];
  critical_assumptions: number;
  can_auto_approve: boolean;
  can_auto_reject: boolean;
}
```

---

## Action Workflow

### Valid Actions by State

| Claim State | Approve | Reject | Refer |
|-------------|---------|--------|-------|
| All checks pass, no critical assumptions | Yes | Yes | Yes |
| Any check FAIL | No | Yes | Yes |
| Any check INCONCLUSIVE | No | No | Yes |
| Critical assumptions present | No | No | Yes |
| Missing critical evidence | No | No | Yes |

### Action API

```typescript
POST /api/claims/{claim_id}/actions
{
  action: 'approve' | 'reject' | 'refer';
  reason: string;  // required
  user_id: string;
}
```

Creates an audit log entry with:
- Timestamp
- User
- Action taken
- Reason provided
- Claim state at time of action (checks, assumptions, etc.)

---

## Migration Path

1. **Phase 1**: Add Overview tab, make it default. Keep other tabs as-is.
2. **Phase 2**: Enhance Facts tab with provenance columns.
3. **Phase 3**: Create Evidence tab, move checks there with fact linkage.
4. **Phase 4**: Create Assumptions tab, promote from Assessment.
5. **Phase 5**: Implement action workflow with validation.
6. **Phase 6**: Remove old Assessment tab.

---

## Success Criteria

1. **User can see at a glance what needs attention** - Overview tab shows blockers
2. **Every fact is traceable to source** - Click any value to see source document
3. **Checks are connected to facts** - Each check shows which facts it evaluated
4. **Assumptions are prominent** - Dedicated tab, summary in Overview
5. **Actions have meaning** - Approve/Reject only enabled when valid
6. **Audit trail complete** - Every decision logged with reason and state

---

## Appendix: Current vs Proposed

| Current | Problem | Proposed |
|---------|---------|----------|
| Default to Facts tab | No overview of decision readiness | Default to Overview tab |
| Approve/Reject/Refer buttons | Do nothing, no validation | Workflow-aware with prerequisites |
| Assessment Checks list | Not linked to facts | Evidence tab with explicit fact linkage |
| Assumptions at bottom of Assessment | Hidden, not prominent | Dedicated Assumptions tab |
| Facts show value only | No provenance, no raw/normalized | Full provenance, raw + normalized |
| Quality Gate in sidebar | Disconnected from workflow | Integrated into Overview blocking issues |
