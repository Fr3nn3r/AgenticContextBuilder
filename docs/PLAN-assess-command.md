# Implementation Plan: `assess` CLI Command

## Overview

Create a new `assess` CLI command that combines **reconciliation** and **assessment** into a single operation, producing a claim decision.

```bash
# Run full assess (reconcile + assess) for a claim
python -m context_builder.cli assess --claim-id 65196

# Force re-reconciliation even if recent reconciliation exists
python -m context_builder.cli assess --claim-id 65196 --force-reconcile

# Assess all claims in workspace
python -m context_builder.cli assess --all

# Dry run - show what would happen
python -m context_builder.cli assess --claim-id 65196 --dry-run
```

---

## Architecture

### Current Flow (Separate Commands)
```
1. reconcile --claim-id 65196
   └── Creates claim_run, aggregates facts, writes reconciliation_report.json

2. (Manual step to run assessment via API or script)
   └── Reads claim_facts.json, runs LLM, writes assessment.json
```

### New Flow (Single Command)
```
assess --claim-id 65196
├── Step 1: Reconciliation (via ReconciliationService)
│   ├── Create claim_run
│   ├── Aggregate facts from extractions
│   ├── Detect conflicts
│   ├── Evaluate quality gate
│   └── Write claim_facts.json + reconciliation_report.json
│
├── Step 2: Assessment (via AssessmentProcessor)
│   ├── Load claim_facts.json from claim_run
│   ├── Load assessment prompt config
│   ├── Call LLM with structured JSON output
│   ├── Validate response (7+ checks)
│   └── Write assessment.json to claim_run
│
└── Step 3: Update Manifest
    └── stages_completed = ["reconciliation", "assessment"]
```

---

## Files to Create

### 1. `src/context_builder/api/services/claim_assessment.py` (NEW)

**Purpose:** Orchestrates reconciliation + assessment for a claim.

```python
"""Claim assessment service - orchestrates reconciliation and assessment."""

class ClaimAssessmentService:
    """Service for running full claim assessment (reconcile + assess)."""

    def __init__(
        self,
        storage: FileStorage,
        reconciliation_service: ReconciliationService,
    ):
        self.storage = storage
        self.reconciliation = reconciliation_service
        self._assessment_processor = None  # Lazy init

    def assess(
        self,
        claim_id: str,
        force_reconcile: bool = False,
        on_token_update: Optional[Callable[[int, int], None]] = None,
    ) -> ClaimAssessmentResult:
        """Run full assessment for a claim.

        Steps:
        1. Run reconciliation (creates claim_run, aggregates facts)
        2. Load aggregated facts
        3. Run assessment processor
        4. Save assessment to claim_run
        5. Update manifest with stages_completed

        Args:
            claim_id: Claim to assess.
            force_reconcile: Force re-reconciliation even if recent exists.
            on_token_update: Callback for token usage updates.

        Returns:
            ClaimAssessmentResult with decision, payout, etc.
        """
        # Step 1: Reconciliation
        reconcile_result = self.reconciliation.reconcile(claim_id)
        if not reconcile_result.success:
            return ClaimAssessmentResult(
                claim_id=claim_id,
                success=False,
                error=f"Reconciliation failed: {reconcile_result.error}",
            )

        claim_run_id = reconcile_result.report.claim_run_id
        gate_status = reconcile_result.report.gate.status

        # Step 2: Load claim facts
        claim_facts = self._load_claim_facts(claim_id, claim_run_id)

        # Step 3: Load prompt config
        prompt_config = self._load_assessment_config()

        # Step 4: Build context and run assessment
        context = ClaimContext(
            claim_id=claim_id,
            run_id=claim_run_id,
            aggregated_facts=claim_facts,
        )

        processor = self._get_assessment_processor()
        assessment_result = processor.process(
            context=context,
            config=prompt_config,
            on_token_update=on_token_update,
        )

        # Step 5: Save assessment to claim_run
        self._save_assessment(claim_id, claim_run_id, assessment_result)

        # Step 6: Update manifest
        self._update_manifest_stages(claim_id, claim_run_id)

        return ClaimAssessmentResult(
            claim_id=claim_id,
            claim_run_id=claim_run_id,
            success=True,
            reconciliation=reconcile_result.report,
            assessment=assessment_result,
        )
```

**Key methods:**
- `assess(claim_id, force_reconcile=False)` - Main entry point
- `_load_claim_facts(claim_id, claim_run_id)` - Load from claim_run
- `_load_assessment_config()` - Load prompt.md from config
- `_save_assessment(claim_id, claim_run_id, result)` - Write to claim_run
- `_update_manifest_stages(claim_id, claim_run_id)` - Add "assessment" to stages

---

### 2. `src/context_builder/schemas/claim_assessment.py` (NEW)

**Purpose:** Pydantic models for claim assessment results.

```python
"""Schemas for claim assessment results."""

from typing import Optional
from pydantic import BaseModel

from context_builder.schemas.reconciliation import ReconciliationReport
from context_builder.schemas.assessment_response import AssessmentResponse


class ClaimAssessmentResult(BaseModel):
    """Result of a full claim assessment (reconcile + assess)."""

    claim_id: str
    claim_run_id: Optional[str] = None
    success: bool
    error: Optional[str] = None

    # Reconciliation output
    reconciliation: Optional[ReconciliationReport] = None

    # Assessment output
    assessment: Optional[AssessmentResponse] = None

    # Summary fields for CLI display
    decision: Optional[str] = None  # APPROVE, REJECT, REFER_TO_HUMAN
    confidence_score: Optional[float] = None
    final_payout: Optional[float] = None
    gate_status: Optional[str] = None  # pass, warn, fail
```

---

### 3. CLI Command Addition to `src/context_builder/cli.py`

**Add new `assess` subcommand** (in `setup_argparser()`):

```python
# ========== ASSESS SUBCOMMAND ==========
assess_parser = subparsers.add_parser(
    "assess",
    help="Run full claim assessment (reconciliation + assessment)",
    epilog="""
Runs the complete claim processing pipeline:
1. Reconciliation - Aggregate facts, detect conflicts, quality gate
2. Assessment - Run checks, calculate payout, produce decision

Output:
  claims/{claim_id}/claim_runs/{claim_run_id}/
    ├── manifest.json              # Updated with stages_completed
    ├── claim_facts.json           # Aggregated facts
    ├── reconciliation_report.json # Quality gate & conflicts
    └── assessment.json            # Decision & payout

Examples:
  %(prog)s assess --claim-id 65196              # Assess single claim
  %(prog)s assess --all                          # Assess all claims
  %(prog)s assess --claim-id 65196 --force-reconcile  # Force re-reconcile
  %(prog)s assess --claim-id 65196 --dry-run    # Preview only
    """,
    formatter_class=argparse.RawDescriptionHelpFormatter,
)

assess_parser.add_argument(
    "--claim-id",
    metavar="ID",
    help="Claim ID to assess (required unless --all)",
)
assess_parser.add_argument(
    "--all",
    action="store_true",
    dest="all_claims",
    help="Assess all claims in workspace",
)
assess_parser.add_argument(
    "--force-reconcile",
    action="store_true",
    help="Force re-reconciliation even if recent reconciliation exists",
)
assess_parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Preview assessment without running LLM calls",
)
assess_parser.add_argument(
    "-v", "--verbose", action="store_true", help="Enable verbose logging"
)
assess_parser.add_argument(
    "-q", "--quiet", action="store_true", help="Minimal console output"
)
```

**Add command handler** (in `main()`):

```python
elif args.command == "assess":
    # ========== ASSESS COMMAND ==========
    from context_builder.api.services.claim_assessment import ClaimAssessmentService
    from context_builder.api.services.reconciliation import ReconciliationService
    from context_builder.api.services.aggregation import AggregationService
    from context_builder.storage.filesystem import FileStorage

    # Validate args
    if not args.claim_id and not args.all_claims:
        print("[X] Error: Either --claim-id or --all is required")
        sys.exit(1)

    # Initialize services
    workspace = get_active_workspace()
    workspace_root = Path(workspace["path"]) if workspace else Path("output")
    storage = FileStorage(workspace_root)
    aggregation = AggregationService(storage)
    reconciliation = ReconciliationService(storage, aggregation)
    assessment_service = ClaimAssessmentService(storage, reconciliation)

    # Determine claims to process
    claim_ids = [args.claim_id] if args.claim_id else discover_all_claims(workspace_root)

    # Process each claim
    results = {"success": [], "failed": []}
    for claim_id in claim_ids:
        if args.dry_run:
            print(f"[DRY RUN] Would assess claim: {claim_id}")
            continue

        result = assessment_service.assess(
            claim_id=claim_id,
            force_reconcile=args.force_reconcile,
        )

        if result.success:
            results["success"].append(claim_id)
            if not args.quiet:
                # Color-coded output
                decision_color = {"APPROVE": "92", "REJECT": "91", "REFER_TO_HUMAN": "93"}
                color = decision_color.get(result.decision, "0")
                print(f"\n[OK] {claim_id}: \033[{color}m{result.decision}\033[0m")
                print(f"     Confidence: {result.confidence_score:.0%}")
                print(f"     Payout: CHF {result.final_payout:,.2f}")
                print(f"     Gate: {result.gate_status}")
        else:
            results["failed"].append(claim_id)
            print(f"[X] {claim_id}: {result.error}")

    # Summary
    if args.all_claims and not args.quiet:
        print(f"\n{'='*50}")
        print(f"ASSESSMENT SUMMARY")
        print(f"{'='*50}")
        print(f"  Successful: {len(results['success'])}")
        print(f"  Failed: {len(results['failed'])}")
```

---

## Files to Modify

### 1. `src/context_builder/schemas/claim_run.py`

**Update ClaimRunManifest** to include assessment metadata:

```python
class ClaimRunManifest(BaseModel):
    # ... existing fields ...

    # Add assessment tracking
    assessment_timestamp: Optional[datetime] = None
    assessment_prompt_version: Optional[str] = None
```

### 2. `src/context_builder/pipeline/claim_stages/assessment_processor.py`

**Minor updates:**
- Ensure `process()` can work with pre-aggregated facts (already does via `context.aggregated_facts`)
- Add logging for claim_run integration

### 3. `src/context_builder/storage/claim_run.py`

**Add convenience method:**

```python
def read_claim_facts(self, claim_run_id: str) -> Optional[dict]:
    """Read claim_facts.json from claim run."""
    return self.read_from_claim_run(claim_run_id, "claim_facts.json")

def write_assessment(self, claim_run_id: str, assessment: dict) -> Path:
    """Write assessment.json to claim run."""
    return self.write_to_claim_run(claim_run_id, "assessment.json", assessment)
```

---

## Output Structure

After running `assess --claim-id 65196`:

```
claims/65196/
├── claim_runs/
│   └── clm_20260128_143000_abc123/
│       ├── manifest.json           # stages_completed: ["reconciliation", "assessment"]
│       ├── claim_facts.json        # Aggregated facts
│       ├── reconciliation_report.json  # Gate status, conflicts
│       └── assessment.json         # Decision, payout, checks
└── context/
    └── assessment.json             # Copy for backward compat (optional)
```

---

## Backward Compatibility

1. **Legacy `context/` path**: Assessment also written to `context/assessment.json` for existing UI compatibility
2. **Standalone reconcile command**: Still works independently
3. **API endpoints**: Existing `/api/claims/{id}/assessment` reads from latest claim_run with fallback

---

## Implementation Order

1. **Create schemas** (`claim_assessment.py`) - Result types
2. **Create service** (`claim_assessment.py`) - Orchestration logic
3. **Update storage** (`claim_run.py`) - Convenience methods
4. **Add CLI command** (`cli.py`) - `assess` subcommand
5. **Test end-to-end** - Run on claim 65196
6. **Update API** (optional) - Add `/api/claims/{id}/assess` endpoint

---

## Testing Plan

### Unit Tests
- `test_claim_assessment_service.py`
  - Test successful assess flow
  - Test reconciliation failure handling
  - Test assessment validation (7+ checks)

### Integration Tests
- Run `assess --claim-id 65196`
- Verify all files created in claim_run
- Verify manifest has both stages
- Verify assessment has 11 checks (with JSON-only prompt)

---

## Success Criteria

1. Single command produces complete claim decision
2. All 11 checks present in assessment JSON
3. Claim run manifest shows `["reconciliation", "assessment"]`
4. Assessment stored in claim_run directory (not just context/)
5. Token usage logged via audit service

---

## Estimated Scope

| File | Action | Lines |
|------|--------|-------|
| `schemas/claim_assessment.py` | CREATE | ~50 |
| `api/services/claim_assessment.py` | CREATE | ~200 |
| `storage/claim_run.py` | MODIFY | ~20 |
| `cli.py` | MODIFY | ~100 |
| `tests/unit/test_claim_assessment.py` | CREATE | ~150 |

**Total: ~520 lines**

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Assessment takes too long | Add `--timeout` flag, default 5 min |
| Reconciliation gate fails | Continue to assessment with warning, let assessment handle data quality |
| LLM returns incomplete checks | Validation in AssessmentProcessor rejects <7 checks |
| Backward compat breaks | Write to both claim_run and context/ paths |
