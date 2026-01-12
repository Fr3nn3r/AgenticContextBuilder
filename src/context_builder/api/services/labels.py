"""Label-focused API services."""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException

from context_builder.api.services.utils import extract_claim_number
from context_builder.storage import StorageFacade


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

        try:
            storage.label_store.save_label(doc_id, label_data)
        except IOError as e:
            raise HTTPException(status_code=500, detail=f"Failed to save labels: {e}")

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

        try:
            storage.label_store.save_label(doc_id, label_data)
        except IOError as e:
            raise HTTPException(status_code=500, detail=f"Failed to save label: {e}")

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

        try:
            storage.label_store.save_label(doc_id, label_data)
        except IOError as e:
            raise HTTPException(status_code=500, detail=f"Failed to save label: {e}")

        return {"status": "saved", "doc_id": doc_id}
