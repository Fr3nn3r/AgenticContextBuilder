"""Decision Ledger Service for tamper-evident audit trail.

This module provides append-only storage with cryptographic hash chaining
for compliance decision records. Each record is linked to the previous
one via SHA-256 hashes, enabling tamper detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.schemas.decision_record import (
    DecisionQuery,
    DecisionRecord,
    DecisionType,
    IntegrityReport,
)

logger = logging.getLogger(__name__)

GENESIS_HASH = "GENESIS"


class DecisionLedger:
    """Append-only decision ledger with hash chain integrity.

    Provides tamper-evident storage for compliance decisions. Each record
    is cryptographically linked to the previous record, enabling detection
    of any modifications or deletions.

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
        self.ledger_file = self.storage_dir / "decisions.jsonl"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure storage directory exists."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, record: DecisionRecord) -> str:
        """Compute SHA-256 hash of a record excluding hash fields.

        Args:
            record: Decision record to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        # Create a copy of the record data without hash fields
        data = record.model_dump()
        data.pop("record_hash", None)
        # Keep previous_hash as it's part of the chain

        # Serialize deterministically
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _get_last_hash(self) -> str:
        """Get the hash of the last record in the ledger.

        Returns:
            Last record's hash, or GENESIS_HASH if ledger is empty
        """
        if not self.ledger_file.exists():
            return GENESIS_HASH

        last_hash = GENESIS_HASH
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "record_hash" in data and data["record_hash"]:
                            last_hash = data["record_hash"]
                    except json.JSONDecodeError:
                        continue
        except IOError as e:
            logger.warning(f"Failed to read ledger file: {e}")

        return last_hash

    def _generate_decision_id(self) -> str:
        """Generate a unique decision ID.

        Returns:
            UUID-based decision identifier
        """
        return f"dec_{uuid.uuid4().hex[:12]}"

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
        self._ensure_dir()

        # Assign decision_id if not set
        if not record.decision_id:
            record.decision_id = self._generate_decision_id()

        # Set timestamp if not set
        if not record.created_at:
            record.created_at = datetime.utcnow().isoformat() + "Z"

        # Link to previous record
        record.previous_hash = self._get_last_hash()

        # Compute hash of this record
        record.record_hash = self._compute_hash(record)

        # Serialize the record
        line = json.dumps(record.model_dump(), ensure_ascii=False, default=str) + "\n"

        # Write atomically using temp file + rename pattern
        tmp_file = self.ledger_file.with_suffix(".jsonl.tmp")
        try:
            # Read existing content
            existing_content = ""
            if self.ledger_file.exists():
                with open(self.ledger_file, "r", encoding="utf-8") as f:
                    existing_content = f.read()

            # Write to temp file
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(existing_content)
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            tmp_file.replace(self.ledger_file)
            logger.debug(f"Appended decision {record.decision_id} to ledger")

        except IOError as e:
            if tmp_file.exists():
                tmp_file.unlink()
            raise IOError(f"Failed to append to ledger: {e}") from e

        return record

    def verify_integrity(self) -> IntegrityReport:
        """Verify the integrity of the entire hash chain.

        Walks through all records and verifies:
        1. Each record's hash matches its content
        2. Each record's previous_hash matches the prior record's hash

        Returns:
            IntegrityReport with verification results
        """
        if not self.ledger_file.exists():
            return IntegrityReport(
                valid=True,
                total_records=0,
            )

        records = []
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        records.append((idx, data))
                    except json.JSONDecodeError as e:
                        return IntegrityReport(
                            valid=False,
                            total_records=idx,
                            break_at_index=idx,
                            error_type="json_parse_error",
                            error_details=f"Failed to parse record at line {idx}: {e}",
                        )
        except IOError as e:
            return IntegrityReport(
                valid=False,
                total_records=0,
                error_type="io_error",
                error_details=f"Failed to read ledger: {e}",
            )

        if not records:
            return IntegrityReport(valid=True, total_records=0)

        expected_previous_hash = GENESIS_HASH

        for idx, data in records:
            stored_hash = data.get("record_hash")
            stored_previous = data.get("previous_hash", GENESIS_HASH)
            decision_id = data.get("decision_id", f"unknown_{idx}")

            # Verify previous hash matches expectation
            if stored_previous != expected_previous_hash:
                return IntegrityReport(
                    valid=False,
                    total_records=len(records),
                    break_at_index=idx,
                    break_at_decision_id=decision_id,
                    error_type="chain_break",
                    error_details=(
                        f"Previous hash mismatch at record {idx}: "
                        f"expected {expected_previous_hash[:16]}..., "
                        f"got {stored_previous[:16] if stored_previous else 'None'}..."
                    ),
                )

            # Recompute hash and verify
            record_for_hash = DecisionRecord.model_validate(data)
            computed_hash = self._compute_hash(record_for_hash)

            if stored_hash != computed_hash:
                return IntegrityReport(
                    valid=False,
                    total_records=len(records),
                    break_at_index=idx,
                    break_at_decision_id=decision_id,
                    error_type="hash_mismatch",
                    error_details=(
                        f"Hash mismatch at record {idx} ({decision_id}): "
                        f"stored {stored_hash[:16] if stored_hash else 'None'}..., "
                        f"computed {computed_hash[:16]}..."
                    ),
                )

            # Update expected previous hash for next iteration
            expected_previous_hash = stored_hash

        return IntegrityReport(
            valid=True,
            total_records=len(records),
        )

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
        if not self.ledger_file.exists():
            return []

        if filters is None:
            filters = DecisionQuery()

        results = []
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        record = DecisionRecord.model_validate(data)

                        # Apply filters
                        if filters.decision_type and record.decision_type != filters.decision_type:
                            continue
                        if filters.claim_id and record.claim_id != filters.claim_id:
                            continue
                        if filters.doc_id and record.doc_id != filters.doc_id:
                            continue
                        if filters.run_id and record.run_id != filters.run_id:
                            continue
                        if filters.actor_id and record.actor_id != filters.actor_id:
                            continue
                        if filters.since and record.created_at < filters.since:
                            continue
                        if filters.until and record.created_at > filters.until:
                            continue

                        results.append(record)
                    except (json.JSONDecodeError, ValueError):
                        continue

        except IOError as e:
            logger.error(f"Failed to query ledger: {e}")
            return []

        # Apply pagination
        results = results[filters.offset : filters.offset + filters.limit]

        return results

    def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]:
        """Get a single decision by ID.

        Args:
            decision_id: Decision identifier

        Returns:
            DecisionRecord if found, None otherwise
        """
        if not self.ledger_file.exists():
            return None

        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("decision_id") == decision_id:
                            return DecisionRecord.model_validate(data)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except IOError as e:
            logger.error(f"Failed to read ledger: {e}")

        return None

    def count(self) -> int:
        """Count total records in the ledger.

        Returns:
            Number of records
        """
        if not self.ledger_file.exists():
            return 0

        count = 0
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
        except IOError:
            return 0

        return count
