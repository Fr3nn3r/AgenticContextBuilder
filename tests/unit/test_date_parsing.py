"""Unit tests for date parsing utilities."""

import pytest

from context_builder.utils.date_parsing import parse_date_to_iso, date_to_iso


# =============================================================================
# ISO pass-through
# =============================================================================


class TestISOFormat:
    def test_standard_iso(self):
        assert parse_date_to_iso("2026-01-23") == "2026-01-23"

    def test_single_digit_month_day(self):
        assert parse_date_to_iso("2026-1-3") == "2026-01-03"

    def test_invalid_iso_month(self):
        assert parse_date_to_iso("2026-13-01") is None

    def test_invalid_iso_day(self):
        assert parse_date_to_iso("2026-02-30") is None


# =============================================================================
# European numeric formats (DD.MM.YYYY, DD/MM/YYYY, DD,MM,YYYY, DD-MM-YYYY)
# =============================================================================


class TestNumericFormats:
    def test_dot_format(self):
        assert parse_date_to_iso("23.01.2026") == "2026-01-23"

    def test_slash_format(self):
        assert parse_date_to_iso("19/01/2026") == "2026-01-19"

    def test_comma_format(self):
        assert parse_date_to_iso("07,01,2026") == "2026-01-07"

    def test_dash_european(self):
        assert parse_date_to_iso("23-01-2026") == "2026-01-23"

    def test_single_digit_day_month(self):
        assert parse_date_to_iso("3.1.2026") == "2026-01-03"

    def test_invalid_numeric_day(self):
        assert parse_date_to_iso("32.01.2026") is None

    def test_invalid_numeric_month(self):
        assert parse_date_to_iso("15.13.2026") is None


# =============================================================================
# German month names
# =============================================================================

GERMAN_MONTHS = [
    ("januar", 1), ("februar", 2), ("märz", 3), ("april", 4),
    ("mai", 5), ("juni", 6), ("juli", 7), ("august", 8),
    ("september", 9), ("oktober", 10), ("november", 11), ("dezember", 12),
]


class TestGermanMonths:
    @pytest.mark.parametrize("month_name,month_num", GERMAN_MONTHS)
    def test_german_month(self, month_name, month_num):
        result = parse_date_to_iso(f"15. {month_name.capitalize()} 2026")
        assert result == f"2026-{month_num:02d}-15"

    def test_german_without_dot(self):
        assert parse_date_to_iso("13 Januar 2026") == "2026-01-13"

    def test_german_with_dot(self):
        assert parse_date_to_iso("20. Januar 2026") == "2026-01-20"

    def test_maerz_without_umlaut(self):
        assert parse_date_to_iso("5. Maerz 2026") == "2026-03-05"


# =============================================================================
# French month names
# =============================================================================

FRENCH_MONTHS = [
    ("janvier", 1), ("février", 2), ("mars", 3), ("avril", 4),
    ("mai", 5), ("juin", 6), ("juillet", 7), ("août", 8),
    ("septembre", 9), ("octobre", 10), ("novembre", 11), ("décembre", 12),
]


class TestFrenchMonths:
    @pytest.mark.parametrize("month_name,month_num", FRENCH_MONTHS)
    def test_french_month(self, month_name, month_num):
        result = parse_date_to_iso(f"15 {month_name} 2026")
        assert result == f"2026-{month_num:02d}-15"

    def test_french_capitalized(self):
        assert parse_date_to_iso("27 Janvier 2026") == "2026-01-27"

    def test_fevrier_without_accent(self):
        assert parse_date_to_iso("10 fevrier 2026") == "2026-02-10"

    def test_aout_without_accent(self):
        assert parse_date_to_iso("1 aout 2026") == "2026-08-01"

    def test_decembre_without_accent(self):
        assert parse_date_to_iso("25 decembre 2026") == "2026-12-25"


# =============================================================================
# Edge cases
# =============================================================================


class TestEdgeCases:
    def test_none(self):
        assert parse_date_to_iso(None) is None

    def test_empty_string(self):
        assert parse_date_to_iso("") is None

    def test_whitespace_only(self):
        assert parse_date_to_iso("   ") is None

    def test_whitespace_around_date(self):
        assert parse_date_to_iso("  23.01.2026  ") == "2026-01-23"

    def test_non_string(self):
        assert parse_date_to_iso(12345) is None

    def test_unknown_month_name(self):
        assert parse_date_to_iso("15 Foobar 2026") is None

    def test_garbage_text(self):
        assert parse_date_to_iso("not a date at all") is None

    def test_feb_29_leap_year(self):
        assert parse_date_to_iso("29.02.2024") == "2024-02-29"

    def test_feb_29_non_leap_year(self):
        assert parse_date_to_iso("29.02.2026") is None


# =============================================================================
# Normalizer wrapper (date_to_iso)
# =============================================================================


class TestDateToIsoWrapper:
    def test_parseable_returns_iso(self):
        assert date_to_iso("23.01.2026") == "2026-01-23"

    def test_unparseable_returns_original(self):
        assert date_to_iso("unknown date") == "unknown date"

    def test_none_returns_empty(self):
        assert date_to_iso(None) == ""

    def test_list_input(self):
        assert date_to_iso(["23.01.2026"]) == "2026-01-23"

    def test_list_unparseable(self):
        assert date_to_iso(["not a date"]) == "not a date"
