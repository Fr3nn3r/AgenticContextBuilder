"""Pipeline command — full document processing pipeline."""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    get_active_workspace,
    get_workspace_claims_dir,
    parse_stages,
    setup_logging,
)
from context_builder.cli._console import console, print_ok, print_err, print_warn, output_result

logger = logging.getLogger(__name__)


@app.command("pipeline", help="Run the full document processing pipeline (discover, classify, extract).")
def pipeline_cmd(
    ctx: typer.Context,
    input_path: Optional[str] = typer.Argument(
        None,
        help="Path to claims folder (each subfolder is a claim with documents)",
    ),
    single_file: Optional[str] = typer.Option(
        None, "--file", help="Process a single document file",
    ),
    multi_files: Optional[List[str]] = typer.Option(
        None, "--files", help="Process multiple document files",
    ),
    multi_claims: Optional[List[str]] = typer.Option(
        None, "--claims", help="Process multiple claim folders",
    ),
    force_claim_id: Optional[str] = typer.Option(
        None, "--claim-id", help="Force all files into a single claim (only with --files)",
    ),
    from_workspace: bool = typer.Option(
        False, "--from-workspace",
        help="Discover documents from active workspace registry",
    ),
    claim_ids: Optional[str] = typer.Option(
        None, "--claim-ids",
        help="Comma-separated claim IDs to filter (only with --from-workspace)",
    ),
    output_dir: Optional[str] = typer.Option(
        None, "-o", "--output-dir",
        help="Output directory for structured results (default: active workspace)",
    ),
    run_id: Optional[str] = typer.Option(
        None, "--run-id", help="Override run ID",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing run folder"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without processing"),
    no_metrics: bool = typer.Option(False, "--no-metrics", help="Skip metrics computation"),
    stages: str = typer.Option(
        "ingest,classify,extract", "--stages",
        help="Comma-separated stages to run: ingest,classify,extract",
    ),
    doc_types: Optional[str] = typer.Option(
        None, "--doc-types",
        help="Comma-separated doc types to extract, or 'list' to show available types",
    ),
    exclude_claims: Optional[str] = typer.Option(
        None, "--exclude-claims",
        help="Comma-separated claim IDs to exclude",
    ),
    skip_first: int = typer.Option(0, "--skip-first", help="Skip first N claims"),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress bars"),
    parallel: int = typer.Option(
        1, "--parallel",
        help="Documents to process in parallel per claim (1-8)",
        min=1, max=8,
    ),
    no_llm_logging: bool = typer.Option(
        False, "--no-llm-logging",
        help="Disable LLM call logging to llm_calls.jsonl",
    ),
):
    """Run the full document processing pipeline."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    # Handle --no-llm-logging
    if no_llm_logging:
        os.environ["COMPLIANCE_LLM_LOGGING_ENABLED"] = "false"
        logger.info("LLM call logging disabled via --no-llm-logging")

    # Handle --doc-types list
    if doc_types and doc_types.lower() == "list":
        from context_builder.extraction.spec_loader import list_available_specs
        available = list_available_specs()
        if ctx.obj["json"]:
            output_result({"doc_types": available}, ctx=ctx)
        else:
            console.print("\n[bold]Available document types for extraction:[/bold]")
            for dt in available:
                console.print(f"  - {dt}")
            console.print(f"\nUsage: --doc-types {','.join(available[:3])}")
        raise SystemExit(0)

    # Validate input modes
    input_modes = sum([
        bool(input_path),
        bool(single_file),
        bool(multi_files),
        bool(multi_claims),
        bool(from_workspace),
    ])
    if input_modes == 0:
        print_err("No input mode specified. Provide input_path, --file, --files, --claims, or --from-workspace")
        raise SystemExit(1)
    if input_modes > 1:
        print_err("Only one input mode allowed at a time")
        raise SystemExit(1)

    if force_claim_id and not multi_files:
        print_err("--claim-id can only be used with --files")
        raise SystemExit(1)
    if claim_ids and not from_workspace:
        print_err("--claim-ids can only be used with --from-workspace")
        raise SystemExit(1)

    if from_workspace and "ingest" in stages.split(","):
        logger.warning("--from-workspace with 'ingest' stage: documents already have extracted text")

    # Resolve output directory
    if output_dir:
        out = Path(output_dir)
    else:
        out = get_workspace_claims_dir()
        workspace = get_active_workspace()
        if workspace:
            logger.info(f"Using workspace '{workspace.get('name', workspace.get('workspace_id'))}': {out}")
    if not out.exists():
        try:
            out.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print_err(f"Failed to create output directory: {e}")
            raise SystemExit(1)

    # Discover claims
    from context_builder.pipeline.discovery import (
        discover_claims,
        discover_single_file,
        discover_files,
        discover_claim_folders,
        discover_from_workspace,
    )

    try:
        if from_workspace:
            workspace = get_active_workspace()
            if not workspace or not workspace.get("path"):
                print_err("No active workspace. Set one via Admin UI or POST /api/workspaces/{id}/activate")
                raise SystemExit(1)
            workspace_dir = Path(workspace["path"])

            claim_id_filter = None
            if claim_ids:
                claim_id_filter = [c.strip() for c in claim_ids.split(",") if c.strip()]

            doc_type_filter_disc = None
            if doc_types and doc_types.lower() != "list":
                doc_type_filter_disc = [t.strip() for t in doc_types.split(",") if t.strip()]

            claims = discover_from_workspace(
                workspace_dir=workspace_dir,
                doc_type_filter=doc_type_filter_disc,
                claim_id_filter=claim_id_filter,
            )
        elif single_file:
            claims = [discover_single_file(Path(single_file))]
        elif multi_files:
            claims = discover_files(
                [Path(f) for f in multi_files],
                claim_id=force_claim_id,
            )
        elif multi_claims:
            claims = discover_claim_folders([Path(d) for d in multi_claims])
        else:
            p = Path(input_path)
            if not p.exists():
                print_err(f"Path not found: {p}")
                raise SystemExit(1)
            if not p.is_dir():
                print_err(f"Input path is not a directory: {p}")
                raise SystemExit(1)
            claims = discover_claims(p)
    except (FileNotFoundError, ValueError, NotADirectoryError) as e:
        print_err(str(e))
        raise SystemExit(1)

    if not claims:
        print_warn("No claims found in the provided input")
        raise SystemExit(1)

    # Apply exclusions
    if exclude_claims:
        excl = {c.strip() for c in exclude_claims.split(",") if c.strip()}
        original = len(claims)
        claims = [c for c in claims if c.claim_id not in excl]
        if original - len(claims) > 0:
            logger.info(f"Excluded {original - len(claims)} claim(s)")
        if not claims:
            print_warn("All claims were excluded — nothing to process")
            return

    # Apply --skip-first
    if skip_first > 0:
        if skip_first >= len(claims):
            print_warn(f"--skip-first {skip_first} skips all {len(claims)} claim(s)")
            return
        claims = claims[skip_first:]
        logger.info(f"Skipped first {skip_first} claim(s), {len(claims)} remaining")

    # Parse --doc-types
    doc_type_filter = None
    if doc_types:
        from context_builder.extraction.spec_loader import list_available_specs
        available = list_available_specs()
        doc_type_filter = [t.strip() for t in doc_types.split(",") if t.strip()]
        invalid = [t for t in doc_type_filter if t not in available]
        if invalid:
            print_err(f"Invalid doc type(s): {', '.join(invalid)}")
            console.print(f"  Available types: {', '.join(available)}")
            raise SystemExit(1)

    # Dry run
    if dry_run:
        data = {
            "mode": "dry_run",
            "claims_count": len(claims),
            "claims": [],
        }
        if doc_type_filter:
            data["doc_type_filter"] = doc_type_filter

        for claim in claims:
            claim_data = {
                "claim_id": claim.claim_id,
                "documents": [],
            }
            for doc in claim.documents:
                claim_data["documents"].append({
                    "filename": doc.original_filename,
                    "source_type": doc.source_type,
                })
            data["claims"].append(claim_data)

        if ctx.obj["json"]:
            output_result(data, ctx=ctx)
        else:
            console.print(f"\n[bold]DRY RUN[/bold] — Would process {len(claims)} claim(s):\n")
            if doc_type_filter:
                console.print(f"  Doc type filter: {', '.join(doc_type_filter)}")
                console.print(f"  (Only documents classified as these types will be extracted)\n")
            for claim in claims:
                console.print(f"  [bold]{claim.claim_id}[/bold] ({len(claim.documents)} docs)")
                for doc in claim.documents:
                    try:
                        fn = doc.original_filename.encode("ascii", errors="replace").decode("ascii")
                    except UnicodeEncodeError:
                        fn = doc.original_filename
                    console.print(f"    - {fn} ({doc.source_type})")
            console.print(f"\n  Output: {out}")
            if run_id:
                console.print(f"  Run ID: {run_id}")
        raise SystemExit(0)

    # Generate run_id
    if not run_id:
        from context_builder.extraction.base import generate_run_id
        run_id = generate_run_id()
    logger.info(f"Using run ID: {run_id}")

    # Parse stages
    from context_builder.pipeline.run import process_claim, StageConfig

    try:
        stage_list = parse_stages(stages)
    except ValueError as e:
        print_err(f"Invalid --stages argument: {e}")
        raise SystemExit(1)

    stage_config = StageConfig(stages=stage_list, doc_type_filter=doc_type_filter)
    stage_names = [s.value for s in stage_list]

    # Determine progress
    show_progress = not ctx.obj["quiet"] and not no_progress

    # Create classifier once
    from context_builder.classification import ClassifierFactory
    classifier = ClassifierFactory.create("openai")

    # Process each claim
    from context_builder.cli._progress import RichClaimProgress
    from context_builder.pipeline.paths import create_workspace_run_structure, get_claim_paths

    command_str = " ".join(sys.argv)
    total_docs = 0
    success_docs = 0
    failed_claims = []
    claim_results = []

    for i, claim in enumerate(claims, 1):
        if not show_progress:
            logger.info(f"[{i}/{len(claims)}] Processing claim: {claim.claim_id}")

        display = None
        if show_progress:
            display = RichClaimProgress(
                claim_id=claim.claim_id,
                doc_count=len(claim.documents),
                stages=stage_names,
                quiet=ctx.obj["quiet"],
                verbose=ctx.obj["verbose"],
            )
            display.start()

        current_doc_id = [None]

        def make_phase_callback(disp):
            def callback(phase, doc_id, filename):
                if disp:
                    if doc_id != current_doc_id[0]:
                        current_doc_id[0] = doc_id
                        disp.start_document(filename, doc_id)
                    disp.on_phase_start(phase)
            return callback

        def make_phase_end_callback(disp):
            def callback(phase, doc_id, filename, status):
                if disp:
                    disp.on_phase_end(phase, status)
            return callback

        def make_progress_callback(disp):
            def callback(idx, total, filename, doc_result):
                if disp:
                    disp.complete_document(
                        timings=doc_result.timings,
                        status=doc_result.status,
                        doc_type=doc_result.doc_type,
                        error=doc_result.error,
                    )
            return callback

        phase_cb = make_phase_callback(display) if show_progress else None
        phase_end_cb = make_phase_end_callback(display) if show_progress else None
        progress_cb = make_progress_callback(display) if show_progress else None

        try:
            result = process_claim(
                claim=claim,
                output_base=out,
                classifier=classifier,
                run_id=run_id,
                force=force or from_workspace,
                command=command_str,
                compute_metrics=not no_metrics,
                stage_config=stage_config,
                progress_callback=progress_cb,
                phase_callback=phase_cb,
                phase_end_callback=phase_end_cb,
                max_workers=parallel,
            )

            total_docs += len(result.documents)
            success_docs += sum(1 for d in result.documents if d.status == "success")
            claim_results.append(result)

            if result.status in ("success", "partial"):
                logger.info(f"Claim {claim.claim_id}: {result.status}")
            else:
                logger.warning(f"Claim {claim.claim_id}: {result.status}")
                failed_claims.append(claim.claim_id)
        except Exception as e:
            logger.error(f"Failed to process claim {claim.claim_id}: {e}")
            failed_claims.append(claim.claim_id)
        finally:
            if display:
                display.finish()

    # Create global run
    if claim_results:
        workspace_paths = create_workspace_run_structure(out, run_id)

        global_manifest = {
            "run_id": run_id,
            "started_at": datetime.now().isoformat() + "Z",
            "ended_at": datetime.now().isoformat() + "Z",
            "command": command_str,
            "claims_count": len(claims),
            "claims": [
                {
                    "claim_id": r.claim_id,
                    "status": r.status,
                    "docs_count": len(r.documents),
                    "claim_run_path": str(out / r.claim_id / "runs" / run_id),
                }
                for r in claim_results
            ],
        }

        with open(workspace_paths.manifest_json, "w", encoding="utf-8") as f:
            json.dump(global_manifest, f, indent=2, ensure_ascii=False)

        global_summary = {
            "run_id": run_id,
            "status": "success" if not failed_claims else ("partial" if success_docs > 0 else "failed"),
            "claims_discovered": len(claims),
            "claims_processed": len(claim_results),
            "claims_failed": len(failed_claims),
            "docs_total": total_docs,
            "docs_success": success_docs,
            "completed_at": datetime.now().isoformat() + "Z",
        }

        with open(workspace_paths.summary_json, "w", encoding="utf-8") as f:
            json.dump(global_summary, f, indent=2, ensure_ascii=False)

        if not no_metrics:
            aggregated_metrics = {
                "run_id": run_id,
                "claims_count": len(claim_results),
                "docs_total": total_docs,
                "docs_success": success_docs,
                "per_claim": [],
            }
            for r in claim_results:
                cp = get_claim_paths(out, r.claim_id)
                metrics_path = cp.runs_dir / run_id / "logs" / "metrics.json"
                if metrics_path.exists():
                    with open(metrics_path, "r", encoding="utf-8") as f:
                        claim_metrics = json.load(f)
                        aggregated_metrics["per_claim"].append({
                            "claim_id": r.claim_id,
                            "metrics": claim_metrics,
                        })

            with open(workspace_paths.metrics_json, "w", encoding="utf-8") as f:
                json.dump(aggregated_metrics, f, indent=2, ensure_ascii=False)

        workspace_paths.complete_marker.touch()

    # Summary
    summary_data = {
        "run_id": run_id,
        "claims_processed": len(claims),
        "docs_success": success_docs,
        "docs_total": total_docs,
        "failed_claims": failed_claims,
        "output": str(out),
    }

    if ctx.obj["json"]:
        output_result(summary_data, ctx=ctx)
    elif not ctx.obj["quiet"]:
        console.rule("Pipeline Complete")
        console.print(f"  Claims processed: {len(claims)}")
        console.print(f"  Documents: {success_docs}/{total_docs} successful")
        if failed_claims:
            console.print(f"  [red]Failed claims:[/red] {', '.join(failed_claims)}")
        console.print(f"  Output: {out}")

    # Auto-build indexes
    if success_docs > 0:
        from context_builder.storage.index_builder import build_all_indexes
        try:
            stats = build_all_indexes(out.parent)
            if not ctx.obj["quiet"] and not ctx.obj["json"]:
                console.print(f"  Indexes updated: {stats['doc_count']} docs, {stats['run_count']} runs")
        except Exception as e:
            logger.warning(f"Index build failed (non-fatal): {e}")
