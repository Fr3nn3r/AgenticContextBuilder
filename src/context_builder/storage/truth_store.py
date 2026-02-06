"""Canonical truth store helpers.

Stores and loads ground-truth labels keyed by full file MD5.
Maintains append-only version history for compliance audit trails.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def _resolve_registry_dir(output_root: Path) -> Path:
    """Resolve registry dir from an output root or claims dir."""
    output_root = Path(output_root)
    if (output_root / "claims").exists():
        return output_root / "registry"
    if output_root.name == "claims":
        return output_root.parent / "registry"
    return output_root.parent / "registry"


class GroundTruthStore:
    """Filesystem-backed ground truth store with version history.

    Stores labeled/verified data for evaluation and comparison against extractions.

    Compliance features:
    - Append-only history: Every save creates a new version file
    - latest.json always points to current truth
    - history.jsonl contains all versions for audit
    """

    def __init__(self, output_root: Path):
        self.registry_dir = _resolve_registry_dir(output_root)
        self.truth_root = self.registry_dir / "truth"

    def get_truth_by_file_md5(self, file_md5: str) -> Optional[dict]:
        """Load canonical truth by file MD5."""
        truth_path = self.truth_root / file_md5 / "latest.json"
        if not truth_path.exists():
            return None

        try:
            with open(truth_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("Failed to load truth for %s: %s", file_md5, exc)
            return None

    def save_truth_by_file_md5(self, file_md5: str, truth_payload: dict) -> None:
        """Save canonical truth by file MD5 with version history.

        Creates:
        - latest.json: Current truth (atomic write)
        - history.jsonl: Append-only version log for compliance
        """
        truth_dir = self.truth_root / file_md5
        truth_dir.mkdir(parents=True, exist_ok=True)

        # Add versioning metadata
        version_ts = datetime.utcnow().isoformat() + "Z"
        versioned_payload = {
            **truth_payload,
            "_version_metadata": {
                "saved_at": version_ts,
                "version_number": self._get_next_version_number(truth_dir),
            },
        }

        # Atomic write to latest.json
        truth_path = truth_dir / "latest.json"
        tmp_path = truth_dir / "latest.json.tmp"

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(versioned_payload, f, indent=2, ensure_ascii=False, default=str)
            tmp_path.replace(truth_path)
        except IOError as exc:
            if tmp_path.exists():
                tmp_path.unlink()
            raise IOError(f"Failed to save truth: {exc}") from exc

        # Append to history.jsonl (append-only for compliance)
        self._append_to_history(truth_dir, versioned_payload)

    def _get_next_version_number(self, truth_dir: Path) -> int:
        """Get the next version number for a truth entry."""
        history_path = truth_dir / "history.jsonl"
        if not history_path.exists():
            return 1

        try:
            with open(history_path, "r", encoding="utf-8") as f:
                count = sum(1 for _ in f)
            return count + 1
        except IOError:
            return 1

    def _append_to_history(self, truth_dir: Path, payload: dict) -> None:
        """Append a version entry to the history log (append-only)."""
        history_path = truth_dir / "history.jsonl"
        try:
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        except IOError as exc:
            logger.warning("Failed to append to truth history: %s", exc)

    def get_truth_history(self, file_md5: str) -> List[dict]:
        """Get all historical versions of truth for a file MD5.

        Returns list of versions from oldest to newest.
        """
        history_path = self.truth_root / file_md5 / "history.jsonl"
        if not history_path.exists():
            return []

        versions = []
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        versions.append(json.loads(line))
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("Failed to load truth history for %s: %s", file_md5, exc)

        return versions

    def get_truth_version(self, file_md5: str, version_number: int) -> Optional[dict]:
        """Get a specific version of truth by version number.

        Args:
            file_md5: File hash
            version_number: 1-indexed version number

        Returns:
            Truth payload for that version or None if not found
        """
        history = self.get_truth_history(file_md5)
        if version_number < 1 or version_number > len(history):
            return None
        return history[version_number - 1]


# Backwards compatibility alias (deprecated - use GroundTruthStore)
TruthStore = GroundTruthStore
