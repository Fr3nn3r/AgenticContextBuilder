"""Service for audit logging of pipeline operations."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """Single audit log entry."""

    timestamp: str
    user: str
    action: str
    action_type: str  # run_started, run_cancelled, run_deleted, config_created, etc.
    entity_type: str  # run, config
    entity_id: str


class AuditService:
    """Service for audit logging to JSONL file."""

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

    def log(
        self,
        action: str,
        action_type: str,
        entity_type: str,
        entity_id: str,
        user: str = "admin",
    ) -> AuditEntry:
        """
        Log an audit entry.

        Args:
            action: Human-readable action description (e.g., "Started run crisp-falcon-47")
            action_type: Machine-readable type (e.g., "run_started")
            entity_type: Type of entity (e.g., "run", "config")
            entity_id: ID of the entity
            user: User who performed the action (default: "admin")

        Returns:
            The created audit entry
        """
        self._ensure_dir()

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            user=user,
            action=action,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        try:
            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry)) + "\n")
            logger.debug(f"Audit log: {action}")
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")

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
