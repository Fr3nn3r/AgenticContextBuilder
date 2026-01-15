"""Label-focused API services.

Includes compliance decision logging for human review and override decisions.
Auto-updates label index when labels are saved.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException

from context_builder.api.services.utils import extract_claim_number
from context_builder.storage import StorageFacade
from context_builder.storage.truth_store import TruthStore
from context_builder.storage.index_builder import upsert_label_entry
from context_builder.storage.workspace_paths import get_workspace_logs_dir
from context_builder.services.decision_ledger import DecisionLedger
from context_builder.schemas.decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionRationale,
    DecisionOutcome,
)

logger = logging.getLogger(__name__)

class LabelsService:
    """Service layer for saving document labels.

    Includes compliance decision logging for human reviews and overrides.
    Auto-updates label index when labels are saved.
    """

    def __init__(
        self,
        storage_factory: Callable[[], StorageFacade],
        ledger_dir: Optional[Path] = None,
        registry_dir: Optional[Path] = None,
    ):
        self.storage_factory = storage_factory
        self.registry_dir = registry_dir
        # Initialize decision ledger for compliance logging
        # Use workspace-aware path when not explicitly provided
        self.decision_ledger = DecisionLedger(ledger_dir or get_workspace_logs_dir())

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

        # Log human review decision for compliance
        self._log_human_review_decision(doc_id, resolved_claim_id, reviewer, notes, field_labels)

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

        # Log classification override decision if doc_type_correct is False
        if not doc_type_correct:
            self._log_classification_override(
                doc_id=doc_id,
                claim_id=label_data.get("claim_id", ""),
                original_doc_type=doc_bundle.metadata.get("classification", {}).get("doc_type", "unknown"),
                corrected_doc_type=doc_type_truth,
                notes=notes,
            )

        return {"status": "saved", "doc_id": doc_id}

    def _log_human_review_decision(
        self,
        doc_id: str,
        claim_id: str,
        reviewer: str,
        notes: str,
        field_labels: List[Dict[str, Any]],
    ) -> None:
        """Log human review decision to the compliance ledger.

        Args:
            doc_id: Document identifier
            claim_id: Claim identifier
            reviewer: Reviewer identifier
            notes: Review notes
            field_labels: List of field label corrections
        """
        try:
            # Count corrections
            corrections = [fl for fl in field_labels if fl.get("truth_value") is not None]

            rationale = DecisionRationale(
                summary=f"Human review: {len(corrections)} fields labeled",
                confidence=1.0,  # Human decisions are authoritative
                notes=notes if notes else None,
            )

            outcome = DecisionOutcome(
                field_corrections=[
                    {
                        "field_name": fl.get("field_name"),
                        "state": fl.get("state"),
                        "truth_value": fl.get("truth_value"),
                    }
                    for fl in corrections
                ],
            )

            record = DecisionRecord(
                decision_id="",  # Will be generated by ledger
                decision_type=DecisionType.HUMAN_REVIEW,
                claim_id=claim_id,
                doc_id=doc_id,
                rationale=rationale,
                outcome=outcome,
                actor_type="human",
                actor_id=reviewer or "anonymous",
            )

            self.decision_ledger.append(record)
            logger.debug(f"Logged human review decision for doc_id={doc_id}")

        except Exception as e:
            logger.warning(f"Failed to log human review decision: {e}")

    def _log_classification_override(
        self,
        doc_id: str,
        claim_id: str,
        original_doc_type: str,
        corrected_doc_type: Optional[str],
        notes: str,
    ) -> None:
        """Log classification override decision to the compliance ledger.

        Args:
            doc_id: Document identifier
            claim_id: Claim identifier
            original_doc_type: Original classification
            corrected_doc_type: Corrected document type
            notes: Override reason/notes
        """
        try:
            rationale = DecisionRationale(
                summary=f"Classification override: {original_doc_type} -> {corrected_doc_type}",
                confidence=1.0,  # Human overrides are authoritative
                notes=notes if notes else None,
            )

            outcome = DecisionOutcome(
                original_value=original_doc_type,
                override_value=corrected_doc_type,
                override_reason=notes,
                doc_type_correction=corrected_doc_type,
            )

            record = DecisionRecord(
                decision_id="",  # Will be generated by ledger
                decision_type=DecisionType.OVERRIDE,
                claim_id=claim_id,
                doc_id=doc_id,
                rationale=rationale,
                outcome=outcome,
                actor_type="human",
                actor_id="reviewer",  # Could be enhanced to capture actual reviewer
                metadata={"original_doc_type": original_doc_type},
            )

            self.decision_ledger.append(record)
            logger.debug(f"Logged classification override for doc_id={doc_id}")

        except Exception as e:
            logger.warning(f"Failed to log classification override: {e}")

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

        # Auto-update label index
        self._update_label_index(label_data)

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

    def _update_label_index(self, label_data: Dict[str, Any]) -> None:
        """Update the label index with the saved label data.

        Args:
            label_data: The label data that was saved.
        """
        if not self.registry_dir:
            return

        try:
            # Count field states
            field_labels = label_data.get("field_labels", [])
            labeled_count = sum(
                1 for fl in field_labels if fl.get("state") == "LABELED"
            )
            unverifiable_count = sum(
                1 for fl in field_labels if fl.get("state") == "UNVERIFIABLE"
            )
            unlabeled_count = sum(
                1 for fl in field_labels if fl.get("state") == "UNLABELED"
            )

            # Get updated_at from review metadata
            review = label_data.get("review", {})
            updated_at = review.get("reviewed_at")

            label_entry = {
                "doc_id": label_data.get("doc_id"),
                "claim_id": label_data.get("claim_id"),
                "has_label": True,
                "labeled_count": labeled_count,
                "unverifiable_count": unverifiable_count,
                "unlabeled_count": unlabeled_count,
                "updated_at": updated_at,
            }

            upsert_label_entry(self.registry_dir, label_entry)
        except Exception as e:
            logger.warning(f"Failed to update label index: {e}")

    @staticmethod
    def _resolve_output_root(doc_root: Path) -> Optional[Path]:
        for parent in doc_root.parents:
            if parent.name == "claims":
                return parent.parent
        if len(doc_root.parents) >= 4:
            return doc_root.parents[3]
        return None
