"""Reconcile commands — fact reconciliation and evaluation summary."""

import sys

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    resolve_workspace_root,
    setup_logging,
)
from context_builder.cli._console import console, print_ok, print_err, output_result

reconcile_app = typer.Typer(
    no_args_is_help=True,
    help="Reconcile facts for claims: aggregate, detect conflicts, evaluate quality gate.",
    invoke_without_command=True,
)
app.add_typer(reconcile_app, name="reconcile")


@reconcile_app.callback(invoke_without_command=True)
def reconcile_default(
    ctx: typer.Context,
    claim_id: str = typer.Option(None, "--claim-id", help="Claim ID to reconcile"),
    all_claims: bool = typer.Option(False, "--all", help="Reconcile all claims in workspace"),
    run_id: str = typer.Option(None, "--run-id", help="Specific extraction run ID to use"),
    policy: str = typer.Option(
        "latest-run",
        "--policy",
        help="Reconciliation policy: latest-run (default) or best-per-doc",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show output without writing to files"),
):
    """Reconcile facts for a claim or all claims."""
    # If a subcommand is invoked, skip
    if ctx.invoked_subcommand is not None:
        return

    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    if not claim_id and not all_claims:
        print_err("Either --claim-id or --all is required")
        raise SystemExit(1)
    if claim_id and all_claims:
        print_err("Cannot use both --claim-id and --all")
        raise SystemExit(1)

    if policy == "best-per-doc":
        print_err("--policy=best-per-doc is not yet implemented.")
        console.print("  This feature will aggregate across all extraction runs.")
        console.print("  See BACKLOG.md for implementation status.")
        console.print("  For now, use --policy=latest-run (default) with --run-id.")
        raise SystemExit(1)

    from context_builder.api.services.aggregation import AggregationService
    from context_builder.api.services.reconciliation import (
        ReconciliationError,
        ReconciliationService,
    )
    from context_builder.storage.filesystem import FileStorage

    workspace_root = resolve_workspace_root(quiet=ctx.obj["quiet"])
    storage = FileStorage(workspace_root)
    aggregation = AggregationService(storage)
    reconciliation = ReconciliationService(storage, aggregation)

    if all_claims:
        claims_dir = workspace_root / "claims"
        if not claims_dir.exists():
            print_err(f"No claims directory found at {claims_dir}")
            raise SystemExit(1)
        claim_ids = sorted([
            folder.name for folder in claims_dir.iterdir()
            if folder.is_dir() and not folder.name.startswith(".")
        ])
        if not claim_ids:
            print_err("No claims found in workspace")
            raise SystemExit(1)
        if not ctx.obj["quiet"]:
            console.print(f"\nFound {len(claim_ids)} claims to reconcile")
    else:
        claim_ids = [claim_id]

    results_summary = {"pass": [], "warn": [], "fail": [], "error": []}
    json_results = []

    for cid in claim_ids:
        try:
            result = reconciliation.reconcile(claim_id=cid)

            if not result.success:
                results_summary["error"].append(cid)
                if ctx.obj["json"]:
                    json_results.append({"claim_id": cid, "error": result.error})
                elif not ctx.obj["quiet"]:
                    print_err(f"{cid}: Failed — {result.error}")
                continue

            report = result.report
            gate_status = report.gate.status.value
            results_summary[gate_status].append(cid)

            if ctx.obj["json"]:
                json_results.append(report.model_dump(mode="json"))
            elif dry_run:
                console.print(f"\n--- {cid} ---")
                console.print(report.model_dump_json(indent=2))
            elif not ctx.obj["quiet"]:
                gate = report.gate
                status_style = {
                    "pass": "[green]PASS[/green]",
                    "warn": "[yellow]WARN[/yellow]",
                    "fail": "[red]FAIL[/red]",
                }.get(gate.status.value, gate.status.value)

                console.print(
                    f"\n[green]✓[/green] {cid}: {status_style} "
                    f"({report.fact_count} facts, {gate.conflict_count} conflicts)"
                )
                if gate.missing_critical_facts:
                    console.print(f"  Missing: {', '.join(gate.missing_critical_facts[:3])}")

        except ReconciliationError as e:
            results_summary["error"].append(cid)
            if ctx.obj["json"]:
                json_results.append({"claim_id": cid, "error": str(e)})
            elif not ctx.obj["quiet"]:
                print_err(f"{cid}: Error — {e}")

    if ctx.obj["json"]:
        output_result({"results": json_results, "summary": results_summary}, ctx=ctx)
    elif all_claims and not ctx.obj["quiet"] and not dry_run:
        console.rule("RECONCILIATION SUMMARY")
        total = len(claim_ids)
        console.print(f"  Total claims: {total}")
        console.print(f"  [green]PASS[/green]:  {len(results_summary['pass'])}")
        console.print(f"  [yellow]WARN[/yellow]:  {len(results_summary['warn'])}")
        console.print(f"  [red]FAIL[/red]:  {len(results_summary['fail'])}")
        if results_summary["error"]:
            console.print(f"  [red]ERROR[/red]: {len(results_summary['error'])}")
            for cid in results_summary["error"]:
                console.print(f"         - {cid}")


@reconcile_app.command("summary", help="Aggregate reconciliation reports into a run-level evaluation.")
def reconcile_summary(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show evaluation output without writing to files"),
    top_n: int = typer.Option(10, "--top-n", help="Number of top missing facts and conflicts to include"),
):
    """Aggregate all reconciliation reports and produce a summary evaluation."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    from context_builder.api.services.aggregation import AggregationService
    from context_builder.api.services.reconciliation import (
        ReconciliationError,
        ReconciliationService,
    )
    from context_builder.storage.filesystem import FileStorage

    workspace_root = resolve_workspace_root(quiet=ctx.obj["quiet"])
    storage = FileStorage(workspace_root)
    aggregation = AggregationService(storage)
    reconciliation = ReconciliationService(storage, aggregation)

    try:
        evaluation = reconciliation.aggregate_run_evaluation(top_n=top_n)

        if evaluation.summary.total_claims == 0:
            console.print("[yellow]![/yellow] No reconciliation reports found in workspace")
            console.print("  Run 'reconcile --claim-id <id>' for each claim first")
            return

        if ctx.obj["json"]:
            output_result(evaluation.model_dump(mode="json"), ctx=ctx)
        elif dry_run:
            console.print(evaluation.model_dump_json(indent=2))
        else:
            output_path = reconciliation.write_run_evaluation(evaluation)

            if not ctx.obj["quiet"]:
                summary = evaluation.summary
                print_ok("Reconciliation evaluation complete")
                console.print(f"  Claims evaluated: {summary.total_claims}")
                console.print(f"  Pass: {summary.passed} ({summary.pass_rate_percent})")
                console.print(f"  Warn: {summary.warned}")
                console.print(f"  Fail: {summary.failed}")
                console.print(f"  Avg facts: {summary.avg_fact_count:.1f}")
                console.print(f"  Avg conflicts: {summary.avg_conflicts:.1f}")
                console.print(f"  Total conflicts: {summary.total_conflicts}")
                if evaluation.top_missing_facts:
                    console.print("  Top missing facts:")
                    for f in evaluation.top_missing_facts[:3]:
                        console.print(f"    - {f.fact_name}: {f.count} claims")
                if evaluation.top_conflicts:
                    console.print("  Top conflicts:")
                    for c in evaluation.top_conflicts[:3]:
                        console.print(f"    - {c.fact_name}: {c.count} claims")
                console.print(f"  Output: {output_path}")

    except ReconciliationError as e:
        print_err(f"Reconciliation evaluation failed: {e}")
        raise SystemExit(1)
