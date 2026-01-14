"""Decision Ledger Service for tamper-evident audit trail.

This module provides the DecisionLedger facade class which maintains
backwards compatibility while delegating to the new FileDecisionStorage
implementation.

For new code, prefer using FileDecisionStorage directly via dependency injection:

    from context_builder.services.compliance import FileDecisionStorage, DecisionStorage

    def process_document(storage: DecisionStorage):
        storage.append(record)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from context_builder.schemas.decision_record import (
    DecisionQuery,
    DecisionRecord,
    IntegrityReport,
)
from context_builder.services.compliance.file import (
    GENESIS_HASH,
    FileDecisionStorage,
)

# Re-export GENESIS_HASH for backwards compatibility
__all__ = ["DecisionLedger", "GENESIS_HASH"]


class DecisionLedger:
    """Append-only decision ledger with hash chain integrity.

    This class is a facade that maintains the existing API while delegating
    to FileDecisionStorage. For new code, prefer injecting DecisionStorage
    interface directly.

    Usage:
        ledger = DecisionLedger(Path("output/logs"))
        record = DecisionRecord(...)
        ledger.append(record)

        # Verify integrity
        report = ledger.verify_integrity()
        if not report.valid:
            raise ValueError(f"Chain broken at {report.break_at_decision_id}")
    """

    def __init__(self, storage_dir: Path):
        """Initialize the decision ledger.

        Args:
            storage_dir: Directory for storing the ledger file
        """
        self.storage_dir = Path(storage_dir)
        self._storage = FileDecisionStorage(storage_dir)
        # Expose ledger_file for backwards compatibility with tests
        self.ledger_file = self._storage.storage_path

    def append(self, record: DecisionRecord) -> DecisionRecord:
        """Append a decision record to the ledger.

        Computes the hash chain and writes the record atomically.

        Args:
            record: Decision record to append

        Returns:
            The record with computed hashes

        Raises:
            IOError: If write fails
        """
        return self._storage.append(record)

    def verify_integrity(self) -> IntegrityReport:
        """Verify the integrity of the entire hash chain.

        Walks through all records and verifies:
        1. Each record's hash matches its content
        2. Each record's previous_hash matches the prior record's hash

        Returns:
            IntegrityReport with verification results
        """
        return self._storage.verify_integrity()

    def query(
        self,
        filters: Optional[DecisionQuery] = None,
    ) -> List[DecisionRecord]:
        """Query decisions with optional filters.

        Args:
            filters: Query parameters for filtering

        Returns:
            List of matching decision records
        """
        return self._storage.query(filters)

    def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]:
        """Get a single decision by ID.

        Args:
            decision_id: Decision identifier

        Returns:
            DecisionRecord if found, None otherwise
        """
        return self._storage.get_by_id(decision_id)

    def count(self) -> int:
        """Count total records in the ledger.

        Returns:
            Number of records
        """
        return self._storage.count()

    def _get_last_hash(self) -> str:
        """Get the hash of the last record in the ledger.

        Returns:
            Last record's hash, or GENESIS_HASH if ledger is empty

        Note:
            This method is exposed for backwards compatibility.
            New code should use FileDecisionStorage.get_last_hash().
        """
        return self._storage.get_last_hash()
