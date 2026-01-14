"""PII Vault stub for future PII separation.

This module provides a placeholder interface for PII (Personally Identifiable Information)
storage that will allow PII to be stored separately from the audit log while maintaining
referential integrity.

IMPORTANT: This is a stub implementation. PII separation is not yet implemented.
All methods raise NotImplementedError or return None.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PIIVault:
    """Stub implementation of a PII vault.

    This class provides a placeholder interface for storing PII separately
    from the main audit trail. When implemented, this will:

    1. Accept PII data and return a reference ID
    2. Store PII with encryption at rest
    3. Support retrieval by reference ID
    4. Enable PII deletion for right-to-be-forgotten compliance

    Current implementation raises NotImplementedError for all operations.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize the PII vault.

        Args:
            storage_dir: Directory for PII storage (unused in stub)
        """
        self.storage_dir = storage_dir
        logger.warning(
            "PIIVault is a stub implementation. PII separation is not yet implemented."
        )

    def store_pii(self, data: Dict[str, Any]) -> Optional[str]:
        """Store PII data and return a reference ID.

        STUB: Returns None, indicating PII was not stored.

        Args:
            data: PII data to store

        Returns:
            None (stub implementation)
        """
        # In a real implementation, this would:
        # 1. Generate a unique reference ID
        # 2. Encrypt the PII data
        # 3. Store encrypted data with metadata
        # 4. Return the reference ID
        logger.debug("PIIVault.store_pii called but not implemented (stub)")
        return None

    def get_pii(self, ref_id: str) -> Dict[str, Any]:
        """Retrieve PII data by reference ID.

        STUB: Raises NotImplementedError.

        Args:
            ref_id: Reference ID from store_pii

        Returns:
            Never returns (raises NotImplementedError)

        Raises:
            NotImplementedError: Always raised in stub implementation
        """
        raise NotImplementedError(
            "PIIVault.get_pii is not implemented. "
            "PII separation is planned for a future release."
        )

    def delete_pii(self, ref_id: str) -> bool:
        """Delete PII data by reference ID (right to be forgotten).

        STUB: Raises NotImplementedError.

        Args:
            ref_id: Reference ID to delete

        Returns:
            Never returns (raises NotImplementedError)

        Raises:
            NotImplementedError: Always raised in stub implementation
        """
        raise NotImplementedError(
            "PIIVault.delete_pii is not implemented. "
            "PII separation is planned for a future release."
        )

    def exists(self, ref_id: str) -> bool:
        """Check if a PII reference exists.

        STUB: Returns False.

        Args:
            ref_id: Reference ID to check

        Returns:
            False (stub implementation)
        """
        return False


# Utility functions for PII handling


def generate_pii_ref_id() -> str:
    """Generate a unique PII reference ID.

    Returns:
        Unique reference ID string
    """
    return f"pii_{uuid.uuid4().hex[:16]}"


def is_pii_field(field_name: str) -> bool:
    """Check if a field name likely contains PII.

    This is a heuristic check based on common field naming conventions.

    Args:
        field_name: Field name to check

    Returns:
        True if field likely contains PII
    """
    pii_indicators = [
        "name",
        "ssn",
        "social_security",
        "email",
        "phone",
        "address",
        "dob",
        "date_of_birth",
        "birth_date",
        "driver_license",
        "passport",
        "account_number",
        "credit_card",
        "bank",
        "routing",
    ]

    field_lower = field_name.lower()
    return any(indicator in field_lower for indicator in pii_indicators)


def redact_pii_in_text(text: str, replacement: str = "[REDACTED]") -> str:
    """Redact common PII patterns from text.

    STUB: Returns text unchanged. Actual implementation would use
    regex patterns to identify and redact PII.

    Args:
        text: Text that may contain PII
        replacement: Replacement string for redacted content

    Returns:
        Text with PII redacted (stub returns unchanged)
    """
    # In a real implementation, this would:
    # 1. Use regex patterns to find SSNs, emails, phones, etc.
    # 2. Replace matched patterns with [REDACTED]
    # 3. Return the redacted text
    logger.debug("redact_pii_in_text called but not implemented (stub)")
    return text
