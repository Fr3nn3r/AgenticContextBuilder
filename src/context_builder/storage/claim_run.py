"""Storage operations for claim-level runs."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from context_builder.schemas.claim_run import ClaimRunManifest

logger = logging.getLogger(__name__)


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
    ) -> ClaimRunManifest:
        """Create a new claim run directory and manifest.

        Args:
            extraction_runs: Extraction run IDs being considered.
            contextbuilder_version: Version of ContextBuilder.

        Returns:
            ClaimRunManifest for the new run.
        """
        claim_run_id = self.generate_claim_run_id()
        run_dir = self.claim_runs_dir / claim_run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        manifest = ClaimRunManifest(
            claim_run_id=claim_run_id,
            claim_id=self.claim_folder.name,
            extraction_runs_considered=extraction_runs,
            contextbuilder_version=contextbuilder_version,
        )

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
            if run_dir.is_dir() and run_dir.name.startswith("clm_"):
                runs.append(run_dir.name)

        # Sort by timestamp in ID (clm_YYYYMMDD_HHMMSS_hash), newest first
        runs.sort(reverse=True)
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
