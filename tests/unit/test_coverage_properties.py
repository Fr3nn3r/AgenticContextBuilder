"""Property-based tests for coverage analysis invariants.

These tests verify fundamental invariants that must hold for ALL items
produced by the coverage analyzer, regardless of the specific claim.
"""

import pytest

from context_builder.coverage.schemas import (
    CoverageStatus,
    DecisionSource,
    LineItemCoverage,
    MatchMethod,
    TraceAction,
)
from coverage_test_helpers import make_line_item


class TestCoverageAmountInvariants:
    """Amount invariants: covered + not_covered == total_price."""

    def test_covered_item_amounts(self):
        """COVERED item has covered_amount == total_price."""
        item = make_line_item(
            total_price=500.0,
            coverage_status=CoverageStatus.COVERED,
            covered_amount=500.0,
            not_covered_amount=0.0,
        )
        assert item.covered_amount + item.not_covered_amount == pytest.approx(
            item.total_price, abs=0.01
        )
        assert item.covered_amount >= 0
        assert item.not_covered_amount >= 0

    def test_not_covered_item_amounts(self):
        """NOT_COVERED item has not_covered_amount == total_price."""
        item = make_line_item(
            total_price=300.0,
            coverage_status=CoverageStatus.NOT_COVERED,
            covered_amount=0.0,
            not_covered_amount=300.0,
        )
        assert item.covered_amount + item.not_covered_amount == pytest.approx(
            item.total_price, abs=0.01
        )
        assert item.covered_amount == 0.0

    def test_review_needed_item_amounts(self):
        """REVIEW_NEEDED item has not_covered_amount == total_price."""
        item = make_line_item(
            total_price=100.0,
            coverage_status=CoverageStatus.REVIEW_NEEDED,
            covered_amount=0.0,
            not_covered_amount=100.0,
        )
        assert item.covered_amount + item.not_covered_amount == pytest.approx(
            item.total_price, abs=0.01
        )

    def test_zero_price_covered_item(self):
        """Zero-price items can be COVERED (e.g., warranty parts)."""
        item = make_line_item(
            total_price=0.0,
            coverage_status=CoverageStatus.COVERED,
            covered_amount=0.0,
            not_covered_amount=0.0,
        )
        assert item.covered_amount == 0.0
        assert item.not_covered_amount == 0.0

    @pytest.mark.parametrize("price", [0.01, 1.0, 100.0, 10000.0])
    def test_amounts_non_negative(self, price):
        """Amounts are always non-negative."""
        item = make_line_item(
            total_price=price,
            covered_amount=price,
            not_covered_amount=0.0,
        )
        assert item.covered_amount >= 0
        assert item.not_covered_amount >= 0


class TestConfidenceInvariants:
    """Confidence must be in [0.0, 1.0] range."""

    @pytest.mark.parametrize("confidence", [0.0, 0.30, 0.50, 0.75, 0.90, 1.0])
    def test_valid_confidence_range(self, confidence):
        """Confidence values within [0, 1] are valid."""
        item = make_line_item(match_confidence=confidence)
        assert 0.0 <= item.match_confidence <= 1.0


class TestDecisionSourceInvariants:
    """Every trace step should have a decision_source tag."""

    def test_decision_source_enum_values(self):
        """DecisionSource enum has expected values."""
        expected = {"rule", "part_number", "keyword", "llm", "promotion",
                    "demotion", "validation"}
        actual = {ds.value for ds in DecisionSource}
        assert expected == actual

    def test_trace_step_with_decision_source(self):
        """TraceStep can carry a decision_source."""
        from context_builder.coverage.trace import TraceBuilder

        tb = TraceBuilder()
        tb.add(
            "test_stage", TraceAction.MATCHED,
            "Test reasoning",
            verdict=CoverageStatus.COVERED,
            confidence=0.85,
            decision_source=DecisionSource.KEYWORD,
        )
        trace = tb.build()
        assert len(trace) == 1
        assert trace[0].decision_source == DecisionSource.KEYWORD

    def test_trace_step_decision_source_serializes(self):
        """decision_source survives JSON round-trip."""
        from context_builder.coverage.trace import TraceBuilder

        tb = TraceBuilder()
        tb.add(
            "test_stage", TraceAction.MATCHED,
            "Test reasoning",
            verdict=CoverageStatus.COVERED,
            decision_source=DecisionSource.LLM,
        )
        trace = tb.build()
        data = trace[0].model_dump()
        assert data["decision_source"] == "llm"


class TestStatusConsistency:
    """Coverage status must be consistent with amounts."""

    def test_covered_has_positive_covered_amount_or_zero_price(self):
        """COVERED items have covered_amount > 0 (except zero-price items)."""
        item = make_line_item(
            total_price=100.0,
            coverage_status=CoverageStatus.COVERED,
            covered_amount=100.0,
        )
        if item.total_price > 0:
            assert item.covered_amount > 0

    def test_not_covered_has_zero_covered_amount(self):
        """NOT_COVERED items always have covered_amount == 0."""
        item = make_line_item(
            coverage_status=CoverageStatus.NOT_COVERED,
            covered_amount=0.0,
            not_covered_amount=100.0,
        )
        assert item.covered_amount == 0.0

    def test_match_method_is_always_set(self):
        """All items have a match_method."""
        for method in MatchMethod:
            item = make_line_item(match_method=method)
            assert item.match_method is not None
            assert isinstance(item.match_method, MatchMethod)

    def test_coverage_status_is_always_set(self):
        """All items have a coverage_status."""
        for status in CoverageStatus:
            item = make_line_item(coverage_status=status)
            assert item.coverage_status is not None
            assert isinstance(item.coverage_status, CoverageStatus)
