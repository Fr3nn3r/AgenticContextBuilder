"""I/O helper functions for pipeline operations."""

from pathlib import Path
from typing import Any, Optional

from context_builder.pipeline.writer import ResultWriter


def get_workspace_logs_dir(output_base: Path) -> Path:
    """Derive workspace logs directory from output base path.

    If output_base is workspace-scoped (e.g., workspaces/default/claims),
    returns the sibling logs directory (workspaces/default/logs).
    Otherwise falls back to output/logs.

    Args:
        output_base: The claims output directory

    Returns:
        Path to logs directory for compliance storage
    """
    # If output_base ends with /claims, sibling is /logs
    if output_base.name == "claims":
        logs_dir = output_base.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir
    # Fallback to output/logs relative to project root
    return Path("output/logs")


def write_json(path: Path, data: Any, writer: Optional[ResultWriter] = None) -> None:
    """Write JSON file with utf-8 encoding."""
    (writer or ResultWriter()).write_json(path, data)


def write_json_atomic(path: Path, data: Any, writer: Optional[ResultWriter] = None) -> None:
    """Write JSON via temp file + rename for atomicity."""
    (writer or ResultWriter()).write_json_atomic(path, data)
