"""Index command — build registry indexes."""

import sys
from pathlib import Path

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    resolve_workspace_root,
    setup_logging,
)
from context_builder.cli._console import console, print_ok, print_err, output_result


@app.command("index", help="Build registry indexes for fast lookups.")
def index_cmd(
    ctx: typer.Context,
    root: str = typer.Option(
        None,
        "--root",
        help="Output root directory (default: active workspace)",
    ),
):
    """Build JSONL indexes (doc, label, run, claim) from workspace filesystem."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    from context_builder.storage.index_builder import build_all_indexes

    if root:
        output_dir = Path(root)
    else:
        output_dir = resolve_workspace_root(quiet=ctx.obj["quiet"])

    if not output_dir.exists():
        print_err(f"Output directory not found: {output_dir}")
        raise SystemExit(1)

    try:
        stats = build_all_indexes(output_dir)
    except Exception as e:
        print_err(f"Index build failed: {e}")
        raise SystemExit(1)

    if ctx.obj["json"]:
        output_result(stats, ctx=ctx)
    elif not ctx.obj["quiet"]:
        print_ok("Index build complete")
        console.print(f"  Documents: {stats['doc_count']}")
        console.print(f"  Labels:    {stats['label_count']}")
        console.print(f"  Runs:      {stats['run_count']}")
        console.print(f"  Claims:    {stats['claim_count']}")
        console.print(f"  Registry:  {output_dir}/registry/")
