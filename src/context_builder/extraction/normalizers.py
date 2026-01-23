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


def normalize_trim(value: str) -> str:
    """Simple trim normalizer - removes leading/trailing whitespace."""
    return value.strip() if value else ""


def normalize_swiss_date_to_iso(value: str) -> str:
    """
    Convert Swiss date formats to ISO.

    Handles: dd.mm.yyyy, dd/mm/yyyy, dd.mm.yy

    Args:
        value: Raw date string (Swiss format with dots)

    Returns:
        ISO format date string (YYYY-MM-DD) or original value if parsing fails
    """
    if not value:
        return ""

    value = value.strip()

    # Try Swiss formats first (dd.mm.yyyy with dots)
    patterns = [
        (r"(\d{1,2})\.(\d{1,2})\.(\d{4})$", "%d.%m.%Y"),  # dd.mm.yyyy
        (r"(\d{1,2})\.(\d{1,2})\.(\d{2})$", "%d.%m.%y"),  # dd.mm.yy
        (r"(\d{1,2})/(\d{1,2})/(\d{4})$", "%d/%m/%Y"),  # dd/mm/yyyy
        (r"(\d{1,2})/(\d{1,2})/(\d{2})$", "%d/%m/%y"),  # dd/mm/yy
    ]

    for pattern, fmt in patterns:
        if re.match(pattern, value):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

    # Try dateutil parser as fallback
    try:
        dt = date_parser.parse(value, dayfirst=True, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass

    return value


def normalize_swiss_currency(value: str) -> Optional[float]:
    """
    Parse Swiss currency format to float.

    Handles: 10'000.00 CHF, CHF 10'000.00, 10000.00

    Args:
        value: Raw currency string

    Returns:
        Float value or None if parsing fails
    """
    if not value:
        return None

    # Convert to string if needed
    value = str(value).strip()

    # Remove currency symbols and thousands separators
    cleaned = re.sub(r"[CHF\s']", "", value)
    cleaned = cleaned.replace(",", ".")

    # Extract number
    match = re.search(r"[\d.]+", cleaned)
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass

    return None


def normalize_covered_boolean(value: str) -> bool:
    """
    Parse coverage status to boolean.

    Handles: Covered, Not covered, Gedeckt, Nicht gedeckt

    Args:
        value: Raw coverage status string

    Returns:
        True if covered, False otherwise
    """
    if not value:
        return False

    value_lower = str(value).lower().strip()

    not_covered_terms = ["not covered", "nicht gedeckt", "no", "nein", "non"]
    covered_terms = ["covered", "gedeckt", "yes", "ja", "oui"]

    for term in not_covered_terms:
        if term in value_lower:
            return False

    for term in covered_terms:
        if term in value_lower:
            return True

    return False


def normalize_transferable_boolean(value: str) -> bool:
    """
    Parse transferability status to boolean.

    Handles: Assignable guarantee, Garantie übertragbar

    Args:
        value: Raw transferability string

    Returns:
        True if transferable, False otherwise
    """
    if not value:
        return False

    value_lower = str(value).lower()

    transferable_terms = ["assignable", "transferable", "übertragbar"]

    for term in transferable_terms:
        if term in value_lower:
            return True

    return False


def normalize_extract_percentage(value: str) -> Optional[float]:
    """
    Extract percentage value from string.

    Handles: 10%, 10 %, 10

    Args:
        value: Raw percentage string

    Returns:
        Float percentage value or None if parsing fails
    """
    if not value:
        return None

    match = re.search(r"(\d+(?:\.\d+)?)\s*%?", str(value))
    if match:
        return float(match.group(1))

    return None


def normalize_extract_number(value: str) -> Optional[int]:
    """
    Extract integer from string.

    Handles: 27'000 km, 1984 cc, 0 days

    Args:
        value: Raw number string with possible units

    Returns:
        Integer value or None if parsing fails
    """
    if not value:
        return None

    # Remove thousands separators and units
    cleaned = re.sub(r"['\s]", "", str(value))
    match = re.search(r"(\d+)", cleaned)

    if match:
        return int(match.group(1))

    return None


def normalize_phone(value: str) -> str:
    """
    Normalize phone number by removing common noise.

    Keeps digits and common phone formatting characters.

    Args:
        value: Raw phone string

    Returns:
        Cleaned phone number
    """
    if not value:
        return ""

    # Keep digits, plus sign, spaces, dashes, and parentheses
    cleaned = re.sub(r"[^\d+\-\s()]", "", str(value).strip())
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


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


def validate_vin_format(value: str) -> bool:
    """
    Validate that value looks like a VIN (Vehicle Identification Number).

    VIN format: 17 alphanumeric characters (no I, O, Q)
    """
    if not value:
        return False

    # Remove spaces and dashes
    cleaned = re.sub(r"[\s-]", "", str(value).upper())

    # VIN is exactly 17 characters
    if len(cleaned) != 17:
        return False

    # VIN contains only alphanumeric (no I, O, Q)
    if re.match(r"^[A-HJ-NPR-Z0-9]{17}$", cleaned):
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
    "trim": normalize_trim,
    "swiss_date_to_iso": normalize_swiss_date_to_iso,
    "swiss_currency": normalize_swiss_currency,
    "covered_boolean": normalize_covered_boolean,
    "transferable_boolean": normalize_transferable_boolean,
    "extract_percentage": normalize_extract_percentage,
    "extract_number": normalize_extract_number,
    "phone_normalize": normalize_phone,
}

VALIDATORS: dict[str, Callable[[str], bool]] = {
    "non_empty": validate_non_empty,
    "is_date": validate_is_date,
    "plate_like": validate_plate_like,
    "vin_format": validate_vin_format,
}


def get_normalizer(name: str) -> Callable[[str], str]:
    """Get normalizer function by name."""
    return NORMALIZERS.get(name, normalize_none)


def get_validator(name: str) -> Callable[[str], bool]:
    """Get validator function by name."""
    return VALIDATORS.get(name, validate_non_empty)
