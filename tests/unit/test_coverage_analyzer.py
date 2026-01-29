"""Tests for the coverage analyzer."""

import pytest

from context_builder.coverage.analyzer import (
    CATEGORY_ALIASES,
    COMPONENT_SYNONYMS,
    AnalyzerConfig,
    CoverageAnalyzer,
)
from context_builder.coverage.schemas import CoverageStatus, LineItemCoverage, MatchMethod


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


class TestIsSystemCovered:
    """Tests for _is_system_covered with category aliases."""

    @pytest.fixture
    def analyzer(self):
        return CoverageAnalyzer(config=AnalyzerConfig(use_llm_fallback=False))

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
    def analyzer(self):
        return CoverageAnalyzer(config=AnalyzerConfig(use_llm_fallback=False))

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

    def test_unknown_component_assumes_covered(self, analyzer, covered_components):
        """Unknown component (no synonym entry) falls back to True."""
        found, reason = analyzer._is_component_in_policy_list(
            "flux_capacitor", "engine", covered_components,
        )
        assert found is True
        assert "assuming covered" in reason

    def test_unknown_component_strict_returns_false(self, analyzer, covered_components):
        """Unknown component in strict mode returns False."""
        found, reason = analyzer._is_component_in_policy_list(
            "flux_capacitor", "engine", covered_components, strict=True,
        )
        assert found is False
        assert "strict mode" in reason

    def test_none_component_returns_true(self, analyzer, covered_components):
        """None component should pass through as True."""
        found, reason = analyzer._is_component_in_policy_list(
            None, "engine", covered_components,
        )
        assert found is True
        assert "No component" in reason

    def test_none_system_returns_true(self, analyzer, covered_components):
        """None system should pass through as True."""
        found, reason = analyzer._is_component_in_policy_list(
            "timing_belt", None, covered_components,
        )
        assert found is True

    def test_category_not_in_policy_returns_true(self, analyzer, covered_components):
        """Category missing from policy → no parts list → True."""
        found, reason = analyzer._is_component_in_policy_list(
            "timing_belt", "turbo_supercharger", covered_components,
        )
        assert found is True
        assert "No specific parts list" in reason

    def test_description_fallback_match(self, analyzer, covered_components):
        """Description containing a policy part name should match."""
        found, reason = analyzer._is_component_in_policy_list(
            "some_widget", "engine", covered_components,
            description="Ersatz Zahnriemen inkl. Montage",
        )
        # "some_widget" has no synonyms → fallback assumes covered
        # But if it did have synonyms that failed, description would catch it
        assert found is True

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
    def analyzer(self):
        return CoverageAnalyzer(config=AnalyzerConfig(use_llm_fallback=False))

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

    def test_covered_item_not_in_policy_becomes_review(self, analyzer, covered_components, excluded_components):
        """LLM COVERED item whose component isn't in policy → REVIEW_NEEDED."""
        item = self._make_item(matched_component="turbocharger")
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        assert result.coverage_status == CoverageStatus.REVIEW_NEEDED
        assert "REVIEW" in result.match_reasoning

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

    def test_unknown_llm_component_assumes_covered(self, analyzer, covered_components, excluded_components):
        """LLM item with unknown component type → fallback assumes covered."""
        item = self._make_item(matched_component="quantum_inverter")
        result = analyzer._validate_llm_coverage_decision(
            item, covered_components, excluded_components,
        )
        # No synonyms for "quantum_inverter", fallback assumes covered
        assert result.coverage_status == CoverageStatus.COVERED


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
    def analyzer(self):
        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config)
        # Set up a mock part_lookup that returns a result
        return analyzer

    def test_deferred_when_has_repair_context(self):
        """Item with non-covered category + repair context should be deferred (unmatched)."""
        from unittest.mock import MagicMock, patch
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config)

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

    def test_not_deferred_when_no_context_no_aliases(self):
        """Item with non-covered category, no repair context, no aliases → NOT_COVERED."""
        from unittest.mock import MagicMock
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config)

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

    def test_deferred_when_category_has_aliases(self):
        """Item with non-covered category but category has aliases → deferred."""
        from unittest.mock import MagicMock
        from context_builder.coverage.part_number_lookup import PartLookupResult

        config = AnalyzerConfig(use_llm_fallback=False)
        analyzer = CoverageAnalyzer(config=config)

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
