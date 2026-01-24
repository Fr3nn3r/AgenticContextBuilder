"""Document-focused API services."""

from pathlib import Path
from typing import Callable, List, Optional, Tuple

from fastapi import HTTPException

from context_builder.api.models import DocPayload, DocSummary
from context_builder.api.services.utils import (
    extract_claim_number,
    get_latest_run_id_for_claim,
)
from context_builder.storage import StorageFacade


class DocumentsService:
    """Service layer for document listing and retrieval."""

    def __init__(self, data_dir: Path, storage_factory: Callable[[], StorageFacade]):
        self.data_dir = data_dir
        self.storage_factory = storage_factory

    def list_docs(self, claim_id: str, run_id: Optional[str] = None) -> List[DocSummary]:
        storage = self.storage_factory()

        # Find the claim folder
        claim_refs = storage.doc_store.list_claims()
        folder_name = None
        for ref in claim_refs:
            if ref.claim_folder == claim_id or extract_claim_number(ref.claim_folder) == claim_id:
                folder_name = ref.claim_folder
                break

        if not folder_name:
            raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

        # Get documents using storage layer
        doc_refs = storage.doc_store.list_docs(folder_name)
        if not doc_refs:
            raise HTTPException(status_code=404, detail="No documents found")

        # Determine which run to use
        effective_run_id = run_id
        if not effective_run_id:
            effective_run_id = get_latest_run_id_for_claim(self.data_dir / folder_name)

        docs = []
        for doc_ref in doc_refs:
            doc_id = doc_ref.doc_id

            # Get metadata using storage layer
            meta = storage.doc_store.get_doc_metadata(doc_id, claim_id=folder_name)
            if not meta:
                continue

            has_extraction = False
            quality_status = None
            confidence = 0.0
            missing_required_fields: List[str] = []

            if effective_run_id:
                ext_data = storage.run_store.get_extraction(effective_run_id, doc_id, claim_id=folder_name)
                if ext_data:
                    has_extraction = True
                    quality_gate = ext_data.get("quality_gate", {})
                    quality_status = quality_gate.get("status")
                    missing_required_fields = quality_gate.get("missing_required_fields", [])
                    fields = ext_data.get("fields", [])
                    if fields:
                        confidence = sum(field.get("confidence", 0) for field in fields) / len(fields)

            # Use storage layer to check for labels
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
                source_type=meta.get("source_type", "unknown"),
                page_count=meta.get("page_count", 0),
            ))

        return docs

    def get_doc(self, doc_id: str, run_id: Optional[str] = None, claim_id: Optional[str] = None) -> DocPayload:
        storage = self.storage_factory()

        # Resolve claim_id and folder_name
        resolved_claim_id = claim_id
        folder_name = None

        if claim_id:
            # Find the folder for this claim_id
            for ref in storage.doc_store.list_claims():
                if ref.claim_folder == claim_id or extract_claim_number(ref.claim_folder) == claim_id:
                    folder_name = ref.claim_folder
                    resolved_claim_id = claim_id
                    break

        # Try to get document metadata directly
        if folder_name:
            meta = storage.doc_store.get_doc_metadata(doc_id, claim_id=folder_name)
        else:
            # Fallback: find which claim this doc belongs to
            doc_bundle = storage.doc_store.get_doc(doc_id)
            if doc_bundle:
                folder_name = doc_bundle.claim_folder
                resolved_claim_id = doc_bundle.claim_id or extract_claim_number(folder_name)
                meta = doc_bundle.metadata
            else:
                meta = None

        if not meta:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        filename = meta.get("original_filename", "Unknown")
        doc_type = meta.get("doc_type", "unknown")
        language = meta.get("language", "es")

        # Load text using storage layer
        doc_text = storage.doc_store.get_doc_text(doc_id)
        pages = doc_text.pages if doc_text else []

        # Load extraction - auto-detect latest run if not specified
        extraction = None
        effective_run_id = run_id
        if not effective_run_id and folder_name:
            # Find latest run that has extraction for this document
            run_ids = storage.run_store.list_runs_for_doc(doc_id, folder_name)
            if run_ids:
                effective_run_id = run_ids[0]  # Most recent
        if effective_run_id:
            extraction = storage.run_store.get_extraction(effective_run_id, doc_id, claim_id=folder_name)

        # Load labels using storage layer
        labels = storage.label_store.get_label(doc_id)

        # Check source files using storage layer
        has_pdf = False
        has_image = False
        source_files = storage.doc_store.get_source_files(doc_id, claim_id=folder_name)
        for sf in source_files:
            if sf.file_type == "pdf":
                has_pdf = True
            elif sf.file_type == "image":
                has_image = True

        return DocPayload(
            doc_id=doc_id,
            claim_id=resolved_claim_id or "",
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

        # Use storage layer to get Azure DI data
        azure_di_data = storage.doc_store.get_doc_azure_di(doc_id)
        if azure_di_data is None:
            # Check if doc exists first
            doc_bundle = storage.doc_store.get_doc(doc_id)
            if not doc_bundle:
                raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
            raise HTTPException(status_code=404, detail="Azure DI data not available")

        return azure_di_data

    def get_doc_runs(self, doc_id: str, claim_id: str) -> List[dict]:
        """
        Get all pipeline runs that processed this document.

        Returns list of runs with extraction summary for each.
        """
        storage = self.storage_factory()

        # Find the folder for this claim_id
        folder_name = None
        for ref in storage.doc_store.list_claims():
            if ref.claim_folder == claim_id or extract_claim_number(ref.claim_folder) == claim_id:
                folder_name = ref.claim_folder
                break

        if not folder_name:
            return []

        # Get all runs that have extraction for this doc
        run_ids = storage.run_store.list_runs_for_doc(doc_id, folder_name)

        result = []
        for r_id in run_ids:
            run_info: dict = {
                "run_id": r_id,
                "timestamp": None,
                "model": "unknown",
                "status": "complete",
                "extraction": None,
            }

            # Get manifest for timestamp and model
            manifest = storage.run_store.get_run_manifest(r_id)
            if manifest:
                run_info["timestamp"] = manifest.get("started_at") or manifest.get("completed_at")
                run_info["model"] = manifest.get("model", "unknown")

            # Load extraction summary
            ext_data = storage.run_store.get_extraction(r_id, doc_id, claim_id=folder_name)
            if ext_data:
                quality_gate = ext_data.get("quality_gate", {})
                fields = ext_data.get("fields", [])
                run_info["extraction"] = {
                    "field_count": len(fields),
                    "gate_status": quality_gate.get("status"),
                }

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

        # Iterate through all claims using storage layer
        for claim_ref in storage.doc_store.list_claims():
            current_claim_id = claim_ref.claim_id
            folder_name = claim_ref.claim_folder

            # Filter by claim_id if specified
            if claim_id and current_claim_id != claim_id and folder_name != claim_id:
                continue

            # Get documents for this claim
            doc_refs = storage.doc_store.list_docs(folder_name)

            # Get latest run for quality status
            run_id = get_latest_run_id_for_claim(self.data_dir / folder_name)

            for doc_ref in doc_refs:
                d_id = doc_ref.doc_id

                # Get metadata using storage layer
                meta = storage.doc_store.get_doc_metadata(d_id, claim_id=folder_name)
                if not meta:
                    continue

                filename = meta.get("original_filename", "Unknown")
                current_doc_type = meta.get("doc_type", "unknown")
                language = meta.get("language", "es")

                # Filter by doc_type
                if doc_type and current_doc_type != doc_type:
                    continue

                # Check for labels (truth) using storage layer
                label_data = storage.label_store.get_label(d_id)
                doc_has_truth = label_data is not None

                # Filter by has_truth
                if has_truth is not None and doc_has_truth != has_truth:
                    continue

                # Filter by search term (filename or doc_id)
                if search:
                    search_lower = search.lower()
                    if search_lower not in filename.lower() and search_lower not in d_id.lower():
                        continue

                # Get quality status from latest extraction using storage layer
                quality_status = None
                if run_id:
                    ext_data = storage.run_store.get_extraction(run_id, d_id, claim_id=folder_name)
                    if ext_data:
                        quality_gate = ext_data.get("quality_gate", {})
                        quality_status = quality_gate.get("status")

                # Get reviewer info from labels
                last_reviewed = None
                reviewer = None
                if label_data:
                    last_reviewed = label_data.get("reviewed_at")
                    reviewer = label_data.get("reviewer")

                all_docs.append({
                    "doc_id": d_id,
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
