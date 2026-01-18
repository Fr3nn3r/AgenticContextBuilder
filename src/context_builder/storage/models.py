"""Data models for the Storage abstraction layer.

These models are used for index records and storage responses.
They are designed to be lightweight references, not full data objects.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal


@dataclass
class ClaimRef:
    """Reference to a claim for listing purposes."""

    claim_id: str
    claim_folder: str  # Actual folder name (may differ from claim_id)
    doc_count: int = 0


@dataclass
class DocRef:
    """Reference to a document for listing purposes."""

    doc_id: str
    claim_id: str
    claim_folder: str
    doc_type: str
    filename: str
    source_type: Literal["pdf", "image", "text"]
    language: str = "unknown"
    page_count: int = 1
    has_pdf: bool = False
    has_text: bool = False
    has_images: bool = False
    doc_root: str = ""  # Path to doc folder (relative to output)


@dataclass
class DocBundle:
    """Full document data bundle for detail views."""

    doc_id: str
    claim_id: str
    claim_folder: str
    metadata: dict  # Full doc.json content
    doc_root: Path  # Absolute path to doc folder


@dataclass
class DocText:
    """Document text content (pages.json)."""

    doc_id: str
    pages: list[dict]  # List of {page: int, text: str, text_md5: str}


@dataclass
class RunRef:
    """Reference to a run for listing purposes."""

    run_id: str
    status: Literal["complete", "partial", "failed"]
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    claims_count: int = 0
    docs_count: int = 0
    run_root: str = ""  # Path to run folder (relative to output)


@dataclass
class RunBundle:
    """Full run data bundle for detail views."""

    run_id: str
    status: str
    manifest: Optional[dict] = None  # manifest.json content
    summary: Optional[dict] = None  # summary.json content
    metrics: Optional[dict] = None  # metrics.json content
    run_root: Path = field(default_factory=Path)


@dataclass
class LabelSummary:
    """Summary of labels for a document (for index)."""

    doc_id: str
    claim_id: str
    has_label: bool = False
    labeled_count: int = 0
    unverifiable_count: int = 0
    unlabeled_count: int = 0
    updated_at: Optional[str] = None


@dataclass
class RegistryMeta:
    """Metadata about the index registry."""

    built_at: str
    doc_count: int = 0
    label_count: int = 0
    run_count: int = 0
    claim_count: int = 0


@dataclass
class SourceFileRef:
    """Reference to a source file in a document."""

    filename: str
    file_type: Literal["pdf", "image", "text"]
    path: str  # Relative path from doc root


@dataclass
class ExtractionRef:
    """Reference to an extraction result in a run."""

    doc_id: str
    claim_id: str
    run_id: str
