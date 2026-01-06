"""Unit tests for field value normalizers."""

import pytest
from context_builder.extraction.normalizers import (
    normalize_uppercase_trim,
    normalize_date_to_iso,
    normalize_plate,
    normalize_none,
    get_normalizer,
)


class TestNormalizeUppercaseTrim:
    """Tests for normalize_uppercase_trim function."""

    def test_basic_uppercase(self):
        assert normalize_uppercase_trim("hello") == "HELLO"

    def test_trim_whitespace(self):
        assert normalize_uppercase_trim("  hello  ") == "HELLO"

    def test_mixed_case_with_whitespace(self):
        assert normalize_uppercase_trim("  HeLLo WoRLD  ") == "HELLO WORLD"

    def test_empty_string(self):
        assert normalize_uppercase_trim("") == ""

    def test_none_value(self):
        assert normalize_uppercase_trim(None) == ""


class TestNormalizeDateToISO:
    """Tests for normalize_date_to_iso function."""

    def test_dd_mm_yyyy_slash(self):
        """Test common Ecuador/Spanish format."""
        assert normalize_date_to_iso("25/12/2024") == "2024-12-25"

    def test_dd_mm_yy_slash(self):
        """Test short year format."""
        assert normalize_date_to_iso("25/12/24") == "2024-12-25"

    def test_dd_mm_yyyy_dash(self):
        """Test dash-separated format."""
        assert normalize_date_to_iso("25-12-2024") == "2024-12-25"

    def test_iso_format_passthrough(self):
        """Test already-ISO format passes through."""
        assert normalize_date_to_iso("2024-12-25") == "2024-12-25"

    def test_single_digit_day_month(self):
        """Test single digit day and month."""
        assert normalize_date_to_iso("5/3/2024") == "2024-03-05"

    def test_invalid_date_returns_original(self):
        """Test that invalid dates return the original value."""
        assert normalize_date_to_iso("not a date") == "not a date"

    def test_empty_string(self):
        assert normalize_date_to_iso("") == ""

    def test_none_value(self):
        assert normalize_date_to_iso(None) == ""

    def test_whitespace_trimmed(self):
        assert normalize_date_to_iso("  25/12/2024  ") == "2024-12-25"


class TestNormalizePlate:
    """Tests for Ecuador vehicle plate normalization."""

    def test_standard_format(self):
        """Test standard ABC-1234 format."""
        assert normalize_plate("ABC-1234") == "ABC-1234"

    def test_lowercase_input(self):
        """Test lowercase is converted to uppercase."""
        assert normalize_plate("abc-1234") == "ABC-1234"

    def test_with_spaces(self):
        """Test spaces are removed."""
        assert normalize_plate("abc 1234") == "ABC-1234"

    def test_no_separator(self):
        """Test format without separator."""
        assert normalize_plate("ABC1234") == "ABC-1234"

    def test_multiple_separators(self):
        """Test multiple separators are normalized."""
        assert normalize_plate("ABC--1234") == "ABC-1234"

    def test_special_characters_removed(self):
        """Test special characters are removed."""
        assert normalize_plate("ABC@#$1234") == "ABC-1234"

    def test_short_plate(self):
        """Test shorter plates are not reformatted."""
        result = normalize_plate("AB123")
        assert result == "AB123"

    def test_empty_string(self):
        assert normalize_plate("") == ""

    def test_none_value(self):
        assert normalize_plate(None) == ""


class TestNormalizeNone:
    """Tests for no-op normalizer."""

    def test_passthrough(self):
        assert normalize_none("Hello World") == "Hello World"

    def test_trims_whitespace(self):
        assert normalize_none("  hello  ") == "hello"

    def test_empty_string(self):
        assert normalize_none("") == ""

    def test_none_value(self):
        assert normalize_none(None) == ""


class TestGetNormalizer:
    """Tests for normalizer registry lookup."""

    def test_get_uppercase_trim(self):
        normalizer = get_normalizer("uppercase_trim")
        assert normalizer("hello") == "HELLO"

    def test_get_date_to_iso(self):
        normalizer = get_normalizer("date_to_iso")
        assert normalizer("25/12/2024") == "2024-12-25"

    def test_get_plate_normalize(self):
        normalizer = get_normalizer("plate_normalize")
        assert normalizer("abc1234") == "ABC-1234"

    def test_unknown_returns_none_normalizer(self):
        """Test unknown normalizer name returns normalize_none."""
        normalizer = get_normalizer("unknown_normalizer")
        assert normalizer("  hello  ") == "hello"
