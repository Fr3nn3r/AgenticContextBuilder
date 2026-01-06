"""Paths module: generate and create folder structure for tidy output."""

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass
class DocPaths:
    """Paths within tidy structure for a single document."""

    doc_root: Path  # <output>/<claim_id>/docs/<doc_id>

    # Directories
    source_dir: Path  # doc_root/source
    text_dir: Path  # doc_root/text
    text_raw_dir: Path  # doc_root/text/raw
    meta_dir: Path  # doc_root/meta

    # Files
    original_txt: Path  # source/original.txt
    pages_json: Path  # text/pages.json
    source_txt: Path  # text/raw/source.txt
    doc_json: Path  # meta/doc.json


@dataclass
class ClaimPaths:
    """Paths for a claim within tidy structure."""

    claim_root: Path  # <output>/<claim_id>
    docs_dir: Path  # claim_root/docs
    runs_dir: Path  # claim_root/runs


@dataclass
class RunPaths:
    """Paths for run-scoped outputs within a claim."""

    run_root: Path  # <claim_root>/runs/<run_id>
    extraction_dir: Path  # run_root/extraction
    context_dir: Path  # run_root/context
    logs_dir: Path  # run_root/logs
    summary_json: Path  # logs/summary.json
    # New run control paths
    manifest_json: Path  # run_root/manifest.json
    metrics_json: Path  # logs/metrics.json
    run_log: Path  # logs/run.log
    complete_marker: Path  # run_root/.complete


def get_claim_paths(output_base: Path, claim_id: str) -> ClaimPaths:
    """Get paths for a claim (does not create directories)."""
    claim_root = output_base / claim_id
    return ClaimPaths(
        claim_root=claim_root,
        docs_dir=claim_root / "docs",
        runs_dir=claim_root / "runs",
    )


def get_doc_paths(claim_paths: ClaimPaths, doc_id: str) -> DocPaths:
    """Get paths for a document within a claim (does not create directories)."""
    doc_root = claim_paths.docs_dir / doc_id
    source_dir = doc_root / "source"
    text_dir = doc_root / "text"
    text_raw_dir = text_dir / "raw"
    meta_dir = doc_root / "meta"

    return DocPaths(
        doc_root=doc_root,
        source_dir=source_dir,
        text_dir=text_dir,
        text_raw_dir=text_raw_dir,
        meta_dir=meta_dir,
        original_txt=source_dir / "original.txt",
        pages_json=text_dir / "pages.json",
        source_txt=text_raw_dir / "source.txt",
        doc_json=meta_dir / "doc.json",
    )


def get_run_paths(claim_paths: ClaimPaths, run_id: str) -> RunPaths:
    """Get paths for a run within a claim (does not create directories)."""
    run_root = claim_paths.runs_dir / run_id
    logs_dir = run_root / "logs"
    return RunPaths(
        run_root=run_root,
        extraction_dir=run_root / "extraction",
        context_dir=run_root / "context",
        logs_dir=logs_dir,
        summary_json=logs_dir / "summary.json",
        # New run control paths
        manifest_json=run_root / "manifest.json",
        metrics_json=logs_dir / "metrics.json",
        run_log=logs_dir / "run.log",
        complete_marker=run_root / ".complete",
    )


def create_doc_structure(
    output_base: Path,
    claim_id: str,
    doc_id: str,
    run_id: str,
) -> Tuple[DocPaths, ClaimPaths, RunPaths]:
    """
    Create tidy folder structure for a document.

    Creates all necessary directories for storing document data and run outputs.

    Args:
        output_base: Base output directory
        claim_id: Claim identifier
        doc_id: Document identifier (md5[:12])
        run_id: Run identifier

    Returns:
        Tuple of (DocPaths, ClaimPaths, RunPaths) with all directories created
    """
    claim_paths = get_claim_paths(output_base, claim_id)
    doc_paths = get_doc_paths(claim_paths, doc_id)
    run_paths = get_run_paths(claim_paths, run_id)

    # Create all directories
    directories = [
        doc_paths.source_dir,
        doc_paths.text_raw_dir,
        doc_paths.meta_dir,
        run_paths.extraction_dir,
        run_paths.context_dir,
        run_paths.logs_dir,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    return doc_paths, claim_paths, run_paths
