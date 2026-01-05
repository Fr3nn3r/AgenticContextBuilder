"""Field value normalizers and validators for extraction."""

import re
from datetime import datetime
from typing import Callable, Optional
from dateutil import parser as date_parser


# =============================================================================
# NORMALIZERS
# =============================================================================

def normalize_uppercase_trim(value: str) -> str:
    """Normalize text to uppercase and trim whitespace."""
    if not value:
        return ""
    return value.strip().upper()


def normalize_date_to_iso(value: str) -> str:
    """
    Normalize various date formats to ISO 8601 (YYYY-MM-DD).

    Handles:
    - dd/mm/yy, dd/mm/yyyy
    - yyyy-mm-dd
    - dd-mm-yyyy
    - Natural language dates (via dateutil)

    Args:
        value: Raw date string

    Returns:
        ISO format date string or original value if parsing fails
    """
    if not value:
        return ""

    value = value.strip()

    # Try common Ecuador/Spanish date formats first (dd/mm/yyyy)
    patterns = [
        (r"(\d{1,2})/(\d{1,2})/(\d{2})$", "%d/%m/%y"),  # dd/mm/yy
        (r"(\d{1,2})/(\d{1,2})/(\d{4})$", "%d/%m/%Y"),  # dd/mm/yyyy
        (r"(\d{1,2})-(\d{1,2})-(\d{2})$", "%d-%m-%y"),  # dd-mm-yy
        (r"(\d{1,2})-(\d{1,2})-(\d{4})$", "%d-%m-%Y"),  # dd-mm-yyyy
        (r"(\d{4})-(\d{1,2})-(\d{1,2})$", "%Y-%m-%d"),  # yyyy-mm-dd (already ISO)
    ]

    for pattern, fmt in patterns:
        if re.match(pattern, value):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

    # Try dateutil parser as fallback (handles many formats)
    try:
        # dayfirst=True for European/Latin American format (dd/mm/yyyy)
        dt = date_parser.parse(value, dayfirst=True, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass

    # Return original if all parsing fails
    return value


def normalize_plate(value: str) -> str:
    """
    Normalize Ecuador vehicle plate format.

    Ecuador plates are typically:
    - Old format: AAA-1234 (3 letters, 4 digits)
    - New format: ABC1234 (3 letters, 4 digits, no dash)

    Args:
        value: Raw plate string

    Returns:
        Normalized plate in uppercase without spaces
    """
    if not value:
        return ""

    # Remove common noise
    cleaned = value.strip().upper()
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)

    # If we have 7 characters (typical plate length), format nicely
    if len(cleaned) == 7:
        # Format as ABC-1234
        return f"{cleaned[:3]}-{cleaned[3:]}"

    return cleaned


def normalize_none(value: str) -> str:
    """No-op normalizer - returns value as-is."""
    return value.strip() if value else ""


# =============================================================================
# VALIDATORS
# =============================================================================

def validate_non_empty(value: str) -> bool:
    """Validate that value is not empty after stripping whitespace."""
    return bool(value and value.strip())


def validate_is_date(value: str) -> bool:
    """Validate that value looks like a date."""
    if not value:
        return False

    # Check for ISO format
    if re.match(r"\d{4}-\d{2}-\d{2}$", value):
        return True

    # Check for common date patterns
    date_patterns = [
        r"\d{1,2}/\d{1,2}/\d{2,4}",  # dd/mm/yy or dd/mm/yyyy
        r"\d{1,2}-\d{1,2}-\d{2,4}",  # dd-mm-yy or dd-mm-yyyy
    ]

    for pattern in date_patterns:
        if re.match(pattern, value):
            return True

    return False


def validate_plate_like(value: str) -> bool:
    """
    Validate that value looks like an Ecuador vehicle plate.

    Ecuador plates: 3 letters + 3-4 digits
    """
    if not value:
        return False

    # Remove non-alphanumeric
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value)

    # Check pattern: 3 letters + 3-4 digits
    if re.match(r"^[A-Za-z]{3}\d{3,4}$", cleaned):
        return True

    return False


# =============================================================================
# REGISTRY
# =============================================================================

NORMALIZERS: dict[str, Callable[[str], str]] = {
    "uppercase_trim": normalize_uppercase_trim,
    "date_to_iso": normalize_date_to_iso,
    "plate_normalize": normalize_plate,
    "none": normalize_none,
}

VALIDATORS: dict[str, Callable[[str], bool]] = {
    "non_empty": validate_non_empty,
    "is_date": validate_is_date,
    "plate_like": validate_plate_like,
}


def get_normalizer(name: str) -> Callable[[str], str]:
    """Get normalizer function by name."""
    return NORMALIZERS.get(name, normalize_none)


def get_validator(name: str) -> Callable[[str], bool]:
    """Get validator function by name."""
    return VALIDATORS.get(name, validate_non_empty)
