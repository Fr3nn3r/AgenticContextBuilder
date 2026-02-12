"""Assess command — full claim assessment (reconciliation + assessment)."""

import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    resolve_workspace_root,
    setup_logging,
)
from context_builder.cli._console import console, print_err, print_warn, output_result
from context_builder.cli._progress import create_progress_reporter

logger = logging.getLogger(__name__)


@app.command("assess", help="Run full claim assessment (reconciliation + assessment).")
def assess_cmd(
    ctx: typer.Context,
    claim_id: Optional[List[str]] = typer.Option(
        None, "--claim-id", help="One or more claim IDs to assess",
    ),
    all_claims: bool = typer.Option(False, "--all", help="Assess all claims in workspace"),
    input_folder: Optional[str] = typer.Option(
        None, "--input-folder",
        help="Folder containing claim subfolders to assess",
    ),
    force_reconcile: bool = typer.Option(
        False, "--force-reconcile",
        help="Force re-reconciliation even if recent reconciliation exists",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview assessment without running LLM calls"),
    exclude_claims: Optional[str] = typer.Option(
        None, "--exclude-claims",
        help="Comma-separated claim IDs to exclude",
    ),
    skip_first: int = typer.Option(0, "--skip-first", help="Skip first N claims"),
    logs: bool = typer.Option(False, "--logs", help="Show detailed logs instead of progress bars"),
    no_llm_logging: bool = typer.Option(
        False, "--no-llm-logging",
        help="Disable LLM call logging to llm_calls.jsonl",
    ),
    parallel: int = typer.Option(
        1, "--parallel",
        help="Process N claims in parallel (1-8, default: 1 = sequential)",
        min=1, max=8,
    ),
):
    """Run the complete claim processing pipeline: reconciliation + assessment."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    # Handle --no-llm-logging
    if no_llm_logging:
        os.environ["COMPLIANCE_LLM_LOGGING_ENABLED"] = "false"
        logger.info("LLM call logging disabled via --no-llm-logging")

    # Validate args
    options_count = sum([bool(claim_id), all_claims, bool(input_folder)])
    if options_count == 0:
        print_err("One of --claim-id, --all, or --input-folder is required")
        raise SystemExit(1)
    if options_count > 1:
        print_err("Cannot combine --claim-id, --all, and --input-folder")
        raise SystemExit(1)

    from context_builder.api.services.claim_assessment import ClaimAssessmentService
    from context_builder.api.services.aggregation import AggregationService
    from context_builder.api.services.reconciliation import ReconciliationService
    from context_builder.pipeline.helpers.metadata import get_git_info, compute_workspace_config_hash
    from context_builder.pipeline.paths import create_workspace_claim_run_structure
    from context_builder.storage.claim_run import generate_claim_run_id, ClaimRunContext
    from context_builder.storage.filesystem import FileStorage

    workspace_root = resolve_workspace_root(quiet=ctx.obj["quiet"])
    storage = FileStorage(workspace_root)
    aggregation = AggregationService(storage)
    reconciliation = ReconciliationService(storage, aggregation)
    assessment_service = ClaimAssessmentService(storage, reconciliation)

    # Create progress reporter
    progress = create_progress_reporter(
        verbose=ctx.obj["verbose"],
        quiet=ctx.obj["quiet"],
        logs=logs,
        parallel=parallel,
    )

    # Only set logging level manually if using logs mode
    if logs:
        if ctx.obj["verbose"]:
            logging.getLogger().setLevel(logging.DEBUG)
        elif ctx.obj["quiet"]:
            logging.getLogger().setLevel(logging.WARNING)

    # Determine which claims to process
    if all_claims:
        claims_dir = workspace_root / "claims"
        if not claims_dir.exists():
            print_err(f"No claims directory found at {claims_dir}")
            raise SystemExit(1)
        claim_ids_list = sorted([
            folder.name for folder in claims_dir.iterdir()
            if folder.is_dir() and not folder.name.startswith(".")
        ])
        if not claim_ids_list:
            print_err("No claims found in workspace")
            raise SystemExit(1)
        if not ctx.obj["quiet"]:
            console.print(f"\nFound {len(claim_ids_list)} claims to assess")
    elif input_folder:
        p = Path(input_folder)
        if not p.exists():
            print_err(f"Input folder not found: {input_folder}")
            raise SystemExit(1)
        if not p.is_dir():
            print_err(f"Input path is not a directory: {input_folder}")
            raise SystemExit(1)
        claim_ids_list = sorted([
            folder.name for folder in p.iterdir()
            if folder.is_dir() and not folder.name.startswith(".")
        ])
        if not claim_ids_list:
            print_err(f"No claim folders found in {input_folder}")
            raise SystemExit(1)
        if not ctx.obj["quiet"]:
            console.print(f"\nFound {len(claim_ids_list)} claims from input folder")
    else:
        # Support both --claim-id A --claim-id B and --claim-id A,B,C
        claim_ids_list = [
            cid.strip()
            for raw in claim_id
            for cid in raw.split(",")
            if cid.strip()
        ]

    # Apply exclusions
    if exclude_claims:
        excl = {c.strip() for c in exclude_claims.split(",") if c.strip()}
        original = len(claim_ids_list)
        claim_ids_list = [cid for cid in claim_ids_list if cid not in excl]
        if original - len(claim_ids_list) > 0:
            logger.info(f"Excluded {original - len(claim_ids_list)} claim(s)")
        if not claim_ids_list:
            print_warn("All claims were excluded — nothing to assess")
            return

    # Apply --skip-first
    if skip_first > 0:
        if skip_first >= len(claim_ids_list):
            print_warn(f"--skip-first {skip_first} skips all {len(claim_ids_list)} claim(s)")
            return
        claim_ids_list = claim_ids_list[skip_first:]
        logger.info(f"Skipped first {skip_first} claim(s), {len(claim_ids_list)} remaining")

    # Generate shared claim run ID
    shared_id = generate_claim_run_id()
    run_start = datetime.now(timezone.utc).isoformat()
    run_context = ClaimRunContext(
        claim_run_id=shared_id,
        started_at=run_start,
        hostname=os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown")),
        python_version=sys.version.split()[0],
        git=get_git_info(),
        workspace_config_hash=compute_workspace_config_hash(),
        command=" ".join(sys.argv),
    )

    if not ctx.obj["quiet"] and not dry_run:
        progress.write(f"Claim run ID: {shared_id}")

    # Thread-safe results
    results_lock = threading.Lock()
    results = {"success": [], "failed": []}

    def assess_single_claim(cid: str):
        """Process a single claim. Creates per-thread services for isolation."""
        try:
            if parallel > 1:
                thread_storage = FileStorage(workspace_root)
                thread_agg = AggregationService(thread_storage)
                thread_recon = ReconciliationService(thread_storage, thread_agg)
                thread_assess = ClaimAssessmentService(thread_storage, thread_recon)
            else:
                thread_assess = assessment_service

            def on_stage_update(stage_name, status, _cid=cid):
                progress.start_stage(_cid, stage_name)

            def on_llm_start(total):
                progress.start_detail(total, desc="LLM calls", unit="call")

            def on_llm_progress(n):
                progress.update_detail(n)

            result = thread_assess.assess(
                claim_id=cid,
                force_reconcile=force_reconcile,
                on_stage_update=on_stage_update,
                on_llm_start=on_llm_start,
                on_llm_progress=on_llm_progress,
                run_context=run_context,
            )

            if result.success:
                progress.complete_claim(
                    claim_id=cid,
                    decision=result.decision,
                    confidence=result.confidence_score,
                    payout=result.final_payout,
                    gate=result.gate_status,
                    confidence_band=result.confidence_band,
                )
                return (cid, True, result.decision)
            else:
                progress.complete_claim(
                    claim_id=cid,
                    decision="FAILED",
                    error=result.error,
                )
                return (cid, False, result.error)
        except Exception as e:
            progress.complete_claim(claim_id=cid, decision="FAILED", error=str(e))
            return (cid, False, str(e))

    # Start progress
    if not dry_run:
        progress.start_claims(claim_ids_list)

    # Execute
    if dry_run:
        dry_data = []
        for cid in claim_ids_list:
            dry_data.append({"claim_id": cid, "run_id": shared_id})
        if ctx.obj["json"]:
            output_result({"mode": "dry_run", "claims": dry_data}, ctx=ctx)
        else:
            for cid in claim_ids_list:
                console.print(f"[dim]DRY RUN[/dim] Would assess claim: {cid} (run: {shared_id})")
    elif parallel == 1:
        for cid in claim_ids_list:
            c, success, _ = assess_single_claim(cid)
            with results_lock:
                results["success" if success else "failed"].append(c)
    else:
        progress.write(f"Processing {len(claim_ids_list)} claims with {parallel} workers")
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {executor.submit(assess_single_claim, cid): cid for cid in claim_ids_list}
            for future in as_completed(futures):
                c, success, _ = future.result()
                with results_lock:
                    results["success" if success else "failed"].append(c)

    progress.finish()

    # Create workspace-level claim run
    if not dry_run:
        from context_builder.pipeline.helpers.io import write_json_atomic

        run_end = datetime.now(timezone.utc).isoformat()
        ws_paths = create_workspace_claim_run_structure(workspace_root, shared_id)

        ws_manifest = {
            "claim_run_id": shared_id,
            "started_at": run_start,
            "ended_at": run_end,
            "command": " ".join(sys.argv),
            "hostname": run_context.hostname,
            "python_version": run_context.python_version,
            "git": run_context.git,
            "workspace_config_hash": run_context.workspace_config_hash,
            "claims_assessed": list(claim_ids_list),
            "claims_succeeded": results["success"],
            "claims_failed": results["failed"],
        }
        write_json_atomic(ws_paths.manifest_json, ws_manifest)

        decision_counts = {}
        for cid in results["success"]:
            claim_folder = storage._find_claim_folder(cid)
            if claim_folder:
                from context_builder.storage.claim_run import ClaimRunStorage
                crs = ClaimRunStorage(claim_folder)
                assessment_data = crs.read_from_claim_run(shared_id, "assessment.json")
                if assessment_data:
                    dec = assessment_data.get("recommendation", "UNKNOWN")
                    decision_counts[dec] = decision_counts.get(dec, 0) + 1

        ws_summary = {
            "claim_run_id": shared_id,
            "total_claims": len(claim_ids_list),
            "succeeded": len(results["success"]),
            "failed": len(results["failed"]),
            "decision_distribution": decision_counts,
        }
        write_json_atomic(ws_paths.summary_json, ws_summary)

        ws_paths.complete_marker.touch()

    # Print summary
    if ctx.obj["json"] and not dry_run:
        output_result({
            "claim_run_id": shared_id,
            "total_claims": len(claim_ids_list),
            "succeeded": len(results["success"]),
            "failed": len(results["failed"]),
        }, ctx=ctx)
    elif len(claim_ids_list) > 1 and not ctx.obj["quiet"] and not dry_run:
        console.rule("ASSESSMENT SUMMARY")
        console.print(f"  Claim Run: {shared_id}")
        console.print(f"  Successful: {len(results['success'])}")
        console.print(f"  Failed: {len(results['failed'])}")
        if results["failed"]:
            for cid in results["failed"]:
                console.print(f"    - {cid}")
        console.print(f"  Workspace run: {ws_paths.run_root}")
