"""Storage operations for claim-level runs."""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.schemas.claim_run import ClaimRunManifest

logger = logging.getLogger(__name__)


@dataclass
class ClaimRunContext:
    """Metadata context for a claim run, passed from CLI to storage."""

    claim_run_id: Optional[str] = None
    started_at: Optional[str] = None
    hostname: Optional[str] = None
    python_version: Optional[str] = None
    git: Optional[Dict[str, Any]] = None
    workspace_config_hash: Optional[str] = None
    command: Optional[str] = None


def generate_claim_run_id(salt: str = "") -> str:
    """Generate a unique claim run ID (module-level, no storage instance needed).

    Format: clm_{YYYYMMDD}_{HHMMSS}_{hash6}

    Args:
        salt: Optional salt for extra uniqueness.

    Returns:
        Unique claim run ID string.
    """
    now = datetime.utcnow()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    hash_input = f"{timestamp}_{salt}_{now.microsecond}"
    hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:6]
    return f"clm_{timestamp}_{hash_suffix}"


class ClaimRunStorage:
    """Storage operations for claim runs.

    Handles creating, reading, and listing claim runs.
    Uses "always latest" strategy - no current pointer.
    """

    def __init__(self, claim_folder: Path):
        """Initialize with claim folder path.

        Args:
            claim_folder: Path to claim directory (e.g., claims/CLM-001/)
        """
        self.claim_folder = claim_folder
        self.claim_runs_dir = claim_folder / "claim_runs"

    def generate_claim_run_id(self) -> str:
        """Generate a unique claim run ID.

        Format: clm_{YYYYMMDD}_{HHMMSS}_{hash6}
        """
        now = datetime.utcnow()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        hash_input = f"{timestamp}_{self.claim_folder.name}_{now.microsecond}"
        hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:6]
        return f"clm_{timestamp}_{hash_suffix}"

    def create_claim_run(
        self,
        extraction_runs: List[str],
        contextbuilder_version: str,
        run_context: Optional[ClaimRunContext] = None,
    ) -> ClaimRunManifest:
        """Create a new claim run directory and manifest.

        Args:
            extraction_runs: Extraction run IDs being considered.
            contextbuilder_version: Version of ContextBuilder.
            run_context: Optional metadata context (shared ID, git, timing, etc.).

        Returns:
            ClaimRunManifest for the new run.
        """
        # Use provided ID from context, or auto-generate
        if run_context and run_context.claim_run_id:
            claim_run_id = run_context.claim_run_id
        else:
            claim_run_id = self.generate_claim_run_id()

        run_dir = self.claim_runs_dir / claim_run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Build manifest with optional enriched metadata
        manifest_kwargs = dict(
            claim_run_id=claim_run_id,
            claim_id=self.claim_folder.name,
            extraction_runs_considered=extraction_runs,
            contextbuilder_version=contextbuilder_version,
        )
        if run_context:
            if run_context.started_at:
                manifest_kwargs["started_at"] = run_context.started_at
            if run_context.hostname:
                manifest_kwargs["hostname"] = run_context.hostname
            if run_context.python_version:
                manifest_kwargs["python_version"] = run_context.python_version
            if run_context.git is not None:
                manifest_kwargs["git"] = run_context.git
            if run_context.workspace_config_hash:
                manifest_kwargs["workspace_config_hash"] = run_context.workspace_config_hash
            if run_context.command:
                manifest_kwargs["command"] = run_context.command

        manifest = ClaimRunManifest(**manifest_kwargs)

        self.write_manifest(manifest)
        logger.info(f"Created claim run {claim_run_id} for {self.claim_folder.name}")
        return manifest

    def write_manifest(self, manifest: ClaimRunManifest) -> Path:
        """Write claim run manifest to disk.

        Args:
            manifest: Manifest to write.

        Returns:
            Path to manifest file.
        """
        run_dir = self.claim_runs_dir / manifest.claim_run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = run_dir / "manifest.json"
        tmp_path = manifest_path.with_suffix(".tmp")

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(manifest.model_dump(mode="json"), f, indent=2, default=str)
        tmp_path.replace(manifest_path)

        return manifest_path

    def read_manifest(self, claim_run_id: str) -> Optional[ClaimRunManifest]:
        """Read claim run manifest.

        Args:
            claim_run_id: Claim run ID.

        Returns:
            ClaimRunManifest or None if not found.
        """
        manifest_path = self.claim_runs_dir / claim_run_id / "manifest.json"
        if not manifest_path.exists():
            return None

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ClaimRunManifest(**data)

    def list_claim_runs(self) -> List[str]:
        """List all claim run IDs, sorted newest first.

        Returns:
            List of claim run IDs.
        """
        if not self.claim_runs_dir.exists():
            return []

        runs = []
        for run_dir in self.claim_runs_dir.iterdir():
            if run_dir.is_dir():
                runs.append(run_dir.name)

        # Sort by directory modification time, newest first
        runs.sort(
            key=lambda name: (self.claim_runs_dir / name).stat().st_mtime,
            reverse=True,
        )
        return runs

    def get_latest_claim_run_id(self) -> Optional[str]:
        """Get the latest claim run ID.

        Returns:
            Latest claim run ID or None if no runs exist.
        """
        runs = self.list_claim_runs()
        return runs[0] if runs else None

    def get_claim_run_path(self, claim_run_id: str) -> Path:
        """Get path to a claim run directory.

        Args:
            claim_run_id: Claim run ID.

        Returns:
            Path to claim run directory.
        """
        return self.claim_runs_dir / claim_run_id

    def write_to_claim_run(
        self, claim_run_id: str, filename: str, data: dict
    ) -> Path:
        """Write a JSON file to a claim run directory.

        Args:
            claim_run_id: Claim run ID.
            filename: Filename (e.g., "claim_facts.json").
            data: Data to write.

        Returns:
            Path to written file.
        """
        run_dir = self.claim_runs_dir / claim_run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        file_path = run_dir / filename
        tmp_path = file_path.with_suffix(".tmp")

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        tmp_path.replace(file_path)

        logger.debug(f"Wrote {filename} to {run_dir}")
        return file_path

    def read_from_claim_run(
        self, claim_run_id: str, filename: str
    ) -> Optional[dict]:
        """Read a JSON file from a claim run directory.

        Args:
            claim_run_id: Claim run ID.
            filename: Filename to read.

        Returns:
            Parsed JSON data or None if not found.
        """
        file_path = self.claim_runs_dir / claim_run_id / filename
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def read_with_fallback(self, filename: str) -> Optional[dict]:
        """Read file from latest claim run, with fallback to legacy context/.

        This is the main read method that handles backward compatibility.

        Args:
            filename: Filename to read (e.g., "claim_facts.json").

        Returns:
            Parsed JSON data or None if not found anywhere.
        """
        # Try latest claim run first
        latest = self.get_latest_claim_run_id()
        if latest:
            data = self.read_from_claim_run(latest, filename)
            if data:
                return data

        # Fallback to legacy context/ path
        legacy_path = self.claim_folder / "context" / filename
        if legacy_path.exists():
            logger.debug(f"Reading from legacy path: {legacy_path}")
            with open(legacy_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return None

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def read_claim_facts(self, claim_run_id: str) -> Optional[dict]:
        """Read claim_facts.json from claim run.

        Args:
            claim_run_id: Claim run ID.

        Returns:
            Parsed claim facts data or None if not found.
        """
        return self.read_from_claim_run(claim_run_id, "claim_facts.json")

    def write_assessment(self, claim_run_id: str, assessment: dict) -> Path:
        """Write assessment.json to claim run.

        Args:
            claim_run_id: Claim run ID.
            assessment: Assessment data to write.

        Returns:
            Path to written file.
        """
        return self.write_to_claim_run(claim_run_id, "assessment.json", assessment)
