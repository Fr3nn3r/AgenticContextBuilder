# Reconciliation Implementation Plan

**Date:** 2026-01-26
**Status:** Ready for Implementation
**Related:** `docs/EVALUATION_DASHBOARD_PLAN.md`

## Overview

This plan implements claim-level reconciliation as a proper pipeline stage with quality gates. The reconciliation process aggregates facts from document extractions, detects conflicts, and produces a gate report.

**Key Decisions:**
- Critical facts: Derived from extraction specs (`required_fields`)
- Conflict detection: Same fact with different values = conflict
- Gate behavior: Advisory (does not block downstream processing)
- CLI: Separate `reconcile` command (claim-level stages separate from document-level)

---

## Core vs Customer-Specific Split

### Architecture Principle

The reconciliation implementation follows the same pattern as extraction:
- **Core (this repo)**: Generic mechanism code that works with any customer
- **Customer config (workspace/customer repo)**: Specs and thresholds that vary per customer

### What Goes Where

| Component | Location | Repository | Rationale |
|-----------|----------|------------|-----------|
| `ReconciliationService` | `src/context_builder/api/services/` | Core | Generic mechanism |
| `schemas/reconciliation.py` | `src/context_builder/schemas/` | Core | Generic data models |
| CLI `reconcile` command | `src/context_builder/cli.py` | Core | Generic tooling |
| API endpoints | `src/context_builder/api/routers/` | Core | Generic infrastructure |
| Default gate thresholds | `src/context_builder/api/services/` | Core | Sensible defaults |
| **Critical facts** | `config/extraction_specs/*.yaml` | Customer | `required_fields` per doc type |
| **Gate threshold overrides** | `config/reconciliation_gate.yaml` | Customer (optional) | Customer-specific tuning |

### Why This Works

The service is **config-driven** - it reads from the active workspace:

```python
# ReconciliationService reads customer-specific specs at runtime
specs_dir = self.workspace_path / "config" / "extraction_specs"
for spec_file in specs_dir.glob("*.yaml"):
    spec = yaml.safe_load(spec_file.read_text())
    required_fields = spec.get("required_fields", [])  # Customer-defined!
```

### Critical Facts Flow

```
Customer Repo                    Workspace                          Core Service
────────────────                ────────────                       ────────────
extraction_specs/               config/extraction_specs/           ReconciliationService
├── nsa_guarantee.yaml   sync   ├── nsa_guarantee.yaml     loads   ├── load_critical_facts_spec()
│   required_fields:        →   │   required_fields:           →   │   reads required_fields
│     - policy_number           │     - policy_number               │   from each spec
│     - coverage_start          │     - coverage_start              │
├── cost_estimate.yaml          ├── cost_estimate.yaml              │   Union of all required_fields
│   required_fields:            │   required_fields:                │   = claim-level critical facts
│     - total_amount            │     - total_amount                │
```

### Optional Customer Gate Config

Customers can override default thresholds by creating:

**File:** `workspaces/{ws}/config/reconciliation_gate.yaml`

```yaml
# Optional - if not present, core defaults apply
thresholds:
  missing_critical_warn: 2    # warn if <= N missing (default: 2)
  missing_critical_fail: 2    # fail if > N missing (default: 2)
  conflict_warn: 2            # warn if <= N conflicts (default: 2)
  conflict_fail: 2            # fail if > N conflicts (default: 2)
  token_warn: 40000           # warn if estimated tokens > N (default: 40000)
  token_fail: 60000           # fail if estimated tokens > N (default: 60000)

# Optional: additional claim-level critical facts beyond extraction specs
additional_critical_facts:
  - policy_number
  - claim_date
```

### No Customer Repo Changes Required Initially

The existing NSA customer repo (`context-builder-nsa`) works immediately because:
1. `required_fields` already exist in each extraction spec YAML
2. Default gate thresholds in core are sensible

Later, NSA can add `config/reconciliation_gate.yaml` if they need different thresholds.

---

## Phase 1: Backend - Reconciliation Engine (Detailed)

### 1.1 Create ReconciliationService

**File:** `src/context_builder/api/services/reconciliation.py` (new)

This service encapsulates all reconciliation logic, separate from the pipeline stage.

```python
class ReconciliationService:
    """Service for claim-level fact reconciliation and quality gates."""

    def __init__(self, storage: FileStorage, aggregation_service: AggregationService):
        self.storage = storage
        self.aggregation = aggregation_service

    def reconcile(self, claim_id: str, run_id: Optional[str] = None) -> ReconciliationResult:
        """Run full reconciliation: aggregate facts, detect conflicts, evaluate gate."""
        pass

    def load_critical_facts_spec(self) -> Dict[str, List[str]]:
        """Load critical facts from extraction specs (required_fields per doc_type)."""
        pass

    def detect_conflicts(self, candidates: Dict[str, List[dict]]) -> List[FactConflict]:
        """Find facts with multiple different values across documents."""
        pass

    def evaluate_gate(self, facts: ClaimFacts, conflicts: List[FactConflict],
                      critical_facts: List[str]) -> ReconciliationGate:
        """Evaluate pass/warn/fail based on missing criticals, conflicts, token size."""
        pass

    def write_reconciliation_report(self, claim_id: str, report: ReconciliationReport) -> Path:
        """Write reconciliation_report.json to claim context directory."""
        pass
```

### 1.2 Define Reconciliation Schemas

**File:** `src/context_builder/schemas/reconciliation.py` (new)

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class GateStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

class FactConflict(BaseModel):
    """A fact with conflicting values across documents."""
    fact_name: str
    values: List[str]  # Different values found
    sources: List[str]  # doc_ids where each value came from
    selected_value: str  # The value we picked (highest confidence)
    selection_reason: str  # "highest_confidence", "most_recent", etc.

class ReconciliationGate(BaseModel):
    """Gate evaluation result."""
    status: GateStatus
    missing_critical_facts: List[str]
    conflict_count: int
    provenance_coverage: float  # % of facts with provenance
    estimated_tokens: int
    reasons: List[str]  # Human-readable reasons for status

class ReconciliationReport(BaseModel):
    """Full reconciliation report written to claim context."""
    claim_id: str
    run_id: str
    generated_at: datetime
    gate: ReconciliationGate
    conflicts: List[FactConflict]
    fact_count: int
    critical_facts_checked: List[str]
    critical_facts_present: List[str]

class ReconciliationResult(BaseModel):
    """Result returned from reconciliation service."""
    claim_facts: ClaimFacts  # The aggregated facts
    report: ReconciliationReport  # The gate report
```

### 1.3 Implement Critical Facts Loading

The service loads critical facts from extraction specs in the active workspace.

**Source:** `{workspace}/config/extraction_specs/*.yaml`

**Logic:**
```python
def load_critical_facts_spec(self) -> Dict[str, List[str]]:
    """Load required_fields from each extraction spec as critical facts."""
    specs_dir = self.workspace_path / "config" / "extraction_specs"
    critical_by_doctype = {}

    for spec_file in specs_dir.glob("*.yaml"):
        spec = yaml.safe_load(spec_file.read_text())
        doc_type = spec.get("doc_type")
        required = spec.get("required_fields", [])
        critical_by_doctype[doc_type] = required

    return critical_by_doctype
```

**Claim-level critical facts:** Union of all required_fields across doc types present in the claim.

### 1.4 Implement Conflict Detection

**Definition:** A conflict exists when the same fact has different values from different documents.

**Logic:**
```python
def detect_conflicts(self, candidates: Dict[str, List[dict]]) -> List[FactConflict]:
    """Detect facts with conflicting values."""
    conflicts = []

    for fact_name, candidate_list in candidates.items():
        # Group by normalized value (or raw value if no normalized)
        values_seen = {}
        for c in candidate_list:
            val = c.get("normalized_value") or c.get("value")
            if val not in values_seen:
                values_seen[val] = []
            values_seen[val].append(c["doc_id"])

        # If more than one distinct value, it's a conflict
        if len(values_seen) > 1:
            conflicts.append(FactConflict(
                fact_name=fact_name,
                values=list(values_seen.keys()),
                sources=[docs for docs in values_seen.values()],
                selected_value=...,  # highest confidence
                selection_reason="highest_confidence"
            ))

    return conflicts
```

### 1.5 Implement Gate Evaluation

**Gate Rules (from EVALUATION_DASHBOARD_PLAN.md):**

| Status | Conditions |
|--------|------------|
| PASS | No missing critical facts AND no conflicts |
| WARN | 1-2 missing critical facts OR 1-2 conflicts OR tokens > 40K |
| FAIL | >2 missing critical facts OR >2 conflicts OR tokens > 60K |

**Logic:**
```python
def evaluate_gate(self, facts, conflicts, critical_facts) -> ReconciliationGate:
    # Check missing critical facts
    present_facts = {f.name for f in facts.facts}
    missing = [f for f in critical_facts if f not in present_facts]

    # Count conflicts
    conflict_count = len(conflicts)

    # Estimate tokens (rough: 4 chars per token)
    token_estimate = sum(len(str(f.value) or "") for f in facts.facts) // 4

    # Calculate provenance coverage
    with_provenance = sum(1 for f in facts.facts if f.selected_from.text_quote)
    coverage = with_provenance / len(facts.facts) if facts.facts else 0

    # Determine status
    reasons = []
    if len(missing) > 2 or conflict_count > 2 or token_estimate > 60000:
        status = GateStatus.FAIL
        if len(missing) > 2:
            reasons.append(f"{len(missing)} critical facts missing")
        if conflict_count > 2:
            reasons.append(f"{conflict_count} fact conflicts")
        if token_estimate > 60000:
            reasons.append(f"Token estimate ({token_estimate}) exceeds 60K limit")
    elif missing or conflicts or token_estimate > 40000:
        status = GateStatus.WARN
        # ... add reasons
    else:
        status = GateStatus.PASS
        reasons.append("All critical facts present, no conflicts")

    return ReconciliationGate(
        status=status,
        missing_critical_facts=missing,
        conflict_count=conflict_count,
        provenance_coverage=coverage,
        estimated_tokens=token_estimate,
        reasons=reasons
    )
```

### 1.6 Update ReconciliationStage to Use Service

**File:** `src/context_builder/pipeline/claim_stages/reconciliation.py`

Replace the stub with a call to `ReconciliationService`:

```python
def run(self, context: ClaimContext) -> ClaimContext:
    # ... existing skip logic ...

    # Create service (storage from context)
    storage = FileStorage(context.workspace_path)
    aggregation = AggregationService(storage)
    reconciliation = ReconciliationService(storage, aggregation)

    # Run reconciliation
    result = reconciliation.reconcile(context.claim_id, context.run_id)

    # Store in context
    context.aggregated_facts = result.claim_facts.model_dump()
    context.reconciliation_report = result.report.model_dump()
    context.facts_run_id = result.claim_facts.run_id

    return context
```

### 1.7 Output File

**Path:** `{workspace}/claims/{claim_id}/context/reconciliation_report.json`

**Example:**
```json
{
  "claim_id": "65196",
  "run_id": "run_20260126_...",
  "generated_at": "2026-01-26T14:30:00Z",
  "gate": {
    "status": "warn",
    "missing_critical_facts": ["policy_end_date"],
    "conflict_count": 1,
    "provenance_coverage": 0.92,
    "estimated_tokens": 21000,
    "reasons": ["1 critical fact missing", "1 fact conflict detected"]
  },
  "conflicts": [
    {
      "fact_name": "odometer_km",
      "values": ["74200", "74410"],
      "sources": [["doc_001"], ["doc_002"]],
      "selected_value": "74200",
      "selection_reason": "highest_confidence"
    }
  ],
  "fact_count": 185,
  "critical_facts_checked": ["policy_number", "policy_start_date", "policy_end_date", ...],
  "critical_facts_present": ["policy_number", "policy_start_date", ...]
}
```

---

## Phase 2: CLI Integration

### 2.1 Add `reconcile` Command

**File:** `src/context_builder/cli.py`

Add a new command for claim-level reconciliation:

```bash
python -m context_builder.cli reconcile --claim-id 65196
python -m context_builder.cli reconcile --claim-id 65196 --run-id run_20260126_...
python -m context_builder.cli reconcile --claim-id 65196 --dry-run  # Show what would happen
```

**Implementation:**
```python
@app.command()
def reconcile(
    claim_id: str = typer.Option(..., "--claim-id", "-c", help="Claim ID to reconcile"),
    run_id: Optional[str] = typer.Option(None, "--run-id", "-r", help="Specific run ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
):
    """Run reconciliation for a claim: aggregate facts, detect conflicts, evaluate gate."""
    storage = FileStorage(get_active_workspace_path())
    aggregation = AggregationService(storage)
    reconciliation = ReconciliationService(storage, aggregation)

    result = reconciliation.reconcile(claim_id, run_id)

    # Print summary
    gate = result.report.gate
    console.print(f"[bold]Reconciliation for {claim_id}[/bold]")
    console.print(f"Status: {gate.status.value.upper()}")
    console.print(f"Facts: {result.report.fact_count}")
    console.print(f"Conflicts: {gate.conflict_count}")
    console.print(f"Missing critical: {len(gate.missing_critical_facts)}")

    if not dry_run:
        reconciliation.write_reconciliation_report(claim_id, result.report)
        console.print(f"[green]Report written to claim context[/green]")
```

### 2.2 Keep Claim-Level Stages Separate

The existing `pipeline` command runs document-level stages. Keep claim-level stages as separate commands:

| Command | Scope | Stages |
|---------|-------|--------|
| `pipeline` | Document | ingestion, classification, extraction |
| `reconcile` | Claim | fact aggregation + conflict detection + gate |
| `assess` (future) | Claim | load facts + run assessment |

---

## Phase 3: API Integration

### 3.1 Add Reconciliation Endpoint

**File:** `src/context_builder/api/routers/claims.py`

```python
@router.post("/{claim_id}/reconcile")
async def run_reconciliation(
    claim_id: str,
    run_id: Optional[str] = None,
    storage: FileStorage = Depends(get_storage),
):
    """Trigger reconciliation for a claim."""
    aggregation = AggregationService(storage)
    reconciliation = ReconciliationService(storage, aggregation)

    result = reconciliation.reconcile(claim_id, run_id)
    reconciliation.write_reconciliation_report(claim_id, result.report)

    return {
        "claim_id": claim_id,
        "status": result.report.gate.status.value,
        "fact_count": result.report.fact_count,
        "conflicts": result.report.gate.conflict_count,
        "report_path": f"claims/{claim_id}/context/reconciliation_report.json"
    }

@router.get("/{claim_id}/reconciliation-report")
async def get_reconciliation_report(
    claim_id: str,
    storage: FileStorage = Depends(get_storage),
):
    """Get the latest reconciliation report for a claim."""
    report_path = storage.get_claim_path(claim_id) / "context" / "reconciliation_report.json"
    if not report_path.exists():
        raise HTTPException(404, "No reconciliation report found")
    return json.loads(report_path.read_text())
```

---

## Phase 4: Aggregation for Dashboard

### 4.1 Run-Level Summary Aggregation

Create a script/service to aggregate all `reconciliation_report.json` files from a run into a summary.

**Output:** `{workspace}/runs/{run_id}/eval/reconciliation_gate_eval.json`

**Logic:**
```python
def aggregate_reconciliation_evals(run_id: str) -> dict:
    """Aggregate all reconciliation reports from a run."""
    reports = []
    for claim_dir in claims_dir.iterdir():
        report_path = claim_dir / "context" / "reconciliation_report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text())
            if report.get("run_id") == run_id:
                reports.append(report)

    # Build summary
    return {
        "run_id": run_id,
        "summary": {
            "claims_total": len(reports),
            "pass_count": sum(1 for r in reports if r["gate"]["status"] == "pass"),
            "warn_count": sum(1 for r in reports if r["gate"]["status"] == "warn"),
            "fail_count": sum(1 for r in reports if r["gate"]["status"] == "fail"),
            "avg_missing_critical": mean(len(r["gate"]["missing_critical_facts"]) for r in reports),
            "avg_conflicts": mean(r["gate"]["conflict_count"] for r in reports),
            "avg_provenance": mean(r["gate"]["provenance_coverage"] for r in reports),
        },
        "top_missing_facts": count_top_missing(reports),
        "top_conflicts": count_top_conflicts(reports),
        "problem_claims": [r for r in reports if r["gate"]["status"] != "pass"],
    }
```

### 4.2 CLI Command for Aggregation

```bash
python -m context_builder.cli eval aggregate-reconciliation --run-id run_20260126_...
```

---

## Phase 5: UI Integration

### 5.1 Add Reconciliation Gate Section to Evaluation Page

**File:** `ui/src/components/evaluation/EvaluationPage.tsx`

Add a new section (not a tab) within the Assessment tab:

```tsx
// Inside AssessmentEvalView
<Section title="Claim Reconciliation Gate">
  <ReconciliationGateSummary data={reconciliationEval} />
</Section>
```

### 5.2 ReconciliationGateSummary Component

**File:** `ui/src/components/evaluation/ReconciliationGateSummary.tsx` (new)

**KPI Cards:**
- Claims evaluated
- Pass rate
- Avg missing critical facts
- Avg conflicts
- Avg provenance coverage

**Tables:**
- Problem Claims (claim_id, status, missing, conflicts)
- Top Missing Facts (fact name, frequency)
- Top Conflicts (fact name, frequency)

### 5.3 API Extension

Either extend `/api/assessment/evals/latest` to include `reconciliation_gate_summary`, or add:

```
GET /api/quality-gates/claims/latest
```

---

## Implementation Order

### Sprint 1: Core Reconciliation (Phase 1)
1. [ ] Create `schemas/reconciliation.py` with Pydantic models
2. [ ] Create `api/services/reconciliation.py` with `ReconciliationService`
3. [ ] Implement `load_critical_facts_spec()` - read extraction specs
4. [ ] Implement `detect_conflicts()` - find value mismatches
5. [ ] Implement `evaluate_gate()` - pass/warn/fail logic
6. [ ] Implement `write_reconciliation_report()` - output JSON
7. [ ] Update `claim_stages/reconciliation.py` to use service
8. [ ] Test with existing claims (65196, 65128, 65157, 65258)

### Sprint 2: CLI (Phase 2)
9. [ ] Add `reconcile` command to CLI
10. [ ] Add `--dry-run` option
11. [ ] Test CLI with all claims

### Sprint 3: API (Phase 3)
12. [ ] Add `POST /claims/{id}/reconcile` endpoint
13. [ ] Add `GET /claims/{id}/reconciliation-report` endpoint
14. [ ] Test from UI manually

### Sprint 4: Dashboard (Phases 4 & 5)
15. [ ] Create aggregation script for run-level summaries
16. [ ] Add `eval aggregate-reconciliation` CLI command
17. [ ] Create `ReconciliationGateSummary` UI component
18. [ ] Add section to Evaluation page
19. [ ] Wire up API endpoint

---

## Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| CREATE | `src/context_builder/schemas/reconciliation.py` | Pydantic models for reconciliation |
| CREATE | `src/context_builder/api/services/reconciliation.py` | ReconciliationService |
| MODIFY | `src/context_builder/pipeline/claim_stages/reconciliation.py` | Replace stub with service call |
| MODIFY | `src/context_builder/cli.py` | Add `reconcile` command |
| MODIFY | `src/context_builder/api/routers/claims.py` | Add reconciliation endpoints |
| CREATE | `ui/src/components/evaluation/ReconciliationGateSummary.tsx` | UI component |
| MODIFY | `ui/src/components/evaluation/EvaluationPage.tsx` | Add reconciliation section |

---

## Testing Strategy

1. **Unit Tests:**
   - `test_reconciliation_service.py` - test conflict detection, gate evaluation
   - Test with mock extraction data

2. **Integration Tests:**
   - Run reconciliation on existing claims (65196, 65128, 65157, 65258)
   - Verify `reconciliation_report.json` output

3. **Manual QA:**
   - CLI: `python -m context_builder.cli reconcile --claim-id 65196`
   - API: `curl -X POST http://localhost:8000/api/claims/65196/reconcile`
   - UI: Check Evaluation page renders reconciliation section

---

## Open Items (Resolved)

| Question | Decision |
|----------|----------|
| Critical facts source | Derived from extraction specs (`required_fields`) |
| Conflict definition | Same fact, different values = conflict |
| Gate blocking | Advisory only (does not block assessment) |
| CLI model | Separate `reconcile` command |
| Claim vs doc stages | Separate (document pipeline vs claim commands) |
