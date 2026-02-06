"""Number parsing utilities for European and international formats."""

import re
from typing import Any, Optional


def parse_european_number(value: Any) -> Optional[float]:
    """Parse a number that may be in European format or contain currency/units.

    Handles:
    - European comma decimal: "249,77" -> 249.77
    - Currency prefixes: "SFr. 358,00" -> 358.00, "CHF 100" -> 100
    - Unit suffixes: "0,2 h" -> 0.2, "5 kg" -> 5
    - Thousand separators: "1'000,50" -> 1000.50, "1.000,50" -> 1000.50

    Args:
        value: The value to parse (string, int, float, or None)

    Returns:
        Parsed float or None if parsing fails or value is None/empty
    """
    if value is None:
        return None

    # Already a number
    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return None

    # Strip whitespace
    text = value.strip()
    if not text:
        return None

    # Remove common currency symbols and prefixes
    currency_patterns = [
        r"^SFr\.?\s*",  # Swiss Franc (SFr. or SFr)
        r"^CHF\s*",     # Swiss Franc code
        r"^EUR\s*",     # Euro code
        r"^€\s*",       # Euro symbol
        r"^USD\s*",     # US Dollar code
        r"^\$\s*",      # Dollar symbol
    ]
    for pattern in currency_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Remove trailing currency codes (with optional space before)
    currency_suffix_patterns = [
        r"\s*CHF$",       # Swiss Franc code
        r"\s*EUR$",       # Euro code
        r"\s*USD$",       # US Dollar code
        r"\s*SFr\.?$",    # Swiss Franc (SFr. or SFr)
    ]
    for pattern in currency_suffix_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Remove common unit suffixes (with optional space before)
    unit_patterns = [
        r"\s*[hH]$",      # hours
        r"\s*[kK][gG]$",  # kilograms
        r"\s*[mM]$",      # meters
        r"\s*[lL]$",      # liters
        r"\s*[pP][cC][sS]?$",  # pieces
        r"\s*[sS][tT][kK]?$",  # Stück (German for pieces)
    ]
    for pattern in unit_patterns:
        text = re.sub(pattern, "", text)

    text = text.strip()
    if not text:
        return None

    # Detect European vs US number format
    # European: 1.000,50 or 1'000,50 (dot/apostrophe as thousand sep, comma as decimal)
    # US: 1,000.50 (comma as thousand sep, dot as decimal)

    has_comma = "," in text
    has_dot = "." in text
    has_apostrophe = "'" in text

    if has_apostrophe:
        # Swiss format: 1'000,50 or 1'000.50
        text = text.replace("'", "")

    if has_comma and has_dot:
        # Mixed format - determine which is decimal separator
        # The one that appears last and has <= 2 digits after is likely decimal
        last_comma = text.rfind(",")
        last_dot = text.rfind(".")

        if last_comma > last_dot:
            # European: 1.000,50 -> comma is decimal
            text = text.replace(".", "").replace(",", ".")
        else:
            # US: 1,000.50 -> dot is decimal
            text = text.replace(",", "")
    elif has_comma:
        # Only comma - likely European decimal separator
        # But could be thousand separator if followed by 3 digits at end
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            # Likely thousand separator: "1,000" -> 1000
            text = text.replace(",", "")
        else:
            # Decimal separator: "249,77" -> 249.77
            text = text.replace(",", ".")
    # If only dot, it's already in standard format

    try:
        return float(text)
    except ValueError:
        return None
