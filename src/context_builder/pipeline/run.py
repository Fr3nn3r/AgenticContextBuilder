"""Run module: orchestrate ingestion, classification, and extraction pipeline."""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.classification import ClassifierFactory
from context_builder.extraction.base import ExtractorFactory, generate_run_id
from context_builder.ingestion import IngestionFactory
from context_builder.pipeline.discovery import DiscoveredClaim, DiscoveredDocument
from context_builder.pipeline.paths import (
    ClaimPaths,
    DocPaths,
    RunPaths,
    create_doc_structure,
    get_claim_paths,
    get_run_paths,
)
from context_builder.pipeline.state import is_claim_processed
from context_builder.pipeline.text import build_pages_json, pages_json_to_page_content
from context_builder.schemas.extraction_result import (
    DocumentMetadata,
    ExtractionRunMetadata,
)
from context_builder.schemas.run_errors import DocStatus, PipelineStage, RunErrorCode, TextSource

logger = logging.getLogger(__name__)


@dataclass
class PhaseTimings:
    """Per-phase timing breakdown in milliseconds."""

    ingestion_ms: int = 0
    classification_ms: int = 0
    extraction_ms: int = 0
    total_ms: int = 0


@dataclass
class StageConfig:
    """Configuration for stage-selective execution."""

    stages: List[PipelineStage] = field(
        default_factory=lambda: [PipelineStage.INGEST, PipelineStage.CLASSIFY, PipelineStage.EXTRACT]
    )

    @property
    def run_ingest(self) -> bool:
        return PipelineStage.INGEST in self.stages

    @property
    def run_classify(self) -> bool:
        return PipelineStage.CLASSIFY in self.stages

    @property
    def run_extract(self) -> bool:
        return PipelineStage.EXTRACT in self.stages

    @property
    def run_kind(self) -> str:
        """Determine run kind based on stages."""
        if self.run_ingest and self.run_classify and self.run_extract:
            return "full"
        elif self.run_classify and self.run_extract:
            return "classify_extract"
        elif self.run_extract:
            return "extract_only"
        elif self.run_classify:
            return "classify_only"
        elif self.run_ingest:
            return "ingest_only"
        return "custom"


@dataclass
class DocResult:
    """Result of processing a single document."""

    doc_id: str
    original_filename: str
    status: str  # "success", "error", "skipped"
    source_type: Optional[str] = None  # "pdf", "image", "text"
    doc_type: Optional[str] = None
    doc_type_confidence: Optional[float] = None
    language: Optional[str] = None
    extraction_path: Optional[Path] = None
    error: Optional[str] = None
    time_ms: int = 0
    # Phase-level tracking
    timings: Optional[PhaseTimings] = None
    failed_phase: Optional[str] = None  # "ingestion", "classification", "extraction"
    quality_gate_status: Optional[str] = None  # "pass", "warn", "fail"
    # Stage reuse tracking
    ingestion_reused: bool = False
    classification_reused: bool = False


@dataclass
class ClaimResult:
    """Result of processing an entire claim."""

    claim_id: str
    status: str  # "success", "partial", "failed", "skipped"
    run_id: str
    documents: List[DocResult] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    time_seconds: float = 0.0


def _write_json(path: Path, data: Any) -> None:
    """Write JSON file with utf-8 encoding."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON via temp file + rename for atomicity."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    tmp_path.replace(path)


def _get_git_info() -> Dict[str, Any]:
    """Get current git commit info."""
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode().strip()

        # Check if working tree is dirty
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            timeout=5,
        )
        is_dirty = len(result.stdout.strip()) > 0

        return {
            "commit_sha": commit_sha,
            "is_dirty": is_dirty,
        }
    except Exception:
        return {
            "commit_sha": None,
            "is_dirty": None,
        }


def _compute_templates_hash() -> str:
    """Compute deterministic hash of extraction specs/templates."""
    try:
        # Hash the extraction specs
        specs_dir = Path(__file__).parent.parent / "extraction" / "specs"
        if not specs_dir.exists():
            return "no_specs"

        hasher = hashlib.md5()
        for spec_file in sorted(specs_dir.glob("*.yaml")):
            hasher.update(spec_file.read_bytes())
        return hasher.hexdigest()[:12]
    except Exception:
        return "hash_error"


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


def _write_manifest(
    run_paths: RunPaths,
    run_id: str,
    claim_id: str,
    command: str,
    doc_count: int,
    model: str,
    stage_config: Optional[StageConfig] = None,
) -> Dict[str, Any]:
    """Write manifest.json at run start. Returns manifest dict for later update."""
    # Default to full pipeline if no config
    if stage_config is None:
        stage_config = StageConfig()

    manifest = {
        "run_id": run_id,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "ended_at": None,
        "command": command,
        "cwd": str(Path.cwd()),
        "hostname": os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown")),
        "python_version": sys.version.split()[0],
        "git": _get_git_info(),
        "pipeline_versions": {
            "contextbuilder_version": "1.0.0",
            "extractor_version": "v1.0.0",
            "templates_hash": _compute_templates_hash(),
            "model_name": model,
        },
        "input": {
            "claim_id": claim_id,
            "docs_discovered": doc_count,
        },
        "counters_expected": {
            "docs": doc_count,
        },
        "run_kind": stage_config.run_kind,
        "stages_executed": [s.value for s in stage_config.stages],
    }
    _write_json_atomic(run_paths.manifest_json, manifest)
    return manifest


def _mark_run_complete(run_paths: RunPaths) -> None:
    """Create .complete marker after all artifacts written."""
    run_paths.complete_marker.touch()


def _ingest_document(
    doc: DiscoveredDocument,
    doc_paths: DocPaths,
) -> str:
    """
    Ingest a PDF or image document to extract text.

    Args:
        doc: Document to ingest
        doc_paths: Paths for output files

    Returns:
        Extracted text content

    Raises:
        Exception: If ingestion fails
    """
    if doc.source_type == "pdf":
        # Use Azure DI for PDFs
        logger.info(f"Ingesting PDF with Azure DI: {doc.original_filename}")
        ingestion = IngestionFactory.create("azure-di")
        ingestion.save_markdown = False  # We'll save ourselves
        result = ingestion.process(doc.source_path)

        # Extract markdown content from Azure DI result
        raw_output = result.get("raw_azure_di_output", {})
        text_content = raw_output.get("content", "")

        if not text_content:
            raise ValueError("Azure DI returned no content")

        # Save raw Azure DI output for debugging
        raw_path = doc_paths.text_raw_dir / "azure_di.json"
        _write_json(raw_path, result)

        return text_content

    elif doc.source_type == "image":
        # Use OpenAI Vision for images
        logger.info(f"Ingesting image with OpenAI Vision: {doc.original_filename}")
        ingestion = IngestionFactory.create("openai")
        result = ingestion.process(doc.source_path)

        # Extract text from vision pages
        pages = result.get("pages", [])
        if not pages:
            raise ValueError("OpenAI Vision returned no pages")

        # Combine text from all pages
        text_parts = []
        for page in pages:
            text_content = page.get("text_content", "")
            if text_content:
                text_parts.append(text_content)
            # Also include summary if no raw text
            elif page.get("summary"):
                text_parts.append(page.get("summary", ""))

        text_content = "\n\n".join(text_parts)

        if not text_content:
            # Fallback: serialize key information
            key_info = pages[0].get("key_information", {})
            if key_info:
                text_content = json.dumps(key_info, indent=2, ensure_ascii=False)

        # Save raw vision output for debugging
        raw_path = doc_paths.text_raw_dir / "vision.json"
        _write_json(raw_path, result)

        return text_content

    else:
        raise ValueError(f"Unknown source type: {doc.source_type}")


def _load_existing_ingestion(
    doc_paths: DocPaths,
) -> tuple[str, Dict[str, Any]]:
    """
    Load existing ingestion output from pages.json.

    Args:
        doc_paths: Document paths

    Returns:
        Tuple of (text_content, pages_data)

    Raises:
        FileNotFoundError: If pages.json doesn't exist
        ValueError: If pages.json is invalid
    """
    if not doc_paths.pages_json.exists():
        raise FileNotFoundError(f"pages.json not found: {doc_paths.pages_json}")

    with open(doc_paths.pages_json, "r", encoding="utf-8") as f:
        pages_data = json.load(f)

    # Reconstruct text content from pages
    pages = pages_data.get("pages", [])
    text_content = "\n\n".join(p.get("text", "") for p in pages)

    return text_content, pages_data


def _load_existing_classification(
    doc_paths: DocPaths,
) -> tuple[str, str, float]:
    """
    Load existing classification from doc.json.

    Args:
        doc_paths: Document paths

    Returns:
        Tuple of (doc_type, language, confidence)

    Raises:
        FileNotFoundError: If doc.json doesn't exist
    """
    if not doc_paths.doc_json.exists():
        raise FileNotFoundError(f"doc.json not found: {doc_paths.doc_json}")

    with open(doc_paths.doc_json, "r", encoding="utf-8") as f:
        doc_meta = json.load(f)

    return (
        doc_meta.get("doc_type", "unknown"),
        doc_meta.get("language", "es"),
        doc_meta.get("doc_type_confidence", 0.8),
    )


def process_document(
    doc: DiscoveredDocument,
    claim_id: str,
    doc_paths: DocPaths,
    run_paths: RunPaths,
    classifier: Any,
    run_id: str,
    stage_config: Optional[StageConfig] = None,
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

    Returns:
        DocResult with processing status and paths
    """
    start_time = time.time()
    timings = PhaseTimings()
    current_phase = "setup"

    # Default to full pipeline if no config provided
    if stage_config is None:
        stage_config = StageConfig()

    # Track reuse
    ingestion_reused = False
    classification_reused = False

    try:
        text_content = None
        pages_data = None
        doc_type = None
        language = None
        confidence = None
        content_md5 = None

        # ========== INGESTION PHASE ==========
        current_phase = "ingestion"
        ingestion_start = time.time()

        if stage_config.run_ingest:
            # Step 1: Copy/write source file
            if doc.source_type in ("pdf", "image"):
                dest_path = doc_paths.source_dir / f"original{doc.source_path.suffix}"
                shutil.copy2(doc.source_path, dest_path)
            else:
                doc_paths.original_txt.write_text(doc.content, encoding="utf-8")

            # Step 2: Ingest or use existing content
            if doc.needs_ingestion:
                text_content = _ingest_document(doc, doc_paths)
            else:
                text_content = doc.content

            # Write source text
            doc_paths.source_txt.write_text(text_content, encoding="utf-8")

            # Step 3: Build and write pages.json
            pages_data = build_pages_json(
                text_content,
                doc.doc_id,
                source_type="azure_di" if doc.source_type == "pdf" else (
                    "vision_ocr" if doc.source_type == "image" else "preextracted_txt"
                ),
            )
            _write_json(doc_paths.pages_json, pages_data)
        else:
            # Load existing ingestion
            try:
                text_content, pages_data = _load_existing_ingestion(doc_paths)
                ingestion_reused = True
                logger.info(f"Reusing existing ingestion for {doc.original_filename}")
            except FileNotFoundError:
                elapsed_ms = int((time.time() - start_time) * 1000)
                return DocResult(
                    doc_id=doc.doc_id,
                    original_filename=doc.original_filename,
                    status="skipped",
                    source_type=doc.source_type,
                    error="TEXT_MISSING: No pages.json found and --stages excludes ingest",
                    time_ms=elapsed_ms,
                    failed_phase="ingestion",
                )

        timings.ingestion_ms = int((time.time() - ingestion_start) * 1000)

        # ========== CLASSIFICATION PHASE ==========
        current_phase = "classification"
        classification_start = time.time()

        if stage_config.run_classify:
            # Step 4: Classify document
            classification = classifier.classify(text_content, doc.original_filename)
            doc_type = classification.get("document_type", "unknown")
            language = classification.get("language", "es")
            confidence = classification.get("confidence")
            if confidence is None:
                confidence = 0.8

            # Step 5: Write context JSON
            context_data = {
                "doc_id": doc.doc_id,
                "original_filename": doc.original_filename,
                "source_type": doc.source_type,
                "classification": classification,
                "classified_at": datetime.utcnow().isoformat() + "Z",
            }
            context_path = run_paths.context_dir / f"{doc.doc_id}.json"
            _write_json(context_path, context_data)

            # Step 6: Write meta/doc.json
            content_md5 = hashlib.md5(text_content.encode("utf-8")).hexdigest()

            doc_meta = {
                "doc_id": doc.doc_id,
                "claim_id": claim_id,
                "original_filename": doc.original_filename,
                "source_type": doc.source_type,
                "doc_type": doc_type,
                "doc_type_confidence": confidence,
                "language": language,
                "file_md5": doc.file_md5,
                "content_md5": content_md5,
                "page_count": pages_data["page_count"],
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            _write_json(doc_paths.doc_json, doc_meta)
        else:
            # Load existing classification
            try:
                doc_type, language, confidence = _load_existing_classification(doc_paths)
                classification_reused = True
                logger.info(f"Reusing existing classification for {doc.original_filename}: {doc_type}")
                # Get content_md5 from existing doc.json
                with open(doc_paths.doc_json, "r", encoding="utf-8") as f:
                    existing_meta = json.load(f)
                content_md5 = existing_meta.get("content_md5", "")
            except FileNotFoundError:
                elapsed_ms = int((time.time() - start_time) * 1000)
                timings.ingestion_ms = int((time.time() - ingestion_start) * 1000)
                return DocResult(
                    doc_id=doc.doc_id,
                    original_filename=doc.original_filename,
                    status="skipped",
                    source_type=doc.source_type,
                    error="CLASSIFICATION_MISSING: No doc.json found and --stages excludes classify",
                    time_ms=elapsed_ms,
                    timings=timings,
                    failed_phase="classification",
                    ingestion_reused=ingestion_reused,
                )

        timings.classification_ms = int((time.time() - classification_start) * 1000)

        # ========== EXTRACTION PHASE ==========
        current_phase = "extraction"
        extraction_start = time.time()
        extraction_path = None
        quality_gate_status = None

        if stage_config.run_extract and ExtractorFactory.is_supported(doc_type):
            extraction_path, quality_gate_status = _run_extraction(
                doc_id=doc.doc_id,
                file_md5=doc.file_md5,
                content_md5=content_md5 or "",
                claim_id=claim_id,
                pages_data=pages_data,
                doc_type=doc_type,
                doc_type_confidence=confidence,
                language=language,
                run_paths=run_paths,
                run_id=run_id,
            )
            logger.info(f"Extracted {doc_type}: {doc.original_filename}")
        elif not stage_config.run_extract:
            logger.debug(f"Extraction skipped by --stages: {doc.original_filename}")
        else:
            logger.debug(f"No extractor for {doc_type}: {doc.original_filename}")

        timings.extraction_ms = int((time.time() - extraction_start) * 1000)
        timings.total_ms = int((time.time() - start_time) * 1000)

        return DocResult(
            doc_id=doc.doc_id,
            original_filename=doc.original_filename,
            status="success",
            source_type=doc.source_type,
            doc_type=doc_type,
            doc_type_confidence=confidence,
            language=language,
            extraction_path=extraction_path,
            time_ms=timings.total_ms,
            timings=timings,
            quality_gate_status=quality_gate_status,
            ingestion_reused=ingestion_reused,
            classification_reused=classification_reused,
        )

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        timings.total_ms = elapsed_ms
        logger.exception(f"Failed to process {doc.original_filename} in {current_phase} phase")
        return DocResult(
            doc_id=doc.doc_id,
            original_filename=doc.original_filename,
            status="error",
            source_type=doc.source_type,
            error=str(e),
            time_ms=elapsed_ms,
            timings=timings,
            failed_phase=current_phase,
            ingestion_reused=ingestion_reused,
            classification_reused=classification_reused,
        )


def _run_extraction(
    doc_id: str,
    file_md5: str,
    content_md5: str,
    claim_id: str,
    pages_data: Dict[str, Any],
    doc_type: str,
    doc_type_confidence: float,
    language: str,
    run_paths: RunPaths,
    run_id: str,
) -> tuple[Path, Optional[str]]:
    """Run field extraction for supported doc types.

    Returns:
        Tuple of (extraction_path, quality_gate_status)
    """
    # Import extractors to ensure they're registered
    import context_builder.extraction.extractors  # noqa: F401

    extractor = ExtractorFactory.create(doc_type)

    # Convert pages to PageContent objects
    pages = pages_json_to_page_content(pages_data)

    # Build metadata
    doc_meta = DocumentMetadata(
        doc_id=doc_id,
        claim_id=claim_id,
        doc_type=doc_type,
        doc_type_confidence=doc_type_confidence,
        language=language,
        page_count=len(pages),
    )

    run_meta = ExtractionRunMetadata(
        run_id=run_id,
        extractor_version="v1.0.0",
        model=extractor.model,
        prompt_version="generic_extraction_v1",
        input_hashes={"file_md5": file_md5, "content_md5": content_md5},
    )

    # Run extraction
    result = extractor.extract(pages, doc_meta, run_meta)

    # Write extraction result
    output_path = run_paths.extraction_dir / f"{doc_id}.json"
    _write_json(output_path, result.model_dump())

    # Get quality gate status
    quality_gate_status = result.quality_gate.status if result.quality_gate else None

    return output_path, quality_gate_status


def _compute_phase_aggregates(results: List[DocResult]) -> Dict[str, Any]:
    """
    Compute aggregate phase metrics from document results.

    Returns dict with ingestion, classification, extraction, and quality_gate sub-dicts.
    """
    from collections import Counter

    # Ingestion metrics
    ingestion_success = sum(1 for r in results if r.status == "success" or (r.failed_phase and r.failed_phase != "ingestion"))
    ingestion_failed = sum(1 for r in results if r.failed_phase == "ingestion")
    ingestion_duration = sum(r.timings.ingestion_ms for r in results if r.timings and r.timings.ingestion_ms)

    # Classification metrics
    # Docs that made it past ingestion
    classified = sum(1 for r in results if r.doc_type is not None)
    classification_failed = sum(1 for r in results if r.failed_phase == "classification")
    classification_duration = sum(r.timings.classification_ms for r in results if r.timings and r.timings.classification_ms)

    # Build doc type distribution
    doc_type_distribution: Counter[str] = Counter()
    for r in results:
        if r.doc_type:
            doc_type_distribution[r.doc_type] += 1

    # Extraction metrics
    extraction_attempted = sum(1 for r in results if r.extraction_path is not None or r.failed_phase == "extraction")
    extraction_succeeded = sum(1 for r in results if r.extraction_path is not None)
    extraction_failed = sum(1 for r in results if r.failed_phase == "extraction")
    extraction_duration = sum(r.timings.extraction_ms for r in results if r.timings and r.timings.extraction_ms)

    # Quality gate metrics
    qg_pass = sum(1 for r in results if r.quality_gate_status == "pass")
    qg_warn = sum(1 for r in results if r.quality_gate_status == "warn")
    qg_fail = sum(1 for r in results if r.quality_gate_status == "fail")

    return {
        "ingestion": {
            "discovered": len(results),
            "ingested": ingestion_success,
            "skipped": 0,  # Would track duplicates/unsupported if we had that info
            "failed": ingestion_failed,
            "duration_ms": ingestion_duration if ingestion_duration > 0 else None,
        },
        "classification": {
            "classified": classified,
            "low_confidence": 0,  # TODO: Track when confidence < threshold
            "distribution": dict(doc_type_distribution),
            "duration_ms": classification_duration if classification_duration > 0 else None,
        },
        "extraction": {
            "attempted": extraction_attempted,
            "succeeded": extraction_succeeded,
            "failed": extraction_failed,
            "skipped_unsupported": len(results) - extraction_attempted,
            "duration_ms": extraction_duration if extraction_duration > 0 else None,
        },
        "quality_gate": {
            "pass": qg_pass,
            "warn": qg_warn,
            "fail": qg_fail,
        },
    }


def process_claim(
    claim: DiscoveredClaim,
    output_base: Path,
    classifier: Any = None,
    run_id: Optional[str] = None,
    force: bool = False,
    command: str = "",
    model: str = "gpt-4o",
    compute_metrics: bool = True,
    stage_config: Optional[StageConfig] = None,
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
        model: Model name for manifest
        compute_metrics: If True, compute metrics.json at end
        stage_config: Configuration for which stages to run (default: all)

    Returns:
        ClaimResult with aggregated stats
    """
    start_time = time.time()
    run_id = run_id or generate_run_id()

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

        # Write manifest at start
        manifest = _write_manifest(
            run_paths=run_paths,
            run_id=run_id,
            claim_id=claim.claim_id,
            command=command,
            doc_count=len(claim.documents),
            model=model,
            stage_config=stage_config,
        )

        # Create classifier if not provided
        if classifier is None:
            classifier = ClassifierFactory.create("openai")

        # Process each document
        results: List[DocResult] = []
        for doc in claim.documents:
            logger.info(f"Processing document: {doc.original_filename}")

            # Create document structure
            doc_paths, _, _ = create_doc_structure(
                output_base, claim.claim_id, doc.doc_id, run_id
            )

            result = process_document(
                doc=doc,
                claim_id=claim.claim_id,
                doc_paths=doc_paths,
                run_paths=run_paths,
                classifier=classifier,
                run_id=run_id,
                stage_config=stage_config,
            )
            results.append(result)

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
        phases = _compute_phase_aggregates(results)

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
        _write_json_atomic(run_paths.summary_json, summary)

        # Compute and write metrics
        if compute_metrics:
            try:
                from context_builder.pipeline.metrics import compute_run_metrics
                metrics = compute_run_metrics(run_paths, claim_paths.claim_root)
                _write_json_atomic(run_paths.metrics_json, metrics)
                logger.info(f"Metrics computed: {metrics.get('coverage', {})}")
            except Exception as e:
                logger.warning(f"Failed to compute metrics: {e}")

        # Update manifest with end time
        manifest["ended_at"] = datetime.utcnow().isoformat() + "Z"
        manifest["counters_actual"] = {
            "docs_processed": success_count,
            "docs_failed": error_count,
        }
        _write_json_atomic(run_paths.manifest_json, manifest)

        # Mark run complete
        _mark_run_complete(run_paths)

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
