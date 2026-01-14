"""Storage protocol defining the abstract interface for data access.

This protocol defines all methods that storage implementations must provide.
The primary implementation is FileStorage, but this allows for future
database implementations without changing consuming code.
"""

from pathlib import Path
from typing import Protocol, Optional, runtime_checkable

from .models import (
    ClaimRef,
    DocRef,
    DocBundle,
    DocText,
    RunRef,
    RunBundle,
    LabelSummary,
)


@runtime_checkable
class Storage(Protocol):
    """Abstract storage interface for document and run data access.

    All methods operate on IDs, not paths. Path resolution is internal
    to the implementation.
    """

    # -------------------------------------------------------------------------
    # Discovery / Listing
    # -------------------------------------------------------------------------

    def list_claims(self) -> list[ClaimRef]:
        """List all claims with document counts.

        Returns:
            List of ClaimRef objects with claim_id, claim_folder, and doc_count.
        """
        ...

    def list_docs(self, claim_id: str) -> list[DocRef]:
        """List all documents in a claim.

        Args:
            claim_id: Claim identifier (or claim folder name).

        Returns:
            List of DocRef objects for documents in the claim.
        """
        ...

    def list_runs(self) -> list[RunRef]:
        """List all completed runs (global runs only).

        Returns:
            List of RunRef objects for runs with .complete marker.
        """
        ...

    # -------------------------------------------------------------------------
    # Document Access
    # -------------------------------------------------------------------------

    def get_doc(self, doc_id: str) -> Optional[DocBundle]:
        """Get full document bundle by doc_id.

        Args:
            doc_id: Document identifier (12-char hash).

        Returns:
            DocBundle with metadata and resolved paths, or None if not found.
        """
        ...

    def get_doc_text(self, doc_id: str) -> Optional[DocText]:
        """Get document text content (pages.json).

        Args:
            doc_id: Document identifier.

        Returns:
            DocText with page content, or None if not found.
        """
        ...

    def get_doc_source_path(self, doc_id: str) -> Optional[Path]:
        """Get path to document source file (PDF/image/txt).

        Args:
            doc_id: Document identifier.

        Returns:
            Path to source file, or None if not found.
        """
        ...

    def find_doc_claim(self, doc_id: str) -> Optional[str]:
        """Find which claim contains a document.

        Args:
            doc_id: Document identifier.

        Returns:
            claim_id if found, None otherwise.
        """
        ...

    # -------------------------------------------------------------------------
    # Run-Scoped Access
    # -------------------------------------------------------------------------

    def get_run(self, run_id: str) -> Optional[RunBundle]:
        """Get full run bundle by run_id.

        Args:
            run_id: Run identifier.

        Returns:
            RunBundle with manifest/summary/metrics, or None if not found.
        """
        ...

    def get_extraction(
        self, run_id: str, doc_id: str, claim_id: Optional[str] = None
    ) -> Optional[dict]:
        """Get extraction result for a document in a specific run.

        Args:
            run_id: Run identifier.
            doc_id: Document identifier.
            claim_id: Optional claim_id hint for faster lookup.

        Returns:
            Extraction result dict, or None if not found.
        """
        ...

    # -------------------------------------------------------------------------
    # Labels (Document-Scoped, Run-Independent)
    # -------------------------------------------------------------------------

    def get_label(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get label data for a document.

        Labels are stored per-document at docs/{doc_id}/labels/latest.json,
        independent of extraction runs.

        Args:
            doc_id: Document identifier.
            claim_id: Optional claim ID for disambiguation when doc_id exists in multiple claims.

        Returns:
            Label dict (LabelResult schema), or None if not found.
        """
        ...

    def save_label(self, doc_id: str, label_data: dict) -> None:
        """Save label data for a document (atomic write).

        Args:
            doc_id: Document identifier.
            label_data: Label dict conforming to LabelResult schema.

        Raises:
            ValueError: If doc_id not found.
            IOError: If write fails.
        """
        ...

    def get_label_summary(self, doc_id: str) -> Optional[LabelSummary]:
        """Get label summary for a document (from index if available).

        Args:
            doc_id: Document identifier.

        Returns:
            LabelSummary with counts, or None if no label exists.
        """
        ...

    # -------------------------------------------------------------------------
    # Index Operations
    # -------------------------------------------------------------------------

    def has_indexes(self) -> bool:
        """Check if indexes are available.

        Returns:
            True if registry indexes exist and are readable.
        """
        ...

    def get_index_meta(self) -> Optional[dict]:
        """Get index registry metadata.

        Returns:
            Registry metadata dict with build timestamp and counts.
        """
        ...


@runtime_checkable
class DocStore(Protocol):
    """Document access interface."""

    def list_claims(self) -> list[ClaimRef]:
        ...

    def list_docs(self, claim_id: str) -> list[DocRef]:
        ...

    def get_doc(self, doc_id: str) -> Optional[DocBundle]:
        ...

    def get_doc_text(self, doc_id: str) -> Optional[DocText]:
        ...

    def get_doc_source_path(self, doc_id: str) -> Optional[Path]:
        ...

    def find_doc_claim(self, doc_id: str) -> Optional[str]:
        ...


@runtime_checkable
class RunStore(Protocol):
    """Run-scoped access interface."""

    def list_runs(self) -> list[RunRef]:
        ...

    def get_run(self, run_id: str) -> Optional[RunBundle]:
        ...

    def get_extraction(
        self, run_id: str, doc_id: str, claim_id: Optional[str] = None
    ) -> Optional[dict]:
        ...


@runtime_checkable
class LabelStore(Protocol):
    """Label access interface."""

    def get_label(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        ...

    def save_label(self, doc_id: str, label_data: dict) -> None:
        ...

    def get_label_summary(self, doc_id: str) -> Optional[LabelSummary]:
        ...
