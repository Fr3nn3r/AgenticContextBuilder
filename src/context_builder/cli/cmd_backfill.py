"""Backfill command — reprocess extractions to fill missing evidence offsets."""

from pathlib import Path

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    get_active_workspace,
    setup_logging,
)
from context_builder.cli._console import console, print_ok, print_err, output_result


@app.command("backfill", help="Reprocess extractions to fill missing evidence offsets.")
def backfill_cmd(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be updated without writing"),
):
    """Backfill missing character offsets and evidence verification flags."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    from context_builder.extraction.backfill import backfill_workspace

    workspace = get_active_workspace()
    if workspace and workspace.get("path"):
        claims_dir = Path(workspace["path"]) / "claims"
        if not ctx.obj["quiet"]:
            console.print(f"Using workspace: {claims_dir}")
    else:
        claims_dir = Path("output") / "claims"

    if not claims_dir.exists():
        print_err(f"Claims directory not found: {claims_dir}")
        raise SystemExit(1)

    if not ctx.obj["quiet"]:
        console.print(f"Backfilling evidence in: {claims_dir}")
        if dry_run:
            console.print("[dim](dry run — no changes will be written)[/dim]")

    stats = backfill_workspace(claims_dir, dry_run=dry_run)

    if ctx.obj["json"]:
        output_result(stats, ctx=ctx)
    elif not ctx.obj["quiet"]:
        console.print(f"\nProcessed: {stats['processed']} extractions")
        console.print(f"Improved:  {stats['improved']} extractions")
        if stats["errors"]:
            console.print(f"Errors:    {len(stats['errors'])}")
            for err in stats["errors"][:5]:
                console.print(f"  - {err['file']}: {err['error']}")
