"""
Filename utilities for consistent naming across the processing pipeline.

Provides functions for:
- Sanitizing filenames (removing special characters)
- Generating timestamped processing folder names
- Extracting policy names from folder names

Single Responsibility: Handle all filename/folder naming logic.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """
    Sanitize a filename by removing/replacing special characters.

    Replaces spaces, slashes, backslashes, colons, and other problematic
    characters with the replacement string (default: underscore).

    Args:
        name: Filename to sanitize
        replacement: Character to use for replacement (default: "_")

    Returns:
        Sanitized filename safe for filesystem use

    Examples:
        >>> sanitize_filename("My Policy (2023).pdf")
        'My_Policy_2023_.pdf'
        >>> sanitize_filename("policy/with\\slashes", "-")
        'policy-with-slashes'
    """
    # Remove or replace problematic characters
    # Keep: alphanumeric, dot, dash, underscore
    # Replace: spaces, slashes, colons, parentheses, etc.
    sanitized = re.sub(r'[<>:"/\\|?*\(\)\[\]\{\}]', replacement, name)

    # Replace multiple consecutive replacement chars with single
    sanitized = re.sub(f'{re.escape(replacement)}+', replacement, sanitized)

    # Remove leading/trailing replacement chars
    sanitized = sanitized.strip(replacement)

    return sanitized


def generate_processing_folder_name(
    pdf_path: Path,
    max_name_len: int = 11,
    timestamp: Optional[datetime] = None
) -> str:
    """
    Generate a timestamped processing folder name.

    Format: YYYYMMDD-HHMMSS-{sanitized_name}

    Args:
        pdf_path: Path to the PDF file
        max_name_len: Maximum length for the name part (default: 11)
        timestamp: Optional datetime to use (default: current time)

    Returns:
        Processing folder name (e.g., "20251128-210530-policy_001")

    Examples:
        >>> pdf = Path("My Policy (2023).pdf")
        >>> generate_processing_folder_name(pdf)
        '20251128-210530-My_Policy_2'
    """
    if timestamp is None:
        timestamp = datetime.now()

    # Format timestamp as YYYYMMDD-HHMMSS
    timestamp_str = timestamp.strftime("%Y%m%d-%H%M%S")

    # Get filename without extension
    name = pdf_path.stem

    # Sanitize the name
    sanitized_name = sanitize_filename(name)

    # Truncate to max length (use full name if shorter)
    if len(sanitized_name) > max_name_len:
        truncated_name = sanitized_name[:max_name_len]
    else:
        truncated_name = sanitized_name

    # Combine timestamp and name
    folder_name = f"{timestamp_str}-{truncated_name}"

    return folder_name


def extract_policy_name_from_folder(folder_name: str) -> str:
    """
    Extract the policy name from a processing folder name.

    Reverses generate_processing_folder_name() by removing the timestamp prefix.

    Args:
        folder_name: Processing folder name (e.g., "20251128-210530-policy_001")

    Returns:
        Policy name portion (e.g., "policy_001")

    Examples:
        >>> extract_policy_name_from_folder("20251128-210530-policy_001")
        'policy_001'
        >>> extract_policy_name_from_folder("20251128-210530-My_Policy_2")
        'My_Policy_2'
    """
    # Pattern: YYYYMMDD-HHMMSS-{name}
    # Extract everything after the second dash
    parts = folder_name.split('-', 2)

    if len(parts) == 3:
        # Return the name part
        return parts[2]
    else:
        # If format doesn't match, return the whole folder name
        return folder_name


def get_policy_stem(pdf_path: Path) -> str:
    """
    Get the policy stem name from a PDF path (filename without extension).

    Args:
        pdf_path: Path to PDF file

    Returns:
        Filename without extension

    Examples:
        >>> get_policy_stem(Path("my_policy.pdf"))
        'my_policy'
    """
    return pdf_path.stem
