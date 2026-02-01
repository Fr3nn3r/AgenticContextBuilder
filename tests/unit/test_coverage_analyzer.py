"""Tests for the coverage analyzer."""

from pathlib import Path

import pytest
import yaml

from context_builder.coverage.analyzer import (
    AnalyzerConfig,
    ComponentConfig,
    CoverageAnalyzer,
    _normalize_coverage_scale,
)
from context_builder.coverage.keyword_matcher import KeywordConfig, KeywordMatcher
from context_builder.coverage.rule_engine import RuleConfig, RuleEngine
from context_builder.coverage.schemas import (
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
    PrimaryRepairResult,
)

_WORKSPACE_COVERAGE_DIR = (
    Path(__file__).resolve().parents[2]
    / "workspaces" / "nsa" / "config" / "coverage"
)


def _load_yaml(filename: str) -> dict:
    """Load a YAML file from the NSA workspace coverage config directory."""
    path = _WORKSPACE_COVERAGE_DIR / filename
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@pytest.fixture(scope="session")
def nsa_component_config():
    """Load the NSA component config from the workspace YAML file."""
    data = _load_yaml("nsa_component_config.yaml")
    if data:
        return ComponentConfig.from_dict(data)
    return ComponentConfig.default()


@pytest.fixture(scope="session")
def nsa_rule_config():
    """Load NSA rule config from workspace."""
    data = _load_yaml("nsa_coverage_config.yaml")
    return RuleConfig.from_dict(data.get("rules", {}))


@pytest.fixture(scope="session")
def nsa_keyword_config():
    """Load NSA keyword config from workspace."""
    data = _load_yaml("nsa_keyword_mappings.yaml")
    return KeywordConfig.from_dict(data)


class TestCoverageAnalyzer:
    """Tests for CoverageAnalyzer class."""

    @pytest.fixture
    def analyzer(self, nsa_rule_config, nsa_keyword_config, nsa_component_config):
        """Create analyzer with NSA config, LLM disabled for faster tests."""
        config = AnalyzerConfig(
            use_llm_fallback=False,  # Disable LLM for unit tests
        )
        return CoverageAnalyzer(
            config=config,
            rule_engine=RuleEngine(nsa_rule_config),
            keyword_matcher=KeywordMatcher(nsa_keyword_config),
            component_config=nsa_component_config,
        )

    @pytest.fixture
    def sample_line_items(self):
        """Sample line items for testing."""
        return [
            # Fee item - should be excluded by rule
            {"description": "HANDLING FEE", "item_type": "fee", "total_price": 50.0},
            # Disposal fee - excluded by pattern
            {"description": "ENTSORGUNG ALTOEL", "item_type": "parts", "total_price": 25.0},
            # Engine part - should match keyword
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 150.0},
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
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 358.0},
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
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 358.0},
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
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 358.0},
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


class TestIsSystemCovered:
    """Tests for _is_system_covered with category aliases."""

    @pytest.fixture
    def analyzer(self, nsa_component_config):
        return CoverageAnalyzer(config=AnalyzerConfig(use_llm_fallback=False), component_config=nsa_component_config)

    def test_exact_match(self, analyzer):
        assert analyzer._is_system_covered("engine", ["engine", "brakes"]) is True

    def test_substring_match(self, analyzer):
        assert analyzer._is_system_covered("electric", ["electrical_system"]) is True

    def test_no_match(self, analyzer):
        assert analyzer._is_system_covered("engine", ["brakes", "chassis"]) is False

    def test_empty_system(self, analyzer):
        assert analyzer._is_system_covered("", ["engine"]) is False

    def test_axle_drive_alias_matches_four_wd(self, analyzer):
        """axle_drive should match when four_wd is covered (alias)."""
        assert analyzer._is_system_covered("axle_drive", ["four_wd"]) is True

    def test_four_wd_alias_matches_axle_drive(self, analyzer):
        """four_wd should match when axle_drive is covered (alias)."""
        assert analyzer._is_system_covered("four_wd", ["axle_drive"]) is True

    def test_differential_alias_matches_four_wd(self, analyzer):
        """differential should match when four_wd is covered."""
        assert analyzer._is_system_covered("differential", ["four_wd"]) is True

    def test_electronics_alias_matches_electrical_system(self, analyzer):
        """electronics should match when electrical_system is covered."""
        assert analyzer._is_system_covered("electronics", ["electrical_system"]) is True

    def test_alias_no_false_positive(self, analyzer):
        """Alias check should not create false positives for unrelated categories."""
        assert analyzer._is_system_covered("axle_drive", ["engine", "brakes"]) is False


class TestIsComponentInPolicyList:
    """Tests for _is_component_in_policy_list (consolidated method)."""

    @pytest.fixture
    def analyzer(self, nsa_component_config):
        return CoverageAnalyzer(config=AnalyzerConfig(use_llm_fallback=False), component_config=nsa_component_config)

    @pytest.fixture
    def covered_components(self):
        return {
            "engine": ["Zahnriemen", "Wasserpumpe", "Ölkühler", "Kolben"],
            "chassis": ["Stossdämpfer", "Federbein"],
        }

    def test_known_component_found_in_french_policy(self, analyzer):
        """Known component matched via French synonym in policy list."""
        policy = {"engine": ["courroie de distribution", "pompe à eau"]}
        found, reason = analyzer._is_component_in_policy_list(
            "timing_belt", "engine", policy,
        )
        assert found is True
        assert "found in policy list" in reason

    def test_known_component_not_in_policy(self, analyzer, covered_components):
        """Known component whose synonyms don't match any policy part."""
        found, reason = analyzer._is_component_in_policy_list(
            "turbocharger", "engine", covered_components,
        )
        assert found is False
        assert "not found in policy" in reason

    def test_unknown_component_returns_none(self, analyzer, covered_components):
        """Unknown component (no synonym entry) returns None (needs LLM verification)."""
        found, reason = analyzer._is_component_in_policy_list(
            "flux_capacitor", "engine", covered_components,
        )
        assert found is None
        assert "needs LLM verification" in reason

    def test_unknown_component_strict_returns_false(self, analyzer, covered_components):
        """Unknown component in strict mode returns False."""
        found, reason = analyzer._is_component_in_policy_list(
            "flux_capacitor", "engine", covered_components, strict=True,
        )
        assert found is False
        assert "strict mode" in reason

    def test_none_component_no_description_returns_none(self, analyzer, covered_components):
        """None component with no description → uncertain (needs LLM)."""
        found, reason = analyzer._is_component_in_policy_list(
            None, "engine", covered_components,
        )
        assert found is None
        assert "No specific component" in reason

    def test_none_component_with_matching_description_returns_true(self, analyzer, covered_components):
        """None component but description matches a policy part → True."""
        found, reason = analyzer._is_component_in_policy_list(
            None, "engine", covered_components, description="KOLBEN AUSTAUSCH",
        )
        assert found is True
        assert "kolben" in reason.lower()

    def test_none_system_returns_true(self, analyzer, covered_components):
        """None system should pass through as True."""
        found, reason = analyzer._is_component_in_policy_list(
            "timing_belt", None, covered_components,
        )
        assert found is True

    def test_category_not_in_policy_returns_none(self, analyzer, covered_components):
        """Category missing from policy → no parts list → None (needs verification)."""
        found, reason = analyzer._is_component_in_policy_list(
            "timing_belt", "turbo_supercharger", covered_components,
        )
        assert found is None
        assert "No specific parts list" in reason

    def test_description_fallback_no_synonyms_matches_policy_part(self, analyzer, covered_components):
        """Unknown component with description matching a policy part returns True."""
        found, reason = analyzer._is_component_in_policy_list(
            "some_widget", "engine", covered_components,
            description="Ersatz Zahnriemen inkl. Montage",
        )
        # "some_widget" has no synonyms, but "Zahnriemen" in description
        # matches a policy part directly → returns True
        assert found is True
        assert "Description contains policy part" in reason

    def test_space_vs_underscore_key_variants(self, analyzer, covered_components):
        """Component given with spaces should resolve to underscore key."""
        found, reason = analyzer._is_component_in_policy_list(
            "timing belt", "engine", covered_components,
        )
        assert found is True
        assert "found in policy list" in reason


class TestValidateLLMCoverageDecision:
    """Tests for _validate_llm_coverage_decision."""

    @pytest.fixture
    def analyzer(self, nsa_component_config):
        return CoverageAnalyzer(config=AnalyzerConfig(use_llm_fallback=False), component_config=nsa_component_config)

    @pytest.fixture
    def covered_components(self):
        return {
            "engine": ["Zahnriemen", "Wasserpumpe", "Kolben"],
        }

    @pytest.fixture
    def excluded_components(self):
        return {
            "consumables": ["Motoröl", "Ölfilter"],
        }

    def _make_item(self, **overrides):
        defaults = dict(
            item_code="P001",
            description="test part",
            item_type="parts",
            total_price=100.0,
            coverage_status=CoverageStatus.COVERED,
            coverage_category="engine",
            matched_component="timing_belt",
            match_method=MatchMethod.LLM,
            match_confidence=0.75,
            match_reasoning="LLM decided covered",
            covered_amount=100.0,
            not_covered_amount=0.0,
        )
        defaults.update(overrides)
        return LineItemCoverage(**defaults)

    def test_non_llm_item_passes_through(self, analyzer, covered_components, excluded_components):
        """Non-LLM items should be returned unchanged."""
        item = self._make_item(match_method=MatchMethod.RULE)
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        assert result.coverage_status == CoverageStatus.COVERED

    def test_excluded_item_overridden_to_not_covered(self, analyzer, covered_components, excluded_components):
        """Item in excluded list should be forced to NOT_COVERED."""
        item = self._make_item(description="Motoröl 5W40")
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert "OVERRIDE" in result.match_reasoning

    def test_covered_item_not_in_list_but_category_covered_stays_covered(self, analyzer, covered_components, excluded_components):
        """LLM COVERED item in a covered category stays COVERED even if specific component isn't listed."""
        item = self._make_item(matched_component="turbocharger")
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        # Category "engine" is covered → item stays COVERED
        assert result.coverage_status == CoverageStatus.COVERED

    def test_covered_item_in_policy_stays_covered(self, analyzer, covered_components, excluded_components):
        """LLM COVERED item whose component IS in policy stays COVERED."""
        item = self._make_item(
            matched_component="water_pump",
            description="Wasserpumpe defekt",
        )
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        assert result.coverage_status == CoverageStatus.COVERED

    def test_already_not_covered_unchanged(self, analyzer, covered_components, excluded_components):
        """LLM NOT_COVERED item stays NOT_COVERED."""
        item = self._make_item(coverage_status=CoverageStatus.NOT_COVERED)
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_unknown_component_in_covered_category_stays_covered(self, analyzer, covered_components, excluded_components):
        """LLM item with unknown component in a covered category stays COVERED."""
        item = self._make_item(matched_component="quantum_inverter")
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        # Category "engine" is covered → item stays COVERED regardless of component name
        assert result.coverage_status == CoverageStatus.COVERED

    def test_item_in_uncovered_category_becomes_review_needed(self, analyzer, covered_components, excluded_components):
        """LLM COVERED item in an uncovered category → REVIEW_NEEDED."""
        item = self._make_item(
            coverage_category="body",
            matched_component="door_handle",
        )
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        # Category "body" is not in covered_components → override to REVIEW_NEEDED
        assert result.coverage_status == CoverageStatus.REVIEW_NEEDED
        assert "REVIEW" in result.match_reasoning


class TestLLMMatcherPromptBuilding:
    """Tests for LLM matcher _build_prompt_messages with repair context."""

    @pytest.fixture
    def matcher(self):
        from context_builder.coverage.llm_matcher import LLMMatcher, LLMMatcherConfig
        # Use inline prompt (no file) for testing
        return LLMMatcher(config=LLMMatcherConfig(prompt_name="nonexistent_prompt"))

    def test_build_prompt_without_repair_context(self, matcher):
        """Prompt messages should be built without repair context."""
        messages = matcher._build_prompt_messages(
            description="VENTIL",
            item_type="parts",
            covered_categories=["engine"],
            covered_components={"engine": ["Ventil"]},
        )
        assert len(messages) == 2
        assert "VENTIL" in messages[1]["content"]

    def test_build_prompt_with_repair_context(self, matcher):
        """When repair_context_description is provided, it should appear in the prompt."""
        messages = matcher._build_prompt_messages(
            description="MULTIFUNKTIONSEINHEIT",
            item_type="parts",
            covered_categories=["electrical_system"],
            covered_components={"electrical_system": ["I-Drive"]},
            repair_context_description="I-Drive Schalter klemmt Teilweise /ersetzen",
        )
        # The inline fallback doesn't use repair_context_description,
        # but the template-based prompt does. Verify messages are returned.
        assert len(messages) == 2
        assert "MULTIFUNKTIONSEINHEIT" in messages[1]["content"]


class TestDeferToLLM:
    """Tests for deferring uncovered-category items to LLM."""

    @pytest.fixture
    def analyzer(self, nsa_component_config):
        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config, component_config=nsa_component_config)
        # Set up a mock part_lookup that returns a result
        return analyzer

    def test_deferred_when_has_repair_context(self, nsa_component_config):
        """Item with non-covered category + repair context should be deferred (unmatched)."""
        from unittest.mock import MagicMock, patch
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config, component_config=nsa_component_config)

        # Mock part_lookup to return a result in an uncovered category
        mock_lookup = MagicMock()
        mock_result = PartLookupResult(
            part_number="12345",
            found=True,
            system="engine",
            component="oil_filter_housing",
            component_description="Gehäuse, Ölfilter",
            covered=None,
            note=None,
            lookup_source="assumptions",
        )
        mock_lookup.lookup.return_value = mock_result
        mock_lookup.lookup_by_description.return_value = None
        analyzer.part_lookup = mock_lookup

        items = [
            {
                "item_code": "12345",
                "description": "Gehäuse, Ölfilter",
                "item_type": "parts",
                "total_price": 100.0,
                "repair_description": "Ölkühler defekt ersetzen",
            },
        ]

        matched, unmatched = analyzer._match_by_part_number(
            items,
            covered_categories=["brakes"],  # engine NOT covered
            covered_components={"brakes": ["Bremssattel"]},
        )

        # Should be deferred (unmatched) because it has repair context
        assert len(unmatched) == 1
        assert len(matched) == 0

    def test_not_deferred_when_no_context_no_aliases(self, nsa_component_config):
        """Item with non-covered category, no repair context, no aliases → NOT_COVERED."""
        from unittest.mock import MagicMock
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config, component_config=nsa_component_config)

        mock_lookup = MagicMock()
        mock_result = PartLookupResult(
            part_number="99999",
            found=True,
            system="turbo_supercharger",
            component="wastegate",
            component_description="Wastegate",
            covered=None,
            note=None,
            lookup_source="assumptions",
        )
        mock_lookup.lookup.return_value = mock_result
        mock_lookup.lookup_by_description.return_value = None
        analyzer.part_lookup = mock_lookup

        items = [
            {
                "item_code": "99999",
                "description": "Wastegate",
                "item_type": "parts",
                "total_price": 200.0,
            },
        ]

        matched, unmatched = analyzer._match_by_part_number(
            items,
            covered_categories=["brakes"],
            covered_components={"brakes": ["Bremssattel"]},
        )

        # Should be NOT_COVERED immediately (no context, no aliases for turbo_supercharger)
        assert len(matched) == 1
        assert matched[0].coverage_status == CoverageStatus.NOT_COVERED
        assert len(unmatched) == 0

    def test_deferred_when_category_has_aliases(self, nsa_component_config):
        """Item with non-covered category but category has aliases → deferred."""
        from unittest.mock import MagicMock
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config, component_config=nsa_component_config)

        mock_lookup = MagicMock()
        mock_result = PartLookupResult(
            part_number="DIFF001",
            found=True,
            system="axle_drive",
            component="differential",
            component_description="DIFFERENTIEL ARRIERE",
            covered=None,
            note=None,
            lookup_source="assumptions",
        )
        mock_lookup.lookup.return_value = mock_result
        mock_lookup.lookup_by_description.return_value = None
        analyzer.part_lookup = mock_lookup

        items = [
            {
                "item_code": "DIFF001",
                "description": "DIFFERENTIEL ARRIERE",
                "item_type": "parts",
                "total_price": 500.0,
            },
        ]

        matched, unmatched = analyzer._match_by_part_number(
            items,
            covered_categories=["four_wd"],  # axle_drive not directly listed
            covered_components={"four_wd": ["Differential"]},
        )

        # axle_drive has aliases (four_wd) so it should be deferred
        # BUT actually _is_system_covered now resolves this via aliases,
        # so it should be COVERED directly (Change 1 handles this case).
        # Only items where _is_system_covered still fails are deferred.
        # With Change 1, axle_drive + four_wd in covered → covered directly.
        assert len(matched) == 1
        assert matched[0].coverage_status == CoverageStatus.COVERED


class TestGasketSealDeferral:
    """Tests for gasket/seal indicator deferral in _match_by_part_number."""

    def test_joint_defers_keyword_match_to_llm(self, nsa_component_config):
        """'Joint du vilebrequin' should be deferred — it's a seal, not the crankshaft."""
        from unittest.mock import MagicMock
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config, component_config=nsa_component_config)

        mock_lookup = MagicMock()
        mock_lookup.lookup.return_value = PartLookupResult(
            part_number="", found=False, lookup_source="none",
        )
        mock_lookup.lookup_by_description.return_value = PartLookupResult(
            part_number="keyword:vilebrequin",
            found=True,
            system="engine",
            component="crankshaft",
            component_description="Kurbelwelle",
            covered=None,
            note=None,
            lookup_source="assumptions_keyword",
        )
        analyzer.part_lookup = mock_lookup

        items = [
            {
                "item_code": None,
                "description": "Joint du vilebrequin",
                "item_type": "parts",
                "total_price": 56.30,
            },
        ]

        matched, unmatched = analyzer._match_by_part_number(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["kurbelwelle"]},
        )

        assert len(unmatched) == 1
        assert len(matched) == 0
        assert unmatched[0].get("_part_lookup_system") == "engine"
        assert unmatched[0].get("_part_lookup_component") == "crankshaft"

    def test_dichtung_defers_keyword_match_to_llm(self, nsa_component_config):
        """'Motordichtung' should be deferred — it's a gasket, not the engine."""
        from unittest.mock import MagicMock
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config, component_config=nsa_component_config)

        mock_lookup = MagicMock()
        mock_lookup.lookup.return_value = PartLookupResult(
            part_number="", found=False, lookup_source="none",
        )
        mock_lookup.lookup_by_description.return_value = PartLookupResult(
            part_number="keyword:motor",
            found=True,
            system="engine",
            component="engine",
            component_description="Motor",
            covered=None,
            note=None,
            lookup_source="assumptions_keyword",
        )
        analyzer.part_lookup = mock_lookup

        items = [
            {
                "item_code": None,
                "description": "Motordichtung Satz",
                "item_type": "parts",
                "total_price": 45.00,
            },
        ]

        matched, unmatched = analyzer._match_by_part_number(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["ölpumpe"]},
        )

        assert len(unmatched) == 1
        assert len(matched) == 0

    def test_no_gasket_indicator_matches_normally(self, nsa_component_config):
        """'Poulie du vilebrequin' has no gasket indicator — should match normally."""
        from unittest.mock import MagicMock
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config, component_config=nsa_component_config)

        mock_lookup = MagicMock()
        mock_lookup.lookup.return_value = PartLookupResult(
            part_number="", found=False, lookup_source="none",
        )
        mock_lookup.lookup_by_description.return_value = PartLookupResult(
            part_number="keyword:vilebrequin",
            found=True,
            system="engine",
            component="crankshaft",
            component_description="Kurbelwelle",
            covered=None,
            note=None,
            lookup_source="assumptions_keyword",
        )
        analyzer.part_lookup = mock_lookup

        items = [
            {
                "item_code": None,
                "description": "Poulie du vilebrequin",
                "item_type": "parts",
                "total_price": 80.0,
            },
        ]

        matched, unmatched = analyzer._match_by_part_number(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["kurbelwelle"]},
        )

        assert len(matched) == 1
        assert len(unmatched) == 0
        assert matched[0].coverage_status == CoverageStatus.COVERED

    def test_exact_part_number_ignores_gasket_indicator(self, nsa_component_config):
        """Exact part number match should NOT be deferred even if description says 'Joint'."""
        from unittest.mock import MagicMock
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config, component_config=nsa_component_config)

        mock_lookup = MagicMock()
        # Exact part number match (lookup_source without "keyword")
        mock_lookup.lookup.return_value = PartLookupResult(
            part_number="OE-12345",
            found=True,
            system="engine",
            component="crankshaft",
            component_description="Kurbelwelle",
            covered=None,
            note=None,
            lookup_source="assumptions",
        )
        mock_lookup.lookup_by_description.return_value = None
        analyzer.part_lookup = mock_lookup

        items = [
            {
                "item_code": "OE-12345",
                "description": "Joint du vilebrequin",
                "item_type": "parts",
                "total_price": 56.30,
            },
        ]

        matched, unmatched = analyzer._match_by_part_number(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["kurbelwelle"]},
        )

        # Exact part number match should not be deferred
        assert len(matched) == 1
        assert len(unmatched) == 0


class TestNormalizeComponentName:
    """Tests for CoverageAnalysisService._normalize_component_name."""

    def test_nbsp_replaced_with_a_grave(self):
        """NBSP (\\xa0) in component names should be replaced with 'à'."""
        from context_builder.api.services.coverage_analysis import CoverageAnalysisService
        assert CoverageAnalysisService._normalize_component_name("pompe \xa0 huile") == "pompe à huile"

    def test_multiple_nbsp_replaced(self):
        """Multiple NBSP occurrences should all be replaced."""
        from context_builder.api.services.coverage_analysis import CoverageAnalysisService
        assert CoverageAnalysisService._normalize_component_name(
            "pignon d'arbre \xa0 cames"
        ) == "pignon d'arbre à cames"

    def test_normal_string_unchanged(self):
        """Normal strings without NBSP pass through unchanged."""
        from context_builder.api.services.coverage_analysis import CoverageAnalysisService
        assert CoverageAnalysisService._normalize_component_name("pompe à huile") == "pompe à huile"

    def test_non_string_passthrough(self):
        """Non-string values pass through unchanged."""
        from context_builder.api.services.coverage_analysis import CoverageAnalysisService
        assert CoverageAnalysisService._normalize_component_name(42) == 42

    def test_empty_string(self):
        """Empty string passes through unchanged."""
        from context_builder.api.services.coverage_analysis import CoverageAnalysisService
        assert CoverageAnalysisService._normalize_component_name("") == ""


class TestDistributionCatchAll:
    """Tests for distribution catch-all matching in _is_component_in_policy_list."""

    @pytest.fixture
    def analyzer(self, nsa_component_config):
        return CoverageAnalyzer(config=AnalyzerConfig(use_llm_fallback=False), component_config=nsa_component_config)

    def test_timing_gear_matches_distribution_catchall(self, analyzer):
        """timing_gear should match when policy has 'Ensemble de distribution'."""
        policy = {"engine": ["Ensemble de distribution (y compris courroie et chaîne)"]}
        found, reason = analyzer._is_component_in_policy_list(
            "timing_gear", "engine", policy,
        )
        assert found is True
        assert "distribution" in reason.lower()

    def test_timing_belt_matches_distribution_catchall(self, analyzer):
        """timing_belt should match via the distribution catch-all."""
        policy = {"engine": ["Ensemble de distribution"]}
        found, reason = analyzer._is_component_in_policy_list(
            "timing_belt", "engine", policy,
        )
        assert found is True

    def test_chain_tensioner_matches_distribution_catchall(self, analyzer):
        """chain_tensioner should match via the distribution catch-all."""
        policy = {"engine": ["Ensemble de distribution (y compris courroie et chaîne)"]}
        found, reason = analyzer._is_component_in_policy_list(
            "chain_tensioner", "engine", policy,
        )
        assert found is True

    def test_pulley_matches_distribution_catchall(self, analyzer):
        """pulley should match via the distribution catch-all."""
        policy = {"engine": ["Ensemble de distribution"]}
        found, reason = analyzer._is_component_in_policy_list(
            "pulley", "engine", policy,
        )
        assert found is True

    def test_valve_body_not_matched_by_distribution(self, analyzer):
        """Non-distribution component should NOT match via catch-all."""
        policy = {"engine": ["Ensemble de distribution (y compris courroie et chaîne)"]}
        found, reason = analyzer._is_component_in_policy_list(
            "valve_body", "engine", policy,
        )
        # valve_body has synonyms but none match "distribution"
        assert found is not True  # Either False or None

    def test_oil_pump_not_matched_by_distribution(self, analyzer):
        """oil_pump is NOT a distribution component, shouldn't match catch-all."""
        policy = {"engine": ["Ensemble de distribution"]}
        found, reason = analyzer._is_component_in_policy_list(
            "oil_pump", "engine", policy,
        )
        # oil_pump has synonyms ("ölpumpe", "pompe à huile") but none are distribution parts
        assert found is not True


class TestDeterminePrimaryRepair:
    """Tests for _determine_primary_repair (three-tier approach)."""

    @pytest.fixture
    def analyzer(self, nsa_component_config):
        return CoverageAnalyzer(
            config=AnalyzerConfig(use_llm_fallback=False),
            component_config=nsa_component_config,
        )

    def _make_item(self, **overrides):
        defaults = dict(
            item_code="P001",
            description="test part",
            item_type="parts",
            total_price=100.0,
            coverage_status=CoverageStatus.COVERED,
            coverage_category="engine",
            matched_component="timing_belt",
            match_method=MatchMethod.KEYWORD,
            match_confidence=0.90,
            match_reasoning="Keyword match",
            covered_amount=100.0,
            not_covered_amount=0.0,
        )
        defaults.update(overrides)
        return LineItemCoverage(**defaults)

    def test_tier1a_highest_value_covered_part(self, analyzer):
        """Tier 1a: highest-value COVERED parts item is selected."""
        items = [
            self._make_item(description="Small part", total_price=50.0),
            self._make_item(description="Big part", total_price=500.0, matched_component="water_pump"),
            self._make_item(description="Labor", item_type="labor", total_price=300.0),
        ]
        result = analyzer._determine_primary_repair(items, {}, None, "TEST")
        assert result.determination_method == "deterministic"
        assert result.description == "Big part"
        assert result.is_covered is True
        assert result.confidence >= 0.85

    def test_tier1b_highest_value_covered_any_when_no_parts(self, analyzer):
        """Tier 1b: when no covered parts, use highest covered item of any type."""
        items = [
            self._make_item(
                description="Motor repair labor", item_type="labor",
                total_price=400.0, matched_component="engine",
            ),
            self._make_item(
                description="Not covered part", item_type="parts",
                total_price=200.0, coverage_status=CoverageStatus.NOT_COVERED,
                matched_component="turbocharger",
            ),
        ]
        result = analyzer._determine_primary_repair(items, {}, None, "TEST")
        assert result.determination_method == "deterministic"
        assert result.description == "Motor repair labor"
        assert result.is_covered is True

    def test_tier2_repair_context(self, analyzer):
        """Tier 2: repair context primary component used when no covered items."""
        from types import SimpleNamespace
        items = [
            self._make_item(
                description="Uncovered part", coverage_status=CoverageStatus.NOT_COVERED,
                matched_component=None,
            ),
        ]
        repair_ctx = SimpleNamespace(
            primary_component="timing_chain",
            primary_category="engine",
            source_description="Steuerkette ersetzen",
            is_covered=True,
        )
        result = analyzer._determine_primary_repair(items, {}, repair_ctx, "TEST")
        assert result.determination_method == "repair_context"
        assert result.component == "timing_chain"
        assert result.confidence == 0.80
        assert result.is_covered is True

    def test_fallback_none_when_no_tiers_match(self, analyzer):
        """Fallback: no covered items, no repair context → determination_method='none'."""
        items = [
            self._make_item(
                description="Unknown part", coverage_status=CoverageStatus.REVIEW_NEEDED,
                matched_component=None,
            ),
        ]
        result = analyzer._determine_primary_repair(items, {}, None, "TEST")
        assert result.determination_method == "none"
        assert result.is_covered is None

    def test_empty_items_returns_none(self, analyzer):
        """Empty line items → determination_method='none'."""
        result = analyzer._determine_primary_repair([], {}, None, "TEST")
        assert result.determination_method == "none"

    def test_tier1a_over_tier1b(self, analyzer):
        """Tier 1a (parts) takes priority over tier 1b (any type) even if labor is higher value."""
        items = [
            self._make_item(description="Covered part", total_price=100.0, item_type="parts"),
            self._make_item(
                description="Expensive labor", total_price=500.0, item_type="labor",
                matched_component="engine",
            ),
        ]
        result = analyzer._determine_primary_repair(items, {}, None, "TEST")
        assert result.determination_method == "deterministic"
        assert result.description == "Covered part"

    def test_source_item_index_populated(self, analyzer):
        """source_item_index should be the index of the selected item."""
        items = [
            self._make_item(description="Not covered", coverage_status=CoverageStatus.NOT_COVERED, matched_component=None),
            self._make_item(description="Fee", item_type="fee", total_price=10.0, coverage_status=CoverageStatus.NOT_COVERED, matched_component=None),
            self._make_item(description="The one", total_price=400.0),
        ]
        result = analyzer._determine_primary_repair(items, {}, None, "TEST")
        assert result.source_item_index == 2

    def test_tier2_repair_context_not_covered(self, analyzer):
        """Tier 2: repair context works even if component is not covered."""
        from types import SimpleNamespace
        items = [
            self._make_item(
                description="Uncovered part", coverage_status=CoverageStatus.NOT_COVERED,
                matched_component=None,
            ),
        ]
        repair_ctx = SimpleNamespace(
            primary_component="turbocharger",
            primary_category="turbo_supercharger",
            source_description="Turbolader ersetzen",
            is_covered=False,
        )
        result = analyzer._determine_primary_repair(items, {}, repair_ctx, "TEST")
        assert result.determination_method == "repair_context"
        assert result.component == "turbocharger"
        assert result.is_covered is False

    def test_tier1c_highest_value_uncovered_item(self, analyzer):
        """Tier 1c: when nothing is covered and no repair context, pick highest uncovered with matched_component."""
        items = [
            self._make_item(
                description="Small uncovered", coverage_status=CoverageStatus.NOT_COVERED,
                total_price=200.0, matched_component="gasket",
            ),
            self._make_item(
                description="Trunk control unit", coverage_status=CoverageStatus.NOT_COVERED,
                total_price=1164.0, matched_component="control_unit",
                coverage_category="electronics",
            ),
            self._make_item(
                description="No component match", coverage_status=CoverageStatus.NOT_COVERED,
                total_price=500.0, matched_component=None,
            ),
        ]
        result = analyzer._determine_primary_repair(items, {}, None, "TEST")
        assert result.determination_method == "deterministic"
        assert result.description == "Trunk control unit"
        assert result.is_covered is False
        assert result.source_item_index == 1

    def test_tier2_before_tier1c(self, analyzer):
        """Tier 2 (repair context) takes priority over tier 1c (uncovered items)."""
        from types import SimpleNamespace
        items = [
            self._make_item(
                description="Expensive uncovered", coverage_status=CoverageStatus.NOT_COVERED,
                total_price=1000.0, matched_component="control_unit",
            ),
        ]
        repair_ctx = SimpleNamespace(
            primary_component="angle_gearbox",
            primary_category="axle_drive",
            source_description="Winkelgetriebe aus/einbau",
            is_covered=True,
        )
        result = analyzer._determine_primary_repair(items, {}, repair_ctx, "TEST")
        assert result.determination_method == "repair_context"
        assert result.component == "angle_gearbox"


class TestNormalizeCoverageScale:
    """Tests for _normalize_coverage_scale helper."""

    def test_old_list_format(self):
        """Old list format returns (None, list)."""
        tiers = [
            {"km_threshold": 50000, "coverage_percent": 80},
            {"km_threshold": 100000, "coverage_percent": 60},
        ]
        age_threshold, result_tiers = _normalize_coverage_scale(tiers)
        assert age_threshold is None
        assert result_tiers == tiers

    def test_new_dict_format_with_age(self):
        """New dict format with age returns (8, tiers)."""
        raw = {
            "age_threshold_years": 8,
            "tiers": [
                {"km_threshold": 50000, "coverage_percent": 90, "age_coverage_percent": 80},
                {"km_threshold": 100000, "coverage_percent": 70, "age_coverage_percent": 60},
            ],
        }
        age_threshold, tiers = _normalize_coverage_scale(raw)
        assert age_threshold == 8
        assert len(tiers) == 2
        assert tiers[0]["age_coverage_percent"] == 80

    def test_new_dict_format_without_age(self):
        """New dict format without age returns (None, tiers)."""
        raw = {
            "age_threshold_years": None,
            "tiers": [
                {"km_threshold": 100000, "coverage_percent": 80, "age_coverage_percent": None},
            ],
        }
        age_threshold, tiers = _normalize_coverage_scale(raw)
        assert age_threshold is None
        assert len(tiers) == 1

    def test_none_input(self):
        """None input returns (None, None)."""
        age_threshold, tiers = _normalize_coverage_scale(None)
        assert age_threshold is None
        assert tiers is None

    def test_invalid_input(self):
        """Invalid input (string) returns (None, None)."""
        age_threshold, tiers = _normalize_coverage_scale("not a scale")
        assert age_threshold is None
        assert tiers is None

    def test_empty_dict(self):
        """Empty dict returns (None, [])."""
        age_threshold, tiers = _normalize_coverage_scale({})
        assert age_threshold is None
        assert tiers == []

    def test_empty_list(self):
        """Empty list returns (None, [])."""
        age_threshold, tiers = _normalize_coverage_scale([])
        assert age_threshold is None
        assert tiers == []


class TestPerTierAgeCoverage:
    """Tests for per-tier age-adjusted coverage rates."""

    @pytest.fixture
    def analyzer(self, nsa_rule_config, nsa_keyword_config, nsa_component_config):
        config = AnalyzerConfig(use_llm_fallback=False)
        return CoverageAnalyzer(
            config=config,
            rule_engine=RuleEngine(nsa_rule_config),
            keyword_matcher=KeywordMatcher(nsa_keyword_config),
            component_config=nsa_component_config,
        )

    @pytest.fixture
    def covered_components(self):
        return {"engine": ["Motor", "Kolben", "Zylinder"]}

    @pytest.fixture
    def age_tier_scale(self):
        """Coverage scale with per-tier age rates."""
        return [
            {"km_threshold": 50000, "coverage_percent": 90, "age_coverage_percent": 80},
            {"km_threshold": 80000, "coverage_percent": 70, "age_coverage_percent": 60},
            {"km_threshold": 110000, "coverage_percent": 50, "age_coverage_percent": 40},
        ]

    @pytest.fixture
    def no_age_scale(self):
        """Coverage scale without age column."""
        return [
            {"km_threshold": 50000, "coverage_percent": 90, "age_coverage_percent": None},
            {"km_threshold": 80000, "coverage_percent": 70, "age_coverage_percent": None},
        ]

    def test_young_vehicle_uses_mileage_rate(self, analyzer, covered_components, age_tier_scale):
        """Young vehicle (below age threshold) uses the normal mileage rate."""
        result = analyzer.analyze(
            claim_id="TEST_AGE_YOUNG",
            line_items=[{"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0}],
            covered_components=covered_components,
            vehicle_km=75000,
            coverage_scale=age_tier_scale,
            vehicle_age_years=5.0,
            age_threshold_years=8,
        )
        # 75k >= 50k → 90%, vehicle is 5y < 8y → no age adjustment
        assert result.inputs.coverage_percent == 90
        assert result.inputs.coverage_percent_effective == 90
        item = result.line_items[0]
        assert item.covered_amount == 900.0

    def test_old_vehicle_uses_per_tier_age_rate(self, analyzer, covered_components, age_tier_scale):
        """Old vehicle uses the per-tier age rate, not a flat blanket rate."""
        result = analyzer.analyze(
            claim_id="TEST_AGE_OLD",
            line_items=[{"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0}],
            covered_components=covered_components,
            vehicle_km=75000,
            coverage_scale=age_tier_scale,
            vehicle_age_years=10.0,
            age_threshold_years=8,
        )
        # 75k >= 50k → tier has age_coverage_percent=80, vehicle is 10y >= 8y → 80%
        assert result.inputs.coverage_percent == 90  # mileage-based
        assert result.inputs.coverage_percent_effective == 80  # age-adjusted
        item = result.line_items[0]
        assert item.covered_amount == 800.0

    def test_old_vehicle_high_km_uses_correct_tier(self, analyzer, covered_components, age_tier_scale):
        """Old vehicle at high km uses the correct tier's age rate."""
        result = analyzer.analyze(
            claim_id="TEST_AGE_HIGH_KM",
            line_items=[{"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0}],
            covered_components=covered_components,
            vehicle_km=95000,
            coverage_scale=age_tier_scale,
            vehicle_age_years=10.0,
            age_threshold_years=8,
        )
        # 95k >= 80k → tier: 70%/60%, vehicle is 10y >= 8y → 60%
        assert result.inputs.coverage_percent == 70
        assert result.inputs.coverage_percent_effective == 60
        item = result.line_items[0]
        assert item.covered_amount == 600.0

    def test_old_vehicle_no_age_column_no_adjustment(self, analyzer, covered_components, no_age_scale):
        """Old vehicle with policy lacking age column gets no age adjustment."""
        result = analyzer.analyze(
            claim_id="TEST_NO_AGE_COL",
            line_items=[{"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0}],
            covered_components=covered_components,
            vehicle_km=75000,
            coverage_scale=no_age_scale,
            vehicle_age_years=12.0,
            age_threshold_years=None,  # No age threshold from extraction
        )
        # 75k >= 50k → 90%, no age column → stays at 90%
        assert result.inputs.coverage_percent == 90
        assert result.inputs.coverage_percent_effective == 90

    def test_below_first_tier_old_vehicle_stays_at_100(self, analyzer, covered_components, age_tier_scale):
        """Below first tier + old vehicle: stays at 100% (conservative)."""
        result = analyzer.analyze(
            claim_id="TEST_BELOW_FIRST",
            line_items=[{"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0}],
            covered_components=covered_components,
            vehicle_km=20000,
            coverage_scale=age_tier_scale,
            vehicle_age_years=10.0,
            age_threshold_years=8,
        )
        # 20k < 50k → 100%, below first tier so no age rate defined → stays 100%
        assert result.inputs.coverage_percent == 100
        assert result.inputs.coverage_percent_effective == 100

    def test_old_list_format_backward_compat(self, analyzer, covered_components):
        """Old list format (no age_coverage_percent) works without age adjustment."""
        old_scale = [
            {"km_threshold": 50000, "coverage_percent": 80},
            {"km_threshold": 100000, "coverage_percent": 60},
        ]
        result = analyzer.analyze(
            claim_id="TEST_OLD_FORMAT",
            line_items=[{"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 1000.0}],
            covered_components=covered_components,
            vehicle_km=75000,
            coverage_scale=old_scale,
            vehicle_age_years=10.0,
            age_threshold_years=8,
        )
        # Old format has no age_coverage_percent → no age adjustment
        assert result.inputs.coverage_percent == 80
        assert result.inputs.coverage_percent_effective == 80
        item = result.line_items[0]
        assert item.covered_amount == 800.0
