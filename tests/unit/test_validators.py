"""Unit tests for field value validators."""

import pytest
from context_builder.extraction.normalizers import (
    validate_non_empty,
    validate_is_date,
    validate_plate_like,
    get_validator,
)


class TestValidateNonEmpty:
    """Tests for validate_non_empty function."""

    def test_non_empty_string(self):
        assert validate_non_empty("hello") is True

    def test_empty_string(self):
        assert validate_non_empty("") is False

    def test_whitespace_only(self):
        assert validate_non_empty("   ") is False

    def test_none_value(self):
        assert validate_non_empty(None) is False

    def test_string_with_spaces(self):
        assert validate_non_empty("  hello  ") is True


class TestValidateIsDate:
    """Tests for validate_is_date function."""

    def test_iso_format(self):
        """Test ISO format YYYY-MM-DD is valid."""
        assert validate_is_date("2024-12-25") is True

    def test_dd_mm_yyyy_slash(self):
        """Test common date format with slashes."""
        assert validate_is_date("25/12/2024") is True

    def test_dd_mm_yy_slash(self):
        """Test short year format."""
        assert validate_is_date("25/12/24") is True

    def test_dd_mm_yyyy_dash(self):
        """Test dash-separated format."""
        assert validate_is_date("25-12-2024") is True

    def test_not_a_date(self):
        """Test non-date string is invalid."""
        assert validate_is_date("not a date") is False

    def test_random_numbers(self):
        """Test random numbers aren't dates."""
        assert validate_is_date("123456") is False

    def test_empty_string(self):
        assert validate_is_date("") is False

    def test_none_value(self):
        assert validate_is_date(None) is False


class TestValidatePlateLike:
    """Tests for Ecuador vehicle plate validation."""

    def test_standard_format_with_dash(self):
        """Test ABC-1234 format."""
        assert validate_plate_like("ABC-1234") is True

    def test_standard_format_no_dash(self):
        """Test ABC1234 format."""
        assert validate_plate_like("ABC1234") is True

    def test_lowercase_valid(self):
        """Test lowercase is accepted."""
        assert validate_plate_like("abc-1234") is True

    def test_three_digits(self):
        """Test 3 digit plates (older format)."""
        assert validate_plate_like("ABC-123") is True

    def test_too_few_letters(self):
        """Test plate with only 2 letters is invalid."""
        assert validate_plate_like("AB-1234") is False

    def test_too_few_digits(self):
        """Test plate with only 2 digits is invalid."""
        assert validate_plate_like("ABC-12") is False

    def test_too_many_digits(self):
        """Test plate with 5 digits is invalid."""
        assert validate_plate_like("ABC-12345") is False

    def test_empty_string(self):
        assert validate_plate_like("") is False

    def test_none_value(self):
        assert validate_plate_like(None) is False


class TestGetValidator:
    """Tests for validator registry lookup."""

    def test_get_non_empty(self):
        validator = get_validator("non_empty")
        assert validator("hello") is True
        assert validator("") is False

    def test_get_is_date(self):
        validator = get_validator("is_date")
        assert validator("2024-12-25") is True
        assert validator("not a date") is False

    def test_get_plate_like(self):
        validator = get_validator("plate_like")
        assert validator("ABC-1234") is True
        assert validator("XX") is False

    def test_unknown_returns_non_empty_validator(self):
        """Test unknown validator name returns validate_non_empty."""
        validator = get_validator("unknown_validator")
        assert validator("hello") is True
        assert validator("") is False
