"""Encrypted file-based decision storage implementation.

This module provides encrypted file-based implementations of the decision
storage protocols. Records are encrypted with envelope encryption before
storage, with hash chain computed over plaintext for integrity verification.

Wire format (per line):
    base64(encrypted_record)

Where encrypted_record is the envelope-encrypted JSON serialization of the
DecisionRecord.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from context_builder.schemas.decision_record import (
    DecisionQuery,
    DecisionRecord,
    IntegrityReport,
)
from context_builder.services.compliance.crypto import (
    CryptoError,
    DecryptionError,
    EnvelopeEncryptor,
)
from context_builder.services.compliance.interfaces import (
    DecisionAppender,
    DecisionReader,
    DecisionStorage,
    DecisionVerifier,
)

logger = logging.getLogger(__name__)

GENESIS_HASH = "GENESIS"


class EncryptedDecisionAppender(DecisionAppender):
    """Append-only encrypted storage for decision records with hash chain.

    Each record is:
    1. Hash chain computed over plaintext (for verification)
    2. Serialized to JSON
    3. Encrypted with envelope encryption
    4. Base64 encoded and written as a line

    Writes are atomic using temp file + rename pattern.
    """

    def __init__(self, storage_path: Path, encryptor: EnvelopeEncryptor):
        """Initialize the encrypted appender.

        Args:
            storage_path: Path to the encrypted JSONL file for storing decisions.
            encryptor: EnvelopeEncryptor instance for encryption/decryption.
        """
        self._path = Path(storage_path)
        self._encryptor = encryptor
        self._ensure_parent_dir()

    def _ensure_parent_dir(self) -> None:
        """Ensure parent directory exists."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_hash(record: DecisionRecord) -> str:
        """Compute SHA-256 hash of a record excluding the record_hash field.

        Args:
            record: Decision record to hash.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        data = record.model_dump()
        data.pop("record_hash", None)
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_decision_id() -> str:
        """Generate a unique decision ID.

        Returns:
            Decision ID in format: dec_<12-char-hex>
        """
        return f"dec_{uuid.uuid4().hex[:12]}"

    def _decrypt_line(self, line: str) -> Optional[dict]:
        """Decrypt a single line and return the JSON data.

        Args:
            line: Base64-encoded encrypted line.

        Returns:
            Decrypted JSON data, or None if decryption fails.
        """
        try:
            encrypted = base64.b64decode(line.strip())
            plaintext = self._encryptor.decrypt(encrypted)
            return json.loads(plaintext.decode("utf-8"))
        except (CryptoError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to decrypt line: {e}")
            return None

    def get_last_hash(self) -> str:
        """Get the hash of the last record in storage.

        Returns:
            Last record's hash, or GENESIS_HASH if storage is empty.
        """
        if not self._path.exists():
            return GENESIS_HASH

        last_hash = GENESIS_HASH
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = self._decrypt_line(line)
                    if data and "record_hash" in data and data["record_hash"]:
                        last_hash = data["record_hash"]
        except IOError as e:
            logger.warning(f"Failed to read storage file: {e}")

        return last_hash

    def append(self, record: DecisionRecord) -> DecisionRecord:
        """Append an encrypted decision record to storage.

        Args:
            record: The decision record to append.

        Returns:
            The record with decision_id, record_hash, and previous_hash populated.

        Raises:
            IOError: If the write fails.
        """
        self._ensure_parent_dir()

        # Assign decision_id if not set
        if not record.decision_id:
            record.decision_id = self.generate_decision_id()

        # Set timestamp if not set
        if not record.created_at:
            record.created_at = datetime.utcnow().isoformat() + "Z"

        # Link to previous record (hash chain over plaintext)
        record.previous_hash = self.get_last_hash()

        # Compute hash of this record (over plaintext)
        record.record_hash = self.compute_hash(record)

        # Serialize the record
        plaintext = json.dumps(
            record.model_dump(), ensure_ascii=False, default=str
        ).encode("utf-8")

        # Encrypt the serialized record
        encrypted = self._encryptor.encrypt(plaintext)
        encoded_line = base64.b64encode(encrypted).decode("ascii") + "\n"

        # Write atomically using temp file + rename pattern
        tmp_file = self._path.with_suffix(".enc.tmp")
        try:
            existing_content = ""
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    existing_content = f.read()

            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(existing_content)
                f.write(encoded_line)
                f.flush()
                os.fsync(f.fileno())

            tmp_file.replace(self._path)
            logger.debug(f"Appended encrypted decision {record.decision_id} to storage")

        except IOError as e:
            if tmp_file.exists():
                tmp_file.unlink()
            raise IOError(f"Failed to append to encrypted storage: {e}") from e

        return record


class EncryptedDecisionReader(DecisionReader):
    """Read-only query interface for encrypted decision records."""

    def __init__(self, storage_path: Path, encryptor: EnvelopeEncryptor):
        """Initialize the encrypted reader.

        Args:
            storage_path: Path to the encrypted JSONL file containing decisions.
            encryptor: EnvelopeEncryptor instance for decryption.
        """
        self._path = Path(storage_path)
        self._encryptor = encryptor

    def _decrypt_line(self, line: str) -> Optional[dict]:
        """Decrypt a single line and return the JSON data."""
        try:
            encrypted = base64.b64decode(line.strip())
            plaintext = self._encryptor.decrypt(encrypted)
            return json.loads(plaintext.decode("utf-8"))
        except (CryptoError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to decrypt line: {e}")
            return None

    def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]:
        """Retrieve a decision by its unique identifier.

        Args:
            decision_id: The decision identifier to look up.

        Returns:
            The DecisionRecord if found, None otherwise.
        """
        if not self._path.exists():
            return None

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = self._decrypt_line(line)
                    if data and data.get("decision_id") == decision_id:
                        return DecisionRecord.model_validate(data)
        except IOError as e:
            logger.error(f"Failed to read storage: {e}")

        return None

    def query(self, filters: Optional[DecisionQuery] = None) -> List[DecisionRecord]:
        """Query decisions with optional filters.

        Args:
            filters: Optional query parameters for filtering results.

        Returns:
            List of matching decision records.
        """
        if not self._path.exists():
            return []

        if filters is None:
            filters = DecisionQuery()

        results = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = self._decrypt_line(line)
                    if not data:
                        continue

                    try:
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
                        if filters.since and record.created_at and record.created_at < filters.since:
                            continue
                        if filters.until and record.created_at and record.created_at > filters.until:
                            continue

                        results.append(record)
                    except ValueError:
                        continue

        except IOError as e:
            logger.error(f"Failed to query storage: {e}")
            return []

        # Apply pagination
        return results[filters.offset : filters.offset + filters.limit]

    def count(self) -> int:
        """Return the total number of decision records.

        Returns:
            Total record count (including records that fail to decrypt).
        """
        if not self._path.exists():
            return 0

        count = 0
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
        except IOError:
            return 0

        return count


class EncryptedDecisionVerifier(DecisionVerifier):
    """Hash chain integrity verification for encrypted decision storage.

    Decrypts records and verifies hash chain over plaintext.
    """

    def __init__(self, storage_path: Path, encryptor: EnvelopeEncryptor):
        """Initialize the encrypted verifier.

        Args:
            storage_path: Path to the encrypted JSONL file containing decisions.
            encryptor: EnvelopeEncryptor instance for decryption.
        """
        self._path = Path(storage_path)
        self._encryptor = encryptor

    def verify_integrity(self) -> IntegrityReport:
        """Verify the hash chain integrity of all stored decisions.

        Decrypts each record and verifies:
        - Each record's hash matches its computed hash
        - Each record's previous_hash matches the prior record's hash
        - The chain starts with GENESIS

        Returns:
            IntegrityReport with verification results.
        """
        if not self._path.exists():
            return IntegrityReport(valid=True, total_records=0)

        records = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue

                    # Decrypt the record
                    try:
                        encrypted = base64.b64decode(line)
                        plaintext = self._encryptor.decrypt(encrypted)
                        data = json.loads(plaintext.decode("utf-8"))
                        records.append((idx, data))
                    except DecryptionError as e:
                        return IntegrityReport(
                            valid=False,
                            total_records=idx,
                            break_at_index=idx,
                            error_type="decryption_error",
                            error_details=f"Failed to decrypt record at line {idx}: {e}",
                        )
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
                error_details=f"Failed to read storage: {e}",
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
            computed_hash = EncryptedDecisionAppender.compute_hash(record_for_hash)

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

        return IntegrityReport(valid=True, total_records=len(records))


class EncryptedDecisionStorage(DecisionStorage):
    """Combined encrypted file-based decision storage using composition.

    This class composes EncryptedDecisionAppender, EncryptedDecisionReader, and
    EncryptedDecisionVerifier to provide the full DecisionStorage interface.
    """

    def __init__(
        self,
        storage_dir: Path,
        encryptor: EnvelopeEncryptor,
        filename: str = "decisions.enc.jsonl",
    ):
        """Initialize the encrypted storage.

        Args:
            storage_dir: Directory for storing the encrypted decisions file.
            encryptor: EnvelopeEncryptor instance for encryption/decryption.
            filename: Name of the encrypted JSONL file (default: decisions.enc.jsonl).
        """
        self._storage_dir = Path(storage_dir)
        self._path = self._storage_dir / filename
        self._encryptor = encryptor

        # Compose the individual implementations
        self._appender = EncryptedDecisionAppender(self._path, encryptor)
        self._reader = EncryptedDecisionReader(self._path, encryptor)
        self._verifier = EncryptedDecisionVerifier(self._path, encryptor)

    @property
    def storage_path(self) -> Path:
        """Get the path to the storage file."""
        return self._path

    # Delegate to appender
    def append(self, record: DecisionRecord) -> DecisionRecord:
        """Append an encrypted decision record to storage."""
        return self._appender.append(record)

    def get_last_hash(self) -> str:
        """Get the hash of the last record in storage."""
        return self._appender.get_last_hash()

    # Delegate to reader
    def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]:
        """Retrieve a decision by its unique identifier."""
        return self._reader.get_by_id(decision_id)

    def query(self, filters: Optional[DecisionQuery] = None) -> List[DecisionRecord]:
        """Query decisions with optional filters."""
        return self._reader.query(filters)

    def count(self) -> int:
        """Return the total number of decision records."""
        return self._reader.count()

    # Delegate to verifier
    def verify_integrity(self) -> IntegrityReport:
        """Verify the hash chain integrity of all stored decisions."""
        return self._verifier.verify_integrity()
