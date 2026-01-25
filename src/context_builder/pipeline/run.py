"""Run module: orchestrate ingestion, classification, and extraction pipeline."""

# Initialize environment and workspace on import
from context_builder.startup import ensure_initialized as _ensure_initialized
_ensure_initialized()

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from context_builder.pipeline.discovery import DiscoveredClaim, DiscoveredDocument
from context_builder.pipeline.paths import (
    ClaimPaths,
    DocPaths,
    RunPaths,
    create_doc_structure,
    get_claim_paths,
    get_run_paths,
)
from context_builder.pipeline.stages import (
    ClassificationStage,
    ClaimResult,
    DocResult,
    DocumentContext,
    ExtractionStage,
    IngestionResult,
    IngestionStage,
    PhaseTimings,
    PipelineProviders,
    PipelineRunner,
    StageConfig,
)
from context_builder.pipeline.helpers.io import (
    get_workspace_logs_dir,
    write_json,
    write_json_atomic,
)
from context_builder.pipeline.helpers.metadata import (
    compute_phase_aggregates,
    mark_run_complete,
    write_manifest,
)
from context_builder.pipeline.state import is_claim_processed
from context_builder.pipeline.writer import ResultWriter
from context_builder.schemas.run_errors import DocStatus, PipelineStage, RunErrorCode, TextSource
from context_builder.storage.version_bundles import VersionBundleStore, get_version_bundle_store

logger = logging.getLogger(__name__)

# Placeholder for tests that patch this symbol without importing extraction at module load.
ExtractorFactory = None
# Placeholder for tests that patch ingestion factory without importing at module load.
IngestionFactory = None


def _setup_run_logging(run_paths: RunPaths, run_id: str) -> logging.Handler:
    """Set up file logging for this run."""
    run_paths.logs_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(run_paths.run_log, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    ))
    handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(handler)
    return handler


def process_document(
    doc: DiscoveredDocument,
    claim_id: str,
    doc_paths: DocPaths,
    run_paths: RunPaths,
    classifier: Any,
    run_id: str,
    stage_config: Optional[StageConfig] = None,
    writer: Optional[ResultWriter] = None,
    providers: Optional[PipelineProviders] = None,
    phase_callback: Optional[Callable[[str, str, str], None]] = None,
    phase_end_callback: Optional[Callable[[str, str, str, str], None]] = None,
    version_bundle_id: Optional[str] = None,
    audit_storage_dir: Optional[Path] = None,
    pii_vault: Optional[Any] = None,
) -> DocResult:
    """
    Process a single document through selected pipeline stages.

    Stages:
    - INGEST: Copy source, extract text, write pages.json
    - CLASSIFY: Classify document type, write context and doc.json
    - EXTRACT: Run field extraction if doc_type supported

    When stages are skipped, existing outputs are loaded from disk.

    Args:
        doc: Discovered document
        claim_id: Parent claim identifier
        doc_paths: Paths for this document
        run_paths: Run-scoped output paths
        classifier: Document classifier instance
        run_id: Current run identifier
        stage_config: Configuration for which stages to run (default: all)
        phase_callback: Optional callback(phase_name, doc_id, filename) for phase start
        phase_end_callback: Optional callback(phase_name, doc_id, filename, status) for phase end
        version_bundle_id: Optional version bundle ID for compliance traceability
        audit_storage_dir: Optional workspace-scoped compliance logs directory
        pii_vault: Optional PII vault for tokenizing extraction results

    Returns:
        DocResult with processing status and paths
    """
    # Default to full pipeline if no config provided
    if stage_config is None:
        stage_config = StageConfig()

    writer = writer or ResultWriter()

    context = DocumentContext(
        doc=doc,
        claim_id=claim_id,
        doc_paths=doc_paths,
        run_paths=run_paths,
        classifier=classifier,
        ingestion_factory=providers.ingestion_factory if providers else None,
        extractor_factory=providers.extractor_factory if providers else None,
        run_id=run_id,
        stage_config=stage_config,
        writer=writer,
        version_bundle_id=version_bundle_id,
        audit_storage_dir=audit_storage_dir,
        pii_vault=pii_vault,
    )

    # Create phase callback wrapper that passes doc_id
    def on_phase_start(stage_name: str, ctx: DocumentContext) -> None:
        if phase_callback:
            phase_callback(stage_name, doc.doc_id, doc.original_filename)

    # Create phase end callback wrapper that passes doc_id and status
    def on_phase_end(stage_name: str, ctx: DocumentContext, status: str) -> None:
        if phase_end_callback:
            phase_end_callback(stage_name, doc.doc_id, doc.original_filename, status)

    runner = PipelineRunner(
        [
            IngestionStage(writer),
            ClassificationStage(writer),
            ExtractionStage(writer),
        ],
        on_phase_start=on_phase_start,
        on_phase_end=on_phase_end,
    )

    try:
        context = runner.run(context)
        if context.timings.total_ms == 0:
            context.timings.total_ms = int((time.time() - context.start_time) * 1000)
        return context.to_doc_result()
    except Exception as e:
        elapsed_ms = int((time.time() - context.start_time) * 1000)
        context.timings.total_ms = elapsed_ms
        # Log clean error message (stack trace only at DEBUG level)
        error_msg = str(e)
        logger.error(
            f"Failed to process {doc.original_filename} in {context.current_phase} phase: {error_msg}"
        )
        logger.debug(f"Full traceback for {doc.original_filename}:", exc_info=True)
        return DocResult(
            doc_id=doc.doc_id,
            original_filename=doc.original_filename,
            status="error",
            source_type=doc.source_type,
            error=str(e),
            time_ms=elapsed_ms,
            timings=context.timings,
            failed_phase=context.current_phase,
            ingestion_reused=context.ingestion_reused,
            classification_reused=context.classification_reused,
        )


def process_claim(
    claim: DiscoveredClaim,
    output_base: Path,
    classifier: Any = None,
    run_id: Optional[str] = None,
    force: bool = False,
    command: str = "",
    compute_metrics: bool = True,
    stage_config: Optional[StageConfig] = None,
    progress_callback: Optional[Callable[[int, int, str, "DocResult"], None]] = None,
    phase_callback: Optional[Callable[[str, str, str], None]] = None,
    phase_end_callback: Optional[Callable[[str, str, str, str], None]] = None,
    providers: Optional[PipelineProviders] = None,
    pii_vault_enabled: bool = False,
) -> ClaimResult:
    """
    Process all documents in a claim through selected pipeline stages.

    Args:
        claim: Discovered claim with documents
        output_base: Base output directory
        classifier: Document classifier (created if None)
        run_id: Run identifier (generated if None)
        force: If True, reprocess even if already done
        command: CLI command string for manifest
        compute_metrics: If True, compute metrics.json at end
        stage_config: Configuration for which stages to run (default: all)
        progress_callback: Optional callback(idx, total, filename, doc_result) for progress reporting
        phase_callback: Optional callback(phase_name, doc_id, filename) for phase start
        phase_end_callback: Optional callback(phase_name, doc_id, filename, status) for phase end
        providers: Optional pipeline providers
        pii_vault_enabled: If True, tokenize PII in extraction results

    Returns:
        ClaimResult with aggregated stats
    """
    start_time = time.time()
    writer = ResultWriter()
    if run_id is None:
        from context_builder.extraction.base import generate_run_id
        run_id = generate_run_id()

    # Create run paths early to check existence
    claim_paths = get_claim_paths(output_base, claim.claim_id)
    run_paths = get_run_paths(claim_paths, run_id)

    # Check if run already exists (unless force)
    if run_paths.run_root.exists() and not force:
        raise ValueError(
            f"Run {run_id} already exists at {run_paths.run_root}. "
            "Use --force to overwrite."
        )

    # Check if already processed (different from run exists)
    if not force and is_claim_processed(output_base, claim.claim_id):
        logger.info(f"Skipping already processed claim: {claim.claim_id}")
        return ClaimResult(
            claim_id=claim.claim_id,
            status="skipped",
            run_id=run_id,
            stats={"total": len(claim.documents), "skipped": len(claim.documents)},
        )

    # Create logs directory and set up file logging
    run_paths.logs_dir.mkdir(parents=True, exist_ok=True)
    log_handler = _setup_run_logging(run_paths, run_id)

    try:
        logger.info(f"Starting run {run_id} for claim {claim.claim_id}")

        # Create version bundle for reproducibility (compliance requirement)
        # Use workspace root (parent of claims dir) so bundles are at {workspace}/version_bundles/
        workspace_root = output_base.parent
        version_bundle_store = get_version_bundle_store(workspace_root)
        version_bundle = version_bundle_store.create_version_bundle(
            run_id=run_id,
            extractor_version="v1.0.0",
        )
        logger.info(f"Created version bundle {version_bundle.bundle_id} for run {run_id}")

        # Write manifest at start
        manifest = write_manifest(
            run_paths=run_paths,
            run_id=run_id,
            claim_id=claim.claim_id,
            command=command,
            doc_count=len(claim.documents),
            stage_config=stage_config,
            writer=writer,
            version_bundle_id=version_bundle.bundle_id,
        )

        # Create classifier if not provided
        if classifier is None and providers and providers.classifier is not None:
            classifier = providers.classifier
        if classifier is None and providers and providers.classifier_factory is not None:
            classifier = providers.classifier_factory.create("openai")
        if classifier is None:
            from context_builder.classification import ClassifierFactory
            # Use workspace-aware audit storage for compliance logging
            audit_dir = get_workspace_logs_dir(output_base)
            classifier = ClassifierFactory.create("openai", audit_storage_dir=audit_dir)

        # Create PII vault if enabled
        pii_vault = None
        if pii_vault_enabled:
            from context_builder.services.compliance.pii import EncryptedPIIVaultStorage
            pii_vault_dir = get_workspace_logs_dir(output_base)
            pii_vault = EncryptedPIIVaultStorage(
                storage_dir=pii_vault_dir,
                claim_id=claim.claim_id,
                create_if_missing=True,
            )
            logger.info(f"Created PII vault {pii_vault.vault_id} for claim {claim.claim_id}")

        # Process each document
        results: List[DocResult] = []
        for idx, doc in enumerate(claim.documents):
            logger.info(f"Processing document: {doc.original_filename}")

            # Create document structure
            doc_paths, _, _ = create_doc_structure(
                output_base, claim.claim_id, doc.doc_id, run_id
            )

            # Compute audit dir for workspace-aware compliance logging
            audit_dir = get_workspace_logs_dir(output_base)

            result = process_document(
                doc=doc,
                claim_id=claim.claim_id,
                doc_paths=doc_paths,
                run_paths=run_paths,
                classifier=classifier,
                run_id=run_id,
                stage_config=stage_config,
                writer=writer,
                providers=providers,
                phase_callback=phase_callback,
                phase_end_callback=phase_end_callback,
                version_bundle_id=version_bundle.bundle_id,
                audit_storage_dir=audit_dir,
                pii_vault=pii_vault,
            )
            results.append(result)

            # Report progress after document completion
            if progress_callback:
                progress_callback(idx + 1, len(claim.documents), doc.original_filename, result)

            logger.info(
                f"Document {doc.original_filename}: {result.status} "
                f"(type={result.doc_type}, {result.time_ms}ms)"
            )

        # Calculate stats
        success_count = sum(1 for r in results if r.status == "success")
        error_count = sum(1 for r in results if r.status == "error")
        total_count = len(results)

        # Count by source type
        pdf_count = sum(1 for r in results if r.source_type == "pdf")
        image_count = sum(1 for r in results if r.source_type == "image")
        text_count = sum(1 for r in results if r.source_type == "text")

        stats = {
            "total": total_count,
            "success": success_count,
            "errors": error_count,
            "pdfs": pdf_count,
            "images": image_count,
            "texts": text_count,
        }

        # Determine overall status
        if success_count == total_count:
            status = "success"
        elif success_count > 0:
            status = "partial"
        else:
            status = "failed"

        elapsed = time.time() - start_time

        # Compute aggregate phase metrics
        phases = compute_phase_aggregates(results)

        # Compute reuse stats
        ingestion_reused_count = sum(1 for r in results if r.ingestion_reused)
        classification_reused_count = sum(1 for r in results if r.classification_reused)
        skipped_text_missing = sum(1 for r in results if r.error and "TEXT_MISSING" in r.error)
        skipped_classification_missing = sum(1 for r in results if r.error and "CLASSIFICATION_MISSING" in r.error)

        # Write enhanced summary with error codes and phase metrics
        summary = {
            "claim_id": claim.claim_id,
            "run_id": run_id,
            "status": status,
            "stats": stats,
            "aggregates": {
                "discovered": total_count,
                "processed": success_count,
                "skipped": sum(1 for r in results if r.status == "skipped"),
                "failed": error_count,
            },
            "phases": phases,
            "stage_reuse": {
                "ingestion": {
                    "executed": total_count - ingestion_reused_count - skipped_text_missing,
                    "reused": ingestion_reused_count,
                    "skipped_missing": skipped_text_missing,
                },
                "classification": {
                    "executed": total_count - classification_reused_count - skipped_classification_missing,
                    "reused": classification_reused_count,
                    "skipped_missing": skipped_classification_missing,
                },
            },
            "documents": [
                {
                    "claim_id": claim.claim_id,
                    "doc_id": r.doc_id,
                    "original_filename": r.original_filename,
                    "source_type": r.source_type,
                    "status": DocStatus.PROCESSED.value if r.status == "success" else DocStatus.FAILED.value,
                    "doc_type_predicted": r.doc_type,
                    "doc_type_confidence": r.doc_type_confidence,
                    "error_code": RunErrorCode.UNKNOWN_EXCEPTION.value if r.error else None,
                    "error_message": r.error,
                    "failed_phase": r.failed_phase,
                    "text_source_used": (
                        TextSource.DI_TEXT.value if r.source_type == "pdf" else
                        TextSource.VISION_OCR.value if r.source_type == "image" else
                        TextSource.RAW_TEXT.value
                    ),
                    "time_ms": r.time_ms,
                    "timings": {
                        "ingestion_ms": r.timings.ingestion_ms if r.timings else None,
                        "classification_ms": r.timings.classification_ms if r.timings else None,
                        "extraction_ms": r.timings.extraction_ms if r.timings else None,
                        "total_ms": r.timings.total_ms if r.timings else r.time_ms,
                    },
                    "quality_gate_status": r.quality_gate_status,
                    "ingestion_reused": r.ingestion_reused,
                    "classification_reused": r.classification_reused,
                    "output_paths": {
                        "extraction": f"extraction/{r.doc_id}.json" if r.extraction_path else None,
                        "context": f"context/{r.doc_id}.json",
                    },
                }
                for r in results
            ],
            "processing_time_seconds": round(elapsed, 2),
            "completed_at": datetime.utcnow().isoformat() + "Z",
        }
        write_json_atomic(run_paths.summary_json, summary, writer=writer)

        # Compute and write metrics
        if compute_metrics:
            try:
                from context_builder.pipeline.metrics import compute_run_metrics
                metrics = compute_run_metrics(run_paths, claim_paths.claim_root)
                write_json_atomic(run_paths.metrics_json, metrics, writer=writer)
                logger.info(f"Metrics computed: {metrics.get('coverage', {})}")
            except Exception as e:
                logger.warning(f"Failed to compute metrics: {e}")

        # Update manifest with end time
        manifest["ended_at"] = datetime.utcnow().isoformat() + "Z"
        manifest["counters_actual"] = {
            "docs_processed": success_count,
            "docs_failed": error_count,
        }
        write_json_atomic(run_paths.manifest_json, manifest, writer=writer)

        # Mark run complete
        mark_run_complete(run_paths, writer=writer)

        logger.info(
            f"Claim {claim.claim_id}: {status} "
            f"({success_count}/{total_count} docs, {elapsed:.1f}s)"
        )

        return ClaimResult(
            claim_id=claim.claim_id,
            status=status,
            run_id=run_id,
            documents=results,
            stats=stats,
            time_seconds=elapsed,
        )

    finally:
        # Always clean up log handler
        logging.getLogger().removeHandler(log_handler)
        log_handler.close()
