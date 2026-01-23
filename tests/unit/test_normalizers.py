"""Unit tests for field value normalizers."""

import pytest
from context_builder.extraction.normalizers import (
    normalize_uppercase_trim,
    normalize_date_to_iso,
    normalize_plate,
    normalize_none,
    normalize_trim,
    normalize_swiss_date_to_iso,
    normalize_swiss_currency,
    normalize_covered_boolean,
    normalize_transferable_boolean,
    normalize_extract_percentage,
    normalize_extract_number,
    normalize_phone,
    validate_vin_format,
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

    def test_get_swiss_date_to_iso(self):
        normalizer = get_normalizer("swiss_date_to_iso")
        assert normalizer("31.12.2025") == "2025-12-31"

    def test_get_swiss_currency(self):
        normalizer = get_normalizer("swiss_currency")
        assert normalizer("10'000.00 CHF") == 10000.0


class TestNormalizeTrim:
    """Tests for normalize_trim function."""

    def test_basic_trim(self):
        assert normalize_trim("  hello  ") == "hello"

    def test_no_whitespace(self):
        assert normalize_trim("hello") == "hello"

    def test_empty_string(self):
        assert normalize_trim("") == ""

    def test_none_value(self):
        assert normalize_trim(None) == ""

    def test_preserves_case(self):
        assert normalize_trim("  HeLLo WoRLD  ") == "HeLLo WoRLD"


class TestNormalizeSwissDateToISO:
    """Tests for normalize_swiss_date_to_iso function."""

    def test_dd_mm_yyyy_dot(self):
        """Test Swiss format with dots."""
        assert normalize_swiss_date_to_iso("31.12.2025") == "2025-12-31"

    def test_dd_mm_yy_dot(self):
        """Test short year Swiss format."""
        assert normalize_swiss_date_to_iso("31.12.25") == "2025-12-31"

    def test_single_digit_day_month(self):
        """Test single digit day and month."""
        assert normalize_swiss_date_to_iso("5.3.2025") == "2025-03-05"

    def test_dd_mm_yyyy_slash(self):
        """Test slash-separated format."""
        assert normalize_swiss_date_to_iso("31/12/2025") == "2025-12-31"

    def test_whitespace_trimmed(self):
        assert normalize_swiss_date_to_iso("  31.12.2025  ") == "2025-12-31"

    def test_empty_string(self):
        assert normalize_swiss_date_to_iso("") == ""

    def test_none_value(self):
        assert normalize_swiss_date_to_iso(None) == ""

    def test_invalid_date_returns_original(self):
        """Test that invalid dates return the original value."""
        assert normalize_swiss_date_to_iso("not a date") == "not a date"


class TestNormalizeSwissCurrency:
    """Tests for normalize_swiss_currency function."""

    def test_swiss_format_with_apostrophe(self):
        """Test Swiss format with apostrophe thousands separator."""
        assert normalize_swiss_currency("10'000.00 CHF") == 10000.0

    def test_chf_prefix(self):
        """Test CHF prefix format."""
        assert normalize_swiss_currency("CHF 10'000.00") == 10000.0

    def test_simple_number(self):
        """Test simple number without formatting."""
        assert normalize_swiss_currency("5000.00") == 5000.0

    def test_with_spaces(self):
        """Test with spaces around value."""
        assert normalize_swiss_currency("  10'000.00 CHF  ") == 10000.0

    def test_large_number(self):
        """Test large numbers."""
        assert normalize_swiss_currency("1'000'000.00 CHF") == 1000000.0

    def test_empty_string(self):
        assert normalize_swiss_currency("") is None

    def test_none_value(self):
        assert normalize_swiss_currency(None) is None

    def test_invalid_returns_none(self):
        """Test that invalid values return None."""
        assert normalize_swiss_currency("no currency here") is None


class TestNormalizeCoveredBoolean:
    """Tests for normalize_covered_boolean function."""

    def test_covered_english(self):
        assert normalize_covered_boolean("Covered") is True

    def test_not_covered_english(self):
        assert normalize_covered_boolean("Not covered") is False

    def test_gedeckt_german(self):
        assert normalize_covered_boolean("Gedeckt") is True

    def test_nicht_gedeckt_german(self):
        assert normalize_covered_boolean("Nicht gedeckt") is False

    def test_yes(self):
        assert normalize_covered_boolean("Yes") is True

    def test_no(self):
        assert normalize_covered_boolean("No") is False

    def test_ja(self):
        assert normalize_covered_boolean("Ja") is True

    def test_nein(self):
        assert normalize_covered_boolean("Nein") is False

    def test_empty_string(self):
        assert normalize_covered_boolean("") is False

    def test_none_value(self):
        assert normalize_covered_boolean(None) is False

    def test_case_insensitive(self):
        assert normalize_covered_boolean("COVERED") is True
        assert normalize_covered_boolean("NOT COVERED") is False


class TestNormalizeTransferableBoolean:
    """Tests for normalize_transferable_boolean function."""

    def test_assignable(self):
        assert normalize_transferable_boolean("Assignable guarantee") is True

    def test_transferable(self):
        assert normalize_transferable_boolean("Transferable") is True

    def test_ubertragbar(self):
        assert normalize_transferable_boolean("Garantie übertragbar") is True

    def test_not_transferable(self):
        assert normalize_transferable_boolean("Not transferable") is True  # Contains "transferable"

    def test_empty_string(self):
        assert normalize_transferable_boolean("") is False

    def test_none_value(self):
        assert normalize_transferable_boolean(None) is False

    def test_unrelated_text(self):
        assert normalize_transferable_boolean("Some other text") is False


class TestNormalizeExtractPercentage:
    """Tests for normalize_extract_percentage function."""

    def test_with_percent_sign(self):
        assert normalize_extract_percentage("10%") == 10.0

    def test_with_space_before_percent(self):
        assert normalize_extract_percentage("10 %") == 10.0

    def test_without_percent_sign(self):
        assert normalize_extract_percentage("10") == 10.0

    def test_decimal_percentage(self):
        assert normalize_extract_percentage("10.5%") == 10.5

    def test_with_text(self):
        assert normalize_extract_percentage("Excess: 10%") == 10.0

    def test_empty_string(self):
        assert normalize_extract_percentage("") is None

    def test_none_value(self):
        assert normalize_extract_percentage(None) is None


class TestNormalizeExtractNumber:
    """Tests for normalize_extract_number function."""

    def test_with_km(self):
        assert normalize_extract_number("27'000 km") == 27000

    def test_with_cc(self):
        assert normalize_extract_number("1984 cc") == 1984

    def test_with_days(self):
        assert normalize_extract_number("0 days") == 0

    def test_simple_number(self):
        assert normalize_extract_number("12345") == 12345

    def test_with_apostrophe_separator(self):
        assert normalize_extract_number("100'000") == 100000

    def test_empty_string(self):
        assert normalize_extract_number("") is None

    def test_none_value(self):
        assert normalize_extract_number(None) is None

    def test_no_numbers(self):
        assert normalize_extract_number("no numbers") is None


class TestNormalizePhone:
    """Tests for normalize_phone function."""

    def test_basic_phone(self):
        assert normalize_phone("+41 79 123 45 67") == "+41 79 123 45 67"

    def test_with_special_chars(self):
        assert normalize_phone("Tel: +41 79 123 45 67") == "+41 79 123 45 67"

    def test_with_parentheses(self):
        assert normalize_phone("(079) 123-45-67") == "(079) 123-45-67"

    def test_empty_string(self):
        assert normalize_phone("") == ""

    def test_none_value(self):
        assert normalize_phone(None) == ""


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
