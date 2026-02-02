"""Index reader utilities for JSONL index files.

Provides efficient reading of JSONL index files and building of
lookup dictionaries for O(1) access by ID.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Iterator

from .models import DocRef, RunRef, LabelSummary, RegistryMeta

logger = logging.getLogger(__name__)


# Index file names
DOC_INDEX_FILE = "doc_index.jsonl"
LABEL_INDEX_FILE = "label_index.jsonl"
RUN_INDEX_FILE = "run_index.jsonl"
CLAIMS_INDEX_FILE = "claims_index.jsonl"
REGISTRY_META_FILE = "registry_meta.json"


def read_jsonl(file_path: Path) -> Iterator[dict]:
    """Read JSONL file and yield each record.

    Args:
        file_path: Path to JSONL file.

    Yields:
        Parsed JSON dict for each line.
    """
    if not file_path.exists():
        return

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON on line {line_num} in {file_path}: {e}")
                continue


def write_jsonl(file_path: Path, records: list[dict]) -> int:
    """Write records to JSONL file.

    Args:
        file_path: Path to JSONL file.
        records: List of dicts to write.

    Returns:
        Number of records written.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return len(records)


class IndexReader:
    """Reader for the registry index files.

    Loads indexes lazily and builds lookup dictionaries for fast access.
    """

    def __init__(self, registry_dir: Path):
        """Initialize index reader.

        Args:
            registry_dir: Path to registry directory (output/registry/).
        """
        self.registry_dir = registry_dir
        self._doc_index: Optional[dict[str, DocRef]] = None
        self._doc_by_claim: Optional[dict[str, list[DocRef]]] = None
        self._label_index: Optional[dict[str, LabelSummary]] = None
        self._run_index: Optional[dict[str, RunRef]] = None
        self._meta: Optional[RegistryMeta] = None
        self._claim_folders: Optional[dict[str, str]] = None  # claim_id -> claim_folder
        self._claims_index: Optional[list[dict]] = None

    @property
    def is_available(self) -> bool:
        """Check if indexes exist and are readable."""
        meta_path = self.registry_dir / REGISTRY_META_FILE
        doc_path = self.registry_dir / DOC_INDEX_FILE
        return meta_path.exists() and doc_path.exists()

    def get_meta(self) -> Optional[RegistryMeta]:
        """Get registry metadata."""
        if self._meta is not None:
            return self._meta

        meta_path = self.registry_dir / REGISTRY_META_FILE
        if not meta_path.exists():
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._meta = RegistryMeta(
                    built_at=data.get("built_at", ""),
                    doc_count=data.get("doc_count", 0),
                    label_count=data.get("label_count", 0),
                    run_count=data.get("run_count", 0),
                    claim_count=data.get("claim_count", 0),
                )
                return self._meta
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read registry meta: {e}")
            return None

    def _load_doc_index(self) -> None:
        """Load document index into memory."""
        if self._doc_index is not None:
            return

        self._doc_index = {}
        self._doc_by_claim = {}
        self._claim_folders = {}

        doc_path = self.registry_dir / DOC_INDEX_FILE
        for record in read_jsonl(doc_path):
            doc_ref = DocRef(
                doc_id=record.get("doc_id", ""),
                claim_id=record.get("claim_id", ""),
                claim_folder=record.get("claim_folder", ""),
                doc_type=record.get("doc_type", "unknown"),
                filename=record.get("filename", ""),
                source_type=record.get("source_type", "text"),
                language=record.get("language", "unknown"),
                page_count=record.get("page_count", 1),
                has_pdf=record.get("has_pdf", False),
                has_text=record.get("has_text", False),
                has_images=record.get("has_images", False),
                doc_root=record.get("doc_root", ""),
            )
            self._doc_index[doc_ref.doc_id] = doc_ref

            # Build claim -> docs mapping
            claim_key = doc_ref.claim_id or doc_ref.claim_folder
            if claim_key not in self._doc_by_claim:
                self._doc_by_claim[claim_key] = []
            self._doc_by_claim[claim_key].append(doc_ref)

            # Track claim_id -> claim_folder mapping
            if doc_ref.claim_id and doc_ref.claim_folder:
                self._claim_folders[doc_ref.claim_id] = doc_ref.claim_folder
                self._claim_folders[doc_ref.claim_folder] = doc_ref.claim_folder

    def _load_label_index(self) -> None:
        """Load label index into memory."""
        if self._label_index is not None:
            return

        self._label_index = {}
        label_path = self.registry_dir / LABEL_INDEX_FILE
        for record in read_jsonl(label_path):
            summary = LabelSummary(
                doc_id=record.get("doc_id", ""),
                claim_id=record.get("claim_id", ""),
                has_label=record.get("has_label", False),
                labeled_count=record.get("labeled_count", 0),
                unverifiable_count=record.get("unverifiable_count", 0),
                unlabeled_count=record.get("unlabeled_count", 0),
                updated_at=record.get("updated_at"),
            )
            self._label_index[summary.doc_id] = summary

    def _load_run_index(self) -> None:
        """Load run index into memory."""
        if self._run_index is not None:
            return

        self._run_index = {}
        run_path = self.registry_dir / RUN_INDEX_FILE
        for record in read_jsonl(run_path):
            run_ref = RunRef(
                run_id=record.get("run_id", ""),
                status=record.get("status", "unknown"),
                started_at=record.get("started_at"),
                ended_at=record.get("ended_at"),
                claims_count=record.get("claims_count", 0),
                docs_count=record.get("docs_count", 0),
                run_root=record.get("run_root", ""),
            )
            self._run_index[run_ref.run_id] = run_ref

    # -------------------------------------------------------------------------
    # Public Access Methods
    # -------------------------------------------------------------------------

    def get_doc(self, doc_id: str) -> Optional[DocRef]:
        """Get document reference by doc_id."""
        self._load_doc_index()
        return self._doc_index.get(doc_id) if self._doc_index else None

    def get_docs_by_claim(self, claim_id: str) -> list[DocRef]:
        """Get all documents for a claim."""
        self._load_doc_index()
        if not self._doc_by_claim:
            return []
        # Try both claim_id and claim_folder as keys
        docs = self._doc_by_claim.get(claim_id, [])
        if not docs and self._claim_folders:
            # Try to resolve claim_folder from claim_id
            folder = self._claim_folders.get(claim_id)
            if folder:
                docs = self._doc_by_claim.get(folder, [])
        return docs

    def get_all_docs(self) -> list[DocRef]:
        """Get all document references."""
        self._load_doc_index()
        return list(self._doc_index.values()) if self._doc_index else []

    def get_all_claims(self) -> list[tuple[str, str, int]]:
        """Get all claims as (claim_id, claim_folder, doc_count) tuples."""
        self._load_doc_index()
        if not self._doc_by_claim:
            return []

        claims = []
        seen_folders = set()
        for key, docs in self._doc_by_claim.items():
            if not docs:
                continue
            claim_folder = docs[0].claim_folder
            if claim_folder in seen_folders:
                continue
            seen_folders.add(claim_folder)
            claim_id = docs[0].claim_id or claim_folder
            claims.append((claim_id, claim_folder, len(docs)))
        return claims

    def get_label_summary(self, doc_id: str) -> Optional[LabelSummary]:
        """Get label summary for a document."""
        self._load_label_index()
        return self._label_index.get(doc_id) if self._label_index else None

    def get_all_label_summaries(self) -> list[LabelSummary]:
        """Get all label summaries."""
        self._load_label_index()
        return list(self._label_index.values()) if self._label_index else []

    def get_run(self, run_id: str) -> Optional[RunRef]:
        """Get run reference by run_id."""
        self._load_run_index()
        return self._run_index.get(run_id) if self._run_index else None

    def get_all_runs(self) -> list[RunRef]:
        """Get all run references."""
        self._load_run_index()
        return list(self._run_index.values()) if self._run_index else []

    def find_claim_for_doc(self, doc_id: str) -> Optional[str]:
        """Find claim_id for a document."""
        doc = self.get_doc(doc_id)
        return doc.claim_id if doc else None

    def get_claim_folder(self, claim_id: str) -> Optional[str]:
        """Get claim folder name for a claim_id."""
        self._load_doc_index()
        return self._claim_folders.get(claim_id) if self._claim_folders else None

    def get_all_claim_summaries(self) -> Optional[list[dict]]:
        """Get pre-computed claim summaries from claims_index.jsonl.

        Returns:
            List of claim summary dicts if index exists, None otherwise.
        """
        if self._claims_index is not None:
            return self._claims_index

        claims_path = self.registry_dir / CLAIMS_INDEX_FILE
        if not claims_path.exists():
            return None

        self._claims_index = list(read_jsonl(claims_path))
        return self._claims_index

    def invalidate(self) -> None:
        """Clear cached indexes (force reload on next access)."""
        self._doc_index = None
        self._doc_by_claim = None
        self._label_index = None
        self._run_index = None
        self._meta = None
        self._claim_folders = None
        self._claims_index = None
