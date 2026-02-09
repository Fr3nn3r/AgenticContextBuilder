"""Export command — export workspace data to Excel."""

from datetime import datetime
from pathlib import Path

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    get_active_workspace,
    setup_logging,
)
from context_builder.cli._console import console, print_ok, print_err, output_result


@app.command("export", help="Export workspace data to Excel file.")
def export_cmd(
    ctx: typer.Context,
    output: str = typer.Option(
        None,
        "-o", "--output",
        help="Output file path (default: auto-generated .xlsx)",
    ),
    output_dir: str = typer.Option(
        None,
        "--output-dir",
        help="Output directory (filename will be auto-generated)",
    ),
):
    """Export all workspace data to an Excel file with separate sheets."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    from context_builder.api.services.export import ExportService
    from context_builder.storage.filesystem import FileStorage

    workspace = get_active_workspace()
    if workspace and workspace.get("path"):
        workspace_root = Path(workspace["path"])
        workspace_name = workspace.get("name", workspace.get("workspace_id"))
    else:
        workspace_root = Path("output")
        workspace_name = "output"

    if not workspace_root.exists():
        print_err(f"Workspace not found: {workspace_root}")
        raise SystemExit(1)

    # Determine output path
    if output:
        output_path = Path(output)
    elif output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(output_dir) / f"workspace_export_{timestamp}.xlsx"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = workspace_root / f"workspace_export_{timestamp}.xlsx"

    storage = FileStorage(workspace_root)
    export_service = ExportService(storage)

    if not ctx.obj["quiet"]:
        console.print(f"Exporting workspace '{workspace_name}' to Excel...")

    try:
        stats = export_service.export_to_excel(output_path)
    except Exception as e:
        print_err(f"Export failed: {e}")
        raise SystemExit(1)

    if ctx.obj["json"]:
        stats["output_path"] = str(output_path)
        output_result(stats, ctx=ctx)
    elif not ctx.obj["quiet"]:
        print_ok(f"Export complete: {output_path}")
        console.print(f"  Claims:         {stats['claims']}")
        console.print(f"  Documents:      {stats['documents']}")
        console.print(f"  Runs:           {stats['runs']}")
        console.print(f"  Claim Runs:     {stats['claim_runs']}")
        console.print(f"  Extractions:    {stats['extractions']}")
        console.print(f"  Claim Facts:    {stats['claim_facts']}")
        console.print(f"  Labels:         {stats['labels']}")
        console.print(f"  Reconciliation: {stats['reconciliation']}")
