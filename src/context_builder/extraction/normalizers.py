"""Field value normalizers and validators for extraction.

Simplified approach: All normalizers just ensure type safety (convert to string).
Raw values from LLM are preserved as-is without transformation.
"""

from typing import Any, Callable


def safe_float(value: Any, default: float = 0.0) -> float | None:
    """
    Convert any value to float safely.

    Handles the common case where LLM returns a string instead of a number,
    including European decimal formats (comma as decimal separator) and
    values with trailing unit suffixes (e.g., '0,2 h', '3 m²').

    Args:
        value: Any value from LLM extraction (str, int, float, None, etc.)
        default: Default value if conversion fails (pass None for optional fields)

    Returns:
        Float representation of the value, or default if conversion fails
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove currency symbols, spaces around currency, and thousand separators
        cleaned = value.strip()
        # Strip trailing unit suffixes (e.g., "0,2 h", "3 m²", "15 Stk")
        import re
        cleaned = re.sub(r'\s+[a-zA-Z²³µ%°]+\.?$', '', cleaned)
        # Remove thousand-separator apostrophes (Swiss: 1'234.50)
        cleaned = cleaned.replace("'", "")
        # Remove currency symbols
        for currency in ["CHF", "EUR", "USD", "Fr.", "Fr"]:
            cleaned = cleaned.replace(currency, "")
        cleaned = cleaned.strip()
        if not cleaned:
            return default
        # Handle European number formats:
        # "1.234,50" → 1234.50 (dot=thousands, comma=decimal)
        # "249,77"   → 249.77  (comma=decimal)
        # "1,234.50" → 1234.50 (comma=thousands, dot=decimal) - US format
        has_dot = '.' in cleaned
        has_comma = ',' in cleaned
        if has_dot and has_comma:
            # Both present: last separator is the decimal
            last_dot = cleaned.rfind('.')
            last_comma = cleaned.rfind(',')
            if last_comma > last_dot:
                # European: 1.234,50 → remove dots, replace comma with dot
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # US: 1,234.50 → remove commas
                cleaned = cleaned.replace(',', '')
        elif has_comma:
            # Only comma: treat as decimal separator
            # "249,77" → "249.77"
            cleaned = cleaned.replace(',', '.')
        # else: only dot or no separator → standard float format
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def safe_string(value: Any) -> str:
    """
    Convert any value to string safely.

    Handles the common case where LLM returns a list instead of a string.

    Args:
        value: Any value from LLM extraction (str, list, None, etc.)

    Returns:
        String representation of the value
    """
    if value is None:
        return ""
    if isinstance(value, list):
        if len(value) == 0:
            return ""
        if len(value) == 1:
            return str(value[0]).strip()
        return " ".join(str(v) for v in value).strip()
    return str(value).strip()


# =============================================================================
# VALIDATORS (kept for quality gate checks)
# =============================================================================

def validate_non_empty(value: Any) -> bool:
    """Validate that value is not empty after conversion to string."""
    return bool(safe_string(value))


def validate_is_date(value: Any) -> bool:
    """Validate that value looks like a date (basic check)."""
    import re
    s = safe_string(value)
    if not s:
        return False
    # Match common date patterns
    date_patterns = [
        r"\d{4}-\d{2}-\d{2}",      # ISO: 2026-01-23
        r"\d{1,2}/\d{1,2}/\d{2,4}", # dd/mm/yy or dd/mm/yyyy
        r"\d{1,2}-\d{1,2}-\d{2,4}", # dd-mm-yy or dd-mm-yyyy
        r"\d{1,2}\.\d{1,2}\.\d{2,4}", # dd.mm.yyyy (Swiss)
    ]
    return any(re.search(p, s) for p in date_patterns)


def validate_plate_like(value: Any) -> bool:
    """Validate that value looks like a vehicle plate (Ecuador: 3 letters + 3-4 digits)."""
    import re
    s = safe_string(value)
    if not s:
        return False
    # Remove non-alphanumeric and check for 3 letters + 3-4 digits
    cleaned = re.sub(r"[^A-Za-z0-9]", "", s)
    return bool(re.match(r"^[A-Za-z]{3}\d{3,4}$", cleaned))


def normalize_vin(value: Any) -> str:
    """Normalize a VIN to canonical form: uppercase, no spaces or hyphens."""
    import re
    s = safe_string(value)
    if not s:
        return s
    return re.sub(r"[\s-]", "", s.upper())


def validate_vin_format(value: Any) -> bool:
    """Validate that value looks like a VIN (17 alphanumeric chars)."""
    import re
    cleaned = normalize_vin(value)
    if not cleaned:
        return False
    return len(cleaned) == 17 and bool(re.match(r"^[A-HJ-NPR-Z0-9]{17}$", cleaned))


# =============================================================================
# REGISTRY
# =============================================================================

# All normalizer names map to safe_string - we keep the names for YAML compatibility
NORMALIZERS: dict[str, Callable[[Any], str]] = {
    "uppercase_trim": safe_string,
    "vin_canonical": normalize_vin,
    "date_to_iso": safe_string,
    "plate_normalize": safe_string,
    "none": safe_string,
    "trim": safe_string,
    "swiss_date_to_iso": safe_string,
    "swiss_currency": safe_string,
    "covered_boolean": safe_string,
    "transferable_boolean": safe_string,
    "extract_percentage": safe_string,
    "extract_number": safe_string,
    "phone_normalize": safe_string,
}

VALIDATORS: dict[str, Callable[[Any], bool]] = {
    "non_empty": validate_non_empty,
    "is_date": validate_is_date,
    "plate_like": validate_plate_like,
    "vin_format": validate_vin_format,
}


def get_normalizer(name: str) -> Callable[[Any], str]:
    """Get normalizer function by name. All return safe_string."""
    return NORMALIZERS.get(name, safe_string)


def get_validator(name: str) -> Callable[[Any], bool]:
    """Get validator function by name."""
    return VALIDATORS.get(name, validate_non_empty)
