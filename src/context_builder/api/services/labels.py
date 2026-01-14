"""Label-focused API services."""

import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException

from context_builder.api.services.utils import extract_claim_number
from context_builder.storage import StorageFacade
from context_builder.storage.truth_store import TruthStore

logger = logging.getLogger(__name__)

class LabelsService:
    """Service layer for saving document labels."""

    def __init__(self, storage_factory: Callable[[], StorageFacade]):
        self.storage_factory = storage_factory

    def save_labels(
        self,
        doc_id: str,
        reviewer: str,
        notes: str,
        field_labels: List[Dict[str, Any]],
        doc_labels: Dict[str, Any],
    ) -> Dict[str, str]:
        storage = self.storage_factory()
        doc_bundle = storage.doc_store.get_doc(doc_id)
        if not doc_bundle:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        resolved_claim_id = doc_bundle.claim_id or extract_claim_number(doc_bundle.claim_folder)

        label_data = {
            "schema_version": "label_v3",
            "doc_id": doc_id,
            "claim_id": resolved_claim_id,
            "review": {
                "reviewed_at": datetime.utcnow().isoformat() + "Z",
                "reviewer": reviewer,
                "notes": notes,
            },
            "field_labels": field_labels,
            "doc_labels": doc_labels,
        }

        self._save_label_with_truth(storage, doc_bundle, label_data)

        return {"status": "saved", "doc_id": doc_id}

    def save_doc_review(
        self,
        doc_id: str,
        claim_id: str,
        doc_type_correct: bool,
        notes: str,
    ) -> Dict[str, str]:
        storage = self.storage_factory()
        doc_bundle = storage.doc_store.get_doc(doc_id)
        if not doc_bundle:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        claim_matches = {
            doc_bundle.claim_id,
            doc_bundle.claim_folder,
            extract_claim_number(doc_bundle.claim_folder),
        }
        if claim_id not in claim_matches:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        label_data = {
            "schema_version": "label_v2",
            "doc_id": doc_id,
            "claim_id": doc_bundle.claim_id or extract_claim_number(doc_bundle.claim_folder),
            "review": {
                "reviewed_at": datetime.utcnow().isoformat(),
                "reviewer": "",
                "notes": notes,
            },
            "field_labels": [],
            "doc_labels": {
                "doc_type_correct": doc_type_correct,
            },
        }

        self._save_label_with_truth(storage, doc_bundle, label_data)

        return {"status": "saved"}

    def save_classification_label(
        self,
        doc_id: str,
        doc_type_correct: bool,
        doc_type_truth: Optional[str],
        notes: str,
    ) -> Dict[str, str]:
        storage = self.storage_factory()
        doc_bundle = storage.doc_store.get_doc(doc_id)
        if not doc_bundle:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        if not doc_type_correct and not doc_type_truth:
            raise HTTPException(
                status_code=400,
                detail="doc_type_truth is required when doc_type_correct is False",
            )

        label_data = storage.label_store.get_label(doc_id)
        if not label_data:
            resolved_claim_id = doc_bundle.claim_id or extract_claim_number(doc_bundle.claim_folder)
            label_data = {
                "schema_version": "label_v3",
                "doc_id": doc_id,
                "claim_id": resolved_claim_id,
                "review": {
                    "reviewed_at": None,
                    "reviewer": "",
                    "notes": "",
                },
                "field_labels": [],
                "doc_labels": {},
            }

        label_data["doc_labels"]["doc_type_correct"] = doc_type_correct
        label_data["doc_labels"]["doc_type_truth"] = doc_type_truth if not doc_type_correct else None
        label_data["review"]["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
        if notes:
            label_data["review"]["notes"] = notes

        self._save_label_with_truth(storage, doc_bundle, label_data)

        return {"status": "saved", "doc_id": doc_id}

    def _save_label_with_truth(
        self,
        storage: StorageFacade,
        doc_bundle,
        label_data: Dict[str, Any],
    ) -> None:
        try:
            storage.label_store.save_label(doc_bundle.doc_id, label_data)
        except IOError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to save label: {exc}")

        file_md5 = doc_bundle.metadata.get("file_md5")
        if not file_md5:
            logger.warning("Skipping truth write for %s: missing file_md5", doc_bundle.doc_id)
            return

        output_root = self._resolve_output_root(doc_bundle.doc_root)
        if not output_root:
            logger.warning("Skipping truth write for %s: cannot resolve output root", doc_bundle.doc_id)
            return

        truth_payload = {
            **label_data,
            "schema_version": "label_v3",
            "input_hashes": {
                "file_md5": file_md5,
                "content_md5": doc_bundle.metadata.get("content_md5", ""),
            },
            "source_doc_ref": {
                "claim_id": label_data.get("claim_id"),
                "doc_id": label_data.get("doc_id"),
                "original_filename": doc_bundle.metadata.get("original_filename", ""),
            },
        }

        try:
            TruthStore(output_root).save_truth_by_file_md5(file_md5, truth_payload)
        except IOError as exc:
            logger.warning("Failed to save canonical truth for %s: %s", doc_bundle.doc_id, exc)

    @staticmethod
    def _resolve_output_root(doc_root: Path) -> Optional[Path]:
        for parent in doc_root.parents:
            if parent.name == "claims":
                return parent.parent
        if len(doc_root.parents) >= 4:
            return doc_root.parents[3]
        return None
