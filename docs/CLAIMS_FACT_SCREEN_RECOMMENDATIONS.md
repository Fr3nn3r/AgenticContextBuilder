# Claims Fact Screen UI Recommendations

This is a pragmatic, professional baseline you can hand to developers without needing to be a designer.

## Quick Diagnosis (What’s wrong today)
- No clear hierarchy—everything has same weight.
- Too many small cards with equal prominence.
- Dense UI, weak spacing, inconsistent alignment.
- Left nav + center + right column all compete.
- KPI strip at top is tiny and low-contrast.

## Target Layout (Simple + Professional)

### Top Bar (sticky)
- Claim ID, Policyholder, Status (Approve/Reject/Refer), Total Payout
- Secondary: claim date, last updated, run id
- Action buttons: “Refer”, “Approve”, “Reject”, “Export”

### Main Content (2-column)
- **Left (60–70%)**
  - **Facts Summary** (key-value grid: vehicle, policy, dates, mileage)
  - **Coverage & Limits** (limits, deductible, coverage tier)
  - **Assessment Checks** (list of checks with PASS/FAIL/INCONCLUSIVE + evidence tag)
- **Right (30–40%)**
  - **Documents** (list with type, page count, evidence hits)
  - **Evidence Preview** (doc page with highlight)
  - **Extraction Quality Gate** (pass/warn/fail + missing fields)

### Tabs (optional)
- Facts | Assessment | History
- Combine Facts + Assessment if business users need both at once.

## Visual Rules for Devs (No design skill required)

### Typography
- One professional family (e.g., “Source Sans 3” or “IBM Plex Sans”).
- Title: 20–24px
- Section headers: 14–16px, bold
- Body: 12–14px

### Spacing
- 16px base grid.
- Card padding: 16–20px.
- Section gaps: 24–32px.

### Cards
- White cards on light gray background.
- Subtle border (1px #E6E8EB).
- Avoid bright accents except status badges.

### Status Colors
- PASS: green (#2E7D32)
- FAIL: red (#C62828)
- INCONCLUSIVE: amber (#F9A825)

### Icons
- Use only for status or doc types. Keep simple.

## Functional Improvements (Business users care about these)
1) Evidence is first-class: each check shows evidence count + quick doc link.
2) Decision logic visible: “Why” summary near the top.
3) Quality gate visible: pass/warn/fail + missing required fields.
4) Action clarity: primary button reflects recommended decision.

## Quick Wins (This week)
- Increase whitespace + align to a grid.
- Merge tiny cards into fewer, bigger sections.
- Move payout + decision into top bar.
- Add a dedicated “Checks” list with colored pills.
- Improve contrast: darker headings, lighter secondary info.
