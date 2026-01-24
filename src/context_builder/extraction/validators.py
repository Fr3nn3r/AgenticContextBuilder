"""Extraction validators for post-extraction quality checks.

Validates extraction results by checking business rules like
financial reconciliation for cost estimates.
"""

import json
from dataclasses import dataclass
from typing import List, Optional

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


def validate_cost_estimate(
    result: ExtractionResult,
    tolerance: float = 5.0,
) -> List[ValidationResult]:
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

    Args:
        result: Extraction result to validate

    Returns:
        List of validation results (empty if no validation rules for doc type)
    """
    doc_type = result.doc.doc_type

    if doc_type == "cost_estimate":
        return validate_cost_estimate(result)

    # Other doc types: no validation rules yet
    return []


def attach_validation_meta(
    result: ExtractionResult,
    validations: List[ValidationResult],
) -> ExtractionResult:
    """
    Attach validation results to extraction result metadata.

    Args:
        result: Extraction result to update
        validations: List of validation results

    Returns:
        Updated extraction result with validation metadata
    """
    result.extraction_meta = result.extraction_meta or {}
    result.extraction_meta["validation"] = {
        "passed": all(v.passed for v in validations),
        "checks": [
            {
                "rule": v.rule,
                "passed": v.passed,
                "expected": v.expected,
                "actual": v.actual,
                "message": v.message,
            }
            for v in validations
        ]
    }
    return result
