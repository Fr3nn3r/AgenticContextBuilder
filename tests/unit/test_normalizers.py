"""Unit tests for field value normalizers (simplified type coercion)."""

import pytest
from context_builder.extraction.normalizers import (
    safe_string,
    safe_float,
    get_normalizer,
    get_validator,
    validate_non_empty,
    validate_is_date,
    validate_plate_like,
    validate_vin_format,
)


class TestSafeString:
    """Tests for safe_string type coercion function."""

    def test_basic_string(self):
        assert safe_string("hello") == "hello"

    def test_string_with_whitespace(self):
        assert safe_string("  hello  ") == "hello"

    def test_empty_string(self):
        assert safe_string("") == ""

    def test_none_value(self):
        assert safe_string(None) == ""

    def test_single_item_list(self):
        """Test list with single item returns that item."""
        assert safe_string(["hello"]) == "hello"

    def test_multi_item_list(self):
        """Test list with multiple items joins them."""
        assert safe_string(["hello", "world"]) == "hello world"

    def test_empty_list(self):
        assert safe_string([]) == ""

    def test_list_with_whitespace(self):
        """Test list items are stripped after joining."""
        assert safe_string(["  hello  "]) == "hello"

    def test_integer_value(self):
        """Test integer is converted to string."""
        assert safe_string(123) == "123"

    def test_float_value(self):
        """Test float is converted to string."""
        assert safe_string(123.45) == "123.45"

    def test_list_of_numbers(self):
        """Test list of numbers is joined as strings."""
        assert safe_string([1, 2, 3]) == "1 2 3"

    def test_mixed_list(self):
        """Test list with mixed types."""
        assert safe_string(["hello", 123, "world"]) == "hello 123 world"


class TestSafeFloat:
    """Tests for safe_float type coercion function."""

    def test_integer_value(self):
        assert safe_float(123) == 123.0

    def test_float_value(self):
        assert safe_float(123.45) == 123.45

    def test_string_numeric(self):
        assert safe_float("123.45") == 123.45

    def test_string_with_spaces(self):
        assert safe_float("  123.45  ") == 123.45

    def test_string_with_chf(self):
        """Test CHF currency prefix is stripped."""
        assert safe_float("CHF 123.45") == 123.45

    def test_string_with_chf_suffix(self):
        """Test CHF currency suffix is stripped."""
        assert safe_float("123.45 CHF") == 123.45

    def test_string_with_swiss_thousands(self):
        """Test Swiss thousand separator (apostrophe) is handled."""
        assert safe_float("1'234.56") == 1234.56

    def test_none_value(self):
        assert safe_float(None) == 0.0

    def test_none_with_custom_default(self):
        assert safe_float(None, default=-1.0) == -1.0

    def test_empty_string(self):
        assert safe_float("") == 0.0

    def test_invalid_string(self):
        assert safe_float("not a number") == 0.0

    def test_invalid_string_with_custom_default(self):
        assert safe_float("not a number", default=-1.0) == -1.0

    def test_string_fr_currency(self):
        """Test Fr. currency prefix is stripped."""
        assert safe_float("Fr. 99.90") == 99.90


class TestGetNormalizer:
    """Tests for normalizer registry lookup."""

    def test_passthrough_normalizers_return_safe_string(self):
        """Non-date normalizer names should return safe_string behavior."""
        normalizer_names = [
            "uppercase_trim",
            "plate_normalize",
            "none",
            "trim",
            "swiss_currency",
            "covered_boolean",
            "transferable_boolean",
            "extract_percentage",
            "extract_number",
            "phone_normalize",
        ]
        for name in normalizer_names:
            normalizer = get_normalizer(name)
            # All should handle the basic string case
            assert normalizer("  test  ") == "test"
            # All should handle list case (the bug fix)
            assert normalizer(["test"]) == "test"
            assert normalizer(["a", "b"]) == "a b"

    def test_date_normalizers_parse_dates(self):
        """date_to_iso and swiss_date_to_iso should parse real dates."""
        for name in ("date_to_iso", "swiss_date_to_iso"):
            normalizer = get_normalizer(name)
            assert normalizer("23.01.2026") == "2026-01-23"
            assert normalizer("2026-01-23") == "2026-01-23"
            assert normalizer("20. Januar 2026") == "2026-01-20"

    def test_date_normalizers_fallback_on_failure(self):
        """date_to_iso should return original string on unparseable input."""
        normalizer = get_normalizer("date_to_iso")
        assert normalizer("not a date") == "not a date"
        assert normalizer(None) == ""

    def test_date_normalizers_handle_lists(self):
        """date_to_iso should handle list input via safe_string first."""
        normalizer = get_normalizer("date_to_iso")
        assert normalizer(["23.01.2026"]) == "2026-01-23"

    def test_unknown_normalizer_returns_safe_string(self):
        """Unknown normalizer name should still return safe_string."""
        normalizer = get_normalizer("unknown_normalizer")
        assert normalizer("  hello  ") == "hello"
        assert normalizer(["test"]) == "test"


class TestValidateNonEmpty:
    """Tests for validate_non_empty validator."""

    def test_non_empty_string(self):
        assert validate_non_empty("hello") is True

    def test_empty_string(self):
        assert validate_non_empty("") is False

    def test_whitespace_only(self):
        assert validate_non_empty("   ") is False

    def test_none_value(self):
        assert validate_non_empty(None) is False

    def test_list_with_value(self):
        """Test list input is handled."""
        assert validate_non_empty(["hello"]) is True

    def test_empty_list(self):
        assert validate_non_empty([]) is False


class TestValidateIsDate:
    """Tests for validate_is_date validator."""

    def test_iso_format(self):
        assert validate_is_date("2024-12-25") is True

    def test_slash_format(self):
        assert validate_is_date("25/12/2024") is True

    def test_dash_format(self):
        assert validate_is_date("25-12-2024") is True

    def test_swiss_dot_format(self):
        assert validate_is_date("31.12.2025") is True

    def test_invalid_date(self):
        assert validate_is_date("not a date") is False

    def test_empty_string(self):
        assert validate_is_date("") is False

    def test_none_value(self):
        assert validate_is_date(None) is False

    def test_list_input(self):
        """Test list input is handled."""
        assert validate_is_date(["2024-12-25"]) is True


class TestValidatePlateLike:
    """Tests for validate_plate_like validator."""

    def test_valid_plate(self):
        assert validate_plate_like("ABC1234") is True

    def test_valid_plate_with_dash(self):
        assert validate_plate_like("ABC-1234") is True

    def test_short_plate_invalid(self):
        """2 letters is invalid for Ecuador plates (need 3)."""
        assert validate_plate_like("AB123") is False

    def test_invalid_plate(self):
        assert validate_plate_like("12345") is False

    def test_empty_string(self):
        assert validate_plate_like("") is False

    def test_none_value(self):
        assert validate_plate_like(None) is False


class TestValidateVinFormat:
    """Tests for validate_vin_format function."""

    def test_valid_vin(self):
        """Test valid 17-character VIN."""
        assert validate_vin_format("WVWZZZ3CZWE123456") is True

    def test_valid_vin_with_spaces(self):
        """Test VIN with spaces (should be cleaned)."""
        assert validate_vin_format("WVWZZZ3C ZWE123456") is True

    def test_valid_vin_lowercase(self):
        """Test lowercase VIN (should be uppercased)."""
        assert validate_vin_format("wvwzzz3czwe123456") is True

    def test_invalid_vin_too_short(self):
        """Test VIN that's too short."""
        assert validate_vin_format("WVWZZZ3CZWE12345") is False

    def test_invalid_vin_too_long(self):
        """Test VIN that's too long."""
        assert validate_vin_format("WVWZZZ3CZWE1234567") is False

    def test_invalid_vin_with_i(self):
        """Test VIN with invalid character I."""
        assert validate_vin_format("WVWZZZ3CZWE12345I") is False

    def test_invalid_vin_with_o(self):
        """Test VIN with invalid character O."""
        assert validate_vin_format("WVWZZZ3CZWE12345O") is False

    def test_invalid_vin_with_q(self):
        """Test VIN with invalid character Q."""
        assert validate_vin_format("WVWZZZ3CZWE12345Q") is False

    def test_empty_string(self):
        assert validate_vin_format("") is False

    def test_none_value(self):
        assert validate_vin_format(None) is False

    def test_list_input(self):
        """Test list input is handled."""
        assert validate_vin_format(["WVWZZZ3CZWE123456"]) is True


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
        assert validator("ABC1234") is True
        assert validator("12345") is False

    def test_get_vin_format(self):
        validator = get_validator("vin_format")
        assert validator("WVWZZZ3CZWE123456") is True
        assert validator("short") is False

    def test_unknown_validator_returns_non_empty(self):
        """Unknown validator name should return non_empty validator."""
        validator = get_validator("unknown_validator")
        assert validator("hello") is True
        assert validator("") is False
