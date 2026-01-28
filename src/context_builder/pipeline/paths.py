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


@dataclass
class WorkspaceRunPaths:
    """Paths for workspace-scoped (global) run outputs.

    These live at output/runs/<run_id>/ and aggregate across all claims.
    """

    run_root: Path  # <output_base>/runs/<run_id>
    manifest_json: Path  # run_root/manifest.json (with claim pointers)
    metrics_json: Path  # run_root/metrics.json (aggregated)
    summary_json: Path  # run_root/summary.json (aggregated)
    logs_dir: Path  # run_root/logs
    run_log: Path  # logs/run.log
    complete_marker: Path  # run_root/.complete


@dataclass
class WorkspaceClaimRunPaths:
    """Paths for workspace-scoped claim run outputs.

    Lives at {workspace}/claim_runs/{clm_run_id}/.
    """

    run_root: Path
    manifest_json: Path
    summary_json: Path
    logs_dir: Path
    run_log: Path
    complete_marker: Path


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


def get_workspace_run_paths(output_base: Path, run_id: str) -> WorkspaceRunPaths:
    """Get paths for a workspace-scoped (global) run (does not create directories).

    Args:
        output_base: Base output directory (e.g., output/claims)
        run_id: Run identifier

    Returns:
        WorkspaceRunPaths with paths under output_base/../runs/<run_id>/
    """
    # Global runs live at output/runs/<run_id>/ (sibling to output/claims/)
    runs_base = output_base.parent / "runs"
    run_root = runs_base / run_id
    logs_dir = run_root / "logs"
    return WorkspaceRunPaths(
        run_root=run_root,
        manifest_json=run_root / "manifest.json",
        metrics_json=run_root / "metrics.json",
        summary_json=run_root / "summary.json",
        logs_dir=logs_dir,
        run_log=logs_dir / "run.log",
        complete_marker=run_root / ".complete",
    )


def create_workspace_run_structure(output_base: Path, run_id: str) -> WorkspaceRunPaths:
    """Create workspace-scoped run directory structure.

    Args:
        output_base: Base output directory (e.g., output/claims)
        run_id: Run identifier

    Returns:
        WorkspaceRunPaths with all directories created
    """
    paths = get_workspace_run_paths(output_base, run_id)
    paths.run_root.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    return paths


def get_workspace_claim_run_paths(
    workspace_root: Path, claim_run_id: str
) -> WorkspaceClaimRunPaths:
    """Get paths for a workspace-scoped claim run (does not create directories).

    Args:
        workspace_root: Workspace directory (e.g., workspaces/nsa/).
        claim_run_id: Claim run identifier.

    Returns:
        WorkspaceClaimRunPaths with paths under workspace_root/claim_runs/{clm_run_id}/.
    """
    run_root = workspace_root / "claim_runs" / claim_run_id
    logs_dir = run_root / "logs"
    return WorkspaceClaimRunPaths(
        run_root=run_root,
        manifest_json=run_root / "manifest.json",
        summary_json=run_root / "summary.json",
        logs_dir=logs_dir,
        run_log=logs_dir / "run.log",
        complete_marker=run_root / ".complete",
    )


def create_workspace_claim_run_structure(
    workspace_root: Path, claim_run_id: str
) -> WorkspaceClaimRunPaths:
    """Create workspace-scoped claim run directory structure.

    Args:
        workspace_root: Workspace directory (e.g., workspaces/nsa/).
        claim_run_id: Claim run identifier.

    Returns:
        WorkspaceClaimRunPaths with all directories created.
    """
    paths = get_workspace_claim_run_paths(workspace_root, claim_run_id)
    paths.run_root.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    return paths


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
