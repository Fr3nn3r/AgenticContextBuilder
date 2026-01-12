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

            labels_path = doc_folder / "labels" / "latest.json"
            has_labels = labels_path.exists()

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

    def get_doc(self, doc_id: str, run_id: Optional[str] = None) -> DocPayload:
        storage = self.storage_factory()
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

    def _find_claim_dir(self, claim_id: str) -> Optional[Path]:
        if not self.data_dir.exists():
            return None
        for d in self.data_dir.iterdir():
            if not d.is_dir():
                continue
            if d.name == claim_id or extract_claim_number(d.name) == claim_id:
                return d
        return None
