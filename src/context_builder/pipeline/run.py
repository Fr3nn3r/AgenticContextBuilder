"""Run module: orchestrate ingestion, classification, and extraction pipeline."""

# Ensure .env is loaded for pipeline execution (fallback for CLI usage)
from pathlib import Path as _Path
from dotenv import load_dotenv
_project_root = _Path(__file__).resolve().parent.parent.parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
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
from context_builder.pipeline.stages import PipelineRunner
from context_builder.pipeline.state import is_claim_processed
from context_builder.pipeline.text import build_pages_json, pages_json_to_page_content
from context_builder.pipeline.writer import ResultWriter
from context_builder.schemas.extraction_result import (
    DocumentMetadata,
    ExtractionRunMetadata,
)
from context_builder.schemas.run_errors import DocStatus, PipelineStage, RunErrorCode, TextSource
from context_builder.storage.version_bundles import VersionBundleStore, get_version_bundle_store

logger = logging.getLogger(__name__)

# Placeholder for tests that patch this symbol without importing extraction at module load.
ExtractorFactory = None
# Placeholder for tests that patch ingestion factory without importing at module load.
IngestionFactory = None


def _get_workspace_logs_dir(output_base: Path) -> Path:
    """Derive workspace logs directory from output base path.

    If output_base is workspace-scoped (e.g., workspaces/default/claims),
    returns the sibling logs directory (workspaces/default/logs).
    Otherwise falls back to output/logs.

    Args:
        output_base: The claims output directory

    Returns:
        Path to logs directory for compliance storage
    """
    # If output_base ends with /claims, sibling is /logs
    if output_base.name == "claims":
        logs_dir = output_base.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir
    # Fallback to output/logs relative to project root
    return Path("output/logs")


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
    doc_type_filter: Optional[List[str]] = None  # If set, only extract these doc types

    @property
    def run_ingest(self) -> bool:
        return PipelineStage.INGEST in self.stages

    @property
    def run_classify(self) -> bool:
        return PipelineStage.CLASSIFY in self.stages

    @property
    def run_extract(self) -> bool:
        return PipelineStage.EXTRACT in self.stages

    def should_extract_doc_type(self, doc_type: str) -> bool:
        """Check if a doc_type should be extracted based on filter."""
        if self.doc_type_filter is None:
            return True  # No filter, extract all
        return doc_type in self.doc_type_filter

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
class PipelineProviders:
    """Optional external providers/factories for dependency injection."""

    classifier: Any = None
    classifier_factory: Any = None
    ingestion_factory: Any = None
    extractor_factory: Any = None


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


def _write_json(path: Path, data: Any, writer: Optional[ResultWriter] = None) -> None:
    """Write JSON file with utf-8 encoding."""
    (writer or ResultWriter()).write_json(path, data)


def _write_json_atomic(path: Path, data: Any, writer: Optional[ResultWriter] = None) -> None:
    """Write JSON via temp file + rename for atomicity."""
    (writer or ResultWriter()).write_json_atomic(path, data)


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
    writer: Optional[ResultWriter] = None,
    version_bundle_id: Optional[str] = None,
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
        "version_bundle_id": version_bundle_id,
    }
    _write_json_atomic(run_paths.manifest_json, manifest, writer=writer)
    return manifest


def _mark_run_complete(run_paths: RunPaths, writer: Optional[ResultWriter] = None) -> None:
    """Create .complete marker after all artifacts written."""
    (writer or ResultWriter()).touch(run_paths.complete_marker)


def _ingest_document(
    doc: DiscoveredDocument,
    doc_paths: DocPaths,
    writer: ResultWriter,
    ingestion_factory: Optional[Any] = None,
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
        factory = ingestion_factory or IngestionFactory
        if factory is None:
            from context_builder.ingestion import IngestionFactory as DefaultIngestionFactory
            factory = DefaultIngestionFactory
        ingestion = factory.create("azure-di")
        ingestion.save_markdown = False  # We'll save ourselves
        result = ingestion.process(doc.source_path, envelope=True)
        data = result.get("data", {})

        # Extract markdown content from Azure DI result
        raw_output = data.get("raw_azure_di_output", {})
        text_content = raw_output.get("content", "")

        if not text_content:
            raise ValueError("Azure DI returned no content")

        # Save raw Azure DI output for debugging
        raw_path = doc_paths.text_raw_dir / "azure_di.json"
        writer.write_json(raw_path, data)

        return text_content

    elif doc.source_type == "image":
        # Use OpenAI Vision for images
        logger.info(f"Ingesting image with OpenAI Vision: {doc.original_filename}")
        factory = ingestion_factory or IngestionFactory
        if factory is None:
            from context_builder.ingestion import IngestionFactory as DefaultIngestionFactory
            factory = DefaultIngestionFactory
        ingestion = factory.create("openai")
        result = ingestion.process(doc.source_path, envelope=True)
        data = result.get("data", {})

        # Extract text from vision pages
        pages = data.get("pages", [])
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
        writer.write_json(raw_path, data)

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


@dataclass
class DocumentContext:
    """Mutable context passed between pipeline stages."""

    doc: DiscoveredDocument
    claim_id: str
    doc_paths: DocPaths
    run_paths: RunPaths
    classifier: Any
    ingestion_factory: Any
    extractor_factory: Any
    run_id: str
    stage_config: StageConfig
    writer: ResultWriter
    start_time: float = field(default_factory=time.time)
    timings: PhaseTimings = field(default_factory=PhaseTimings)
    text_content: Optional[str] = None
    pages_data: Optional[Dict[str, Any]] = None
    doc_type: Optional[str] = None
    language: Optional[str] = None
    confidence: Optional[float] = None
    content_md5: Optional[str] = None
    extraction_path: Optional[Path] = None
    quality_gate_status: Optional[str] = None
    status: str = "success"
    error: Optional[str] = None
    failed_phase: Optional[str] = None
    ingestion_reused: bool = False
    classification_reused: bool = False
    current_phase: str = "setup"
    version_bundle_id: Optional[str] = None  # For compliance traceability
    audit_storage_dir: Optional[Path] = None  # Workspace-scoped compliance logs dir
    pii_vault: Optional[Any] = None  # PII vault for tokenizing extraction results

    def to_doc_result(self) -> DocResult:
        """Convert the context into a DocResult."""
        total_ms = int((time.time() - self.start_time) * 1000)
        if self.timings.total_ms == 0:
            self.timings.total_ms = total_ms
        return DocResult(
            doc_id=self.doc.doc_id,
            original_filename=self.doc.original_filename,
            status=self.status,
            source_type=self.doc.source_type,
            doc_type=self.doc_type,
            doc_type_confidence=self.confidence,
            language=self.language,
            extraction_path=self.extraction_path,
            error=self.error,
            time_ms=self.timings.total_ms,
            timings=self.timings,
            failed_phase=self.failed_phase,
            quality_gate_status=self.quality_gate_status,
            ingestion_reused=self.ingestion_reused,
            classification_reused=self.classification_reused,
        )


@dataclass
class IngestionStage:
    """Ingestion stage: copy source, extract text, write pages.json."""

    writer: ResultWriter
    name: str = "ingestion"

    def run(self, context: DocumentContext) -> DocumentContext:
        context.current_phase = self.name
        start = time.time()

        if context.stage_config.run_ingest:
            if context.doc.source_type in ("pdf", "image"):
                dest_path = context.doc_paths.source_dir / f"original{context.doc.source_path.suffix}"
                self.writer.copy_file(context.doc.source_path, dest_path)
            else:
                self.writer.write_text(context.doc_paths.original_txt, context.doc.content)

            if context.doc.needs_ingestion:
                context.text_content = _ingest_document(
                    context.doc,
                    context.doc_paths,
                    self.writer,
                    ingestion_factory=context.ingestion_factory,
                )
            else:
                context.text_content = context.doc.content

            self.writer.write_text(context.doc_paths.source_txt, context.text_content)

            context.pages_data = build_pages_json(
                context.text_content,
                context.doc.doc_id,
                source_type="azure_di" if context.doc.source_type == "pdf" else (
                    "vision_ocr" if context.doc.source_type == "image" else "preextracted_txt"
                ),
            )
            self.writer.write_json(context.doc_paths.pages_json, context.pages_data)
        else:
            try:
                context.text_content, context.pages_data = _load_existing_ingestion(context.doc_paths)
                context.ingestion_reused = True
                logger.info(f"Reusing existing ingestion for {context.doc.original_filename}")
            except FileNotFoundError:
                context.status = "skipped"
                context.error = "TEXT_MISSING: No pages.json found and --stages excludes ingest"
                context.failed_phase = "ingestion"
                return context

        context.timings.ingestion_ms = int((time.time() - start) * 1000)
        return context


@dataclass
class ClassificationStage:
    """Classification stage: classify and write context/doc.json."""

    writer: ResultWriter
    name: str = "classification"

    def run(self, context: DocumentContext) -> DocumentContext:
        context.current_phase = self.name
        start = time.time()

        if context.text_content is None:
            raise ValueError("Missing text content for classification")

        if context.stage_config.run_classify:
            # Set audit context for compliance logging (links decision to claim/doc/run)
            if hasattr(context.classifier, 'set_audit_context'):
                context.classifier.set_audit_context(
                    claim_id=context.claim_id,
                    doc_id=context.doc.doc_id,
                    run_id=context.run_id,
                )

            # Use page-based classification if pages data is available
            if context.pages_data and "pages" in context.pages_data:
                pages = [p.get("text", "") for p in context.pages_data["pages"]]
                classification = context.classifier.classify_pages(
                    pages,
                    context.doc.original_filename,
                )
                logger.info(
                    f"Classification used {classification.get('context_tier', 'unknown')} context, "
                    f"retried={classification.get('retried', False)}, "
                    f"token_savings={classification.get('token_savings_estimate', 0)}"
                )
            else:
                # Fallback to text-based classification
                classification = context.classifier.classify(
                    context.text_content,
                    context.doc.original_filename,
                )

            context.doc_type = classification.get("document_type", "unknown")
            context.language = classification.get("language", "es")
            confidence = classification.get("confidence")
            context.confidence = confidence if confidence is not None else 0.8

            context_data = {
                "doc_id": context.doc.doc_id,
                "original_filename": context.doc.original_filename,
                "source_type": context.doc.source_type,
                "classification": classification,
                "classified_at": datetime.utcnow().isoformat() + "Z",
            }
            context_path = context.run_paths.context_dir / f"{context.doc.doc_id}.json"
            self.writer.write_json(context_path, context_data)

            context.content_md5 = hashlib.md5(context.text_content.encode("utf-8")).hexdigest()
            doc_meta = {
                "doc_id": context.doc.doc_id,
                "claim_id": context.claim_id,
                "original_filename": context.doc.original_filename,
                "source_type": context.doc.source_type,
                "doc_type": context.doc_type,
                "doc_type_confidence": context.confidence,
                "language": context.language,
                "file_md5": context.doc.file_md5,
                "content_md5": context.content_md5,
                "page_count": context.pages_data["page_count"],
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            self.writer.write_json(context.doc_paths.doc_json, doc_meta)
        else:
            try:
                context.doc_type, context.language, context.confidence = _load_existing_classification(
                    context.doc_paths
                )
                context.classification_reused = True
                logger.info(
                    f"Reusing existing classification for {context.doc.original_filename}: {context.doc_type}"
                )
                with open(context.doc_paths.doc_json, "r", encoding="utf-8") as f:
                    existing_meta = json.load(f)
                context.content_md5 = existing_meta.get("content_md5", "")
            except FileNotFoundError:
                context.status = "skipped"
                context.error = "CLASSIFICATION_MISSING: No doc.json found and --stages excludes classify"
                context.failed_phase = "classification"
                return context

        context.timings.classification_ms = int((time.time() - start) * 1000)
        return context


@dataclass
class ExtractionStage:
    """Extraction stage: run extractor and write extraction output."""

    writer: ResultWriter
    name: str = "extraction"

    def run(self, context: DocumentContext) -> DocumentContext:
        context.current_phase = self.name
        start = time.time()

        doc_type = context.doc_type or "unknown"
        extractor_factory = context.extractor_factory or ExtractorFactory
        if context.stage_config.run_extract and extractor_factory is None:
            from context_builder.extraction.base import ExtractorFactory as DefaultExtractorFactory
            extractor_factory = DefaultExtractorFactory

        # Check if extraction should run for this doc type
        should_extract = (
            context.stage_config.run_extract
            and extractor_factory.is_supported(doc_type)
            and context.stage_config.should_extract_doc_type(doc_type)
        )

        if should_extract:
            if context.pages_data is None:
                raise ValueError("Missing pages data for extraction")
            context.extraction_path, context.quality_gate_status = _run_extraction(
                doc_id=context.doc.doc_id,
                file_md5=context.doc.file_md5,
                content_md5=context.content_md5 or "",
                claim_id=context.claim_id,
                pages_data=context.pages_data,
                doc_type=doc_type,
                doc_type_confidence=context.confidence or 0.0,
                language=context.language or "es",
                run_paths=context.run_paths,
                run_id=context.run_id,
                writer=self.writer,
                extractor_factory=extractor_factory,
                version_bundle_id=context.version_bundle_id,
                audit_storage_dir=context.audit_storage_dir,
                pii_vault=context.pii_vault,
            )
            logger.info(f"Extracted {doc_type}: {context.doc.original_filename}")
        elif not context.stage_config.run_extract:
            logger.debug(f"Extraction skipped by --stages: {context.doc.original_filename}")
        elif not context.stage_config.should_extract_doc_type(doc_type):
            logger.debug(f"Extraction skipped by --doc-types filter: {doc_type} ({context.doc.original_filename})")
        else:
            logger.debug(f"No extractor for {doc_type}: {context.doc.original_filename}")

        context.timings.extraction_ms = int((time.time() - start) * 1000)
        return context


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
    phase_callback: Optional[Callable[[str, str], None]] = None,
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
        phase_callback: Optional callback(phase_name, doc_id) for phase transitions
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
            phase_callback(stage_name, doc.doc_id)

    runner = PipelineRunner(
        [
            IngestionStage(writer),
            ClassificationStage(writer),
            ExtractionStage(writer),
        ],
        on_phase_start=on_phase_start,
    )

    try:
        context = runner.run(context)
        if context.timings.total_ms == 0:
            context.timings.total_ms = int((time.time() - context.start_time) * 1000)
        return context.to_doc_result()
    except Exception as e:
        elapsed_ms = int((time.time() - context.start_time) * 1000)
        context.timings.total_ms = elapsed_ms
        logger.exception(
            f"Failed to process {doc.original_filename} in {context.current_phase} phase"
        )
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
    writer: ResultWriter,
    extractor_factory: Any,
    version_bundle_id: Optional[str] = None,
    audit_storage_dir: Optional[Path] = None,
    pii_vault: Optional[Any] = None,
) -> tuple[Path, Optional[str]]:
    """Run field extraction for supported doc types.

    Args:
        doc_id: Document identifier.
        file_md5: MD5 hash of input file.
        content_md5: MD5 hash of content.
        claim_id: Parent claim identifier.
        pages_data: Page content data.
        doc_type: Document type.
        doc_type_confidence: Classification confidence.
        language: Document language.
        run_paths: Output paths for this run.
        run_id: Extraction run identifier.
        writer: Result writer instance.
        extractor_factory: Factory for creating extractors.
        version_bundle_id: Optional version bundle ID.
        audit_storage_dir: Optional directory for audit logs.
        pii_vault: Optional PII vault for tokenizing PII in extraction results.

    Returns:
        Tuple of (extraction_path, quality_gate_status)
    """
    # Import extractors to ensure they're registered
    import context_builder.extraction.extractors  # noqa: F401
    extractor = extractor_factory.create(doc_type, audit_storage_dir=audit_storage_dir)

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
        version_bundle_id=version_bundle_id,  # Link to version snapshot
    )

    # Run extraction
    result = extractor.extract(pages, doc_meta, run_meta)

    # PII Tokenization: Replace PII with vault tokens before persisting
    result_data = result.model_dump()
    if pii_vault is not None:
        from context_builder.services.compliance.pii import PIITokenizer

        tokenizer = PIITokenizer(claim_id=claim_id, vault_id=pii_vault.vault_id)
        tokenization = tokenizer.tokenize(result, run_id)

        if tokenization.vault_entries:
            pii_vault.store_batch(tokenization.vault_entries)
            logger.info(
                f"Tokenized {len(tokenization.vault_entries)} PII values for doc {doc_id}"
            )

        result_data = tokenization.redacted_result  # Use redacted for persistence

    # Write extraction result (with tokens if PII vault enabled)
    output_path = run_paths.extraction_dir / f"{doc_id}.json"
    writer.write_json(output_path, result_data)

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
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    phase_callback: Optional[Callable[[str, str], None]] = None,
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
        model: Model name for manifest
        compute_metrics: If True, compute metrics.json at end
        stage_config: Configuration for which stages to run (default: all)
        progress_callback: Optional callback(idx, total, filename) for progress reporting
        phase_callback: Optional callback(phase_name, doc_id) for real-time phase updates
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
            model_name=model,
            extractor_version="v1.0.0",
        )
        logger.info(f"Created version bundle {version_bundle.bundle_id} for run {run_id}")

        # Write manifest at start
        manifest = _write_manifest(
            run_paths=run_paths,
            run_id=run_id,
            claim_id=claim.claim_id,
            command=command,
            doc_count=len(claim.documents),
            model=model,
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
            audit_dir = _get_workspace_logs_dir(output_base)
            classifier = ClassifierFactory.create("openai", audit_storage_dir=audit_dir)

        # Create PII vault if enabled
        pii_vault = None
        if pii_vault_enabled:
            from context_builder.services.compliance.pii import EncryptedPIIVaultStorage
            pii_vault_dir = _get_workspace_logs_dir(output_base)
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
            audit_dir = _get_workspace_logs_dir(output_base)

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
                version_bundle_id=version_bundle.bundle_id,
                audit_storage_dir=audit_dir,
                pii_vault=pii_vault,
            )
            results.append(result)

            # Report progress after document completion
            if progress_callback:
                progress_callback(idx + 1, len(claim.documents), doc.original_filename)

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
        _write_json_atomic(run_paths.summary_json, summary, writer=writer)

        # Compute and write metrics
        if compute_metrics:
            try:
                from context_builder.pipeline.metrics import compute_run_metrics
                metrics = compute_run_metrics(run_paths, claim_paths.claim_root)
                _write_json_atomic(run_paths.metrics_json, metrics, writer=writer)
                logger.info(f"Metrics computed: {metrics.get('coverage', {})}")
            except Exception as e:
                logger.warning(f"Failed to compute metrics: {e}")

        # Update manifest with end time
        manifest["ended_at"] = datetime.utcnow().isoformat() + "Z"
        manifest["counters_actual"] = {
            "docs_processed": success_count,
            "docs_failed": error_count,
        }
        _write_json_atomic(run_paths.manifest_json, manifest, writer=writer)

        # Mark run complete
        _mark_run_complete(run_paths, writer=writer)

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
