"""Tests for the coverage keyword matcher."""

import pytest
import yaml

from context_builder.coverage.analyzer import CoverageAnalyzer
from context_builder.coverage.keyword_matcher import KeywordConfig, KeywordMatcher
from context_builder.coverage.schemas import CoverageStatus, MatchMethod


class TestKeywordMatcher:
    """Tests for KeywordMatcher class."""

    def test_default_config(self):
        """Test that default NSA config is created correctly."""
        matcher = KeywordMatcher()
        assert matcher.config is not None
        assert len(matcher.config.mappings) > 0

    def test_motor_matches_engine(self):
        """Test that MOTOR keyword maps to engine category."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="MOTOR BLOCK",
            item_type="parts",
            total_price=150.0,
            covered_categories=["engine", "chassis"],
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED
        assert result.coverage_category == "engine"
        assert result.match_method == MatchMethod.KEYWORD
        assert result.match_confidence > 0.7

    def test_stossdaempfer_matches_chassis(self):
        """Test that STOSSDAEMPFER maps to chassis category."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="STOSSDAEMPFER HINTEN LINKS",
            item_type="parts",
            total_price=400.0,
            covered_categories=["chassis", "suspension"],
        )

        assert result is not None
        assert result.coverage_category == "chassis"

    def test_getriebe_matches_transmission(self):
        """Test that GETRIEBE maps to mechanical_transmission category."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="GETRIEBE REPARATUR",
            item_type="labor",
            total_price=800.0,
            covered_categories=["mechanical_transmission"],
        )

        assert result is not None
        assert result.coverage_category == "mechanical_transmission"

    def test_klimakompressor_matches_ac(self):
        """Test that KLIMAKOMPRESSOR maps to air_conditioning."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="KLIMAKOMPRESSOR",
            item_type="parts",
            total_price=900.0,
            covered_categories=["air_conditioning"],
        )

        assert result is not None
        assert result.coverage_category == "air_conditioning"

    def test_bremse_matches_brakes(self):
        """Test that BREMSE maps to brakes category."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="BREMSSATTEL VORNE",
            item_type="parts",
            total_price=250.0,
            covered_categories=["brakes"],
        )

        assert result is not None
        assert result.coverage_category == "brakes"

    def test_uncovered_category_returns_not_covered(self):
        """Test that matching a non-covered category returns NOT_COVERED."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="KLIMAKOMPRESSOR",
            item_type="parts",
            total_price=900.0,
            covered_categories=["engine", "brakes"],  # AC not covered
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert result.coverage_category == "air_conditioning"

    def test_no_match_returns_none(self):
        """Test that unmatched descriptions return None."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="RANDOM TEXT WITHOUT KEYWORDS",
            item_type="parts",
            total_price=100.0,
            covered_categories=["engine"],
        )

        assert result is None

    def test_case_insensitive_matching(self):
        """Test that matching is case insensitive."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="motor block",  # lowercase
            item_type="parts",
            total_price=150.0,
            covered_categories=["engine"],
        )

        assert result is not None
        assert result.coverage_category == "engine"

    def test_context_hint_boosts_confidence(self):
        """Test that context hints boost confidence."""
        matcher = KeywordMatcher()

        # MOTOR with ENGINE context hint should have boosted confidence
        result1 = matcher.match(
            description="MOTOR ENGINE BLOCK",
            item_type="parts",
            total_price=150.0,
            covered_categories=["engine"],
        )

        # MOTOR without context hint
        result2 = matcher.match(
            description="MOTOR REPARATUR",
            item_type="parts",
            total_price=150.0,
            covered_categories=["engine"],
        )

        assert result1 is not None
        assert result2 is not None
        # Both should match, confidence may vary
        assert result1.match_confidence >= result2.match_confidence

    def test_labor_for_covered_category(self):
        """Test that labor for covered category is covered."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="MOTOR REPARATUR ARBEIT",
            item_type="labor",
            total_price=300.0,
            covered_categories=["engine"],
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED

    def test_batch_match(self):
        """Test batch matching functionality."""
        matcher = KeywordMatcher()

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 150.0},
            {"description": "UNKNOWN PART", "item_type": "parts", "total_price": 100.0},
            {"description": "BREMSSATTEL", "item_type": "parts", "total_price": 250.0},
        ]

        covered_categories = ["engine", "brakes"]
        matched, unmatched = matcher.batch_match(items, covered_categories)

        # MOTOR and BREMSE should match
        assert len(matched) == 2
        # UNKNOWN should not match
        assert len(unmatched) == 1

    def test_batch_match_with_min_confidence(self):
        """Test batch matching with custom minimum confidence."""
        matcher = KeywordMatcher()

        items = [
            {"description": "MOTOR DICHTUNG", "item_type": "parts", "total_price": 150.0},
        ]

        # Very high threshold - nothing should match
        matched, unmatched = matcher.batch_match(
            items,
            covered_categories=["engine"],
            min_confidence=0.99,
        )

        # Should not match with very high threshold
        assert len(matched) == 0
        assert len(unmatched) == 1

    def test_item_code_preserved(self):
        """Test that item code is preserved in result."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="MOTOR DICHTUNG",
            item_type="parts",
            item_code="PART123",
            total_price=150.0,
            covered_categories=["engine"],
        )

        assert result is not None
        assert result.item_code == "PART123"

    def test_niveau_matches_chassis(self):
        """Test that NIVEAU (height control) maps to chassis."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="NIVEAUREGULIERUNG HINTEN",
            item_type="parts",
            total_price=600.0,
            covered_categories=["chassis"],
        )

        assert result is not None
        assert result.coverage_category == "chassis"

    def test_hydraulik_with_niveau_context(self):
        """Test HYDRAULIK with NIVEAU context maps to chassis."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="HYDRAULIK NIVEAU VENTIL",
            item_type="parts",
            total_price=350.0,
            covered_categories=["chassis"],
        )

        assert result is not None
        # Should match chassis due to HYDRAULIK or NIVEAU keywords
        assert result.coverage_category in ["chassis"]

    def test_empty_covered_categories(self):
        """Test with empty covered categories list."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="MOTOR DICHTUNG",
            item_type="parts",
            total_price=150.0,
            covered_categories=[],  # Nothing covered
        )

        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_empty_config_falls_back_to_defaults(self):
        """Empty KeywordConfig should trigger default_nsa() fallback."""
        empty = KeywordConfig(mappings=[])
        matcher = KeywordMatcher(empty)
        assert len(matcher.config.mappings) > 0

    def test_none_config_falls_back_to_defaults(self):
        """None config should trigger default_nsa() fallback."""
        matcher = KeywordMatcher(None)
        assert len(matcher.config.mappings) > 0

    def test_joint_reduces_confidence(self):
        """JOINT (gasket) alongside VILEBREQUIN should reduce confidence below 0.80."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="Joint du vilebrequin",
            item_type="parts",
            total_price=45.0,
            covered_categories=["engine"],
        )

        assert result is not None
        assert result.coverage_category == "engine"
        assert result.match_confidence < 0.80

    def test_dichtung_reduces_confidence(self):
        """DICHTUNG (seal) alongside MOTOR should reduce confidence below 0.80."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="MOTOR DICHTUNG",
            item_type="parts",
            total_price=30.0,
            covered_categories=["engine"],
        )

        assert result is not None
        assert result.coverage_category == "engine"
        assert result.match_confidence < 0.80

    def test_soufflet_reduces_confidence(self):
        """SOUFFLET (boot) alongside DIRECTION should reduce confidence below 0.80."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="SOUFFLET DE DIRECTION",
            item_type="parts",
            total_price=25.0,
            covered_categories=["steering"],
        )

        assert result is not None
        assert result.match_confidence < 0.80

    def test_component_without_consumable_unchanged(self):
        """VILEBREQUIN alone (no consumable term) should keep full confidence."""
        matcher = KeywordMatcher()

        result = matcher.match(
            description="VILEBREQUIN",
            item_type="parts",
            total_price=800.0,
            covered_categories=["engine"],
        )

        assert result is not None
        assert result.coverage_category == "engine"
        assert result.match_confidence == 0.88

    def test_consumable_falls_to_unmatched_in_batch(self):
        """Consumable items should fall to unmatched in batch_match (default threshold 0.80)."""
        matcher = KeywordMatcher()

        items = [
            {"description": "VILEBREQUIN", "item_type": "parts", "total_price": 800.0},
            {"description": "Joint du vilebrequin", "item_type": "parts", "total_price": 45.0},
            {"description": "MOTOR DICHTUNG", "item_type": "parts", "total_price": 30.0},
        ]

        matched, unmatched = matcher.batch_match(
            items,
            covered_categories=["engine"],
            min_confidence=0.80,
        )

        # Only VILEBREQUIN (no consumable term) should match
        assert len(matched) == 1
        assert matched[0].description == "VILEBREQUIN"
        # Gasket/seal items should fall to unmatched for LLM
        assert len(unmatched) == 2


class TestFromConfigPathKeywordLoading:
    """Tests for CoverageAnalyzer.from_config_path keyword discovery."""

    def test_loads_keywords_from_sibling_file(self, tmp_path):
        """from_config_path should load keywords from a sibling *_keyword_mappings.yaml."""
        # Write a main config with no keywords section
        main_config = {
            "analyzer": {"keyword_min_confidence": 0.80},
            "rules": {},
        }
        config_file = tmp_path / "nsa_coverage_config.yaml"
        config_file.write_text(yaml.dump(main_config), encoding="utf-8")

        # Write a sibling keyword mappings file
        keyword_data = {
            "mappings": [
                {
                    "category": "engine",
                    "keywords": ["MOTOR", "KOLBEN"],
                    "confidence": 0.90,
                },
            ],
        }
        keyword_file = tmp_path / "nsa_keyword_mappings.yaml"
        keyword_file.write_text(yaml.dump(keyword_data), encoding="utf-8")

        analyzer = CoverageAnalyzer.from_config_path(config_file)

        # Should have loaded the sibling keyword mappings
        assert len(analyzer.keyword_matcher.config.mappings) == 1
        assert analyzer.keyword_matcher.config.mappings[0].category == "engine"

    def test_falls_back_to_defaults_when_no_sibling(self, tmp_path):
        """from_config_path should fall back to defaults when no sibling file exists."""
        main_config = {
            "analyzer": {},
            "rules": {},
        }
        config_file = tmp_path / "nsa_coverage_config.yaml"
        config_file.write_text(yaml.dump(main_config), encoding="utf-8")

        analyzer = CoverageAnalyzer.from_config_path(config_file)

        # Should have fallen back to built-in defaults
        assert len(analyzer.keyword_matcher.config.mappings) > 0

    def test_inline_keywords_not_overridden(self, tmp_path):
        """from_config_path should use inline keywords when present in main config."""
        main_config = {
            "analyzer": {},
            "rules": {},
            "keywords": {
                "mappings": [
                    {
                        "category": "brakes",
                        "keywords": ["BREMSE"],
                        "confidence": 0.88,
                    },
                ],
            },
        }
        config_file = tmp_path / "nsa_coverage_config.yaml"
        config_file.write_text(yaml.dump(main_config), encoding="utf-8")

        # Also write a sibling file that should NOT be loaded
        keyword_file = tmp_path / "nsa_keyword_mappings.yaml"
        keyword_file.write_text(
            yaml.dump({"mappings": [{"category": "engine", "keywords": ["MOTOR"]}]}),
            encoding="utf-8",
        )

        analyzer = CoverageAnalyzer.from_config_path(config_file)

        # Should use inline keywords, not sibling file
        assert len(analyzer.keyword_matcher.config.mappings) == 1
        assert analyzer.keyword_matcher.config.mappings[0].category == "brakes"
