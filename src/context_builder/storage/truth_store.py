"""Canonical truth store helpers.

Stores and loads ground-truth labels keyed by full file MD5.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _resolve_registry_dir(output_root: Path) -> Path:
    """Resolve registry dir from an output root or claims dir."""
    output_root = Path(output_root)
    if (output_root / "claims").exists():
        return output_root / "registry"
    if output_root.name == "claims":
        return output_root.parent / "registry"
    return output_root.parent / "registry"


class TruthStore:
    """Filesystem-backed canonical truth store."""

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
        """Save canonical truth by file MD5 (atomic write)."""
        truth_dir = self.truth_root / file_md5
        truth_dir.mkdir(parents=True, exist_ok=True)

        truth_path = truth_dir / "latest.json"
        tmp_path = truth_dir / "latest.json.tmp"

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(truth_payload, f, indent=2, ensure_ascii=False, default=str)
            tmp_path.replace(truth_path)
        except IOError as exc:
            if tmp_path.exists():
                tmp_path.unlink()
            raise IOError(f"Failed to save truth: {exc}") from exc
