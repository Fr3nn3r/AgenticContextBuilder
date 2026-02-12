"""Tests for KeywordMatcher.generate_hint() and generate_hints().

These methods produce advisory hint dicts for the LLM-first pipeline
without making coverage decisions.
"""

import pytest

from context_builder.coverage.keyword_matcher import (
    KeywordConfig,
    KeywordMapping,
    KeywordMatcher,
)


@pytest.fixture
def config():
    """Minimal keyword config for testing hints."""
    return KeywordConfig(
        mappings=[
            KeywordMapping(
                category="engine",
                keywords=["MOTOR", "KOLBEN", "ZYLINDER"],
                context_hints=["BLOCK"],
                confidence=0.85,
                component_name="motor",
            ),
            KeywordMapping(
                category="chassis",
                keywords=["STOSSDAEMPFER", "FEDERBEIN"],
                confidence=0.85,
                component_name="shock_absorber",
            ),
        ],
        consumable_indicators=["OEL", "FILTER", "DICHTUNG"],
        consumable_confidence_penalty=0.7,
        context_confidence_boost=0.05,
    )


@pytest.fixture
def matcher(config):
    return KeywordMatcher(config)


class TestGenerateHint:
    """Tests for generate_hint() single-item method."""

    def test_returns_hint_for_matching_keyword(self, matcher):
        hint = matcher.generate_hint("MOTOR BLOCK", "parts")
        assert hint is not None
        assert hint["keyword"] == "MOTOR"
        assert hint["category"] == "engine"
        assert hint["component"] == "motor"
        assert isinstance(hint["confidence"], float)
        assert hint["confidence"] > 0

    def test_returns_none_for_no_match(self, matcher):
        hint = matcher.generate_hint("UNKNOWN WIDGET XYZ", "parts")
        assert hint is None

    def test_context_hint_boosts_confidence(self, matcher):
        hint_with_context = matcher.generate_hint("MOTOR BLOCK", "parts")
        hint_without_context = matcher.generate_hint("MOTOR REPARATUR", "parts")
        # "BLOCK" is a context hint for engine, so should have higher confidence
        assert hint_with_context is not None
        assert hint_without_context is not None
        assert hint_with_context["confidence"] > hint_without_context["confidence"]

    def test_consumable_indicator_reduces_confidence(self, matcher):
        hint_clean = matcher.generate_hint("MOTOR REPARATUR", "parts")
        hint_consumable = matcher.generate_hint("MOTOR OEL", "parts")
        assert hint_clean is not None
        assert hint_consumable is not None
        assert hint_consumable["has_consumable_indicator"] is True
        assert hint_clean["has_consumable_indicator"] is False
        assert hint_consumable["confidence"] < hint_clean["confidence"]

    def test_case_insensitive_matching(self, matcher):
        hint = matcher.generate_hint("motor block", "parts")
        assert hint is not None
        assert hint["category"] == "engine"

    def test_hint_for_chassis_keyword(self, matcher):
        hint = matcher.generate_hint("STOSSDAEMPFER VORNE", "parts")
        assert hint is not None
        assert hint["category"] == "chassis"
        assert hint["component"] == "shock_absorber"

    def test_empty_description_returns_none(self, matcher):
        hint = matcher.generate_hint("", "parts")
        assert hint is None

    def test_confidence_is_rounded(self, matcher):
        hint = matcher.generate_hint("MOTOR BLOCK", "parts")
        assert hint is not None
        # confidence should be rounded to 3 decimal places
        assert hint["confidence"] == round(hint["confidence"], 3)


class TestGenerateHints:
    """Tests for generate_hints() batch method."""

    def test_returns_parallel_list(self, matcher):
        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts"},
            {"description": "UNKNOWN WIDGET", "item_type": "parts"},
            {"description": "STOSSDAEMPFER", "item_type": "parts"},
        ]
        hints = matcher.generate_hints(items)
        assert len(hints) == 3
        assert hints[0] is not None  # MOTOR matches
        assert hints[1] is None  # No match
        assert hints[2] is not None  # STOSSDAEMPFER matches

    def test_empty_items_returns_empty(self, matcher):
        hints = matcher.generate_hints([])
        assert hints == []

    def test_all_unmatched_returns_all_none(self, matcher):
        items = [
            {"description": "XYZ", "item_type": "parts"},
            {"description": "ABC", "item_type": "labor"},
        ]
        hints = matcher.generate_hints(items)
        assert all(h is None for h in hints)

    def test_all_matched_returns_all_hints(self, matcher):
        items = [
            {"description": "MOTOR REPARATUR", "item_type": "labor"},
            {"description": "STOSSDAEMPFER HINTEN", "item_type": "parts"},
        ]
        hints = matcher.generate_hints(items)
        assert all(h is not None for h in hints)
        assert hints[0]["category"] == "engine"
        assert hints[1]["category"] == "chassis"

    def test_hint_dict_keys(self, matcher):
        items = [{"description": "MOTOR BLOCK", "item_type": "parts"}]
        hints = matcher.generate_hints(items)
        hint = hints[0]
        assert hint is not None
        expected_keys = {"keyword", "category", "component", "confidence", "has_consumable_indicator"}
        assert set(hint.keys()) == expected_keys


class TestNoMappings:
    """Tests with empty keyword config."""

    def test_generate_hint_with_no_mappings(self):
        matcher = KeywordMatcher(config=None)
        hint = matcher.generate_hint("MOTOR BLOCK", "parts")
        assert hint is None

    def test_generate_hints_with_no_mappings(self):
        matcher = KeywordMatcher(config=None)
        hints = matcher.generate_hints([
            {"description": "MOTOR BLOCK", "item_type": "parts"},
        ])
        assert hints == [None]
