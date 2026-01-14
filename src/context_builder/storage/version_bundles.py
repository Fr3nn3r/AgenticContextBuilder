"""Version Bundle Storage for compliance snapshots.

This module captures and stores version snapshots at the time of each pipeline run,
enabling exact reproducibility by recording the versions of all components.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from context_builder.schemas.decision_record import VersionBundle

logger = logging.getLogger(__name__)


class VersionBundleStore:
    """Storage for version bundle snapshots.

    Creates and retrieves version snapshots that capture the state of:
    - Git commit and working tree status
    - ContextBuilder version
    - Prompt templates (hashed)
    - Extraction specifications (hashed)
    - Model configuration
    """

    CONTEXTBUILDER_VERSION = "1.0.0"

    def __init__(self, storage_dir: Path):
        """Initialize the version bundle store.

        Args:
            storage_dir: Base directory for storing version bundles
        """
        self.storage_dir = Path(storage_dir) / "version_bundles"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure storage directory exists."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_git_info(self) -> Dict[str, Any]:
        """Get current git commit and dirty status.

        Returns:
            Dict with git_commit (str or None) and git_dirty (bool or None)
        """
        try:
            # Get current commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            commit = result.stdout.strip() if result.returncode == 0 else None

            # Check if working tree is dirty
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            dirty = bool(result.stdout.strip()) if result.returncode == 0 else None

            return {"git_commit": commit, "git_dirty": dirty}
        except Exception as e:
            logger.debug(f"Failed to get git info: {e}")
            return {"git_commit": None, "git_dirty": None}

    def _hash_file(self, file_path: Path) -> Optional[str]:
        """Compute SHA-256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex-encoded hash or None if file doesn't exist
        """
        if not file_path.exists():
            return None

        try:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except IOError:
            return None

    def _hash_directory(self, dir_path: Path, pattern: str = "**/*") -> Optional[str]:
        """Compute combined hash of all files in a directory.

        Args:
            dir_path: Directory to hash
            pattern: Glob pattern for files to include

        Returns:
            Combined hex-encoded hash or None if directory doesn't exist
        """
        if not dir_path.exists():
            return None

        try:
            hasher = hashlib.sha256()
            files = sorted(dir_path.glob(pattern))
            for file_path in files:
                if file_path.is_file():
                    file_hash = self._hash_file(file_path)
                    if file_hash:
                        hasher.update(file_hash.encode("utf-8"))
            return hasher.hexdigest() if files else None
        except Exception as e:
            logger.debug(f"Failed to hash directory {dir_path}: {e}")
            return None

    def _get_prompt_template_hash(self) -> Optional[str]:
        """Get hash of prompt templates directory.

        Returns:
            Combined hash of all prompt templates
        """
        # Try common prompt locations
        possible_paths = [
            Path("prompts"),
            Path("src/context_builder/prompts"),
            Path(__file__).parent.parent / "prompts",
        ]
        for path in possible_paths:
            if path.exists():
                return self._hash_directory(path, "*.md")
        return None

    def _get_extraction_spec_hash(self) -> Optional[str]:
        """Get hash of extraction specifications.

        Returns:
            Combined hash of extraction specs
        """
        # Try common spec locations
        possible_paths = [
            Path("src/context_builder/extraction/specs"),
            Path(__file__).parent.parent / "extraction" / "specs",
        ]
        for path in possible_paths:
            if path.exists():
                return self._hash_directory(path, "*.yaml")
        return None

    def create_version_bundle(
        self,
        run_id: str,
        model_name: str = "gpt-4o",
        model_version: Optional[str] = None,
        extractor_version: str = "v1.0.0",
    ) -> VersionBundle:
        """Create a version bundle snapshot for a pipeline run.

        Args:
            run_id: Pipeline run identifier
            model_name: LLM model being used
            model_version: Specific model version if known
            extractor_version: Extractor version

        Returns:
            VersionBundle with captured versions
        """
        bundle_id = f"vb_{uuid.uuid4().hex[:12]}"
        created_at = datetime.utcnow().isoformat() + "Z"

        # Get git info
        git_info = self._get_git_info()

        # Create version bundle
        bundle = VersionBundle(
            bundle_id=bundle_id,
            created_at=created_at,
            git_commit=git_info.get("git_commit"),
            git_dirty=git_info.get("git_dirty"),
            contextbuilder_version=self.CONTEXTBUILDER_VERSION,
            extractor_version=extractor_version,
            model_name=model_name,
            model_version=model_version,
            prompt_template_hash=self._get_prompt_template_hash(),
            extraction_spec_hash=self._get_extraction_spec_hash(),
        )

        # Save to storage
        self._save_bundle(run_id, bundle)

        logger.debug(f"Created version bundle {bundle_id} for run {run_id}")
        return bundle

    def _save_bundle(self, run_id: str, bundle: VersionBundle) -> None:
        """Save version bundle to storage.

        Args:
            run_id: Pipeline run identifier
            bundle: Version bundle to save
        """
        # Create run-specific directory
        run_dir = self.storage_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save bundle.json
        bundle_file = run_dir / "bundle.json"
        with open(bundle_file, "w", encoding="utf-8") as f:
            json.dump(bundle.model_dump(), f, indent=2, default=str)

        logger.debug(f"Saved version bundle to {bundle_file}")

    def get_version_bundle(self, run_id: str) -> Optional[VersionBundle]:
        """Retrieve a version bundle by run ID.

        Args:
            run_id: Pipeline run identifier

        Returns:
            VersionBundle if found, None otherwise
        """
        bundle_file = self.storage_dir / run_id / "bundle.json"
        if not bundle_file.exists():
            return None

        try:
            with open(bundle_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return VersionBundle.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load version bundle for run {run_id}: {e}")
            return None

    def list_bundles(self) -> list[str]:
        """List all stored version bundle run IDs.

        Returns:
            List of run IDs with stored bundles
        """
        if not self.storage_dir.exists():
            return []

        return [
            d.name
            for d in self.storage_dir.iterdir()
            if d.is_dir() and (d / "bundle.json").exists()
        ]


# Singleton for convenience
_default_store: Optional[VersionBundleStore] = None


def get_version_bundle_store(storage_dir: Optional[Path] = None) -> VersionBundleStore:
    """Get or create the default version bundle store.

    Args:
        storage_dir: Optional directory override

    Returns:
        VersionBundleStore instance
    """
    global _default_store

    if storage_dir:
        return VersionBundleStore(storage_dir)

    if _default_store is None:
        default_dir = Path("output")
        _default_store = VersionBundleStore(default_dir)

    return _default_store
