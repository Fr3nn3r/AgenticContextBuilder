"""Tests for extraction validators."""

import json
import pytest

from context_builder.extraction.validators import (
    validate_cost_estimate,
    validate_extraction,
    attach_validation_meta,
    ValidationResult,
)
from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    PageContent,
    DocumentMetadata,
    ExtractionRunMetadata,
    QualityGate,
)


def make_field(
    name: str,
    value: str,
    normalized_value: str | None = None,
) -> ExtractedField:
    """Create a test field."""
    return ExtractedField(
        name=name,
        value=value,
        normalized_value=normalized_value or value,
        confidence=0.9,
        status="present",
        provenance=[],
        value_is_placeholder=False,
        has_verified_evidence=False,
    )


def make_result(
    fields: list[ExtractedField],
    doc_type: str = "cost_estimate",
) -> ExtractionResult:
    """Create a test extraction result."""
    import hashlib
    return ExtractionResult(
        schema_version="extraction_result_v1",
        run=ExtractionRunMetadata(
            run_id="test_run",
            extractor_version="v1.0.0",
            model="gpt-4o",
            prompt_version="v1",
        ),
        doc=DocumentMetadata(
            doc_id="doc_001",
            claim_id="claim_001",
            doc_type=doc_type,
            doc_type_confidence=0.95,
            language="de",
            page_count=1,
        ),
        pages=[PageContent(
            page=1,
            text="Test content",
            text_md5=hashlib.md5(b"Test content").hexdigest(),
        )],
        fields=fields,
        quality_gate=QualityGate(status="pass"),
    )


class TestValidateCostEstimate:
    """Tests for cost estimate validation."""

    def test_valid_totals(self):
        """Should pass when totals reconcile."""
        line_items = [
            {"description": "Labor", "total_price": 500.0},
            {"description": "Parts", "total_price": 300.0},
        ]
        fields = [
            make_field("line_items", "2 items", json.dumps(line_items)),
            make_field("subtotal_before_vat", "800.00", "800.00"),
            make_field("vat_amount", "64.00", "64.00"),
            make_field("total_amount_incl_vat", "864.00", "864.00"),
        ]
        result = make_result(fields)

        validations = validate_cost_estimate(result)

        assert len(validations) == 2
        assert all(v.passed for v in validations)

    def test_items_sum_mismatch(self):
        """Should fail when line items don't sum to subtotal."""
        line_items = [
            {"description": "Labor", "total_price": 500.0},
            {"description": "Parts", "total_price": 300.0},
        ]
        fields = [
            make_field("line_items", "2 items", json.dumps(line_items)),
            make_field("subtotal_before_vat", "1000.00", "1000.00"),  # Wrong
        ]
        result = make_result(fields)

        validations = validate_cost_estimate(result)

        items_check = next(v for v in validations if v.rule == "items_sum_matches_subtotal")
        assert items_check.passed is False
        assert items_check.expected == "1000.00"
        assert items_check.actual == "800.00"

    def test_vat_total_mismatch(self):
        """Should fail when subtotal + VAT doesn't equal total."""
        line_items = [{"description": "Labor", "total_price": 800.0}]
        fields = [
            make_field("line_items", "1 item", json.dumps(line_items)),
            make_field("subtotal_before_vat", "800.00", "800.00"),
            make_field("vat_amount", "64.00", "64.00"),
            make_field("total_amount_incl_vat", "900.00", "900.00"),  # Wrong
        ]
        result = make_result(fields)

        validations = validate_cost_estimate(result)

        vat_check = next(v for v in validations if v.rule == "subtotal_plus_vat_equals_total")
        assert vat_check.passed is False
        assert vat_check.expected == "864.00"
        assert vat_check.actual == "900.00"

    def test_within_tolerance(self):
        """Should pass when difference is within tolerance."""
        line_items = [{"description": "Labor", "total_price": 798.0}]  # 2 CHF off
        fields = [
            make_field("line_items", "1 item", json.dumps(line_items)),
            make_field("subtotal_before_vat", "800.00", "800.00"),
        ]
        result = make_result(fields)

        validations = validate_cost_estimate(result, tolerance=5.0)

        items_check = next(v for v in validations if v.rule == "items_sum_matches_subtotal")
        assert items_check.passed is True

    def test_missing_line_items(self):
        """Should return error when line items missing."""
        fields = [
            make_field("subtotal_before_vat", "800.00", "800.00"),
        ]
        result = make_result(fields)

        validations = validate_cost_estimate(result)

        assert len(validations) == 1
        assert validations[0].rule == "line_items_present"
        assert validations[0].passed is False

    def test_invalid_line_items_json(self):
        """Should return error when line items is invalid JSON."""
        fields = [
            make_field("line_items", "invalid", "not valid json"),
        ]
        result = make_result(fields)

        validations = validate_cost_estimate(result)

        assert len(validations) == 1
        assert validations[0].rule == "line_items_valid_json"
        assert validations[0].passed is False

    def test_handles_string_prices(self):
        """Should handle prices as strings (from LLM)."""
        line_items = [
            {"description": "Labor", "total_price": "500.00"},
            {"description": "Parts", "total_price": "300.00 CHF"},
        ]
        fields = [
            make_field("line_items", "2 items", json.dumps(line_items)),
            make_field("subtotal_before_vat", "CHF 800.00", "800.00"),
        ]
        result = make_result(fields)

        validations = validate_cost_estimate(result)

        items_check = next(v for v in validations if v.rule == "items_sum_matches_subtotal")
        assert items_check.passed is True


class TestValidateExtraction:
    """Tests for validate_extraction dispatcher."""

    def test_dispatches_to_cost_estimate(self):
        """Should run cost estimate validation for cost_estimate docs."""
        line_items = [{"total_price": 100.0}]
        fields = [
            make_field("line_items", "1 item", json.dumps(line_items)),
            make_field("subtotal_before_vat", "100.00", "100.00"),
        ]
        result = make_result(fields, doc_type="cost_estimate")

        validations = validate_extraction(result)

        assert len(validations) >= 1
        assert any(v.rule == "items_sum_matches_subtotal" for v in validations)

    def test_returns_empty_for_unknown_type(self):
        """Should return empty list for unknown doc types."""
        fields = [make_field("some_field", "value")]
        result = make_result(fields, doc_type="unknown_type")

        validations = validate_extraction(result)

        assert validations == []


class TestAttachValidationMeta:
    """Tests for attach_validation_meta function."""

    def test_attaches_validation_results(self):
        """Should attach validation results to extraction_meta."""
        fields = [make_field("test", "value")]
        result = make_result(fields, doc_type="test")

        validations = [
            ValidationResult(rule="test_rule", passed=True),
            ValidationResult(rule="another_rule", passed=False, message="Failed"),
        ]

        result = attach_validation_meta(result, validations)

        assert result.extraction_meta is not None
        assert result.extraction_meta["validation"]["passed"] is False
        assert len(result.extraction_meta["validation"]["checks"]) == 2

    def test_all_passed_is_true(self):
        """Should set passed=True when all validations pass."""
        fields = [make_field("test", "value")]
        result = make_result(fields, doc_type="test")

        validations = [
            ValidationResult(rule="rule1", passed=True),
            ValidationResult(rule="rule2", passed=True),
        ]

        result = attach_validation_meta(result, validations)

        assert result.extraction_meta["validation"]["passed"] is True

    def test_preserves_existing_meta(self):
        """Should preserve existing extraction_meta fields."""
        fields = [make_field("test", "value")]
        result = make_result(fields, doc_type="test")
        result.extraction_meta = {"existing": "value"}

        validations = [ValidationResult(rule="test", passed=True)]
        result = attach_validation_meta(result, validations)

        assert result.extraction_meta["existing"] == "value"
        assert "validation" in result.extraction_meta
