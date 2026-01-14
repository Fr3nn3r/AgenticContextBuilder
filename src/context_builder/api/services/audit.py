"""Service for audit logging of pipeline operations.

This module provides tamper-evident audit logging with cryptographic hash chaining.
Each audit entry is linked to the previous entry via SHA-256 hashes, enabling
detection of any modifications or deletions.
"""

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GENESIS_HASH = "GENESIS"


@dataclass
class AuditEntry:
    """Single audit log entry with hash chain support.

    Each entry contains a record_hash computed from its content and a
    previous_hash linking to the prior entry, forming a tamper-evident chain.
    """

    timestamp: str
    user: str
    action: str
    action_type: str  # run_started, run_cancelled, run_deleted, config_created, etc.
    entity_type: str  # run, config
    entity_id: str
    # Hash chain fields
    record_hash: Optional[str] = field(default=None)
    previous_hash: str = field(default=GENESIS_HASH)


@dataclass
class AuditIntegrityReport:
    """Report from verifying audit log hash chain integrity."""

    valid: bool
    total_records: int
    break_at_index: Optional[int] = None
    error_type: Optional[str] = None
    error_details: Optional[str] = None
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditService:
    """Service for audit logging to JSONL file with hash chain integrity."""

    def __init__(self, config_dir: Path):
        """
        Initialize the audit service.

        Args:
            config_dir: Directory to store audit file (e.g., output/config/)
        """
        self.config_dir = config_dir
        self.audit_file = config_dir / "audit.jsonl"

    def _ensure_dir(self) -> None:
        """Ensure config directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, entry: AuditEntry) -> str:
        """Compute SHA-256 hash of an entry excluding the record_hash field.

        Args:
            entry: Audit entry to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        data = asdict(entry)
        data.pop("record_hash", None)
        # Keep previous_hash as it's part of the chain
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _get_last_hash(self) -> str:
        """Get the hash of the last entry in the audit log.

        Returns:
            Last entry's hash, or GENESIS_HASH if log is empty
        """
        if not self.audit_file.exists():
            return GENESIS_HASH

        last_hash = GENESIS_HASH
        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
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
            logger.warning(f"Failed to read audit file: {e}")

        return last_hash

    def log(
        self,
        action: str,
        action_type: str,
        entity_type: str,
        entity_id: str,
        user: str = "admin",
    ) -> AuditEntry:
        """
        Log an audit entry with hash chain integrity.

        Args:
            action: Human-readable action description (e.g., "Started run crisp-falcon-47")
            action_type: Machine-readable type (e.g., "run_started")
            entity_type: Type of entity (e.g., "run", "config")
            entity_id: ID of the entity
            user: User who performed the action (default: "admin")

        Returns:
            The created audit entry with computed hashes
        """
        self._ensure_dir()

        # Create entry with previous hash link
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            user=user,
            action=action,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            previous_hash=self._get_last_hash(),
        )

        # Compute hash for this entry
        entry.record_hash = self._compute_hash(entry)

        # Serialize the entry
        line = json.dumps(asdict(entry), ensure_ascii=False, default=str) + "\n"

        # Write atomically using temp file + rename pattern
        tmp_file = self.audit_file.with_suffix(".jsonl.tmp")
        try:
            # Read existing content
            existing_content = ""
            if self.audit_file.exists():
                with open(self.audit_file, "r", encoding="utf-8") as f:
                    existing_content = f.read()

            # Write to temp file
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(existing_content)
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            tmp_file.replace(self.audit_file)
            logger.debug(f"Audit log: {action}")

        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")
            if tmp_file.exists():
                tmp_file.unlink()

        return entry

    def list_entries(
        self,
        action_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        List audit log entries.

        Args:
            action_type: Filter by action type (e.g., "run_started")
            entity_type: Filter by entity type (e.g., "run", "config")
            since: ISO timestamp to filter entries after
            limit: Maximum number of entries to return

        Returns:
            List of audit entries, newest first
        """
        if not self.audit_file.exists():
            return []

        entries = []
        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = AuditEntry(**data)

                        # Apply filters
                        if action_type and entry.action_type != action_type:
                            continue
                        if entity_type and entry.entity_type != entity_type:
                            continue
                        if since and entry.timestamp < since:
                            continue

                        entries.append(entry)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Invalid audit entry: {e}")
                        continue

        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
            return []

        # Sort by timestamp descending (newest first) and limit
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def log_run_started(self, run_id: str, friendly_name: str, user: str = "admin") -> AuditEntry:
        """Log a run started event."""
        return self.log(
            action=f"Started run {friendly_name}",
            action_type="run_started",
            entity_type="run",
            entity_id=run_id,
            user=user,
        )

    def log_run_cancelled(self, run_id: str, friendly_name: str, user: str = "admin") -> AuditEntry:
        """Log a run cancelled event."""
        return self.log(
            action=f"Cancelled run {friendly_name}",
            action_type="run_cancelled",
            entity_type="run",
            entity_id=run_id,
            user=user,
        )

    def log_run_deleted(self, run_id: str, friendly_name: str, user: str = "admin") -> AuditEntry:
        """Log a run deleted event."""
        return self.log(
            action=f"Deleted run {friendly_name}",
            action_type="run_deleted",
            entity_type="run",
            entity_id=run_id,
            user=user,
        )

    def log_config_created(self, config_id: str, config_name: str, user: str = "admin") -> AuditEntry:
        """Log a config created event."""
        return self.log(
            action=f"Created config {config_name}",
            action_type="config_created",
            entity_type="config",
            entity_id=config_id,
            user=user,
        )

    def log_config_updated(self, config_id: str, config_name: str, user: str = "admin") -> AuditEntry:
        """Log a config updated event."""
        return self.log(
            action=f"Updated config {config_name}",
            action_type="config_updated",
            entity_type="config",
            entity_id=config_id,
            user=user,
        )

    def log_config_deleted(self, config_id: str, config_name: str, user: str = "admin") -> AuditEntry:
        """Log a config deleted event."""
        return self.log(
            action=f"Deleted config {config_name}",
            action_type="config_deleted",
            entity_type="config",
            entity_id=config_id,
            user=user,
        )

    def verify_chain_integrity(self) -> AuditIntegrityReport:
        """Verify the integrity of the entire audit log hash chain.

        Walks through all entries and verifies:
        1. Each entry's hash matches its content
        2. Each entry's previous_hash matches the prior entry's hash

        Returns:
            AuditIntegrityReport with verification results
        """
        if not self.audit_file.exists():
            return AuditIntegrityReport(valid=True, total_records=0)

        entries: List[tuple[int, Dict[str, Any]]] = []
        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entries.append((idx, data))
                    except json.JSONDecodeError as e:
                        return AuditIntegrityReport(
                            valid=False,
                            total_records=idx,
                            break_at_index=idx,
                            error_type="json_parse_error",
                            error_details=f"Failed to parse entry at line {idx}: {e}",
                        )
        except IOError as e:
            return AuditIntegrityReport(
                valid=False,
                total_records=0,
                error_type="io_error",
                error_details=f"Failed to read audit log: {e}",
            )

        if not entries:
            return AuditIntegrityReport(valid=True, total_records=0)

        expected_previous_hash = GENESIS_HASH

        for idx, data in entries:
            stored_hash = data.get("record_hash")
            stored_previous = data.get("previous_hash", GENESIS_HASH)

            # Verify previous hash matches expectation
            if stored_previous != expected_previous_hash:
                return AuditIntegrityReport(
                    valid=False,
                    total_records=len(entries),
                    break_at_index=idx,
                    error_type="chain_break",
                    error_details=(
                        f"Previous hash mismatch at entry {idx}: "
                        f"expected {expected_previous_hash[:16]}..., "
                        f"got {stored_previous[:16] if stored_previous else 'None'}..."
                    ),
                )

            # Recompute hash and verify
            # Handle entries with or without hash fields (for backwards compatibility)
            entry_data = {k: v for k, v in data.items() if k not in ("record_hash",)}
            if "previous_hash" not in entry_data:
                entry_data["previous_hash"] = GENESIS_HASH
            try:
                entry = AuditEntry(**entry_data)
                computed_hash = self._compute_hash(entry)
            except TypeError:
                # Legacy entry without hash fields - skip hash verification
                expected_previous_hash = stored_hash or GENESIS_HASH
                continue

            if stored_hash and stored_hash != computed_hash:
                return AuditIntegrityReport(
                    valid=False,
                    total_records=len(entries),
                    break_at_index=idx,
                    error_type="hash_mismatch",
                    error_details=(
                        f"Hash mismatch at entry {idx}: "
                        f"stored {stored_hash[:16] if stored_hash else 'None'}..., "
                        f"computed {computed_hash[:16]}..."
                    ),
                )

            # Update expected previous hash for next iteration
            expected_previous_hash = stored_hash or computed_hash

        return AuditIntegrityReport(valid=True, total_records=len(entries))
