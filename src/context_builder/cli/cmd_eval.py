"""Eval command — evaluate a pipeline run against canonical truth."""

from pathlib import Path

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    get_active_workspace,
    setup_logging,
)
from context_builder.cli._console import console, print_ok, print_err, output_result


@app.command("eval", help="Evaluate a run against canonical truth.")
def eval_cmd(
    ctx: typer.Context,
    run_id: str = typer.Option(..., "--run-id", help="Run ID to evaluate"),
    output: str = typer.Option(
        None,
        "--output",
        help="Output root directory (default: active workspace)",
    ),
):
    """Evaluate a pipeline run and emit per-doc + summary eval outputs."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    from context_builder.pipeline.eval import evaluate_run

    if output:
        output_dir = Path(output)
    else:
        workspace = get_active_workspace()
        if not workspace or not workspace.get("path"):
            print_err("No active workspace configured and no --output specified")
            raise SystemExit(1)
        output_dir = Path(workspace["path"])

    if not output_dir.exists():
        print_err(f"Output directory not found: {output_dir}")
        raise SystemExit(1)

    summary = evaluate_run(output_dir, run_id)

    if ctx.obj["json"]:
        output_result(summary, ctx=ctx)
    elif not ctx.obj["quiet"]:
        print_ok(f"Eval complete for {run_id}")
        console.print(f"  Docs evaluated: {summary['docs_evaluated']}/{summary['docs_total']}")
        console.print(f"  Fields labeled: {summary['fields_labeled']}")
        console.print(f"  Correct:        {summary['correct']}")
        console.print(f"  Incorrect:      {summary['incorrect']}")
        console.print(f"  Missing:        {summary['missing']}")
        console.print(f"  Unverifiable:   {summary['unverifiable']}")
