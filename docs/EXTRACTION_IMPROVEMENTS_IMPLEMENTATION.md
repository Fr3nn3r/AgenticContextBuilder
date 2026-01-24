# Extraction Improvements Implementation Plan (Pragmatic Scope)

Implements 4 high-ROI items from `docs/EXTRACTION_IMPROVEMENTS_PLAN.md`.

## Scope Decision

**In Scope (4 items):**
1. Evidence Offset Resolution - Fill 0/0 char offsets
2. Simple Evidence Flag - Binary `has_verified_evidence`
3. Cost Estimate Validation - Financial reconciliation for cost estimates
4. Backfill CLI - Reprocess existing extractions

**Out of Scope (deferred):**
- Normalizers - Keep as stubs, use prompts for formatting
- Table per-item provenance - Too complex, current placeholders work
- Source metadata in provenance - Redundant (already at result level)
- Evidence requirements per field - Current quality gate sufficient
- Input context hashing - Already have input_hashes

---

## Phase 1: Schema Changes (Minimal)

### 1.1 Add Evidence Flag and Validation Meta

**File: `src/context_builder/schemas/extraction_result.py`**

Add to `FieldProvenance`:
```python
match_quality: Optional[str] = Field(
    default=None,
    description="How quote was matched: exact/case_insensitive/normalized/not_found"
)
```

Add to `ExtractedField`:
```python
has_verified_evidence: bool = Field(
    default=False,
    description="True if provenance has verified char offsets"
)
```

Add to `ExtractionResult`:
```python
_extraction_meta: Optional[Dict[str, Any]] = Field(
    default=None,
    description="Validation results and diagnostics"
)
```

---

## Phase 2: Evidence Resolution

### 2.1 Evidence Offset Resolution

**New file: `src/context_builder/extraction/evidence_resolver.py`**

```python
from typing import List, Optional
from context_builder.schemas.extraction_result import (
    ExtractionResult, ExtractedField, FieldProvenance, PageContent
)
from context_builder.extraction.page_parser import find_text_position


def resolve_evidence_offsets(result: ExtractionResult) -> ExtractionResult:
    """
    Post-process extraction to fill missing char offsets.

    For each field with provenance where char_start=0 and char_end=0,
    attempt to locate the text_quote in the corresponding page.

    Updates:
    - provenance.char_start / char_end
    - provenance.match_quality
    - field.has_verified_evidence
    """
    pages_by_num = {p.page: p for p in result.pages}

    for field in result.fields:
        field_verified = False

        for prov in field.provenance:
            # Skip if already has offsets
            if prov.char_start > 0 or prov.char_end > 0:
                prov.match_quality = prov.match_quality or "exact"
                field_verified = True
                continue

            # Skip placeholder quotes
            if prov.text_quote.startswith("[") and prov.text_quote.endswith("]"):
                prov.match_quality = "placeholder"
                continue

            # Try to find quote in page
            page = pages_by_num.get(prov.page)
            if not page:
                prov.match_quality = "page_not_found"
                continue

            position = find_text_position(page.text, prov.text_quote)
            if position:
                prov.char_start = position[0]
                prov.char_end = position[1]
                prov.match_quality = "resolved"
                field_verified = True
            else:
                prov.match_quality = "not_found"

        field.has_verified_evidence = field_verified

    return result
```

### 2.2 Integration Point

**File: `src/context_builder/extraction/extractors/generic.py`**

Add at end of `extract()` method:
```python
from context_builder.extraction.evidence_resolver import resolve_evidence_offsets

# ... existing extraction code ...

result = ExtractionResult(...)
result = resolve_evidence_offsets(result)
return result
```

Same pattern for `nsa_guarantee.py`, `nsa_cost_estimate.py`, `nsa_service_history.py`.

---

## Phase 3: Cost Estimate Validation

### 3.1 Validation Module

**New file: `src/context_builder/extraction/validators.py`**

```python
from dataclasses import dataclass
from typing import List, Optional
import json

from context_builder.schemas.extraction_result import ExtractionResult
from context_builder.extraction.normalizers import safe_float


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    rule: str
    passed: bool
    expected: Optional[str] = None
    actual: Optional[str] = None
    message: Optional[str] = None


def validate_cost_estimate(result: ExtractionResult, tolerance: float = 5.0) -> List[ValidationResult]:
    """
    Validate cost estimate totals reconcile.

    Checks:
    1. Sum of line items ≈ subtotal_before_vat
    2. subtotal + vat_amount ≈ total_amount_incl_vat

    Args:
        result: Extraction result for a cost_estimate document
        tolerance: Allowed difference in CHF (default 5.0)

    Returns:
        List of validation results
    """
    results = []

    # Get fields by name
    fields = {f.name: f for f in result.fields}

    # Get line items
    line_items_field = fields.get("line_items")
    if not line_items_field or not line_items_field.normalized_value:
        return [ValidationResult(
            rule="line_items_present",
            passed=False,
            message="No line items found"
        )]

    try:
        line_items = json.loads(line_items_field.normalized_value)
    except json.JSONDecodeError:
        return [ValidationResult(
            rule="line_items_valid_json",
            passed=False,
            message="Line items is not valid JSON"
        )]

    # Sum line item totals
    items_sum = sum(safe_float(item.get("total_price", 0)) for item in line_items)

    # Check vs subtotal
    subtotal_field = fields.get("subtotal_before_vat")
    if subtotal_field and subtotal_field.normalized_value:
        subtotal = safe_float(subtotal_field.normalized_value)
        diff = abs(items_sum - subtotal)
        results.append(ValidationResult(
            rule="items_sum_matches_subtotal",
            passed=diff <= tolerance,
            expected=f"{subtotal:.2f}",
            actual=f"{items_sum:.2f}",
            message=f"Difference: {diff:.2f} CHF" if diff > tolerance else None
        ))

    # Check subtotal + VAT = total
    vat_field = fields.get("vat_amount")
    total_field = fields.get("total_amount_incl_vat")

    if subtotal_field and vat_field and total_field:
        subtotal = safe_float(subtotal_field.normalized_value)
        vat = safe_float(vat_field.normalized_value)
        total = safe_float(total_field.normalized_value)

        expected_total = subtotal + vat
        diff = abs(expected_total - total)
        results.append(ValidationResult(
            rule="subtotal_plus_vat_equals_total",
            passed=diff <= tolerance,
            expected=f"{expected_total:.2f}",
            actual=f"{total:.2f}",
            message=f"Difference: {diff:.2f} CHF" if diff > tolerance else None
        ))

    return results


def validate_extraction(result: ExtractionResult) -> List[ValidationResult]:
    """
    Run doc-type-specific validation.

    Dispatches based on result.doc.doc_type.
    """
    doc_type = result.doc.doc_type

    if doc_type == "cost_estimate":
        return validate_cost_estimate(result)

    # Other doc types: no validation rules yet
    return []
```

### 3.2 Integration

**File: `src/context_builder/extraction/extractors/nsa_cost_estimate.py`**

Add at end of `extract()`:
```python
from context_builder.extraction.validators import validate_extraction

# ... existing extraction code ...

result = ExtractionResult(...)
result = resolve_evidence_offsets(result)

# Run validation
validations = validate_extraction(result)
result._extraction_meta = {
    "validation": {
        "passed": all(v.passed for v in validations),
        "checks": [
            {"rule": v.rule, "passed": v.passed, "expected": v.expected,
             "actual": v.actual, "message": v.message}
            for v in validations
        ]
    }
}

return result
```

---

## Phase 4: Backfill CLI

### 4.1 Backfill Module

**New file: `src/context_builder/extraction/backfill.py`**

```python
from pathlib import Path
from typing import Dict, Any, Optional
import json

from context_builder.schemas.extraction_result import ExtractionResult, PageContent
from context_builder.extraction.evidence_resolver import resolve_evidence_offsets
from context_builder.extraction.validators import validate_extraction


def backfill_extraction(
    extraction_path: Path,
    pages_path: Path,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Backfill evidence for a single extraction file.

    Args:
        extraction_path: Path to *.extraction.json
        pages_path: Path to pages.json
        dry_run: If True, don't write changes

    Returns:
        Stats about what was updated
    """
    # Load extraction
    with open(extraction_path) as f:
        data = json.load(f)

    result = ExtractionResult.model_validate(data)

    # Load pages if not embedded
    if not result.pages:
        with open(pages_path) as f:
            pages_data = json.load(f)
        result.pages = [PageContent.model_validate(p) for p in pages_data]

    # Count before
    before_verified = sum(1 for f in result.fields if getattr(f, 'has_verified_evidence', False))

    # Resolve offsets
    result = resolve_evidence_offsets(result)

    # Run validation
    validations = validate_extraction(result)
    result._extraction_meta = result._extraction_meta or {}
    result._extraction_meta["validation"] = {
        "passed": all(v.passed for v in validations),
        "checks": [{"rule": v.rule, "passed": v.passed} for v in validations]
    }

    # Count after
    after_verified = sum(1 for f in result.fields if f.has_verified_evidence)

    stats = {
        "file": str(extraction_path),
        "fields_total": len(result.fields),
        "verified_before": before_verified,
        "verified_after": after_verified,
        "validation_passed": result._extraction_meta["validation"]["passed"],
        "dry_run": dry_run
    }

    if not dry_run:
        with open(extraction_path, "w") as f:
            json.dump(result.model_dump(exclude_none=True), f, indent=2, ensure_ascii=False)

    return stats


def backfill_workspace(
    claims_dir: Path,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Backfill all extractions in a workspace.

    Args:
        claims_dir: Path to claims directory
        dry_run: If True, don't write changes

    Returns:
        Aggregate stats
    """
    stats = {"processed": 0, "improved": 0, "errors": []}

    for claim_dir in claims_dir.iterdir():
        if not claim_dir.is_dir():
            continue

        docs_dir = claim_dir / "docs"
        if not docs_dir.exists():
            continue

        for doc_dir in docs_dir.iterdir():
            if not doc_dir.is_dir():
                continue

            # Find extraction files
            for ext_file in doc_dir.glob("*.extraction.json"):
                pages_file = doc_dir / "pages.json"
                if not pages_file.exists():
                    continue

                try:
                    result = backfill_extraction(ext_file, pages_file, dry_run)
                    stats["processed"] += 1
                    if result["verified_after"] > result["verified_before"]:
                        stats["improved"] += 1
                except Exception as e:
                    stats["errors"].append({"file": str(ext_file), "error": str(e)})

    return stats
```

### 4.2 CLI Subcommand

**File: `src/context_builder/cli.py`**

Add subcommand:
```python
# Add to argument parser setup
backfill_parser = subparsers.add_parser(
    "backfill-evidence",
    help="Reprocess extractions to fill missing evidence offsets"
)
backfill_parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Show what would be updated without writing"
)

# Add handler
def handle_backfill(args):
    from context_builder.extraction.backfill import backfill_workspace
    from context_builder.api.services.workspace import get_active_workspace

    workspace = get_active_workspace()
    claims_dir = Path(workspace.path) / "claims"

    print(f"Backfilling evidence in: {claims_dir}")
    if args.dry_run:
        print("(dry run - no changes will be written)")

    stats = backfill_workspace(claims_dir, dry_run=args.dry_run)

    print(f"\nProcessed: {stats['processed']} extractions")
    print(f"Improved:  {stats['improved']} extractions")
    if stats['errors']:
        print(f"Errors:    {len(stats['errors'])}")
        for err in stats['errors'][:5]:
            print(f"  - {err['file']}: {err['error']}")
```

---

## Files Summary

### New Files (3)
| File | Purpose |
|------|---------|
| `src/context_builder/extraction/evidence_resolver.py` | Offset resolution + evidence flag |
| `src/context_builder/extraction/validators.py` | Cost estimate validation |
| `src/context_builder/extraction/backfill.py` | Batch backfill logic |

### Modified Files (5)
| File | Changes |
|------|---------|
| `schemas/extraction_result.py` | Add match_quality, has_verified_evidence, _extraction_meta |
| `extraction/extractors/generic.py` | Call resolve_evidence_offsets |
| `extraction/extractors/nsa_guarantee.py` | Call resolve_evidence_offsets |
| `extraction/extractors/nsa_cost_estimate.py` | Call resolve + validate |
| `cli.py` | Add backfill-evidence subcommand |

---

## Tests

**New file: `tests/unit/test_evidence_resolver.py`**
- Test offset resolution with various match scenarios
- Test has_verified_evidence flag setting
- Test placeholder quote handling

**New file: `tests/unit/test_validators.py`**
- Test cost estimate validation with valid data
- Test tolerance handling
- Test missing field scenarios

---

## Verification

1. **Run tests:**
   ```bash
   python -m pytest tests/unit/test_evidence_resolver.py tests/unit/test_validators.py -v
   ```

2. **Test backfill (dry run):**
   ```bash
   python -m context_builder.cli backfill-evidence --dry-run
   ```

3. **Run extraction and check output:**
   ```bash
   python -m context_builder.cli extract --model gpt-4o
   # Check *.extraction.json has has_verified_evidence and _extraction_meta
   ```
