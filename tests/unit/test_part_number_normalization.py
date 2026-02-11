"""Tests for part number normalization in part_number_lookup.py."""

import pytest

from context_builder.coverage.part_number_lookup import _normalize_part_number


class TestNormalizePartNumber:
    """Verify that part numbers with different separators are normalized identically."""

    def test_strips_spaces(self):
        assert _normalize_part_number("5WA 713 033 CC") == "5WA713033CC"

    def test_strips_dashes(self):
        assert _normalize_part_number("2S6Q-6K682-AF") == "2S6Q6K682AF"

    def test_strips_dots(self):
        assert _normalize_part_number("1.234.567") == "1234567"

    def test_strips_slashes(self):
        assert _normalize_part_number("06K/145/778AS") == "06K145778AS"

    def test_mixed_separators(self):
        assert _normalize_part_number("A001 989-85.03/13") == "A001989850313"

    def test_uppercases(self):
        assert _normalize_part_number("abc123def") == "ABC123DEF"

    def test_no_separators_unchanged(self):
        assert _normalize_part_number("0CK325031AR") == "0CK325031AR"

    def test_empty_string(self):
        assert _normalize_part_number("") == ""

    @pytest.mark.parametrize(
        "extracted, stored",
        [
            ("5WA 713 033 CC", "5WA713033CC"),
            ("A001 989 85 03 13", "A001989850313"),
            ("0GC 325 201 L", "0GC325201L"),
            ("G 060 175 A2", "G060175A2"),
            ("G 052731A2", "G052731A2"),
            ("0GC 325 183 D", "0GC325183D"),
            ("0CK 325 031 AR", "0CK325031AR"),
        ],
        ids=[
            "VW-gear-selector",
            "Mercedes-oil",
            "VW-trans-cover",
            "VW-haldex",
            "VW-hydraulic-oil",
            "VW-trans-filter",
            "VW-sliding-sleeve",
        ],
    )
    def test_real_leaked_part_numbers_match(self, extracted, stored):
        """Part numbers from the 33 leaked items should match after normalization."""
        assert _normalize_part_number(extracted) == _normalize_part_number(stored)
