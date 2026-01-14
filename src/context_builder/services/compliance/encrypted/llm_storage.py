"""Encrypted file-based LLM call storage implementation.

This module provides encrypted file-based implementations of the LLM call
storage protocols. Records are encrypted with envelope encryption before
storage for protecting sensitive prompt and response data.

Wire format (per line):
    base64(encrypted_record)

Where encrypted_record is the envelope-encrypted JSON serialization of the
LLMCallRecord.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from context_builder.schemas.llm_call_record import LLMCallRecord
from context_builder.services.compliance.crypto import (
    CryptoError,
    EnvelopeEncryptor,
)
from context_builder.services.compliance.interfaces import (
    LLMCallReader,
    LLMCallSink,
    LLMCallStorage,
)

logger = logging.getLogger(__name__)


class EncryptedLLMCallSink(LLMCallSink):
    """Append-only encrypted storage for LLM call records.

    Each call is:
    1. Serialized to JSON
    2. Encrypted with envelope encryption
    3. Base64 encoded and written as a line

    Writes are atomic using temp file + rename pattern.
    """

    def __init__(self, storage_path: Path, encryptor: EnvelopeEncryptor):
        """Initialize the encrypted sink.

        Args:
            storage_path: Path to the encrypted JSONL file for storing calls.
            encryptor: EnvelopeEncryptor instance for encryption.
        """
        self._path = Path(storage_path)
        self._encryptor = encryptor
        self._ensure_parent_dir()

    def _ensure_parent_dir(self) -> None:
        """Ensure parent directory exists."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def generate_call_id() -> str:
        """Generate a unique call ID.

        Returns:
            Call ID in format: llm_<12-char-hex>
        """
        return f"llm_{uuid.uuid4().hex[:12]}"

    def log_call(self, record: LLMCallRecord) -> LLMCallRecord:
        """Log an encrypted LLM call record.

        Assigns call_id if not set, encrypts, and writes atomically.

        Args:
            record: The call record to log.

        Returns:
            The record with call_id populated.
        """
        self._ensure_parent_dir()

        # Ensure call_id is set
        if not record.call_id:
            record.call_id = self.generate_call_id()

        # Serialize the record
        plaintext = json.dumps(asdict(record), ensure_ascii=False, default=str).encode(
            "utf-8"
        )

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
            logger.debug(f"Logged encrypted LLM call {record.call_id}")

        except IOError as e:
            logger.warning(f"Failed to log encrypted LLM call: {e}")
            if tmp_file.exists():
                tmp_file.unlink()

        return record


class EncryptedLLMCallReader(LLMCallReader):
    """Read-only query interface for encrypted LLM call records."""

    def __init__(self, storage_path: Path, encryptor: EnvelopeEncryptor):
        """Initialize the encrypted reader.

        Args:
            storage_path: Path to the encrypted JSONL file containing calls.
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
            logger.warning(f"Failed to decrypt LLM call line: {e}")
            return None

    def get_by_id(self, call_id: str) -> Optional[LLMCallRecord]:
        """Retrieve an LLM call by its identifier.

        Args:
            call_id: The call identifier to look up.

        Returns:
            The LLMCallRecord if found, None otherwise.
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
                    if data and data.get("call_id") == call_id:
                        return LLMCallRecord(**data)
        except IOError as e:
            logger.error(f"Failed to read encrypted LLM storage: {e}")

        return None

    def query_by_decision(self, decision_id: str) -> List[LLMCallRecord]:
        """Get all LLM calls linked to a decision.

        Args:
            decision_id: The decision identifier to filter by.

        Returns:
            List of call records linked to the decision.
        """
        results = []
        if not self._path.exists():
            return results

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = self._decrypt_line(line)
                    if data and data.get("decision_id") == decision_id:
                        try:
                            results.append(LLMCallRecord(**data))
                        except TypeError:
                            continue
        except IOError as e:
            logger.error(f"Failed to read encrypted LLM storage: {e}")

        return results

    def count(self) -> int:
        """Return the total number of call records.

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


class EncryptedLLMCallStorage(LLMCallStorage):
    """Combined encrypted file-based LLM call storage using composition.

    This class composes EncryptedLLMCallSink and EncryptedLLMCallReader to
    provide the full LLMCallStorage interface.
    """

    def __init__(
        self,
        storage_dir: Path,
        encryptor: EnvelopeEncryptor,
        filename: str = "llm_calls.enc.jsonl",
    ):
        """Initialize the encrypted storage.

        Args:
            storage_dir: Directory for storing the encrypted calls file.
            encryptor: EnvelopeEncryptor instance for encryption/decryption.
            filename: Name of the encrypted JSONL file (default: llm_calls.enc.jsonl).
        """
        self._storage_dir = Path(storage_dir)
        self._path = self._storage_dir / filename
        self._encryptor = encryptor

        # Compose the individual implementations
        self._sink = EncryptedLLMCallSink(self._path, encryptor)
        self._reader = EncryptedLLMCallReader(self._path, encryptor)

    @property
    def storage_path(self) -> Path:
        """Get the path to the storage file."""
        return self._path

    # Delegate to sink
    def log_call(self, record: LLMCallRecord) -> LLMCallRecord:
        """Log an encrypted LLM call record."""
        return self._sink.log_call(record)

    # Delegate to reader
    def get_by_id(self, call_id: str) -> Optional[LLMCallRecord]:
        """Retrieve an LLM call by its identifier."""
        return self._reader.get_by_id(call_id)

    def query_by_decision(self, decision_id: str) -> List[LLMCallRecord]:
        """Get all LLM calls linked to a decision."""
        return self._reader.query_by_decision(decision_id)

    def count(self) -> int:
        """Return the total number of call records."""
        return self._reader.count()
