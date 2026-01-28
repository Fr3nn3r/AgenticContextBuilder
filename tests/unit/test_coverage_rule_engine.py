"""Tests for the coverage rule engine."""

import pytest

from context_builder.coverage.rule_engine import RuleConfig, RuleEngine
from context_builder.coverage.schemas import CoverageStatus, MatchMethod


class TestRuleEngine:
    """Tests for RuleEngine class."""

    def test_default_config(self):
        """Test that default config is created correctly."""
        engine = RuleEngine()
        assert engine.config is not None
        assert "fee" in engine.config.fee_item_types
        assert len(engine.config.exclusion_patterns) > 0

    def test_fee_items_not_covered(self):
        """Test that fee items are always not covered."""
        engine = RuleEngine()

        result = engine.match(
            description="Handling fee",
            item_type="fee",
            total_price=50.0,
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert result.match_method == MatchMethod.RULE
        assert result.match_confidence == 1.0
        assert result.not_covered_amount == 50.0
        assert "fee" in result.match_reasoning.lower()

    def test_exclusion_pattern_entsorgung(self):
        """Test that ENTSORGUNG pattern triggers not covered."""
        engine = RuleEngine()

        result = engine.match(
            description="ENTSORGUNG ALTOEL",
            item_type="parts",
            total_price=25.0,
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert result.match_method == MatchMethod.RULE
        assert "ENTSORGUNG" in result.match_reasoning

    def test_exclusion_pattern_ersatzfahrzeug(self):
        """Test that rental car pattern triggers not covered."""
        engine = RuleEngine()

        result = engine.match(
            description="ERSATZFAHRZEUG 3 TAGE",
            item_type="fee",
            total_price=300.0,
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_exclusion_pattern_case_insensitive(self):
        """Test that patterns are matched case-insensitively."""
        engine = RuleEngine()

        result = engine.match(
            description="Entsorgung altöl",
            item_type="parts",
            total_price=25.0,
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_consumable_motoroel(self):
        """Test that engine oil is not covered."""
        engine = RuleEngine()

        result = engine.match(
            description="MOTOROEL 5W30 6L",
            item_type="parts",
            total_price=120.0,
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "Consumable" in result.match_reasoning

    def test_consumable_oil_filter(self):
        """Test that oil filter is not covered."""
        engine = RuleEngine()

        result = engine.match(
            description="OELFILTER MANN",
            item_type="parts",
            total_price=35.0,
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_consumable_labor_not_excluded(self):
        """Test that consumable pattern doesn't apply to labor."""
        engine = RuleEngine()

        result = engine.match(
            description="OELFILTER WECHSELN",
            item_type="labor",  # Labor, not parts
            total_price=50.0,
        )

        # Labor should not be excluded by consumable pattern
        # It might be excluded by another rule or pass through
        if result is not None:
            # If matched, should not be a consumable match
            assert "Consumable" not in result.match_reasoning

    def test_zero_price_item(self):
        """Test that zero-price items are marked covered."""
        engine = RuleEngine()

        result = engine.match(
            description="SERVICE GRATIS",
            item_type="labor",
            total_price=0.0,
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED
        assert result.match_method == MatchMethod.RULE
        assert result.covered_amount == 0.0

    def test_normal_part_passes_through(self):
        """Test that normal parts pass through without matching."""
        engine = RuleEngine()

        result = engine.match(
            description="STOSSDAEMPFER HINTEN LINKS",
            item_type="parts",
            total_price=450.0,
        )

        # Should not match any rule
        assert result is None

    def test_normal_labor_passes_through(self):
        """Test that normal labor passes through without matching."""
        engine = RuleEngine()

        result = engine.match(
            description="STOSSDAEMPFER ERSETZEN AW 2.5",
            item_type="labor",
            total_price=175.0,
        )

        # Should not match any rule
        assert result is None

    def test_batch_match(self):
        """Test batch matching functionality."""
        engine = RuleEngine()

        items = [
            {"description": "ENTSORGUNG", "item_type": "fee", "total_price": 20.0},
            {"description": "STOSSDAEMPFER", "item_type": "parts", "total_price": 400.0},
            {"description": "MOTOROEL", "item_type": "parts", "total_price": 80.0},
            {"description": "ARBEIT", "item_type": "labor", "total_price": 200.0},
        ]

        matched, unmatched = engine.batch_match(items)

        # ENTSORGUNG and MOTOROEL should be matched
        assert len(matched) == 2
        # STOSSDAEMPFER and ARBEIT should be unmatched
        assert len(unmatched) == 2

    def test_custom_config(self):
        """Test with custom configuration."""
        config = RuleConfig(
            fee_item_types=["fee", "charge"],
            exclusion_patterns=["CUSTOM_EXCLUSION"],
            consumable_patterns=[],
            non_covered_labor_patterns=[],
        )
        engine = RuleEngine(config)

        # Custom fee type should work
        result = engine.match(
            description="Additional charge",
            item_type="charge",
            total_price=50.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

        # Custom exclusion pattern should work
        result = engine.match(
            description="CUSTOM_EXCLUSION item",
            item_type="parts",
            total_price=100.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_item_code_preserved(self):
        """Test that item code is preserved in result."""
        engine = RuleEngine()

        result = engine.match(
            description="ENTSORGUNG",
            item_type="fee",
            item_code="FEE001",
            total_price=20.0,
        )

        assert result is not None
        assert result.item_code == "FEE001"
