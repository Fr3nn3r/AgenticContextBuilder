"""Batch counter for generating sequential batch numbers per workspace.

Tracks daily sequence numbers and generates BATCH-YYYYMMDD-NNN formatted IDs.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BatchCounter:
    """Generates sequential batch numbers with date-based format.

    Format: BATCH-YYYYMMDD-NNN (e.g., BATCH-20260115-001)

    The counter resets daily and is persisted to disk in the registry directory.
    """

    COUNTER_FILE = "batch_counter.json"

    def __init__(self, registry_dir: Path):
        """Initialize batch counter.

        Args:
            registry_dir: Path to registry directory (workspace/registry/).
        """
        self.registry_dir = registry_dir
        self._counter_path = registry_dir / self.COUNTER_FILE

    def _load_counter(self) -> dict:
        """Load counter state from disk."""
        if not self._counter_path.exists():
            return {"date": "", "sequence": 0}

        try:
            with open(self._counter_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read batch counter: {e}")
            return {"date": "", "sequence": 0}

    def _save_counter(self, state: dict) -> None:
        """Save counter state to disk."""
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._counter_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save batch counter: {e}")

    def next_batch_id(self) -> str:
        """Generate the next batch ID.

        Returns:
            Batch ID in format BATCH-YYYYMMDD-NNN
        """
        today = datetime.utcnow().strftime("%Y%m%d")
        state = self._load_counter()

        if state.get("date") == today:
            # Same day: increment sequence
            sequence = state.get("sequence", 0) + 1
        else:
            # New day: reset sequence
            sequence = 1

        # Update state
        state = {"date": today, "sequence": sequence}
        self._save_counter(state)

        return f"BATCH-{today}-{sequence:03d}"

    def current_sequence(self) -> Optional[int]:
        """Get the current sequence number for today.

        Returns:
            Current sequence number, or None if no batches created today.
        """
        today = datetime.utcnow().strftime("%Y%m%d")
        state = self._load_counter()

        if state.get("date") == today:
            return state.get("sequence", 0)
        return None
