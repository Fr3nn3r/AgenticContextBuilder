"""Shared utilities extracted from the legacy CLI."""

import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler

from context_builder.schemas.run_errors import PipelineStage
from context_builder.startup import ensure_initialized as _ensure_initialized


logger = logging.getLogger(__name__)


def ensure_initialized() -> None:
    """Initialize environment and workspace."""
    _ensure_initialized()


def setup_logging(*, verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging with Rich handler."""
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    handler = RichHandler(
        console=None,  # Use default stderr
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Suppress noisy third-party loggers
    for name in (
        "openai._base_client",
        "httpx",
        "httpcore",
        "azure",
        "azure.core",
        "azure.core.http",
        "azure.identity",
        "azure.ai.documentintelligence",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    def handler(signum, frame):
        from context_builder.cli._console import console
        console.print("\n[yellow]![/yellow] Process interrupted by user. Exiting gracefully...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handler)


def get_project_root() -> Path:
    """Find project root by looking for .contextbuilder directory."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / ".contextbuilder").is_dir():
            return parent
    return current


def get_active_workspace() -> Optional[dict]:
    """Read active workspace from .contextbuilder/workspaces.json."""
    project_root = get_project_root()
    workspaces_file = project_root / ".contextbuilder" / "workspaces.json"

    if not workspaces_file.exists():
        return None

    try:
        with open(workspaces_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        active_id = config.get("active_workspace_id")
        if not active_id:
            return None

        for ws in config.get("workspaces", []):
            if ws.get("workspace_id") == active_id:
                return ws

        return None
    except (json.JSONDecodeError, IOError):
        return None


def get_workspace_claims_dir() -> Path:
    """Get claims directory for active workspace, or default to output/claims."""
    workspace = get_active_workspace()
    if workspace and workspace.get("path"):
        return Path(workspace["path"]) / "claims"
    return Path("output/claims")


def get_workspace_logs_dir() -> Path:
    """Get logs directory for active workspace, or default to output/logs."""
    workspace = get_active_workspace()
    if workspace and workspace.get("path"):
        return Path(workspace["path"]) / "logs"
    return Path("output/logs")


def resolve_workspace_root(*, quiet: bool = False) -> Path:
    """Resolve workspace root from active workspace or fall back to 'output'.

    Raises:
        SystemExit: If workspace directory does not exist.
    """
    workspace = get_active_workspace()
    if workspace and workspace.get("path"):
        workspace_root = Path(workspace["path"])
        if not quiet:
            logger.info(
                f"Using workspace '{workspace.get('name', workspace.get('workspace_id'))}': {workspace_root}"
            )
    else:
        workspace_root = Path("output")

    if not workspace_root.exists():
        from context_builder.cli._console import print_err
        print_err(f"Workspace not found: {workspace_root}")
        raise SystemExit(1)

    return workspace_root


def parse_stages(stages_str: str) -> list[PipelineStage]:
    """Parse comma-separated stages string into PipelineStage list.

    Args:
        stages_str: Comma-separated stages (e.g., "ingest,classify,extract")

    Returns:
        List of PipelineStage enums

    Raises:
        ValueError: If invalid stage name provided
    """
    valid_stages = {s.value for s in PipelineStage}
    stages = []

    for s in stages_str.split(","):
        s = s.strip().lower()
        if s not in valid_stages:
            raise ValueError(
                f"Invalid stage '{s}'. Valid stages: {', '.join(valid_stages)}"
            )
        stages.append(PipelineStage(s))

    return stages
