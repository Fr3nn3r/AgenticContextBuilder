"""CLI package — Typer-based command-line interface.

Usage:
    python -m context_builder.cli --help
    python -m context_builder.cli pipeline --help
"""

from context_builder.cli._app import app
from context_builder.cli._common import parse_stages  # re-export for test compat

# Register command modules (side-effect imports)
import context_builder.cli.cmd_index  # noqa: F401
import context_builder.cli.cmd_eval  # noqa: F401
import context_builder.cli.cmd_backfill  # noqa: F401
import context_builder.cli.cmd_export  # noqa: F401
import context_builder.cli.cmd_workspace  # noqa: F401
import context_builder.cli.cmd_coverage  # noqa: F401
import context_builder.cli.cmd_reconcile  # noqa: F401
import context_builder.cli.cmd_pipeline  # noqa: F401
import context_builder.cli.cmd_assess  # noqa: F401

__all__ = ["app", "parse_stages"]
