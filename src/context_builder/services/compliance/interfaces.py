"""Storage interfaces for compliance subsystem.

This module defines the abstract interfaces (protocols) that all compliance
storage backends must implement. Using protocols enables dependency injection
and allows swapping backends (file, encrypted, S3, database) without changing
consumer code.

Design principles:
- DecisionAppender/Reader/Verifier are separate for single-responsibility
- LLMCallSink/Reader are separate for append vs query operations
- Combined interfaces (DecisionStorage, LLMCallStorage) for convenience
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Protocol, runtime_checkable

# Re-export DecisionQuery for convenience (used by consumers for type hints and queries)
from context_builder.schemas.decision_record import DecisionQuery

if TYPE_CHECKING:
    from context_builder.schemas.decision_record import (
        DecisionRecord,
        IntegrityReport,
    )
    from context_builder.schemas.llm_call_record import LLMCallRecord
    from context_builder.schemas.pii_vault import PIIVaultEntry


@runtime_checkable
class DecisionAppender(Protocol):
    """Protocol for append-only decision storage.

    Implementations must:
    - Compute and set record_hash before persisting
    - Link to previous record via previous_hash
    - Ensure atomic writes (no partial records)
    """

    def append(self, record: "DecisionRecord") -> "DecisionRecord":
        """Append a decision record to storage.

        Args:
            record: The decision record to append. The record_hash and
                   previous_hash fields will be computed/set by the implementation.

        Returns:
            The record with record_hash populated.

        Raises:
            IOError: If the write fails.
        """
        ...


@runtime_checkable
class DecisionReader(Protocol):
    """Protocol for querying decision records."""

    def get_by_id(self, decision_id: str) -> Optional["DecisionRecord"]:
        """Retrieve a decision by its unique identifier.

        Args:
            decision_id: The decision identifier to look up.

        Returns:
            The DecisionRecord if found, None otherwise.
        """
        ...

    def query(self, filters: Optional["DecisionQuery"] = None) -> List["DecisionRecord"]:
        """Query decisions with optional filters.

        Args:
            filters: Optional query parameters for filtering results.
                    If None, returns all records (up to default limit).

        Returns:
            List of matching decision records.
        """
        ...

    def count(self) -> int:
        """Return the total number of decision records.

        Returns:
            Total record count.
        """
        ...


@runtime_checkable
class DecisionVerifier(Protocol):
    """Protocol for verifying decision chain integrity."""

    def verify_integrity(self) -> "IntegrityReport":
        """Verify the hash chain integrity of all stored decisions.

        Checks that:
        - Each record's hash matches its computed hash
        - Each record's previous_hash matches the prior record's hash
        - The chain starts with GENESIS

        Returns:
            IntegrityReport with verification results.
        """
        ...


@runtime_checkable
class DecisionStorage(DecisionAppender, DecisionReader, DecisionVerifier, Protocol):
    """Combined interface for full decision storage operations.

    This protocol combines append, read, and verify capabilities.
    Implementations can use composition to combine separate implementations
    of each sub-protocol.
    """

    pass


@runtime_checkable
class LLMCallSink(Protocol):
    """Protocol for append-only LLM call logging.

    Implementations must:
    - Ensure atomic writes
    - Preserve call_id if already set
    """

    def log_call(self, record: "LLMCallRecord") -> "LLMCallRecord":
        """Log an LLM call record.

        Args:
            record: The call record to log.

        Returns:
            The logged record (potentially with generated call_id).
        """
        ...


@runtime_checkable
class LLMCallReader(Protocol):
    """Protocol for querying LLM call records."""

    def get_by_id(self, call_id: str) -> Optional["LLMCallRecord"]:
        """Retrieve an LLM call by its identifier.

        Args:
            call_id: The call identifier to look up.

        Returns:
            The LLMCallRecord if found, None otherwise.
        """
        ...

    def query_by_decision(self, decision_id: str) -> List["LLMCallRecord"]:
        """Get all LLM calls linked to a decision.

        Args:
            decision_id: The decision identifier to filter by.

        Returns:
            List of call records linked to the decision.
        """
        ...


@runtime_checkable
class LLMCallStorage(LLMCallSink, LLMCallReader, Protocol):
    """Combined interface for full LLM call storage operations.

    This protocol combines sink (append) and reader capabilities.
    """

    pass


# =============================================================================
# PII Vault Protocols
# =============================================================================


@runtime_checkable
class PIISink(Protocol):
    """Protocol for storing PII in the vault.

    Implementations must:
    - Encrypt entries before persisting
    - Update the vault index atomically
    - Ensure atomic writes (no partial entries)
    """

    def store(self, entry: "PIIVaultEntry") -> "PIIVaultEntry":
        """Store a single PII vault entry.

        Args:
            entry: The vault entry to store.

        Returns:
            The stored entry.

        Raises:
            IOError: If the write fails.
        """
        ...

    def store_batch(self, entries: List["PIIVaultEntry"]) -> List["PIIVaultEntry"]:
        """Store multiple PII vault entries atomically.

        Args:
            entries: List of vault entries to store.

        Returns:
            List of stored entries.

        Raises:
            IOError: If the write fails.
        """
        ...


@runtime_checkable
class PIIReader(Protocol):
    """Protocol for reading PII from the vault."""

    def get(self, entry_id: str) -> Optional["PIIVaultEntry"]:
        """Retrieve a PII entry by its identifier.

        Args:
            entry_id: The entry identifier to look up.

        Returns:
            The PIIVaultEntry if found, None otherwise.
        """
        ...

    def get_batch(self, entry_ids: List[str]) -> Dict[str, "PIIVaultEntry"]:
        """Retrieve multiple PII entries by their identifiers.

        Args:
            entry_ids: List of entry identifiers to look up.

        Returns:
            Dict mapping entry_id -> PIIVaultEntry for found entries.
        """
        ...

    def list_by_doc(self, doc_id: str) -> List["PIIVaultEntry"]:
        """Get all PII entries for a document.

        Args:
            doc_id: The document identifier.

        Returns:
            List of vault entries for the document.
        """
        ...


@runtime_checkable
class PIIShredder(Protocol):
    """Protocol for crypto-shredding PII vaults.

    Crypto-shredding is the process of destroying the encryption key,
    making the encrypted data permanently unrecoverable. This implements
    the "right to erasure" requirement from GDPR and similar regulations.
    """

    def shred_vault(self, vault_id: str, reason: str) -> bool:
        """Crypto-shred an entire vault by destroying its KEK.

        This permanently destroys access to all PII in the vault.
        The encrypted data remains but is cryptographically unrecoverable.

        Args:
            vault_id: The vault identifier (vault_<claim_id>).
            reason: Reason for shredding (for audit trail).

        Returns:
            True if shredded successfully, False if vault not found.
        """
        ...

    def shred_entries(self, entry_ids: List[str], reason: str) -> int:
        """Mark specific entries as shredded.

        Note: For true crypto-shredding, use shred_vault() which destroys
        the KEK. This method marks entries as deleted in the index for
        cases where individual entry deletion is needed.

        Args:
            entry_ids: List of entry identifiers to shred.
            reason: Reason for shredding (for audit trail).

        Returns:
            Number of entries shredded.
        """
        ...


@runtime_checkable
class PIIVault(PIISink, PIIReader, PIIShredder, Protocol):
    """Combined interface for full PII vault operations.

    This protocol combines sink (store), reader (retrieve), and
    shredder (crypto-delete) capabilities.

    Properties:
        vault_id: The vault identifier (vault_<claim_id>)
    """

    @property
    def vault_id(self) -> str:
        """Return the vault identifier."""
        ...

    def is_shredded(self) -> bool:
        """Check if the vault has been crypto-shredded.

        Returns:
            True if the vault KEK has been destroyed.
        """
        ...
