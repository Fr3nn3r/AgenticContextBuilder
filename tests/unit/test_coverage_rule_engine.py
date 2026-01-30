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

    def test_exclusion_pattern_adblue_parts(self):
        """Test that AdBlue parts are excluded (emissions system, not covered)."""
        engine = RuleEngine()

        result = engine.match(
            description="Adblueeinspritzdüse ersetzt inkl. entlüftet und angelernt",
            item_type="labor",
            total_price=160.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "ADBLUE" in result.match_reasoning

    def test_exclusion_pattern_adblue_valve(self):
        """Test that AdBlue valve/clamp parts are excluded."""
        engine = RuleEngine()

        result = engine.match(
            description="Ersatzteile Amag Ventil Klemmschelle Adblue",
            item_type="parts",
            total_price=521.75,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "ADBLUE" in result.match_reasoning

    def test_exclusion_pattern_harnstoff(self):
        """Test that Harnstoff (urea) items are excluded."""
        engine = RuleEngine()

        result = engine.match(
            description="HARNSTOFF EINSPRITZDÜSE",
            item_type="parts",
            total_price=300.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "HARNSTOFF" in result.match_reasoning

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
            {"description": "STOSSDAEMPFER EINBAUEN", "item_type": "labor", "total_price": 200.0},
        ]

        matched, unmatched = engine.batch_match(items)

        # ENTSORGUNG and MOTOROEL should be matched
        assert len(matched) == 2
        # STOSSDAEMPFER and STOSSDAEMPFER EINBAUEN should be unmatched
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


class TestRule5NonCoveredLaborPatterns:
    """Tests for Rule 5: Non-covered labor patterns."""

    def test_diagnose_labor_not_covered(self):
        """DIAGNOSE labor with non-zero price is not covered."""
        engine = RuleEngine()
        result = engine.match(
            description="DIAGNOSE MOTORSTEUERGERÄT",
            item_type="labor",
            total_price=150.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert result.match_method == MatchMethod.RULE
        assert "non-covered pattern" in result.match_reasoning

    def test_kontrolle_labor_not_covered(self):
        """KONTROLLE labor is not covered."""
        engine = RuleEngine()
        result = engine.match(
            description="KONTROLLE BREMSEN",
            item_type="labor",
            total_price=80.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_pruefung_labor_not_covered(self):
        """PRÜFUNG labor is not covered."""
        engine = RuleEngine()
        result = engine.match(
            description="PRÜFUNG ABGASANLAGE",
            item_type="labor",
            total_price=60.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_labor_pattern_only_applies_to_labor(self):
        """Non-covered labor patterns should not match parts."""
        engine = RuleEngine()
        result = engine.match(
            description="DIAGNOSE KABEL",
            item_type="parts",
            total_price=30.0,
        )
        # Parts should NOT be matched by labor-only rule
        assert result is None

    def test_zero_price_labor_still_covered(self):
        """Zero-price DIAGNOSE labor should be covered (Rule 4 before Rule 5)."""
        engine = RuleEngine()
        result = engine.match(
            description="DIAGNOSE GRATIS",
            item_type="labor",
            total_price=0.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED

    def test_labor_pattern_case_insensitive(self):
        """Labor patterns match case-insensitively."""
        engine = RuleEngine()
        result = engine.match(
            description="diagnose fahrwerk",
            item_type="labor",
            total_price=100.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED


class TestRule6GenericDescriptions:
    """Tests for Rule 6: Generic/empty descriptions."""

    @pytest.mark.parametrize(
        "description",
        [
            "ARBEIT",
            "ARBEIT:",
            "MATERIAL",
            "MATERIAL:",
            "REPARATURSATZ",
            "DIVERSES",
            "VARIOUS",
            "DIVERS",
        ],
    )
    def test_generic_descriptions_not_covered(self, description):
        """Generic placeholder descriptions are not covered."""
        engine = RuleEngine()
        result = engine.match(
            description=description,
            item_type="labor",
            total_price=100.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "Generic description" in result.match_reasoning

    def test_generic_with_whitespace(self):
        """Generic descriptions with surrounding whitespace still match."""
        engine = RuleEngine()
        result = engine.match(
            description="  ARBEIT  ",
            item_type="labor",
            total_price=100.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_generic_case_insensitive(self):
        """Generic pattern matches case-insensitively."""
        engine = RuleEngine()
        result = engine.match(
            description="arbeit:",
            item_type="labor",
            total_price=50.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_non_generic_description_passes_through(self):
        """Descriptions with actual content should pass through."""
        engine = RuleEngine()
        result = engine.match(
            description="ARBEIT STOSSDAEMPFER WECHSELN",
            item_type="labor",
            total_price=200.0,
        )
        # Has real content beyond just "ARBEIT", should not match Rule 6
        assert result is None

    def test_generic_parts_also_matched(self):
        """Generic descriptions apply to all item types, not just labor."""
        engine = RuleEngine()
        result = engine.match(
            description="MATERIAL",
            item_type="parts",
            total_price=50.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_zero_price_generic_still_covered(self):
        """Zero-price generic items are still covered (Rule 4 before Rule 6)."""
        engine = RuleEngine()
        result = engine.match(
            description="ARBEIT",
            item_type="labor",
            total_price=0.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED


class TestRule7FastenerPatterns:
    """Tests for Rule 7: Standalone fastener items."""

    @pytest.mark.parametrize(
        "description",
        [
            "ECROU",
            "MUTTER",
            "SCHRAUBE",
            "BOULON",
            "VIS",
            "BEFESTIGUNGSSCHRAUBE",
            "SELBSTSICHERNDE MUTTER",
            "GOUPILLE",
            "SICHERUNGSRING",
            "SICHERUNGSMUTTER",
        ],
    )
    def test_standalone_fasteners_review_needed(self, description):
        """Standalone fastener descriptions trigger REVIEW_NEEDED."""
        engine = RuleEngine()
        result = engine.match(
            description=description,
            item_type="parts",
            total_price=5.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.REVIEW_NEEDED
        assert result.match_method == MatchMethod.RULE
        assert result.match_confidence == 0.45
        assert "fastener" in result.match_reasoning.lower()
        assert result.not_covered_amount == 5.0

    def test_fastener_case_insensitive(self):
        """Fastener pattern matches case-insensitively."""
        engine = RuleEngine()
        result = engine.match(
            description="schraube",
            item_type="parts",
            total_price=3.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.REVIEW_NEEDED

    def test_fastener_does_not_match_substring(self):
        """'VIS' should not match 'SERVISE' or 'VIS DE REGLAGE SOUPAPE'."""
        engine = RuleEngine()

        # "VIS" as part of a larger word
        result = engine.match(
            description="SERVISE COMPLET",
            item_type="parts",
            total_price=100.0,
        )
        assert result is None

        # "VIS" as part of a compound description
        result = engine.match(
            description="VIS DE REGLAGE SOUPAPE",
            item_type="parts",
            total_price=15.0,
        )
        assert result is None

    def test_fastener_compound_description_passes_through(self):
        """Compound descriptions containing fastener words should pass."""
        engine = RuleEngine()

        result = engine.match(
            description="SCHRAUBE OELWANNENDICHTUNG M8X20",
            item_type="parts",
            total_price=2.0,
        )
        # Not a standalone fastener - should pass through
        assert result is None

    def test_fastener_with_whitespace(self):
        """Fastener with surrounding whitespace still matches."""
        engine = RuleEngine()
        result = engine.match(
            description="  MUTTER  ",
            item_type="parts",
            total_price=1.50,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.REVIEW_NEEDED

    def test_zero_price_fastener_covered(self):
        """Zero-price fastener is covered (Rule 4 before Rule 7)."""
        engine = RuleEngine()
        result = engine.match(
            description="SCHRAUBE",
            item_type="parts",
            total_price=0.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED
