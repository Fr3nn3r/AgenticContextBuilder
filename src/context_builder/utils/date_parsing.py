"""Date parsing utilities for European multilingual date formats.

Handles German, French, and numeric date formats commonly found in
Swiss/European insurance documents. Normalizes to ISO YYYY-MM-DD.
"""

import re
from datetime import date
from typing import Any, Optional

# German month names (lowercase) -> month number
_GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3,
    "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}

# French month names (lowercase) -> month number
_FRENCH_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2,
    "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

_MONTH_NAMES = {**_GERMAN_MONTHS, **_FRENCH_MONTHS}

# ISO: 2026-01-23 (optionally followed by T or space + time)
_RE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T \s].*)?$")

# Named month: "20. Januar 2026", "27 janvier 2026", "3 mars 2026"
_RE_NAMED_MONTH = re.compile(
    r"^(\d{1,2})\.?\s+([A-Za-z\u00e0-\u00fc]+)\s+(\d{4})$"
)

# Numeric with separators: DD.MM.YYYY, DD/MM/YYYY, DD,MM,YYYY, DD-MM-YYYY
# Optionally followed by space + time part
_RE_NUMERIC = re.compile(
    r"^(\d{1,2})[./,\-](\d{1,2})[./,\-](\d{2,4})(?:\s.*)?$"
)


def _expand_year(year: int) -> int:
    """Expand 2-digit year to 4-digit (assume 2000-2099)."""
    if year < 100:
        return 2000 + year
    return year


def _validate_date(year: int, month: int, day: int) -> Optional[str]:
    """Validate and return ISO string, or None if invalid."""
    try:
        d = date(_expand_year(year), month, day)
        return d.isoformat()
    except ValueError:
        return None


def parse_date_to_iso(value: Any) -> Optional[str]:
    """Parse a date string in various European formats to ISO YYYY-MM-DD.

    Supported formats:
    - ISO pass-through: 2026-01-23
    - European dot: 23.01.2026
    - Slash: 19/01/2026
    - Comma: 07,01,2026
    - Dash (DD-MM-YYYY): 23-01-2026
    - German long: "20. Januar 2026", "13 Januar 2026"
    - French long: "27 janvier 2026", "20 Janvier 2026"
    - Accented: fevrier, aout, decembre, maerz (accepted without accents too)

    Numeric formats always assume DD/MM/YYYY (European context).

    Args:
        value: Date string (or None/non-string).

    Returns:
        ISO date string (YYYY-MM-DD), or None if unparseable.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = value.strip()
    if not text:
        return None

    # 1. ISO format: YYYY-MM-DD
    m = _RE_ISO.match(text)
    if m:
        return _validate_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # 2. Named month: "20. Januar 2026" or "27 janvier 2026"
    m = _RE_NAMED_MONTH.match(text)
    if m:
        day_s, month_name, year_s = m.group(1), m.group(2).lower(), m.group(3)
        month_num = _MONTH_NAMES.get(month_name)
        if month_num is not None:
            return _validate_date(int(year_s), month_num, int(day_s))

    # 3. Numeric separators: DD.MM.YYYY, DD/MM/YYYY, DD,MM,YYYY, DD-MM-YYYY
    m = _RE_NUMERIC.match(text)
    if m:
        day_s, month_s, year_s = m.group(1), m.group(2), m.group(3)
        return _validate_date(int(year_s), int(month_s), int(day_s))

    return None


def date_to_iso(value: Any) -> str:
    """Normalizer-registry wrapper: returns ISO string or original on failure.

    This is the function wired into the NORMALIZERS dict. It always returns
    a string (never None), falling back to the original value when parsing fails.
    """
    from context_builder.extraction.normalizers import safe_string

    raw = safe_string(value)
    result = parse_date_to_iso(raw)
    return result if result is not None else raw
