"""Claim-level pipeline context dataclasses.

These dataclasses are used for claim-level processing stages (reconciliation, processing)
which operate across all documents in a claim, as opposed to document-level stages
(ingestion, classification, extraction) which operate on individual documents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ClaimStageTimings:
    """Per-stage timing breakdown in milliseconds for claim-level pipeline."""

    reconciliation_ms: int = 0
    enrichment_ms: int = 0
    screening_ms: int = 0
    processing_ms: int = 0
    decision_ms: int = 0
    total_ms: int = 0


@dataclass
class ClaimStageConfig:
    """Configuration for claim-level stage execution."""

    run_reconciliation: bool = True
    run_enrichment: bool = True  # Run enrichment stage (if enricher configured)
    run_screening: bool = True  # Run screening stage (if screener configured)
    run_processing: bool = True
    run_decision: bool = True  # Run decision stage (if engine configured)
    processing_type: str = "assessment"  # Type of processing to run

    @property
    def run_kind(self) -> str:
        """Determine run kind based on stages."""
        if self.run_reconciliation and self.run_processing:
            return "full"
        elif self.run_processing:
            return "processing_only"
        elif self.run_reconciliation:
            return "reconciliation_only"
        return "none"


@dataclass
class ClaimContext:
    """Mutable context passed between claim-level pipeline stages.

    This context operates at the claim level, aggregating data from all documents
    that have already been processed by the document-level pipeline.
    """

    # Required inputs
    claim_id: str
    workspace_path: Path
    run_id: str

    # Configuration
    stage_config: ClaimStageConfig = field(default_factory=ClaimStageConfig)

    # Timing
    start_time: datetime = field(default_factory=datetime.utcnow)
    timings: ClaimStageTimings = field(default_factory=ClaimStageTimings)

    # Loaded by reconciliation stage
    aggregated_facts: Optional[Dict[str, Any]] = None
    facts_run_id: Optional[str] = None  # Run ID the facts came from
    reconciliation_report: Optional[Any] = None  # ReconciliationReport from reconciliation stage

    # Set by screening stage
    screening_result: Optional[Dict[str, Any]] = None

    # Set by processing stage
    processing_type: str = "assessment"
    processing_result: Optional[Dict[str, Any]] = None

    # Set by decision stage
    decision_result: Optional[Dict[str, Any]] = None

    # Streaming callbacks for live progress
    on_token_update: Optional[Callable[[int, int], None]] = None  # (input_tokens, output_tokens)
    on_stage_update: Optional[Callable[[str, str], None]] = None  # (stage_name, status)
    on_llm_start: Optional[Callable[[int], None]] = None  # (total_llm_calls)
    on_llm_progress: Optional[Callable[[int], None]] = None  # (increment)

    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0

    # Compliance/versioning
    version_bundle_id: Optional[str] = None
    prompt_version: Optional[str] = None
    extraction_bundle_id: Optional[str] = None

    # Status tracking
    status: str = "pending"  # "pending", "running", "success", "error"
    error: Optional[str] = None
    current_stage: str = "setup"

    def notify_token_update(self, input_tokens: int, output_tokens: int) -> None:
        """Update token counts and notify callback if set."""
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        if self.on_token_update:
            try:
                self.on_token_update(input_tokens, output_tokens)
            except Exception:
                pass  # Don't let callback errors break the pipeline

    def notify_stage_update(self, stage_name: str, status: str) -> None:
        """Notify stage status change."""
        self.current_stage = stage_name
        if self.on_stage_update:
            try:
                self.on_stage_update(stage_name, status)
            except Exception:
                pass  # Don't let callback errors break the pipeline


@dataclass
class ClaimProcessingResult:
    """Result of claim-level processing."""

    claim_id: str
    run_id: str
    status: str  # "success", "error"
    processing_type: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timings: Optional[ClaimStageTimings] = None

    # Versioning info
    prompt_version: Optional[str] = None
    extraction_bundle_id: Optional[str] = None

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
