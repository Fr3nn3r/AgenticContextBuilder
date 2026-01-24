"""Claims-focused API services."""

from pathlib import Path
from typing import Callable, List, Optional

from fastapi import HTTPException

from context_builder.api.models import ClaimReviewPayload, ClaimSummary, DocSummary, RunSummary
from context_builder.api.services.utils import (
    calculate_risk_score,
    extract_amount_from_extraction,
    extract_claim_number,
    format_completed_date,
    get_latest_run_id_for_claim,
    get_run_dir_by_id,
    parse_loss_type_from_folder,
)
from context_builder.storage import StorageFacade


class ClaimsService:
    """Service layer for claims and run summaries."""

    def __init__(self, data_dir: Path, storage_factory: Callable[[], StorageFacade]):
        self.data_dir = data_dir
        self.storage_factory = storage_factory

    def list_claims(self, run_id: Optional[str] = None) -> List[ClaimSummary]:
        if not self.data_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Data directory not found: {self.data_dir}",
            )

        storage = self.storage_factory()
        claims = []

        # Use storage layer to list claims
        for claim_ref in storage.doc_store.list_claims():
            claim_id = claim_ref.claim_id
            folder_name = claim_ref.claim_folder

            # Get documents for this claim using storage layer
            doc_refs = storage.doc_store.list_docs(folder_name)
            if not doc_refs:
                continue

            doc_types = list(set(d.doc_type for d in doc_refs))

            # Determine which run to use
            effective_run_id = run_id
            if not effective_run_id:
                # Get latest run for this claim
                effective_run_id = get_latest_run_id_for_claim(self.data_dir / folder_name)

            extracted_count = 0
            labeled_count = 0
            total_risk_score = 0
            total_amount = 0.0
            flags_count = 0
            closed_date = None
            last_processed = None
            gate_pass_count = 0
            gate_warn_count = 0
            gate_fail_count = 0

            if effective_run_id:
                # Get run summary using storage layer
                summary = storage.run_store.get_run_summary(effective_run_id, claim_id=folder_name)
                if summary:
                    completed = summary.get("completed_at", "")
                    dates = format_completed_date(completed)
                    closed_date = dates["closed_date"]
                    last_processed = dates["last_processed"]

                # Get extractions using storage layer
                extractions = storage.run_store.list_extractions(effective_run_id, claim_id=folder_name)
                for ext_ref in extractions:
                    ext_data = storage.run_store.get_extraction(
                        effective_run_id, ext_ref.doc_id, claim_id=folder_name
                    )
                    if ext_data:
                        extracted_count += 1
                        total_risk_score += calculate_risk_score(ext_data)

                        quality = ext_data.get("quality_gate", {})
                        status = quality.get("status", "unknown")
                        if status == "pass":
                            gate_pass_count += 1
                        elif status == "warn":
                            gate_warn_count += 1
                            flags_count += 1
                        elif status == "fail":
                            gate_fail_count += 1
                            flags_count += 2

                        flags_count += len(quality.get("missing_required_fields", []))

                        amount = extract_amount_from_extraction(ext_data)
                        if amount:
                            total_amount = max(total_amount, amount)

            # Count labeled docs using storage layer
            labeled_count = storage.label_store.count_labels_for_claim(folder_name)

            avg_risk = total_risk_score // max(extracted_count, 1)
            status = "Reviewed" if labeled_count > 0 else "Not Reviewed"
            claim_number = extract_claim_number(folder_name)
            in_run = effective_run_id is not None and extracted_count > 0

            claims.append(ClaimSummary(
                claim_id=claim_number,
                folder_name=folder_name,
                doc_count=len(doc_refs),
                doc_types=doc_types,
                extracted_count=extracted_count,
                labeled_count=labeled_count,
                lob="MOTOR",
                risk_score=avg_risk,
                loss_type=parse_loss_type_from_folder(folder_name),
                amount=total_amount if total_amount > 0 else None,
                currency="USD",
                flags_count=flags_count,
                status=status,
                closed_date=closed_date,
                gate_pass_count=gate_pass_count,
                gate_warn_count=gate_warn_count,
                gate_fail_count=gate_fail_count,
                last_processed=last_processed,
                in_run=in_run,
            ))

        return sorted(claims, key=lambda c: c.risk_score, reverse=True)

    def list_runs(self) -> List[dict]:
        storage = self.storage_factory()
        run_ids = [r.run_id for r in storage.run_store.list_runs()]
        runs = []

        for r_id in run_ids:
            metadata = {"run_id": r_id, "timestamp": None, "model": None}

            # Try global run summary first
            summary = storage.run_store.get_run_summary(r_id)
            if summary:
                metadata["timestamp"] = summary.get("completed_at")

            # Get manifest for model and claims_count
            manifest = storage.run_store.get_run_manifest(r_id)
            if manifest:
                metadata["model"] = manifest.get("model")
                metadata["claims_count"] = manifest.get("claims_count", 0)
            else:
                # Fallback: check per-claim summaries
                for claim_ref in storage.doc_store.list_claims():
                    claim_summary = storage.run_store.get_run_summary(r_id, claim_id=claim_ref.claim_folder)
                    if claim_summary:
                        metadata["timestamp"] = claim_summary.get("completed_at")
                        metadata["model"] = claim_summary.get("model")
                        break

            runs.append(metadata)

        return runs

    def get_run_summary(self) -> RunSummary:
        if not self.data_dir.exists():
            raise HTTPException(status_code=404, detail="Data directory not found")

        storage = self.storage_factory()
        total_claims = 0
        total_docs = 0
        extracted_count = 0
        labeled_count = 0
        quality_gate = {"pass": 0, "warn": 0, "fail": 0}

        for claim_ref in storage.doc_store.list_claims():
            total_claims += 1
            doc_refs = storage.doc_store.list_docs(claim_ref.claim_folder)
            total_docs += len(doc_refs)

            # Get latest run for this claim
            run_id = get_latest_run_id_for_claim(self.data_dir / claim_ref.claim_folder)
            if not run_id:
                continue

            # Get extractions for this run
            extractions = storage.run_store.list_extractions(run_id, claim_id=claim_ref.claim_folder)
            for ext_ref in extractions:
                ext_data = storage.run_store.get_extraction(
                    run_id, ext_ref.doc_id, claim_id=claim_ref.claim_folder
                )
                if ext_data:
                    extracted_count += 1
                    status = ext_data.get("quality_gate", {}).get("status", "unknown")
                    if status in quality_gate:
                        quality_gate[status] += 1

            # Count labels for this claim
            labeled_count += storage.label_store.count_labels_for_claim(claim_ref.claim_folder)

        return RunSummary(
            run_dir=str(self.data_dir),
            total_claims=total_claims,
            total_docs=total_docs,
            extracted_count=extracted_count,
            labeled_count=labeled_count,
            quality_gate=quality_gate,
        )

    def get_claim_review(self, claim_id: str) -> ClaimReviewPayload:
        storage = self.storage_factory()

        # Find the claim using storage layer
        claim_refs = storage.doc_store.list_claims()
        target_claim = None
        for ref in claim_refs:
            if ref.claim_folder == claim_id or extract_claim_number(ref.claim_folder) == claim_id:
                target_claim = ref
                break

        if not target_claim:
            raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

        folder_name = target_claim.claim_folder

        # Get all claims for prev/next navigation
        all_claims = sorted([ref.claim_folder for ref in claim_refs])

        current_idx = None
        for i, c in enumerate(all_claims):
            if c == folder_name or extract_claim_number(c) == claim_id:
                current_idx = i
                break

        prev_claim_id = (
            extract_claim_number(all_claims[current_idx - 1])
            if current_idx and current_idx > 0
            else None
        )
        next_claim_id = (
            extract_claim_number(all_claims[current_idx + 1])
            if current_idx is not None and current_idx < len(all_claims) - 1
            else None
        )

        # Get documents for this claim
        doc_refs = storage.doc_store.list_docs(folder_name)

        # Determine latest run
        run_id = get_latest_run_id_for_claim(self.data_dir / folder_name)

        docs = []
        gate_counts = {"pass": 0, "warn": 0, "fail": 0}
        unlabeled_count = 0

        for doc_ref in doc_refs:
            doc_id = doc_ref.doc_id

            # Get doc metadata using storage layer
            meta = storage.doc_store.get_doc_metadata(doc_id, claim_id=folder_name)
            if not meta:
                continue

            has_extraction = False
            quality_status = None
            confidence = 0.0
            missing_required_fields: List[str] = []

            if run_id:
                ext_data = storage.run_store.get_extraction(run_id, doc_id, claim_id=folder_name)
                if ext_data:
                    has_extraction = True
                    quality_gate = ext_data.get("quality_gate", {})
                    quality_status = quality_gate.get("status")
                    missing_required_fields = quality_gate.get("missing_required_fields", [])
                    fields = ext_data.get("fields", [])
                    if fields:
                        confidence = sum(
                            field.get("confidence", 0) for field in fields
                        ) / len(fields)
                    if quality_status == "pass":
                        gate_counts["pass"] += 1
                    elif quality_status == "warn":
                        gate_counts["warn"] += 1
                    elif quality_status == "fail":
                        gate_counts["fail"] += 1

            # Use storage layer to check for labels
            has_labels = storage.label_store.get_label(doc_id) is not None

            if not has_labels:
                unlabeled_count += 1

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

        status_order = {"fail": 0, "warn": 1, "pass": 2, None: 3}
        docs.sort(key=lambda d: (d.has_labels, status_order.get(d.quality_status, 3)))

        default_doc_id = None
        for doc in docs:
            if not doc.has_labels:
                default_doc_id = doc.doc_id
                break
        if not default_doc_id and docs:
            default_doc_id = docs[0].doc_id

        run_metadata = None
        if run_id:
            summary = storage.run_store.get_run_summary(run_id, claim_id=folder_name)
            if summary:
                run_metadata = {
                    "run_id": run_id,
                    "model": summary.get("model", ""),
                }

        return ClaimReviewPayload(
            claim_id=extract_claim_number(folder_name),
            folder_name=folder_name,
            lob="MOTOR",
            doc_count=len(docs),
            unlabeled_count=unlabeled_count,
            gate_counts=gate_counts,
            run_metadata=run_metadata,
            prev_claim_id=prev_claim_id,
            next_claim_id=next_claim_id,
            docs=docs,
            default_doc_id=default_doc_id,
        )
