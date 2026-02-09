"""Coverage command — analyze line item coverage against policy."""

import sys

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    resolve_workspace_root,
    setup_logging,
)
from context_builder.cli._console import console, print_ok, print_err, output_result


@app.command("coverage", help="Analyze line item coverage against policy.")
def coverage_cmd(
    ctx: typer.Context,
    claim_id: str = typer.Option(None, "--claim-id", help="Claim ID to analyze"),
    all_claims: bool = typer.Option(False, "--all", help="Analyze all claims in workspace"),
    force: bool = typer.Option(False, "--force", help="Rerun analysis even if results exist"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print analysis output without writing to file"),
):
    """Run coverage analysis for one or all claims."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    if not claim_id and not all_claims:
        print_err("Either --claim-id or --all is required")
        raise SystemExit(1)
    if claim_id and all_claims:
        print_err("Cannot use both --claim-id and --all")
        raise SystemExit(1)

    from context_builder.api.services.coverage_analysis import (
        CoverageAnalysisError,
        CoverageAnalysisService,
    )
    from context_builder.storage.filesystem import FileStorage

    workspace_root = resolve_workspace_root(quiet=ctx.obj["quiet"])
    storage = FileStorage(workspace_root)
    coverage_service = CoverageAnalysisService(storage)

    if all_claims:
        claim_ids = coverage_service.list_claims_for_analysis()
        if not claim_ids:
            print_err("No claims with claim_facts.json found in workspace")
            raise SystemExit(1)
        if not ctx.obj["quiet"]:
            console.print(f"\nFound {len(claim_ids)} claims to analyze")
    else:
        claim_ids = [claim_id]

    results = {"success": [], "failed": []}
    json_results = []

    for cid in claim_ids:
        try:
            if dry_run:
                result = coverage_service.analyze_claim(claim_id=cid, force=True)
                if ctx.obj["json"]:
                    json_results.append(result.model_dump(mode="json"))
                else:
                    console.print(f"\n--- {cid} (DRY RUN) ---")
                    console.print(result.model_dump_json(indent=2))
                results["success"].append(cid)
                continue

            result = coverage_service.analyze_claim(claim_id=cid, force=force)
            results["success"].append(cid)

            if ctx.obj["json"]:
                json_results.append(result.model_dump(mode="json"))
            elif not ctx.obj["quiet"]:
                summary = result.summary
                print_ok(f"{cid}: Coverage analysis complete")
                console.print(f"  [green]Covered:[/green] {summary.items_covered} items (CHF {summary.total_covered_before_excess:,.2f})")
                console.print(f"  [red]Not Covered:[/red] {summary.items_not_covered} items (CHF {summary.total_not_covered:,.2f})")
                if summary.items_review_needed > 0:
                    console.print(f"  [yellow]Review Needed:[/yellow] {summary.items_review_needed} items")
                if summary.coverage_percent is not None:
                    console.print(f"  Coverage %: {summary.coverage_percent}%")
                console.print(f"  Covered (net): CHF {summary.total_covered_before_excess:,.2f}")
                console.print(f"  Claim Run: {result.claim_run_id}")

        except CoverageAnalysisError as e:
            results["failed"].append(cid)
            if ctx.obj["json"]:
                json_results.append({"claim_id": cid, "error": str(e)})
            elif not ctx.obj["quiet"]:
                print_err(f"{cid}: {e}")

    if ctx.obj["json"]:
        if len(json_results) == 1 and not all_claims:
            output_result(json_results[0], ctx=ctx)
        else:
            output_result({"results": json_results, "summary": results}, ctx=ctx)
    elif all_claims and not ctx.obj["quiet"] and not dry_run:
        console.rule("COVERAGE ANALYSIS SUMMARY")
        console.print(f"  Successful: {len(results['success'])}")
        console.print(f"  Failed: {len(results['failed'])}")
        if results["failed"]:
            for cid in results["failed"]:
                console.print(f"    - {cid}")
