"""Tests for the coverage analyzer."""

import pytest

from context_builder.coverage.analyzer import AnalyzerConfig, CoverageAnalyzer
from context_builder.coverage.schemas import CoverageStatus, MatchMethod


class TestCoverageAnalyzer:
    """Tests for CoverageAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with LLM disabled for faster tests."""
        config = AnalyzerConfig(
            use_llm_fallback=False,  # Disable LLM for unit tests
        )
        return CoverageAnalyzer(config=config)

    @pytest.fixture
    def sample_line_items(self):
        """Sample line items for testing."""
        return [
            # Fee item - should be excluded by rule
            {"description": "HANDLING FEE", "item_type": "fee", "total_price": 50.0},
            # Disposal fee - excluded by pattern
            {"description": "ENTSORGUNG ALTOEL", "item_type": "parts", "total_price": 25.0},
            # Engine part - should match keyword
            {"description": "MOTOR DICHTUNG", "item_type": "parts", "total_price": 150.0},
            # Chassis part - should match keyword
            {"description": "STOSSDAEMPFER HINTEN", "item_type": "parts", "total_price": 400.0},
            # Labor for engine - should match keyword
            {"description": "MOTOR REPARATUR AW 3.0", "item_type": "labor", "total_price": 210.0},
            # Consumable - excluded
            {"description": "MOTOROEL 5W30", "item_type": "parts", "total_price": 80.0},
            # Unknown item - no match
            {"description": "MISCELLANEOUS PART", "item_type": "parts", "total_price": 100.0},
        ]

    @pytest.fixture
    def covered_components(self):
        """Sample covered components from policy."""
        return {
            "engine": ["Motor", "Kolben", "Zylinder"],
            "chassis": ["Stossdaempfer", "Federbein"],
            "brakes": ["Bremssattel", "Bremsscheibe"],
        }

    def test_analyzer_creation(self, analyzer):
        """Test analyzer is created correctly."""
        assert analyzer is not None
        assert analyzer.rule_engine is not None
        assert analyzer.keyword_matcher is not None

    def test_analyze_basic(self, analyzer, sample_line_items, covered_components):
        """Test basic analysis flow."""
        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=sample_line_items,
            covered_components=covered_components,
        )

        assert result is not None
        assert result.claim_id == "TEST001"
        assert result.schema_version == "coverage_analysis_v1"
        assert len(result.line_items) == len(sample_line_items)

    def test_rule_engine_exclusions(self, analyzer, covered_components):
        """Test that rule engine exclusions work."""
        items = [
            {"description": "SERVICE FEE", "item_type": "fee", "total_price": 50.0},
            {"description": "ENTSORGUNG", "item_type": "parts", "total_price": 25.0},
            {"description": "MOTOROEL", "item_type": "parts", "total_price": 80.0},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
        )

        # All items should be not covered
        for item in result.line_items:
            assert item.coverage_status == CoverageStatus.NOT_COVERED
            assert item.match_method == MatchMethod.RULE

    def test_keyword_matches(self, analyzer, covered_components):
        """Test that keyword matching works."""
        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500.0},
            {"description": "STOSSDAEMPFER VORNE", "item_type": "parts", "total_price": 300.0},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
        )

        # Both should be covered via keywords
        for item in result.line_items:
            assert item.coverage_status == CoverageStatus.COVERED
            assert item.match_method == MatchMethod.KEYWORD

    def test_unmatched_items_flagged_for_review(self, analyzer, covered_components):
        """Test that unmatched items are flagged for review (LLM disabled)."""
        items = [
            {"description": "COMPLETELY UNKNOWN PART ABC", "item_type": "parts", "total_price": 100.0},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
        )

        # Should be flagged for review since LLM is disabled
        assert len(result.line_items) == 1
        assert result.line_items[0].coverage_status == CoverageStatus.REVIEW_NEEDED

    def test_summary_calculation(self, analyzer, sample_line_items, covered_components):
        """Test that summary is calculated correctly."""
        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=sample_line_items,
            covered_components=covered_components,
        )

        summary = result.summary
        assert summary.total_claimed > 0
        assert summary.items_covered + summary.items_not_covered + summary.items_review_needed == len(sample_line_items)

    def test_coverage_percent_applied(self, analyzer, covered_components):
        """Test that coverage percentage is applied correctly.

        Scale uses "a partir de" (from X km onwards) semantics:
        - Below 50,000 km: 100% coverage
        - 50,000+ km: 80% coverage
        - 100,000+ km: 60% coverage
        """
        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0},
        ]

        coverage_scale = [
            {"km_threshold": 50000, "coverage_percent": 80},
            {"km_threshold": 100000, "coverage_percent": 60},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
            vehicle_km=75000,  # 75k >= 50k, so 80% coverage
            coverage_scale=coverage_scale,
        )

        assert result.inputs.coverage_percent == 80
        assert result.summary.coverage_percent == 80

        # Covered amount should be 80% of 1000 = 800
        item = result.line_items[0]
        assert item.coverage_status == CoverageStatus.COVERED
        assert item.covered_amount == 800.0
        assert item.not_covered_amount == 200.0

    def test_coverage_percent_low_km(self, analyzer, covered_components):
        """Test coverage percent for low km vehicle (below first threshold).

        Scale uses "a partir de" (from X km onwards) semantics:
        - Below first threshold (50,000 km): 100% coverage (full coverage)
        """
        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0},
        ]

        coverage_scale = [
            {"km_threshold": 50000, "coverage_percent": 80},
            {"km_threshold": 100000, "coverage_percent": 60},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
            vehicle_km=25000,  # 25k < 50k, so 100% coverage
            coverage_scale=coverage_scale,
        )

        assert result.inputs.coverage_percent == 100

    def test_excess_calculation(self, analyzer, covered_components):
        """Test excess calculation."""
        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
            excess_percent=10.0,
            excess_minimum=50.0,
        )

        summary = result.summary
        # 10% of 1000 = 100, but minimum is 50, so excess should be 100
        assert summary.excess_amount >= 50.0

    def test_metadata_tracking(self, analyzer, sample_line_items, covered_components):
        """Test that metadata is tracked correctly."""
        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=sample_line_items,
            covered_components=covered_components,
        )

        metadata = result.metadata
        assert metadata.rules_applied >= 0
        assert metadata.keywords_applied >= 0
        assert metadata.llm_calls == 0  # LLM disabled
        assert metadata.processing_time_ms > 0

    def test_empty_line_items(self, analyzer, covered_components):
        """Test with empty line items list."""
        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=[],
            covered_components=covered_components,
        )

        assert len(result.line_items) == 0
        assert result.summary.total_claimed == 0

    def test_empty_covered_components(self, analyzer):
        """Test with no covered components."""
        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500.0},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components={},
        )

        # Should not be covered if no components covered
        assert result.line_items[0].coverage_status in [
            CoverageStatus.NOT_COVERED,
            CoverageStatus.REVIEW_NEEDED,
        ]

    def test_claim_run_id_preserved(self, analyzer, covered_components):
        """Test that claim_run_id is preserved."""
        items = [{"description": "MOTOR", "item_type": "parts", "total_price": 100.0}]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
            claim_run_id="clm_20260128_120000_abc123",
        )

        assert result.claim_run_id == "clm_20260128_120000_abc123"

    def test_inputs_recorded(self, analyzer, covered_components):
        """Test that inputs are recorded in result."""
        items = [{"description": "MOTOR", "item_type": "parts", "total_price": 100.0}]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
            vehicle_km=75000,
            excess_percent=10.0,
            excess_minimum=50.0,
        )

        inputs = result.inputs
        assert inputs.vehicle_km == 75000
        assert inputs.excess_percent == 10.0
        assert inputs.excess_minimum == 50.0
        assert len(inputs.covered_categories) > 0

    def test_simple_invoice_rule_links_labor_to_covered_part(self, analyzer, covered_components):
        """Test simple invoice rule: generic labor linked to covered part.

        When an invoice has:
        - 1 covered part
        - 1 generic labor entry (e.g., "Main d'œuvre")
        The labor should be automatically linked to the covered part.
        """
        items = [
            {"description": "MOTOR DICHTUNG", "item_type": "parts", "total_price": 358.0},
            {"description": "Main d'œuvre", "item_type": "labor", "total_price": 160.0},
            {"description": "Petites fourniture", "item_type": "fee", "total_price": 6.4},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
        )

        # Find the labor item
        labor_item = next(i for i in result.line_items if i.item_type == "labor")

        # Labor should be covered via simple invoice rule
        assert labor_item.coverage_status == CoverageStatus.COVERED
        assert "simple invoice rule" in labor_item.match_reasoning.lower()
        assert labor_item.coverage_category == "engine"

    def test_simple_invoice_rule_not_applied_to_specific_labor(self, analyzer, covered_components):
        """Test that simple invoice rule doesn't apply to specific labor descriptions.

        Labor with specific part references (like "remplacement X") should not
        be auto-linked - they need to match the actual part.
        """
        items = [
            {"description": "MOTOR DICHTUNG", "item_type": "parts", "total_price": 358.0},
            # This labor mentions a specific part that doesn't match
            {"description": "remplacement courroie distribution", "item_type": "labor", "total_price": 160.0},
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
        )

        # Find the labor item
        labor_item = next(i for i in result.line_items if i.item_type == "labor")

        # Labor should NOT be auto-linked (description is specific, not generic)
        # It will be REVIEW_NEEDED since LLM is disabled
        assert labor_item.coverage_status != CoverageStatus.COVERED or \
            "simple invoice rule" not in labor_item.match_reasoning.lower()

    def test_simple_invoice_rule_not_applied_multiple_labor_items(self, analyzer, covered_components):
        """Test that simple invoice rule only applies with exactly 1 generic labor item."""
        items = [
            {"description": "MOTOR DICHTUNG", "item_type": "parts", "total_price": 358.0},
            {"description": "Main d'œuvre", "item_type": "labor", "total_price": 100.0},
            {"description": "Arbeit", "item_type": "labor", "total_price": 60.0},  # Second labor
        ]

        result = analyzer.analyze(
            claim_id="TEST001",
            line_items=items,
            covered_components=covered_components,
        )

        # Find the labor items
        labor_items = [i for i in result.line_items if i.item_type == "labor"]

        # Neither should be covered via simple invoice rule (multiple labor items)
        for labor_item in labor_items:
            if labor_item.coverage_status == CoverageStatus.COVERED:
                assert "simple invoice rule" not in labor_item.match_reasoning.lower()
