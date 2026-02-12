"""Tests for the coverage rule engine."""

from pathlib import Path

import pytest
import yaml

from context_builder.coverage.rule_engine import RuleConfig, RuleEngine
from context_builder.coverage.schemas import CoverageStatus, MatchMethod, TraceAction


def _load_nsa_rule_config() -> RuleConfig:
    """Load NSA rule config from workspace YAML."""
    config_path = (
        Path(__file__).resolve().parents[2]
        / "workspaces" / "nsa" / "config" / "coverage" / "nsa_coverage_config.yaml"
    )
    if not config_path.exists():
        pytest.skip("NSA workspace config not available")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return RuleConfig.from_dict(data.get("rules", {}))


@pytest.fixture(scope="session")
def nsa_rule_config():
    """Load NSA rule config from workspace."""
    return _load_nsa_rule_config()


@pytest.fixture
def nsa_engine(nsa_rule_config):
    """Create a RuleEngine with NSA config."""
    return RuleEngine(nsa_rule_config)


class TestRuleEngineDefaults:
    """Tests for RuleEngine with empty default config."""

    def test_default_config_is_empty(self):
        """Test that default config has no customer-specific patterns."""
        engine = RuleEngine()
        assert engine.config is not None
        assert "fee" in engine.config.fee_item_types
        assert len(engine.config.exclusion_patterns) == 0
        assert len(engine.config.consumable_patterns) == 0
        assert len(engine.config.non_covered_labor_patterns) == 0
        assert len(engine.config.component_override_patterns) == 0
        assert len(engine.config.generic_description_patterns) == 0

    def test_fee_items_not_covered(self):
        """Fee items are always not covered (even without customer config)."""
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
        assert result.exclusion_reason == "fee"
        # Trace assertions
        assert result.decision_trace is not None
        assert len(result.decision_trace) == 1
        assert result.decision_trace[0].stage == "rule_engine"
        assert result.decision_trace[0].action == TraceAction.EXCLUDED
        assert result.decision_trace[0].detail["rule"] == "fee_item"

    def test_zero_price_item_covered(self):
        """Zero-price items are marked covered."""
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
        # Trace assertions
        assert result.decision_trace is not None
        assert len(result.decision_trace) == 1
        assert result.decision_trace[0].action == TraceAction.MATCHED
        assert result.decision_trace[0].detail["rule"] == "zero_price"

    def test_normal_part_passes_through(self):
        """Normal parts pass through without matching (no patterns configured)."""
        engine = RuleEngine()
        result = engine.match(
            description="STOSSDAEMPFER HINTEN LINKS",
            item_type="parts",
            total_price=450.0,
        )
        assert result is None

    def test_normal_labor_passes_through(self):
        """Normal labor passes through without matching."""
        engine = RuleEngine()
        result = engine.match(
            description="STOSSDAEMPFER ERSETZEN AW 2.5",
            item_type="labor",
            total_price=175.0,
        )
        assert result is None

    def test_empty_engine_no_exclusions(self):
        """Empty engine does not exclude ENTSORGUNG (no patterns)."""
        engine = RuleEngine()
        result = engine.match(
            description="ENTSORGUNG ALTOEL",
            item_type="parts",
            total_price=25.0,
        )
        # No exclusion patterns → passes through
        assert result is None

    def test_empty_engine_no_generic_rule(self):
        """Empty engine does not trigger generic description rule."""
        engine = RuleEngine()
        result = engine.match(
            description="ARBEIT",
            item_type="labor",
            total_price=100.0,
        )
        # No generic patterns → passes through
        assert result is None

    def test_fastener_passes_through_to_llm(self):
        """Fasteners pass through to LLM (no rule engine handling)."""
        engine = RuleEngine()
        result = engine.match(
            description="SCHRAUBE",
            item_type="parts",
            total_price=5.0,
        )
        # Fasteners are now handled by the LLM, not the rule engine
        assert result is None


class TestRuleEngineNSA:
    """Tests for RuleEngine with NSA config (customer-specific patterns)."""

    def test_nsa_config_has_patterns(self, nsa_engine):
        """NSA config has customer-specific patterns."""
        assert len(nsa_engine.config.exclusion_patterns) > 0
        assert len(nsa_engine.config.consumable_patterns) > 0
        assert len(nsa_engine.config.non_covered_labor_patterns) > 0
        assert len(nsa_engine.config.component_override_patterns) > 0
        assert len(nsa_engine.config.generic_description_patterns) > 0

    def test_fee_items_not_covered(self, nsa_engine):
        """Fee items are always not covered."""
        result = nsa_engine.match(
            description="Handling fee",
            item_type="fee",
            total_price=50.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert result.match_method == MatchMethod.RULE
        assert result.match_confidence == 1.0
        assert result.not_covered_amount == 50.0

    def test_exclusion_pattern_entsorgung(self, nsa_engine):
        """ENTSORGUNG pattern triggers not covered."""
        result = nsa_engine.match(
            description="ENTSORGUNG ALTOEL",
            item_type="parts",
            total_price=25.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert result.match_method == MatchMethod.RULE
        assert "ENTSORGUNG" in result.match_reasoning
        assert result.exclusion_reason == "exclusion_pattern"

    def test_exclusion_pattern_ersatzfahrzeug(self, nsa_engine):
        """Rental car pattern triggers not covered."""
        result = nsa_engine.match(
            description="ERSATZFAHRZEUG 3 TAGE",
            item_type="fee",
            total_price=300.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_exclusion_pattern_case_insensitive(self, nsa_engine):
        """Patterns are matched case-insensitively."""
        result = nsa_engine.match(
            description="Entsorgung altöl",
            item_type="parts",
            total_price=25.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_consumable_motoroel(self, nsa_engine):
        """Engine oil is not covered."""
        result = nsa_engine.match(
            description="MOTOROEL 5W30 6L",
            item_type="parts",
            total_price=120.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "Consumable" in result.match_reasoning
        assert result.exclusion_reason == "consumable"

    def test_consumable_oil_filter(self, nsa_engine):
        """Oil filter is not covered."""
        result = nsa_engine.match(
            description="OELFILTER MANN",
            item_type="parts",
            total_price=35.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_consumable_labor_not_excluded(self, nsa_engine):
        """Consumable pattern doesn't apply to labor."""
        result = nsa_engine.match(
            description="OELFILTER WECHSELN",
            item_type="labor",
            total_price=50.0,
        )
        if result is not None:
            assert "Consumable" not in result.match_reasoning

    def test_zero_price_item(self, nsa_engine):
        """Zero-price items are marked covered."""
        result = nsa_engine.match(
            description="SERVICE GRATIS",
            item_type="labor",
            total_price=0.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED
        assert result.match_method == MatchMethod.RULE
        assert result.covered_amount == 0.0

    def test_normal_part_passes_through(self, nsa_engine):
        """Normal parts pass through without matching."""
        result = nsa_engine.match(
            description="STOSSDAEMPFER HINTEN LINKS",
            item_type="parts",
            total_price=450.0,
        )
        assert result is None

    def test_normal_labor_passes_through(self, nsa_engine):
        """Normal labor passes through without matching."""
        result = nsa_engine.match(
            description="STOSSDAEMPFER ERSETZEN AW 2.5",
            item_type="labor",
            total_price=175.0,
        )
        assert result is None

    def test_batch_match(self, nsa_engine):
        """Batch matching functionality."""
        items = [
            {"description": "ENTSORGUNG", "item_type": "fee", "total_price": 20.0},
            {"description": "STOSSDAEMPFER", "item_type": "parts", "total_price": 400.0},
            {"description": "MOTOROEL", "item_type": "parts", "total_price": 80.0},
            {"description": "STOSSDAEMPFER EINBAUEN", "item_type": "labor", "total_price": 200.0},
        ]
        matched, unmatched = nsa_engine.batch_match(items)
        # ENTSORGUNG and MOTOROEL should be matched
        assert len(matched) == 2
        # STOSSDAEMPFER and STOSSDAEMPFER EINBAUEN should be unmatched
        assert len(unmatched) == 2

    def test_item_code_preserved(self, nsa_engine):
        """Item code is preserved in result."""
        result = nsa_engine.match(
            description="ENTSORGUNG",
            item_type="fee",
            item_code="FEE001",
            total_price=20.0,
        )
        assert result is not None
        assert result.item_code == "FEE001"


class TestCustomConfig:
    """Tests for RuleEngine with custom configuration."""

    def test_custom_config(self):
        """Custom configuration works correctly."""
        config = RuleConfig(
            fee_item_types=["fee", "charge"],
            exclusion_patterns=["CUSTOM_EXCLUSION"],
            consumable_patterns=[],
            non_covered_labor_patterns=[],
            component_override_patterns=[],
            generic_description_patterns=[],
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


class TestRule5NonCoveredLaborPatterns:
    """Tests for Rule 5: Non-covered labor patterns (NSA-specific)."""

    def test_diagnose_labor_not_covered(self, nsa_engine):
        """DIAGNOSE labor with non-zero price is not covered."""
        result = nsa_engine.match(
            description="DIAGNOSE MOTORSTEUERGERÄT",
            item_type="labor",
            total_price=150.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert result.match_method == MatchMethod.RULE
        assert "non-covered pattern" in result.match_reasoning
        assert result.exclusion_reason == "non_covered_labor"

    def test_kontrolle_labor_not_covered(self, nsa_engine):
        """KONTROLLE labor is not covered."""
        result = nsa_engine.match(
            description="KONTROLLE BREMSEN",
            item_type="labor",
            total_price=80.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_pruefung_labor_not_covered(self, nsa_engine):
        """PRÜFUNG labor is not covered."""
        result = nsa_engine.match(
            description="PRÜFUNG ABGASANLAGE",
            item_type="labor",
            total_price=60.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_labor_pattern_only_applies_to_labor(self, nsa_engine):
        """Non-covered labor patterns should not match parts."""
        result = nsa_engine.match(
            description="DIAGNOSE KABEL",
            item_type="parts",
            total_price=30.0,
        )
        # Parts should NOT be matched by labor-only rule
        assert result is None

    def test_zero_price_labor_still_covered(self, nsa_engine):
        """Zero-price DIAGNOSE labor should be covered (Rule 4 before Rule 5)."""
        result = nsa_engine.match(
            description="DIAGNOSE GRATIS",
            item_type="labor",
            total_price=0.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED

    def test_labor_pattern_case_insensitive(self, nsa_engine):
        """Labor patterns match case-insensitively."""
        result = nsa_engine.match(
            description="diagnose fahrwerk",
            item_type="labor",
            total_price=100.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED


class TestRule6GenericDescriptions:
    """Tests for Rule 6: Generic/empty descriptions (NSA-specific)."""

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
    def test_generic_descriptions_not_covered(self, nsa_engine, description):
        """Generic placeholder descriptions are not covered."""
        result = nsa_engine.match(
            description=description,
            item_type="labor",
            total_price=100.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "Generic description" in result.match_reasoning
        assert result.exclusion_reason == "generic_description"

    def test_generic_with_whitespace(self, nsa_engine):
        """Generic descriptions with surrounding whitespace still match."""
        result = nsa_engine.match(
            description="  ARBEIT  ",
            item_type="labor",
            total_price=100.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_generic_case_insensitive(self, nsa_engine):
        """Generic pattern matches case-insensitively."""
        result = nsa_engine.match(
            description="arbeit:",
            item_type="labor",
            total_price=50.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_non_generic_description_passes_through(self, nsa_engine):
        """Descriptions with actual content should pass through."""
        result = nsa_engine.match(
            description="ARBEIT STOSSDAEMPFER WECHSELN",
            item_type="labor",
            total_price=200.0,
        )
        # Has real content beyond just "ARBEIT", should not match Rule 6
        assert result is None

    def test_generic_parts_also_matched(self, nsa_engine):
        """Generic descriptions apply to all item types, not just labor."""
        result = nsa_engine.match(
            description="MATERIAL",
            item_type="parts",
            total_price=50.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_zero_price_generic_still_covered(self, nsa_engine):
        """Zero-price generic items are still covered (Rule 4 before Rule 6)."""
        result = nsa_engine.match(
            description="ARBEIT",
            item_type="labor",
            total_price=0.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED


class TestFastenersPassThroughToLLM:
    """Tests that fasteners/gaskets now pass through to LLM (removed from rule engine)."""

    @pytest.mark.parametrize(
        "description",
        [
            "ECROU",
            "MUTTER",
            "SCHRAUBE",
            "BOULON",
            "DICHTUNG",
        ],
    )
    def test_standalone_fasteners_pass_through(self, nsa_engine, description):
        """Standalone fastener/gasket descriptions now pass through to LLM."""
        result = nsa_engine.match(
            description=description,
            item_type="parts",
            total_price=5.0,
        )
        # These items should NOT be matched by rules anymore -- they pass to LLM
        assert result is None


class TestSealGasketPassThroughToLLM:
    """Tests that seal/gasket items now pass through to LLM (removed from rule engine)."""

    def test_standalone_dichtung_passes_through(self):
        """Standalone DICHTUNG now passes through to LLM."""
        config = RuleConfig(
            fee_item_types=["fee"],
            exclusion_patterns=[],
            consumable_patterns=[],
            non_covered_labor_patterns=[],
            component_override_patterns=[],
            generic_description_patterns=[],
        )
        engine = RuleEngine(config)
        result = engine.match(
            description="DICHTUNG",
            item_type="parts",
            total_price=15.0,
        )
        # No longer caught by rule engine -- passes to LLM
        assert result is None

    def test_oring_passes_through(self):
        """O-RING now passes through to LLM."""
        config = RuleConfig(
            fee_item_types=["fee"],
            exclusion_patterns=[],
            consumable_patterns=[],
            non_covered_labor_patterns=[],
            component_override_patterns=[],
            generic_description_patterns=[],
        )
        engine = RuleEngine(config)
        for desc in ["O-RING", "ORING"]:
            result = engine.match(
                description=desc,
                item_type="parts",
                total_price=5.0,
            )
            assert result is None, f"'{desc}' should pass through to LLM"


class TestMatchesExclusionPattern:
    """Tests for RuleEngine.matches_exclusion_pattern()."""

    def test_matches_adblue_in_component_name(self, nsa_engine):
        """ADBLUE in component name triggers exclusion match."""
        result = nsa_engine.matches_exclusion_pattern("Adblue_injection_valve")
        assert result is not None
        assert "ADBLUE" in result.upper() or "adblue" in result.lower()

    def test_no_match_normal_component(self, nsa_engine):
        """Normal covered component returns None."""
        result = nsa_engine.matches_exclusion_pattern("water_pump")
        assert result is None

    def test_none_input_returns_none(self, nsa_engine):
        """None input returns None."""
        result = nsa_engine.matches_exclusion_pattern(None)
        assert result is None

    def test_empty_string_returns_none(self, nsa_engine):
        """Empty string returns None."""
        result = nsa_engine.matches_exclusion_pattern("")
        assert result is None

    def test_case_insensitive(self, nsa_engine):
        """Exclusion patterns are case-insensitive."""
        lower = nsa_engine.matches_exclusion_pattern("adblue_valve")
        upper = nsa_engine.matches_exclusion_pattern("ADBLUE_VALVE")
        assert lower is not None
        assert upper is not None
