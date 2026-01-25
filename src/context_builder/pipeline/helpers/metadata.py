"""Metadata helpers for pipeline runs - git info, hashes, manifests."""

import hashlib
import logging
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.pipeline.helpers.io import write_json_atomic
from context_builder.pipeline.paths import RunPaths
from context_builder.pipeline.writer import ResultWriter
from context_builder.storage.workspace_paths import get_workspace_config_dir

logger = logging.getLogger(__name__)


def get_git_info() -> Dict[str, Any]:
    """Get current git commit info."""
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode().strip()

        # Check if working tree is dirty
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            timeout=5,
        )
        is_dirty = len(result.stdout.strip()) > 0

        return {
            "commit_sha": commit_sha,
            "is_dirty": is_dirty,
        }
    except Exception:
        return {
            "commit_sha": None,
            "is_dirty": None,
        }


def compute_templates_hash() -> str:
    """Compute deterministic hash of extraction specs/templates."""
    try:
        # Hash the extraction specs
        specs_dir = Path(__file__).parent.parent.parent / "extraction" / "specs"
        if not specs_dir.exists():
            return "no_specs"

        hasher = hashlib.md5()
        for spec_file in sorted(specs_dir.glob("*.yaml")):
            hasher.update(spec_file.read_bytes())
        return hasher.hexdigest()[:12]
    except Exception:
        return "hash_error"


def compute_workspace_config_hash() -> Optional[str]:
    """Compute SHA-256 hash of workspace config directory.

    Returns:
        Hex-encoded hash of all config files, or None if config dir doesn't exist.
    """
    try:
        config_dir = get_workspace_config_dir()
        if not config_dir.exists():
            return None

        hasher = hashlib.sha256()
        files_found = False

        # Hash all files in config directory recursively
        for file_path in sorted(config_dir.rglob("*")):
            if file_path.is_file():
                files_found = True
                # Include relative path in hash for structure awareness
                rel_path = file_path.relative_to(config_dir)
                hasher.update(str(rel_path).encode("utf-8"))
                hasher.update(file_path.read_bytes())

        return hasher.hexdigest() if files_found else None
    except Exception as e:
        logger.warning(f"Failed to compute workspace config hash: {e}")
        return None


def snapshot_workspace_config(run_paths: RunPaths) -> Optional[Path]:
    """Snapshot workspace config directory to run's config_snapshot folder.

    Args:
        run_paths: Run-scoped output paths

    Returns:
        Path to the snapshot directory, or None if no config to snapshot.
    """
    try:
        config_dir = get_workspace_config_dir()
        if not config_dir.exists():
            logger.debug("No workspace config directory to snapshot")
            return None

        # Check if there are any files to snapshot
        files = list(config_dir.rglob("*"))
        if not any(f.is_file() for f in files):
            logger.debug("Workspace config directory is empty, skipping snapshot")
            return None

        # Create snapshot directory under the run
        snapshot_dir = run_paths.run_root / "config_snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Copy entire config directory structure
        for file_path in files:
            if file_path.is_file():
                rel_path = file_path.relative_to(config_dir)
                dest_path = snapshot_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)

        logger.debug(f"Snapshotted workspace config to {snapshot_dir}")
        return snapshot_dir
    except Exception as e:
        logger.warning(f"Failed to snapshot workspace config: {e}")
        return None


def write_manifest(
    run_paths: RunPaths,
    run_id: str,
    claim_id: str,
    command: str,
    doc_count: int,
    stage_config: Optional[Any] = None,
    writer: Optional[ResultWriter] = None,
    version_bundle_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Write manifest.json at run start. Returns manifest dict for later update."""
    from context_builder.pipeline.stages.context import StageConfig

    # Default to full pipeline if no config
    if stage_config is None:
        stage_config = StageConfig()

    # Compute workspace config hash for compliance traceability
    workspace_config_hash = compute_workspace_config_hash()

    manifest = {
        "run_id": run_id,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "ended_at": None,
        "command": command,
        "cwd": str(Path.cwd()),
        "hostname": os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown")),
        "python_version": sys.version.split()[0],
        "git": get_git_info(),
        "pipeline_versions": {
            "contextbuilder_version": "1.0.0",
            "extractor_version": "v1.0.0",
            "templates_hash": compute_templates_hash(),
        },
        "input": {
            "claim_id": claim_id,
            "docs_discovered": doc_count,
        },
        "counters_expected": {
            "docs": doc_count,
        },
        "run_kind": stage_config.run_kind,
        "stages_executed": [s.value for s in stage_config.stages],
        "version_bundle_id": version_bundle_id,
        "workspace_config_hash": workspace_config_hash,
    }
    write_json_atomic(run_paths.manifest_json, manifest, writer=writer)

    # Snapshot workspace config for full reproducibility
    snapshot_workspace_config(run_paths)

    return manifest


def mark_run_complete(run_paths: RunPaths, writer: Optional[ResultWriter] = None) -> None:
    """Create .complete marker after all artifacts written."""
    (writer or ResultWriter()).touch(run_paths.complete_marker)


def compute_phase_aggregates(results: List[Any]) -> Dict[str, Any]:
    """Compute aggregate phase metrics from document results.

    Args:
        results: List of DocResult objects

    Returns:
        Dict with ingestion, classification, extraction, and quality_gate sub-dicts.
    """
    # Ingestion metrics
    ingestion_success = sum(
        1 for r in results
        if r.status == "success" or (r.failed_phase and r.failed_phase != "ingestion")
    )
    ingestion_failed = sum(1 for r in results if r.failed_phase == "ingestion")
    ingestion_duration = sum(
        r.timings.ingestion_ms for r in results
        if r.timings and r.timings.ingestion_ms
    )

    # Classification metrics
    # Docs that made it past ingestion
    classified = sum(1 for r in results if r.doc_type is not None)
    classification_failed = sum(1 for r in results if r.failed_phase == "classification")
    classification_duration = sum(
        r.timings.classification_ms for r in results
        if r.timings and r.timings.classification_ms
    )

    # Build doc type distribution
    doc_type_distribution: Counter[str] = Counter()
    for r in results:
        if r.doc_type:
            doc_type_distribution[r.doc_type] += 1

    # Extraction metrics
    extraction_attempted = sum(
        1 for r in results
        if r.extraction_path is not None or r.failed_phase == "extraction"
    )
    extraction_succeeded = sum(1 for r in results if r.extraction_path is not None)
    extraction_failed = sum(1 for r in results if r.failed_phase == "extraction")
    extraction_duration = sum(
        r.timings.extraction_ms for r in results
        if r.timings and r.timings.extraction_ms
    )

    # Quality gate metrics
    qg_pass = sum(1 for r in results if r.quality_gate_status == "pass")
    qg_warn = sum(1 for r in results if r.quality_gate_status == "warn")
    qg_fail = sum(1 for r in results if r.quality_gate_status == "fail")

    return {
        "ingestion": {
            "discovered": len(results),
            "ingested": ingestion_success,
            "skipped": 0,  # Would track duplicates/unsupported if we had that info
            "failed": ingestion_failed,
            "duration_ms": ingestion_duration if ingestion_duration > 0 else None,
        },
        "classification": {
            "classified": classified,
            "low_confidence": 0,  # TODO: Track when confidence < threshold
            "distribution": dict(doc_type_distribution),
            "duration_ms": classification_duration if classification_duration > 0 else None,
        },
        "extraction": {
            "attempted": extraction_attempted,
            "succeeded": extraction_succeeded,
            "failed": extraction_failed,
            "skipped_unsupported": len(results) - extraction_attempted,
            "duration_ms": extraction_duration if extraction_duration > 0 else None,
        },
        "quality_gate": {
            "pass": qg_pass,
            "warn": qg_warn,
            "fail": qg_fail,
        },
    }
