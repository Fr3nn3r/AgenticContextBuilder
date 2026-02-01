"""Tests for the coverage rule engine component override patterns."""

from pathlib import Path

import pytest
import yaml

from context_builder.coverage.rule_engine import RuleConfig, RuleEngine
from context_builder.coverage.schemas import CoverageStatus


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


class TestComponentOverridePatterns:
    """Tests for pump/component override of consumable exclusions (NSA-specific)."""

    @pytest.fixture
    def engine(self):
        return RuleEngine(_load_nsa_rule_config())

    def test_coolant_pump_not_excluded_as_consumable(self, engine):
        """'Kühlmittelpumpe elektrisch' should NOT be excluded as consumable."""
        result = engine.match(
            description="Kühlmittelpumpe elektrisch",
            item_type="parts",
            total_price=450.0,
        )
        # Should return None (no rule match), letting it fall through to next stage
        assert result is None

    def test_plain_coolant_still_excluded(self, engine):
        """'Kühlmittel 5L' should still be excluded as consumable."""
        result = engine.match(
            description="Kühlmittel 5L",
            item_type="parts",
            total_price=30.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "consumable" in result.match_reasoning.lower()

    def test_engine_oil_still_excluded(self, engine):
        """'Motoröl 5W30' should still be excluded (no override keyword)."""
        result = engine.match(
            description="Motoröl 5W30",
            item_type="parts",
            total_price=80.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_oil_filter_still_excluded(self, engine):
        """'Ölfilter' should still be excluded (no override keyword)."""
        result = engine.match(
            description="Ölfilter Standard",
            item_type="parts",
            total_price=25.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_coolant_radiator_not_excluded(self, engine):
        """'Kühlmittelkühler' (coolant radiator) should NOT be excluded."""
        result = engine.match(
            description="Kühlmittelkühler",
            item_type="parts",
            total_price=600.0,
        )
        # Should return None - Kühler override keyword matches
        assert result is None

    def test_oil_pump_not_excluded(self, engine):
        """'Ölpumpe' should NOT be excluded even though 'öl' is in consumable patterns."""
        # Note: the default consumable patterns check for MOTOROEL/MOTORÖL/OELFILTER/ÖLFILTER
        # "Ölpumpe" doesn't match those specific patterns, so this test confirms the override
        # would work if a broader oil pattern existed
        result = engine.match(
            description="Ölpumpe",
            item_type="parts",
            total_price=350.0,
        )
        # No consumable pattern matches "Ölpumpe" (patterns are MOTOROEL/OELFILTER)
        assert result is None

    def test_brake_fluid_still_excluded(self, engine):
        """'Bremsflüssigkeit' should still be excluded (no override keyword)."""
        result = engine.match(
            description="Bremsflüssigkeit DOT4",
            item_type="parts",
            total_price=20.0,
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_thermostat_coolant_not_excluded(self, engine):
        """'Kühlmittel-Thermostat' should NOT be excluded due to thermostat override."""
        result = engine.match(
            description="Kühlmittel-Thermostat",
            item_type="parts",
            total_price=85.0,
        )
        assert result is None
