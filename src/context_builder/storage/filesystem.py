"""Filesystem-based Storage implementation.

Uses JSONL indexes for fast lookups when available,
falls back to filesystem scanning with warning when indexes are missing.

Includes compliance features:
- Append-only label history for audit trails
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import (
    ClaimRef,
    DocRef,
    DocBundle,
    DocText,
    RunRef,
    RunBundle,
    LabelSummary,
)
from .index_reader import IndexReader

logger = logging.getLogger(__name__)

# Module-level set tracking which registry paths have already had "no index" warnings
# This prevents duplicate warnings when multiple FileStorage instances are created
_warned_registry_paths: set[str] = set()


class FileStorage:
    """Filesystem-based storage implementation with index support.

    Uses indexes from output/registry/ for O(1) lookups when available.
    Falls back to filesystem scanning with a warning when indexes are missing.
    """

    def __init__(self, output_root: Path):
        """Initialize FileStorage.

        Args:
            output_root: Root output directory (e.g., output/ or output/claims/).
                         Will normalize to find claims/ and runs/ subdirectories.
        """
        self.output_root = Path(output_root)

        # Normalize to find the actual output structure
        # Support both output/ and output/claims/ as root
        if (self.output_root / "claims").exists():
            self.claims_dir = self.output_root / "claims"
            self.runs_dir = self.output_root / "runs"
            self.registry_dir = self.output_root / "registry"
        elif self.output_root.name == "claims":
            self.claims_dir = self.output_root
            self.runs_dir = self.output_root.parent / "runs"
            self.registry_dir = self.output_root.parent / "registry"
        else:
            # Assume output_root is the claims directory
            self.claims_dir = self.output_root
            self.runs_dir = self.output_root.parent / "runs"
            self.registry_dir = self.output_root.parent / "registry"

        self._index_reader = IndexReader(self.registry_dir)

    def _warn_no_index(self, operation: str) -> None:
        """Log warning about missing indexes (once per registry path per session)."""
        registry_key = str(self.registry_dir)
        if registry_key not in _warned_registry_paths:
            logger.warning(
                f"Registry indexes not found at {self.registry_dir}. "
                f"Falling back to filesystem scan for '{operation}'. "
                f"Run 'python -m context_builder.cli index build' to create indexes."
            )
            _warned_registry_paths.add(registry_key)

    # -------------------------------------------------------------------------
    # Discovery / Listing
    # -------------------------------------------------------------------------

    def list_claims(self) -> list[ClaimRef]:
        """List all claims with document counts."""
        if self._index_reader.is_available:
            claims_data = self._index_reader.get_all_claims()
            return [
                ClaimRef(claim_id=cid, claim_folder=folder, doc_count=count)
                for cid, folder, count in claims_data
            ]

        # Fallback to filesystem scan
        self._warn_no_index("list_claims")
        claims = []

        if not self.claims_dir.exists():
            return claims

        for claim_folder in sorted(self.claims_dir.iterdir()):
            if not claim_folder.is_dir():
                continue
            if claim_folder.name.startswith("."):
                continue

            docs_dir = claim_folder / "docs"
            doc_count = 0
            if docs_dir.exists():
                doc_count = sum(1 for d in docs_dir.iterdir() if d.is_dir())

            # Try to extract claim_id from first doc
            claim_id = claim_folder.name
            if docs_dir.exists():
                for doc_folder in docs_dir.iterdir():
                    if doc_folder.is_dir():
                        doc_json = doc_folder / "meta" / "doc.json"
                        if doc_json.exists():
                            try:
                                with open(doc_json, "r", encoding="utf-8") as f:
                                    data = json.load(f)
                                    if data.get("claim_id"):
                                        claim_id = data["claim_id"]
                                        break
                            except (json.JSONDecodeError, IOError):
                                pass

            claims.append(ClaimRef(
                claim_id=claim_id,
                claim_folder=claim_folder.name,
                doc_count=doc_count,
            ))

        return claims

    def list_docs(self, claim_id: str) -> list[DocRef]:
        """List all documents in a claim."""
        if self._index_reader.is_available:
            return self._index_reader.get_docs_by_claim(claim_id)

        # Fallback to filesystem scan
        self._warn_no_index("list_docs")
        docs = []

        # Find claim folder
        claim_folder = self._find_claim_folder(claim_id)
        if not claim_folder:
            return docs

        docs_dir = claim_folder / "docs"
        if not docs_dir.exists():
            return docs

        for doc_folder in sorted(docs_dir.iterdir()):
            if not doc_folder.is_dir():
                continue

            doc_json = doc_folder / "meta" / "doc.json"
            if not doc_json.exists():
                continue

            try:
                with open(doc_json, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

            # Check artifact availability
            source_dir = doc_folder / "source"
            has_pdf = any(source_dir.glob("*.pdf")) if source_dir.exists() else False
            has_text = (doc_folder / "text" / "pages.json").exists()

            docs.append(DocRef(
                doc_id=meta.get("doc_id", doc_folder.name),
                claim_id=meta.get("claim_id", claim_id),
                claim_folder=claim_folder.name,
                doc_type=meta.get("doc_type", "unknown"),
                filename=meta.get("original_filename", ""),
                source_type=meta.get("source_type", "unknown"),
                language=meta.get("language", "unknown"),
                page_count=meta.get("page_count", 1),
                has_pdf=has_pdf,
                has_text=has_text,
                has_images=False,
                doc_root=str(doc_folder.relative_to(self.claims_dir.parent)),
            ))

        return docs

    def list_runs(self) -> list[RunRef]:
        """List all completed runs (global runs only)."""
        if self._index_reader.is_available:
            return self._index_reader.get_all_runs()

        # Fallback to filesystem scan
        self._warn_no_index("list_runs")
        runs = []

        if not self.runs_dir.exists():
            return runs

        for run_folder in sorted(self.runs_dir.iterdir(), reverse=True):
            if not run_folder.is_dir():
                continue
            if not run_folder.name.startswith("run_"):
                continue

            # Only include complete runs
            if not (run_folder / ".complete").exists():
                continue

            # Read metadata
            manifest = {}
            summary = {}

            manifest_path = run_folder / "manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

            summary_path = run_folder / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

            runs.append(RunRef(
                run_id=run_folder.name,
                status=summary.get("status", "complete"),
                started_at=manifest.get("started_at"),
                ended_at=manifest.get("ended_at") or summary.get("completed_at"),
                claims_count=manifest.get("claims_count", 0),
                docs_count=summary.get("docs_total", 0),
                run_root=str(run_folder.relative_to(self.runs_dir.parent)),
            ))

        return runs

    # -------------------------------------------------------------------------
    # Document Access
    # -------------------------------------------------------------------------

    def get_doc(self, doc_id: str) -> Optional[DocBundle]:
        """Get full document bundle by doc_id."""
        doc_folder = self._find_doc_folder(doc_id)
        if not doc_folder:
            return None

        doc_json = doc_folder / "meta" / "doc.json"
        if not doc_json.exists():
            return None

        try:
            with open(doc_json, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

        # Determine claim_folder from path
        claim_folder = doc_folder.parent.parent.name

        return DocBundle(
            doc_id=metadata.get("doc_id", doc_id),
            claim_id=metadata.get("claim_id", claim_folder),
            claim_folder=claim_folder,
            metadata=metadata,
            doc_root=doc_folder,
        )

    def get_doc_text(self, doc_id: str) -> Optional[DocText]:
        """Get document text content (pages.json)."""
        doc_folder = self._find_doc_folder(doc_id)
        if not doc_folder:
            return None

        pages_json = doc_folder / "text" / "pages.json"
        if not pages_json.exists():
            return None

        try:
            with open(pages_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

        return DocText(
            doc_id=doc_id,
            pages=data.get("pages", []),
        )

    def get_doc_source_path(self, doc_id: str) -> Optional[Path]:
        """Get path to document source file (PDF/image/txt)."""
        doc_folder = self._find_doc_folder(doc_id)
        if not doc_folder:
            return None

        source_dir = doc_folder / "source"
        if not source_dir.exists():
            return None

        # Look for source files in priority order
        for pattern in ["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.txt"]:
            files = list(source_dir.glob(pattern))
            if files:
                return files[0]

        return None

    def find_doc_claim(self, doc_id: str) -> Optional[str]:
        """Find which claim contains a document."""
        if self._index_reader.is_available:
            return self._index_reader.find_claim_for_doc(doc_id)

        doc = self.get_doc(doc_id)
        return doc.claim_id if doc else None

    # -------------------------------------------------------------------------
    # Run-Scoped Access
    # -------------------------------------------------------------------------

    def get_run(self, run_id: str) -> Optional[RunBundle]:
        """Get full run bundle by run_id."""
        run_folder = self.runs_dir / run_id
        if not run_folder.exists():
            return None

        manifest = None
        summary = None
        metrics = None

        manifest_path = run_folder / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        summary_path = run_folder / "summary.json"
        if summary_path.exists():
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        metrics_path = run_folder / "metrics.json"
        if metrics_path.exists():
            try:
                with open(metrics_path, "r", encoding="utf-8") as f:
                    metrics = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return RunBundle(
            run_id=run_id,
            status=summary.get("status", "unknown") if summary else "unknown",
            manifest=manifest,
            summary=summary,
            metrics=metrics,
            run_root=run_folder,
        )

    def get_extraction(
        self, run_id: str, doc_id: str, claim_id: Optional[str] = None
    ) -> Optional[dict]:
        """Get extraction result for a document in a specific run."""
        # First try claim-scoped run path
        if claim_id:
            claim_folder = self._find_claim_folder(claim_id)
            if claim_folder:
                extraction_path = (
                    claim_folder / "runs" / run_id / "extraction" / f"{doc_id}.json"
                )
                if extraction_path.exists():
                    try:
                        with open(extraction_path, "r", encoding="utf-8") as f:
                            return json.load(f)
                    except (json.JSONDecodeError, IOError):
                        pass

        # If no claim_id provided, find doc first to get claim
        if not claim_id:
            doc = self.get_doc(doc_id)
            if doc:
                claim_folder = self._find_claim_folder(doc.claim_id)
                if claim_folder:
                    extraction_path = (
                        claim_folder / "runs" / run_id / "extraction" / f"{doc_id}.json"
                    )
                    if extraction_path.exists():
                        try:
                            with open(extraction_path, "r", encoding="utf-8") as f:
                                return json.load(f)
                        except (json.JSONDecodeError, IOError):
                            pass

        return None

    # -------------------------------------------------------------------------
    # Labels (Document-Scoped, Run-Independent)
    # -------------------------------------------------------------------------

    def get_label(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get label data for a document.

        Args:
            doc_id: Document ID.
            claim_id: Optional claim ID for disambiguation when doc_id exists in multiple claims.
        """
        # If claim_id provided, look in that specific claim folder first
        if claim_id:
            claim_folder = self._find_claim_folder(claim_id)
            if claim_folder:
                label_path = claim_folder / "docs" / doc_id / "labels" / "latest.json"
                if label_path.exists():
                    try:
                        with open(label_path, "r", encoding="utf-8") as f:
                            return json.load(f)
                    except (json.JSONDecodeError, IOError):
                        pass

        # Fallback to finding doc folder by doc_id alone
        doc_folder = self._find_doc_folder(doc_id)
        if not doc_folder:
            return None

        label_path = doc_folder / "labels" / "latest.json"
        if not label_path.exists():
            return None

        try:
            with open(label_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def save_label(self, doc_id: str, label_data: dict) -> None:
        """Save label data for a document (atomic write) with version history.

        Compliance: Also appends to history.jsonl for audit trail.
        """
        doc_folder = self._find_doc_folder(doc_id)
        if not doc_folder:
            raise ValueError(f"Document not found: {doc_id}")

        labels_dir = doc_folder / "labels"
        labels_dir.mkdir(parents=True, exist_ok=True)

        # Add version metadata
        version_ts = datetime.utcnow().isoformat() + "Z"
        versioned_data = {
            **label_data,
            "_version_metadata": {
                "saved_at": version_ts,
                "version_number": self._get_next_label_version(labels_dir),
            },
        }

        label_path = labels_dir / "latest.json"
        tmp_path = labels_dir / "latest.json.tmp"

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(versioned_data, f, indent=2, ensure_ascii=False, default=str)
            tmp_path.replace(label_path)

            # Append to history for compliance (append-only)
            self._append_label_history(labels_dir, versioned_data)
        except IOError as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise IOError(f"Failed to save label: {e}")

    def _get_next_label_version(self, labels_dir: Path) -> int:
        """Get the next version number for a label."""
        history_path = labels_dir / "history.jsonl"
        if not history_path.exists():
            return 1
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                return sum(1 for _ in f) + 1
        except IOError:
            return 1

    def _append_label_history(self, labels_dir: Path, label_data: dict) -> None:
        """Append label version to history (append-only for compliance)."""
        history_path = labels_dir / "history.jsonl"
        try:
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(label_data, ensure_ascii=False, default=str) + "\n")
        except IOError as e:
            logger.warning(f"Failed to append label history: {e}")

    def get_label_history(self, doc_id: str) -> List[dict]:
        """Get all historical versions of labels for a document.

        Returns list from oldest to newest.
        """
        doc_folder = self._find_doc_folder(doc_id)
        if not doc_folder:
            return []

        history_path = doc_folder / "labels" / "history.jsonl"
        if not history_path.exists():
            return []

        history = []
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        history.append(json.loads(line))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load label history for {doc_id}: {e}")

        return history

    def get_label_summary(self, doc_id: str) -> Optional[LabelSummary]:
        """Get label summary for a document (from index if available)."""
        if self._index_reader.is_available:
            return self._index_reader.get_label_summary(doc_id)

        # Fallback: load full label and compute summary
        label = self.get_label(doc_id)
        if not label:
            return None

        field_labels = label.get("field_labels", [])
        labeled_count = sum(1 for fl in field_labels if fl.get("state") == "LABELED")
        unverifiable_count = sum(
            1 for fl in field_labels if fl.get("state") == "UNVERIFIABLE"
        )
        unlabeled_count = sum(
            1 for fl in field_labels if fl.get("state") == "UNLABELED"
        )

        review = label.get("review", {})

        return LabelSummary(
            doc_id=doc_id,
            claim_id=label.get("claim_id", ""),
            has_label=True,
            labeled_count=labeled_count,
            unverifiable_count=unverifiable_count,
            unlabeled_count=unlabeled_count,
            updated_at=review.get("reviewed_at"),
        )

    # -------------------------------------------------------------------------
    # Index Operations
    # -------------------------------------------------------------------------

    def has_indexes(self) -> bool:
        """Check if indexes are available."""
        return self._index_reader.is_available

    def get_index_meta(self) -> Optional[dict]:
        """Get index registry metadata."""
        meta = self._index_reader.get_meta()
        if meta:
            return {
                "built_at": meta.built_at,
                "doc_count": meta.doc_count,
                "label_count": meta.label_count,
                "run_count": meta.run_count,
                "claim_count": meta.claim_count,
            }
        return None

    def invalidate_indexes(self) -> None:
        """Clear cached indexes (force reload on next access)."""
        self._index_reader.invalidate()

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _find_claim_folder(self, claim_id: str) -> Optional[Path]:
        """Find claim folder by claim_id or folder name."""
        if not self.claims_dir.exists():
            return None

        # Try index first
        if self._index_reader.is_available:
            folder_name = self._index_reader.get_claim_folder(claim_id)
            if folder_name:
                folder_path = self.claims_dir / folder_name
                if folder_path.exists():
                    return folder_path

        # Direct match by folder name
        direct_path = self.claims_dir / claim_id
        if direct_path.exists():
            return direct_path

        # Scan for matching claim_id in doc.json files
        for folder in self.claims_dir.iterdir():
            if not folder.is_dir():
                continue

            docs_dir = folder / "docs"
            if not docs_dir.exists():
                continue

            for doc_folder in docs_dir.iterdir():
                if not doc_folder.is_dir():
                    continue

                doc_json = doc_folder / "meta" / "doc.json"
                if doc_json.exists():
                    try:
                        with open(doc_json, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if data.get("claim_id") == claim_id:
                                return folder
                    except (json.JSONDecodeError, IOError):
                        pass
                break  # Only check first doc in each claim

        return None

    def _find_doc_folder(self, doc_id: str) -> Optional[Path]:
        """Find document folder by doc_id."""
        # Try index first
        if self._index_reader.is_available:
            doc_ref = self._index_reader.get_doc(doc_id)
            if doc_ref and doc_ref.doc_root:
                # doc_root is relative to output parent
                doc_path = self.claims_dir.parent / doc_ref.doc_root
                if doc_path.exists():
                    return doc_path

        # Fallback: scan all claims
        if not self.claims_dir.exists():
            return None

        for claim_folder in self.claims_dir.iterdir():
            if not claim_folder.is_dir():
                continue

            doc_folder = claim_folder / "docs" / doc_id
            if doc_folder.exists():
                return doc_folder

        return None
