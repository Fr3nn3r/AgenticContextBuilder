"""File-based LLM call storage implementation.

This module provides file-based (JSONL) implementations of the LLM call
storage protocols. Records are stored as one JSON object per line with
atomic writes for durability.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from context_builder.schemas.llm_call_record import (
    InjectedContext,
    InjectedContextSource,
    LLMCallRecord,
)
from context_builder.services.compliance.interfaces import (
    LLMCallReader,
    LLMCallSink,
    LLMCallStorage,
)

logger = logging.getLogger(__name__)


def _deserialize_llm_call_record(data: dict) -> LLMCallRecord:
    """Deserialize a dictionary to LLMCallRecord, handling nested structures.

    Args:
        data: Dictionary from JSON deserialization.

    Returns:
        LLMCallRecord with properly deserialized nested InjectedContext.
    """
    # Handle nested injected_context
    if "injected_context" in data and data["injected_context"] is not None:
        ic_data = data["injected_context"]
        # Deserialize nested sources
        sources = []
        for source_data in ic_data.get("sources", []):
            sources.append(InjectedContextSource(**source_data))
        # Create InjectedContext with deserialized sources
        data["injected_context"] = InjectedContext(
            context_tier=ic_data.get("context_tier", "full"),
            total_source_chars=ic_data.get("total_source_chars", 0),
            injected_chars=ic_data.get("injected_chars", 0),
            sources=sources,
            cues_matched=ic_data.get("cues_matched", []),
            field_hints_used=ic_data.get("field_hints_used", []),
            template_variables=ic_data.get("template_variables", {}),
        )

    return LLMCallRecord(**data)


class FileLLMCallSink(LLMCallSink):
    """Append-only file storage for LLM call records.

    Each call is written as a single JSON line with atomic writes
    using temp file + rename pattern.
    """

    def __init__(self, storage_path: Path):
        """Initialize the sink.

        Args:
            storage_path: Path to the JSONL file for storing calls.
        """
        self._path = Path(storage_path)
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
        """Log an LLM call record.

        Assigns call_id if not set and writes atomically using
        temp file + rename pattern.

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
        line = json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n"

        # Write atomically using temp file + rename pattern
        tmp_file = self._path.with_suffix(".jsonl.tmp")
        try:
            existing_content = ""
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    existing_content = f.read()

            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(existing_content)
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            tmp_file.replace(self._path)
            logger.debug(f"Logged LLM call {record.call_id}")

        except IOError as e:
            logger.warning(f"Failed to log LLM call: {e}")
            if tmp_file.exists():
                tmp_file.unlink()

        return record


class FileLLMCallReader(LLMCallReader):
    """Read-only query interface for LLM call records stored in JSONL."""

    def __init__(self, storage_path: Path):
        """Initialize the reader.

        Args:
            storage_path: Path to the JSONL file containing calls.
        """
        self._path = Path(storage_path)

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
                    try:
                        data = json.loads(line)
                        if data.get("call_id") == call_id:
                            return _deserialize_llm_call_record(data)
                    except (json.JSONDecodeError, TypeError):
                        continue
        except IOError as e:
            logger.error(f"Failed to read LLM storage: {e}")

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
                    try:
                        data = json.loads(line)
                        if data.get("decision_id") == decision_id:
                            results.append(_deserialize_llm_call_record(data))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except IOError as e:
            logger.error(f"Failed to read LLM storage: {e}")

        return results

    def count(self) -> int:
        """Return the total number of call records.

        Returns:
            Total record count.
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


class FileLLMCallStorage(LLMCallStorage):
    """Combined file-based LLM call storage using composition.

    This class composes FileLLMCallSink and FileLLMCallReader to provide
    the full LLMCallStorage interface.
    """

    def __init__(self, storage_dir: Path, filename: str = "llm_calls.jsonl"):
        """Initialize the storage.

        Args:
            storage_dir: Directory for storing the calls file.
            filename: Name of the JSONL file (default: llm_calls.jsonl).
        """
        self._storage_dir = Path(storage_dir)
        self._path = self._storage_dir / filename

        # Compose the individual implementations
        self._sink = FileLLMCallSink(self._path)
        self._reader = FileLLMCallReader(self._path)

    @property
    def storage_path(self) -> Path:
        """Get the path to the storage file."""
        return self._path

    # Delegate to sink
    def log_call(self, record: LLMCallRecord) -> LLMCallRecord:
        """Log an LLM call record."""
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
