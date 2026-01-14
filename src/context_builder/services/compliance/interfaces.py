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

from typing import TYPE_CHECKING, List, Optional, Protocol, runtime_checkable

# Re-export DecisionQuery for convenience (used by consumers for type hints and queries)
from context_builder.schemas.decision_record import DecisionQuery

if TYPE_CHECKING:
    from context_builder.schemas.decision_record import (
        DecisionRecord,
        IntegrityReport,
    )
    from context_builder.schemas.llm_call_record import LLMCallRecord


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
