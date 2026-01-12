"""Pipeline package for batch claims processing."""

from context_builder.pipeline.discovery import (
    DiscoveredDocument,
    DiscoveredClaim,
    SourceType,
    discover_claims,
    doc_id_from_content,
    doc_id_from_bytes,
)
from context_builder.pipeline.paths import (
    DocPaths,
    ClaimPaths,
    RunPaths,
    create_doc_structure,
)
from context_builder.pipeline.text import build_pages_json
from context_builder.pipeline.state import is_claim_processed, get_latest_run
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from context_builder.pipeline.run import ClaimResult, DocResult, process_claim, process_document

__all__ = [
    "DiscoveredDocument",
    "DiscoveredClaim",
    "discover_claims",
    "doc_id_from_content",
    "DocPaths",
    "ClaimPaths",
    "RunPaths",
    "create_doc_structure",
    "build_pages_json",
    "is_claim_processed",
    "get_latest_run",
    "process_claim",
    "process_document",
    "ClaimResult",
    "DocResult",
]


def __getattr__(name: str):
    if name in {"process_claim", "process_document", "ClaimResult", "DocResult"}:
        from context_builder.pipeline import run as _run
        return getattr(_run, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
