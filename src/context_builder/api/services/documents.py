"""Document-focused API services."""

import json
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from fastapi import HTTPException

from context_builder.api.models import DocPayload, DocSummary
from context_builder.api.services.utils import (
    extract_claim_number,
    get_latest_run_dir_for_claim,
    get_run_dir_by_id,
)
from context_builder.storage import StorageFacade


class DocumentsService:
    """Service layer for document listing and retrieval."""

    def __init__(self, data_dir: Path, storage_factory: Callable[[], StorageFacade]):
        self.data_dir = data_dir
        self.storage_factory = storage_factory

    def list_docs(self, claim_id: str, run_id: Optional[str] = None) -> List[DocSummary]:
        storage = self.storage_factory()
        claim_dir = self._find_claim_dir(claim_id)
        if not claim_dir or not claim_dir.exists():
            raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

        docs_dir = claim_dir / "docs"
        if not docs_dir.exists():
            raise HTTPException(status_code=404, detail="No documents found")

        run_dir = (
            get_run_dir_by_id(claim_dir, run_id)
            if run_id
            else get_latest_run_dir_for_claim(claim_dir)
        )
        extraction_dir = run_dir / "extraction" if run_dir else None

        docs = []
        for doc_folder in docs_dir.iterdir():
            if not doc_folder.is_dir():
                continue

            doc_id = doc_folder.name
            meta_path = doc_folder / "meta" / "doc.json"

            if not meta_path.exists():
                continue

            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            has_extraction = False
            quality_status = None
            confidence = 0.0
            missing_required_fields: List[str] = []

            if extraction_dir:
                extraction_path = extraction_dir / f"{doc_id}.json"
                has_extraction = extraction_path.exists()
                if has_extraction:
                    with open(extraction_path, "r", encoding="utf-8") as f:
                        ext_data = json.load(f)
                        quality_gate = ext_data.get("quality_gate", {})
                        quality_status = quality_gate.get("status")
                        missing_required_fields = quality_gate.get("missing_required_fields", [])
                        fields = ext_data.get("fields", [])
                        if fields:
                            confidence = sum(field.get("confidence", 0) for field in fields) / len(fields)

            # Use storage layer to check for labels (reads from registry/labels/)
            has_labels = storage.label_store.get_label(doc_id) is not None

            docs.append(DocSummary(
                doc_id=doc_id,
                filename=meta.get("original_filename", "Unknown"),
                doc_type=meta.get("doc_type", "unknown"),
                language=meta.get("language", "es"),
                has_extraction=has_extraction,
                has_labels=has_labels,
                quality_status=quality_status,
                confidence=round(confidence, 2),
                missing_required_fields=missing_required_fields,
            ))

        return docs

    def get_doc(self, doc_id: str, run_id: Optional[str] = None, claim_id: Optional[str] = None) -> DocPayload:
        storage = self.storage_factory()

        # If claim_id is provided, look up document directly in that claim
        # This avoids the issue of duplicate doc_ids across claims (same file MD5)
        if claim_id:
            claim_dir = self._find_claim_dir(claim_id)
            if claim_dir:
                doc_folder = claim_dir / "docs" / doc_id
                meta_path = doc_folder / "meta" / "doc.json"
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    filename = meta.get("original_filename", "Unknown")
                    doc_type = meta.get("doc_type", "unknown")
                    language = meta.get("language", "es")
                    resolved_claim_id = claim_id

                    # Load text
                    pages_json = doc_folder / "text" / "pages.json"
                    pages = []
                    if pages_json.exists():
                        with open(pages_json, "r", encoding="utf-8") as f:
                            pages_data = json.load(f)
                            pages = pages_data.get("pages", [])

                    # Load extraction
                    extraction = None
                    if run_id:
                        extraction = storage.run_store.get_extraction(run_id, doc_id, claim_id=resolved_claim_id)

                    # Load labels
                    labels = storage.label_store.get_label(doc_id)

                    # Check source files
                    has_pdf = False
                    has_image = False
                    source_dir = doc_folder / "source"
                    if source_dir.exists():
                        for source_file in source_dir.iterdir():
                            ext = source_file.suffix.lower()
                            if ext == ".pdf":
                                has_pdf = True
                            elif ext in {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp"}:
                                has_image = True

                    return DocPayload(
                        doc_id=doc_id,
                        claim_id=resolved_claim_id,
                        filename=filename,
                        doc_type=doc_type,
                        language=language,
                        pages=pages,
                        extraction=extraction,
                        labels=labels,
                        has_pdf=has_pdf,
                        has_image=has_image,
                    )

        # Fallback to storage lookup (may find wrong doc if duplicates exist)
        doc_bundle = storage.doc_store.get_doc(doc_id)
        if not doc_bundle:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        meta = doc_bundle.metadata
        filename = meta.get("original_filename", "Unknown")
        doc_type = meta.get("doc_type", "unknown")
        language = meta.get("language", "es")
        resolved_claim_id = doc_bundle.claim_id or extract_claim_number(doc_bundle.claim_folder)

        doc_text = storage.doc_store.get_doc_text(doc_id)
        pages = doc_text.pages if doc_text else []

        extraction = None
        if run_id:
            extraction = storage.run_store.get_extraction(run_id, doc_id, claim_id=resolved_claim_id)

        labels = storage.label_store.get_label(doc_id)

        has_pdf = False
        has_image = False
        source_dir = doc_bundle.doc_root / "source"
        if source_dir.exists():
            for source_file in source_dir.iterdir():
                ext = source_file.suffix.lower()
                if ext == ".pdf":
                    has_pdf = True
                elif ext in {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp"}:
                    has_image = True

        return DocPayload(
            doc_id=doc_id,
            claim_id=resolved_claim_id,
            filename=filename,
            doc_type=doc_type,
            language=language,
            pages=pages,
            extraction=extraction,
            labels=labels,
            has_pdf=has_pdf,
            has_image=has_image,
        )

    def get_doc_source(self, doc_id: str) -> Tuple[Path, str, str]:
        storage = self.storage_factory()
        source_file = storage.doc_store.get_doc_source_path(doc_id)
        if not source_file:
            doc = storage.doc_store.get_doc(doc_id)
            if not doc:
                raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
            raise HTTPException(status_code=404, detail="No source file available")

        ext_to_media = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
        }

        ext = source_file.suffix.lower()
        media_type = ext_to_media.get(ext, "application/octet-stream")
        return source_file, media_type, source_file.name

    def get_doc_azure_di(self, doc_id: str) -> dict:
        storage = self.storage_factory()
        doc_bundle = storage.doc_store.get_doc(doc_id)
        if not doc_bundle:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        azure_di_path = doc_bundle.doc_root / "text" / "raw" / "azure_di.json"
        if not azure_di_path.exists():
            raise HTTPException(status_code=404, detail="Azure DI data not available")

        with open(azure_di_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_doc_runs(self, doc_id: str, claim_id: str) -> List[dict]:
        """
        Get all pipeline runs that processed this document.

        Returns list of runs with extraction summary for each.
        """
        claim_dir = self._find_claim_dir(claim_id)
        if not claim_dir:
            return []

        runs_dir = claim_dir / "runs"
        if not runs_dir.exists():
            return []

        result = []
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            if not (run_dir.name.startswith("run_") or run_dir.name.startswith("BATCH-")):
                continue

            # Check if this run has extraction for this document
            extraction_path = run_dir / "extraction" / f"{doc_id}.json"
            if not extraction_path.exists():
                continue

            # Load run metadata
            run_info: dict = {
                "run_id": run_dir.name,
                "timestamp": None,
                "model": "unknown",
                "status": "complete",
                "extraction": None,
            }

            # Try to get timestamp and model from manifest
            manifest_path = run_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                        run_info["timestamp"] = manifest.get("started_at") or manifest.get("completed_at")
                        run_info["model"] = manifest.get("model", "unknown")
                except Exception:
                    pass

            # Load extraction summary
            try:
                with open(extraction_path, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
                    quality_gate = ext_data.get("quality_gate", {})
                    fields = ext_data.get("fields", [])
                    run_info["extraction"] = {
                        "field_count": len(fields),
                        "gate_status": quality_gate.get("status"),
                    }
            except Exception:
                pass

            result.append(run_info)

        return result

    def list_all_documents(
        self,
        claim_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        has_truth: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[dict], int]:
        """
        List all documents across all claims with optional filters.

        Returns (documents, total_count) for pagination.
        """
        storage = self.storage_factory()
        all_docs: List[dict] = []

        if not self.data_dir.exists():
            return [], 0

        # Iterate through all claims
        for claim_dir in self.data_dir.iterdir():
            if not claim_dir.is_dir():
                continue

            current_claim_id = extract_claim_number(claim_dir.name)

            # Filter by claim_id if specified
            if claim_id and current_claim_id != claim_id and claim_dir.name != claim_id:
                continue

            docs_dir = claim_dir / "docs"
            if not docs_dir.exists():
                continue

            # Get latest run for quality status
            run_dir = get_latest_run_dir_for_claim(claim_dir)
            extraction_dir = run_dir / "extraction" if run_dir else None

            for doc_folder in docs_dir.iterdir():
                if not doc_folder.is_dir():
                    continue

                doc_id = doc_folder.name
                meta_path = doc_folder / "meta" / "doc.json"

                if not meta_path.exists():
                    continue

                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)

                filename = meta.get("original_filename", "Unknown")
                current_doc_type = meta.get("doc_type", "unknown")
                language = meta.get("language", "es")

                # Filter by doc_type
                if doc_type and current_doc_type != doc_type:
                    continue

                # Check for labels (truth)
                label_data = storage.label_store.get_label(doc_id)
                doc_has_truth = label_data is not None

                # Filter by has_truth
                if has_truth is not None and doc_has_truth != has_truth:
                    continue

                # Filter by search term (filename or doc_id)
                if search:
                    search_lower = search.lower()
                    if search_lower not in filename.lower() and search_lower not in doc_id.lower():
                        continue

                # Get quality status from latest extraction
                quality_status = None
                if extraction_dir:
                    extraction_path = extraction_dir / f"{doc_id}.json"
                    if extraction_path.exists():
                        try:
                            with open(extraction_path, "r", encoding="utf-8") as f:
                                ext_data = json.load(f)
                                quality_gate = ext_data.get("quality_gate", {})
                                quality_status = quality_gate.get("status")
                        except Exception:
                            pass

                # Get reviewer info from labels
                last_reviewed = None
                reviewer = None
                if label_data:
                    last_reviewed = label_data.get("reviewed_at")
                    reviewer = label_data.get("reviewer")

                all_docs.append({
                    "doc_id": doc_id,
                    "claim_id": current_claim_id,
                    "filename": filename,
                    "doc_type": current_doc_type,
                    "language": language,
                    "has_truth": doc_has_truth,
                    "last_reviewed": last_reviewed,
                    "reviewer": reviewer,
                    "quality_status": quality_status,
                })

        # Sort by last_reviewed (most recent first), then by filename
        all_docs.sort(key=lambda d: (d["last_reviewed"] or "", d["filename"]), reverse=True)

        total = len(all_docs)

        # Apply pagination
        paginated = all_docs[offset:offset + limit]

        return paginated, total

    def _find_claim_dir(self, claim_id: str) -> Optional[Path]:
        if not self.data_dir.exists():
            return None
        for d in self.data_dir.iterdir():
            if not d.is_dir():
                continue
            if d.name == claim_id or extract_claim_number(d.name) == claim_id:
                return d
        return None
