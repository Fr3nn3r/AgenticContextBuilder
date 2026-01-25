"""Pipeline context dataclasses for passing state between stages."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.pipeline.discovery import DiscoveredDocument
from context_builder.pipeline.paths import DocPaths, RunPaths
from context_builder.pipeline.writer import ResultWriter
from context_builder.schemas.run_errors import PipelineStage


@dataclass
class IngestionResult:
    """Result of document ingestion."""

    text_content: str
    provider_name: str
    azure_di_data: Optional[Dict[str, Any]] = None  # For Azure DI, includes raw output with page spans


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
