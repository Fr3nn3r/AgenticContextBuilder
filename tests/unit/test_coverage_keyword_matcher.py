"""Tests for the coverage keyword matcher."""

from pathlib import Path

import pytest
import yaml

from context_builder.coverage.analyzer import CoverageAnalyzer
from context_builder.coverage.keyword_matcher import KeywordConfig, KeywordMatcher
from context_builder.coverage.schemas import CoverageStatus, MatchMethod


def _load_nsa_keyword_config() -> KeywordConfig:
    """Load NSA keyword config from workspace YAML."""
    config_path = (
        Path(__file__).resolve().parents[2]
        / "workspaces" / "nsa" / "config" / "coverage" / "nsa_keyword_mappings.yaml"
    )
    if not config_path.exists():
        pytest.skip("NSA workspace keyword config not available")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return KeywordConfig.from_dict(data)


@pytest.fixture(scope="session")
def nsa_keyword_config():
    """Load NSA keyword config from workspace."""
    return _load_nsa_keyword_config()


@pytest.fixture
def nsa_matcher(nsa_keyword_config):
    """Create a KeywordMatcher with NSA config."""
    return KeywordMatcher(nsa_keyword_config)


class TestKeywordMatcherDefaults:
    """Tests for KeywordMatcher with empty default config."""

    def test_empty_config_has_no_mappings(self):
        """Empty config falls back to empty mappings."""
        matcher = KeywordMatcher()
        assert len(matcher.config.mappings) == 0

    def test_none_config_has_no_mappings(self):
        """None config falls back to empty mappings."""
        matcher = KeywordMatcher(None)
        assert len(matcher.config.mappings) == 0

    def test_empty_config_no_match(self):
        """Empty matcher does not match anything."""
        matcher = KeywordMatcher()
        result = matcher.match(
            description="MOTOR BLOCK",
            item_type="parts",
            total_price=150.0,
            covered_categories=["engine"],
        )
        assert result is None


class TestKeywordMatcherNSA:
    """Tests for KeywordMatcher with NSA config."""

    def test_nsa_config_has_mappings(self, nsa_matcher):
        """NSA config has keyword mappings."""
        assert len(nsa_matcher.config.mappings) > 0

    def test_motor_matches_engine(self, nsa_matcher):
        """MOTOR keyword maps to engine category."""
        result = nsa_matcher.match(
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

    def test_stossdaempfer_matches_chassis(self, nsa_matcher):
        """STOSSDAEMPFER maps to chassis category."""
        result = nsa_matcher.match(
            description="STOSSDAEMPFER HINTEN LINKS",
            item_type="parts",
            total_price=400.0,
            covered_categories=["chassis", "suspension"],
        )
        assert result is not None
        assert result.coverage_category == "chassis"

    def test_getriebe_matches_transmission(self, nsa_matcher):
        """GETRIEBE maps to mechanical_transmission category."""
        result = nsa_matcher.match(
            description="GETRIEBE REPARATUR",
            item_type="labor",
            total_price=800.0,
            covered_categories=["mechanical_transmission"],
        )
        assert result is not None
        assert result.coverage_category == "mechanical_transmission"

    def test_klimakompressor_matches_ac(self, nsa_matcher):
        """KLIMAKOMPRESSOR maps to air_conditioning."""
        result = nsa_matcher.match(
            description="KLIMAKOMPRESSOR",
            item_type="parts",
            total_price=900.0,
            covered_categories=["air_conditioning"],
        )
        assert result is not None
        assert result.coverage_category == "air_conditioning"

    def test_bremse_matches_brakes(self, nsa_matcher):
        """BREMSE maps to brakes category."""
        result = nsa_matcher.match(
            description="BREMSSATTEL VORNE",
            item_type="parts",
            total_price=250.0,
            covered_categories=["brakes"],
        )
        assert result is not None
        assert result.coverage_category == "brakes"

    def test_uncovered_category_returns_not_covered(self, nsa_matcher):
        """Matching a non-covered category returns NOT_COVERED."""
        result = nsa_matcher.match(
            description="KLIMAKOMPRESSOR",
            item_type="parts",
            total_price=900.0,
            covered_categories=["engine", "brakes"],  # AC not covered
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED
        assert result.coverage_category == "air_conditioning"

    def test_no_match_returns_none(self, nsa_matcher):
        """Unmatched descriptions return None."""
        result = nsa_matcher.match(
            description="RANDOM TEXT WITHOUT KEYWORDS",
            item_type="parts",
            total_price=100.0,
            covered_categories=["engine"],
        )
        assert result is None

    def test_case_insensitive_matching(self, nsa_matcher):
        """Matching is case insensitive."""
        result = nsa_matcher.match(
            description="motor block",
            item_type="parts",
            total_price=150.0,
            covered_categories=["engine"],
        )
        assert result is not None
        assert result.coverage_category == "engine"

    def test_context_hint_boosts_confidence(self, nsa_matcher):
        """Context hints boost confidence."""
        result1 = nsa_matcher.match(
            description="MOTOR ENGINE BLOCK",
            item_type="parts",
            total_price=150.0,
            covered_categories=["engine"],
        )
        result2 = nsa_matcher.match(
            description="MOTOR REPARATUR",
            item_type="parts",
            total_price=150.0,
            covered_categories=["engine"],
        )
        assert result1 is not None
        assert result2 is not None
        assert result1.match_confidence >= result2.match_confidence

    def test_labor_for_covered_category(self, nsa_matcher):
        """Labor for covered category is covered."""
        result = nsa_matcher.match(
            description="MOTOR REPARATUR ARBEIT",
            item_type="labor",
            total_price=300.0,
            covered_categories=["engine"],
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.COVERED

    def test_batch_match(self, nsa_matcher):
        """Batch matching functionality."""
        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 150.0},
            {"description": "UNKNOWN PART", "item_type": "parts", "total_price": 100.0},
            {"description": "BREMSSATTEL", "item_type": "parts", "total_price": 250.0},
        ]
        covered_categories = ["engine", "brakes"]
        matched, unmatched = nsa_matcher.batch_match(items, covered_categories)
        assert len(matched) == 2
        assert len(unmatched) == 1

    def test_batch_match_with_min_confidence(self, nsa_matcher):
        """Batch matching with custom minimum confidence."""
        items = [
            {"description": "MOTOR DICHTUNG", "item_type": "parts", "total_price": 150.0},
        ]
        matched, unmatched = nsa_matcher.batch_match(
            items,
            covered_categories=["engine"],
            min_confidence=0.99,
        )
        assert len(matched) == 0
        assert len(unmatched) == 1

    def test_item_code_preserved(self, nsa_matcher):
        """Item code is preserved in result."""
        result = nsa_matcher.match(
            description="MOTOR DICHTUNG",
            item_type="parts",
            item_code="PART123",
            total_price=150.0,
            covered_categories=["engine"],
        )
        assert result is not None
        assert result.item_code == "PART123"

    def test_niveau_matches_chassis(self, nsa_matcher):
        """NIVEAU (height control) maps to chassis."""
        result = nsa_matcher.match(
            description="NIVEAUREGULIERUNG HINTEN",
            item_type="parts",
            total_price=600.0,
            covered_categories=["chassis"],
        )
        assert result is not None
        assert result.coverage_category == "chassis"

    def test_hydraulik_with_niveau_context(self, nsa_matcher):
        """HYDRAULIK with NIVEAU context maps to chassis."""
        result = nsa_matcher.match(
            description="HYDRAULIK NIVEAU VENTIL",
            item_type="parts",
            total_price=350.0,
            covered_categories=["chassis"],
        )
        assert result is not None
        assert result.coverage_category in ["chassis"]

    def test_empty_covered_categories(self, nsa_matcher):
        """With empty covered categories list."""
        result = nsa_matcher.match(
            description="MOTOR DICHTUNG",
            item_type="parts",
            total_price=150.0,
            covered_categories=[],
        )
        assert result is not None
        assert result.coverage_status == CoverageStatus.NOT_COVERED

    def test_joint_reduces_confidence(self, nsa_matcher):
        """JOINT (gasket) alongside VILEBREQUIN should reduce confidence below 0.80."""
        result = nsa_matcher.match(
            description="Joint du vilebrequin",
            item_type="parts",
            total_price=45.0,
            covered_categories=["engine"],
        )
        assert result is not None
        assert result.coverage_category == "engine"
        assert result.match_confidence < 0.80

    def test_dichtung_reduces_confidence(self, nsa_matcher):
        """DICHTUNG (seal) alongside MOTOR should reduce confidence below 0.80."""
        result = nsa_matcher.match(
            description="MOTOR DICHTUNG",
            item_type="parts",
            total_price=30.0,
            covered_categories=["engine"],
        )
        assert result is not None
        assert result.coverage_category == "engine"
        assert result.match_confidence < 0.80

    def test_soufflet_reduces_confidence(self, nsa_matcher):
        """SOUFFLET (boot) alongside DIRECTION should reduce confidence below 0.80."""
        result = nsa_matcher.match(
            description="SOUFFLET DE DIRECTION",
            item_type="parts",
            total_price=25.0,
            covered_categories=["steering"],
        )
        assert result is not None
        assert result.match_confidence < 0.80

    def test_component_without_consumable_unchanged(self, nsa_matcher):
        """VILEBREQUIN alone (no consumable term) should keep full confidence."""
        result = nsa_matcher.match(
            description="VILEBREQUIN",
            item_type="parts",
            total_price=800.0,
            covered_categories=["engine"],
        )
        assert result is not None
        assert result.coverage_category == "engine"
        assert result.match_confidence == 0.88

    def test_consumable_falls_to_unmatched_in_batch(self, nsa_matcher):
        """Consumable items should fall to unmatched in batch_match (default threshold 0.80)."""
        items = [
            {"description": "VILEBREQUIN", "item_type": "parts", "total_price": 800.0},
            {"description": "Joint du vilebrequin", "item_type": "parts", "total_price": 45.0},
            {"description": "MOTOR DICHTUNG", "item_type": "parts", "total_price": 30.0},
        ]
        matched, unmatched = nsa_matcher.batch_match(
            items,
            covered_categories=["engine"],
            min_confidence=0.80,
        )
        assert len(matched) == 1
        assert matched[0].description == "VILEBREQUIN"
        assert len(unmatched) == 2


class TestFromConfigPathKeywordLoading:
    """Tests for CoverageAnalyzer.from_config_path keyword discovery."""

    def test_loads_keywords_from_sibling_file(self, tmp_path):
        """from_config_path should load keywords from a sibling *_keyword_mappings.yaml."""
        main_config = {
            "analyzer": {"keyword_min_confidence": 0.80},
            "rules": {},
        }
        config_file = tmp_path / "nsa_coverage_config.yaml"
        config_file.write_text(yaml.dump(main_config), encoding="utf-8")

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
        assert len(analyzer.keyword_matcher.config.mappings) == 1
        assert analyzer.keyword_matcher.config.mappings[0].category == "engine"

    def test_falls_back_to_empty_when_no_sibling(self, tmp_path):
        """from_config_path should fall back to empty config when no sibling file exists."""
        main_config = {
            "analyzer": {},
            "rules": {},
        }
        config_file = tmp_path / "nsa_coverage_config.yaml"
        config_file.write_text(yaml.dump(main_config), encoding="utf-8")

        analyzer = CoverageAnalyzer.from_config_path(config_file)
        # Should have empty mappings (no built-in defaults)
        assert len(analyzer.keyword_matcher.config.mappings) == 0

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

        keyword_file = tmp_path / "nsa_keyword_mappings.yaml"
        keyword_file.write_text(
            yaml.dump({"mappings": [{"category": "engine", "keywords": ["MOTOR"]}]}),
            encoding="utf-8",
        )

        analyzer = CoverageAnalyzer.from_config_path(config_file)
        assert len(analyzer.keyword_matcher.config.mappings) == 1
        assert analyzer.keyword_matcher.config.mappings[0].category == "brakes"
