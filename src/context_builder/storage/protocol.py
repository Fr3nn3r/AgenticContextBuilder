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
    SourceFileRef,
    ExtractionRef,
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

    def get_doc_text(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[DocText]:
        """Get document text content (pages.json).

        Args:
            doc_id: Document identifier.
            claim_id: Optional claim_id hint for faster lookup.

        Returns:
            DocText with page content, or None if not found.
        """
        ...

    def get_doc_source_path(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[Path]:
        """Get path to document source file (PDF/image/txt).

        Args:
            doc_id: Document identifier.
            claim_id: Optional claim_id hint for faster lookup.

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

    def get_doc_text(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[DocText]:
        ...

    def get_doc_source_path(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[Path]:
        ...

    def find_doc_claim(self, doc_id: str) -> Optional[str]:
        ...

    def get_doc_metadata(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get document metadata (doc.json) by doc_id.

        Args:
            doc_id: Document identifier.
            claim_id: Optional claim_id hint for faster lookup when doc_id
                      exists in multiple claims.

        Returns:
            Document metadata dict (doc.json content), or None if not found.
        """
        ...

    def get_source_files(self, doc_id: str, claim_id: Optional[str] = None) -> list[SourceFileRef]:
        """List source files for a document.

        Args:
            doc_id: Document identifier.
            claim_id: Optional claim_id hint for faster lookup.

        Returns:
            List of SourceFileRef objects for files in the source/ directory.
        """
        ...

    def get_doc_azure_di(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get Azure Document Intelligence data for a document.

        Args:
            doc_id: Document identifier.
            claim_id: Optional claim_id hint for faster lookup.

        Returns:
            Azure DI data dict, or None if not available.
        """
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

    def get_run_manifest(self, run_id: str) -> Optional[dict]:
        """Get run manifest.json content.

        Args:
            run_id: Run identifier.

        Returns:
            Manifest dict, or None if not found.
        """
        ...

    def get_run_summary(self, run_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get run summary.json content.

        Args:
            run_id: Run identifier.
            claim_id: Optional claim_id for claim-scoped summary (logs/summary.json).

        Returns:
            Summary dict, or None if not found.
        """
        ...

    def list_extractions(self, run_id: str, claim_id: Optional[str] = None) -> list[ExtractionRef]:
        """List all extractions in a run.

        Args:
            run_id: Run identifier.
            claim_id: Optional claim_id to filter by claim.

        Returns:
            List of ExtractionRef objects.
        """
        ...

    def save_run_manifest(self, run_id: str, manifest: dict) -> None:
        """Save run manifest (atomic write).

        Args:
            run_id: Run identifier.
            manifest: Manifest data to save.

        Raises:
            IOError: If write fails.
        """
        ...

    def save_run_summary(self, run_id: str, summary: dict, claim_id: Optional[str] = None) -> None:
        """Save run summary (atomic write).

        Args:
            run_id: Run identifier.
            summary: Summary data to save.
            claim_id: Optional claim_id for claim-scoped summary.

        Raises:
            IOError: If write fails.
        """
        ...

    def save_extraction(self, run_id: str, doc_id: str, claim_id: str, data: dict) -> None:
        """Save extraction result for a document (atomic write).

        Args:
            run_id: Run identifier.
            doc_id: Document identifier.
            claim_id: Claim identifier.
            data: Extraction data to save.

        Raises:
            IOError: If write fails.
        """
        ...

    def mark_run_complete(self, run_id: str) -> None:
        """Mark a run as complete (create .complete marker).

        Args:
            run_id: Run identifier.

        Raises:
            IOError: If write fails.
        """
        ...

    def list_runs_for_doc(self, doc_id: str, claim_id: str) -> list[str]:
        """List all run IDs that have extraction for a document.

        Args:
            doc_id: Document identifier.
            claim_id: Claim identifier.

        Returns:
            List of run IDs (most recent first).
        """
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

    def get_label_history(self, doc_id: str) -> list[dict]:
        """Get all historical versions of labels for a document.

        Args:
            doc_id: Document identifier.

        Returns:
            List of label versions, oldest to newest.
        """
        ...

    def count_labels_for_claim(self, claim_id: str) -> int:
        """Count the number of labeled documents in a claim.

        Args:
            claim_id: Claim identifier.

        Returns:
            Number of documents with labels in the claim.
        """
        ...


@runtime_checkable
class PendingStore(Protocol):
    """Interface for pending/staging claim storage.

    Note: This is for the ephemeral staging area, not the main workspace data.
    The staging area holds uploads before they enter the pipeline.
    """

    def get_pending_manifest(self, claim_id: str) -> Optional[dict]:
        """Get pending claim manifest.

        Args:
            claim_id: Pending claim identifier.

        Returns:
            Manifest dict, or None if not found.
        """
        ...

    def save_pending_manifest(self, claim_id: str, data: dict) -> None:
        """Save pending claim manifest.

        Args:
            claim_id: Pending claim identifier.
            data: Manifest data to save.
        """
        ...

    def list_pending_claims(self) -> list[str]:
        """List all pending claim IDs.

        Returns:
            List of claim IDs in staging.
        """
        ...

    def save_pending_document(
        self, claim_id: str, doc_id: str, filename: str, content: bytes
    ) -> None:
        """Save a document to pending storage.

        Args:
            claim_id: Pending claim identifier.
            doc_id: Document identifier.
            filename: Original filename.
            content: File content.
        """
        ...

    def delete_pending_claim(self, claim_id: str) -> bool:
        """Delete a pending claim and all its documents.

        Args:
            claim_id: Pending claim identifier.

        Returns:
            True if deletion was successful.
        """
        ...
