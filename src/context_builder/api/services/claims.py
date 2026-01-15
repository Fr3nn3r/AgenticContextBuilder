"""Claims-focused API services."""

import json
from pathlib import Path
from typing import Callable, List, Optional

from fastapi import HTTPException

from context_builder.api.models import ClaimReviewPayload, ClaimSummary, DocSummary, RunSummary
from context_builder.api.services.utils import (
    calculate_risk_score,
    extract_amount_from_extraction,
    extract_claim_number,
    format_completed_date,
    get_global_runs_dir,
    get_latest_run_dir_for_claim,
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
        for claim_dir in self._iter_claim_dirs():
            docs_dir = claim_dir / "docs"
            if not docs_dir.exists():
                continue

            doc_metas = []
            for doc_folder in docs_dir.iterdir():
                if not doc_folder.is_dir():
                    continue
                meta_path = doc_folder / "meta" / "doc.json"
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        doc_metas.append(meta)

            if not doc_metas:
                continue

            doc_types = list(set(m.get("doc_type", "unknown") for m in doc_metas))

            run_dir = (
                get_run_dir_by_id(claim_dir, run_id)
                if run_id
                else get_latest_run_dir_for_claim(claim_dir)
            )

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

            if run_dir:
                extraction_dir = run_dir / "extraction"
                summary_path = run_dir / "logs" / "summary.json"
                if summary_path.exists():
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary = json.load(f)
                        completed = summary.get("completed_at", "")
                        dates = format_completed_date(completed)
                        closed_date = dates["closed_date"]
                        last_processed = dates["last_processed"]

                if extraction_dir.exists():
                    for ext_file in extraction_dir.glob("*.json"):
                        extracted_count += 1
                        with open(ext_file, "r", encoding="utf-8") as f:
                            ext_data = json.load(f)
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

            # Count labeled docs using storage layer (reads from registry/labels/)
            for doc_folder in docs_dir.iterdir():
                if doc_folder.is_dir():
                    doc_id = doc_folder.name
                    if storage.label_store.get_label(doc_id) is not None:
                        labeled_count += 1

            avg_risk = total_risk_score // max(extracted_count, 1)
            status = "Reviewed" if labeled_count > 0 else "Not Reviewed"
            claim_number = extract_claim_number(claim_dir.name)
            in_run = run_dir is not None and extracted_count > 0

            claims.append(ClaimSummary(
                claim_id=claim_number,
                folder_name=claim_dir.name,
                doc_count=len(doc_metas),
                doc_types=doc_types,
                extracted_count=extracted_count,
                labeled_count=labeled_count,
                lob="MOTOR",
                risk_score=avg_risk,
                loss_type=parse_loss_type_from_folder(claim_dir.name),
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
        global_runs_dir = get_global_runs_dir(self.data_dir)

        for r_id in run_ids:
            metadata = {"run_id": r_id, "timestamp": None, "model": None}
            global_run_dir = global_runs_dir / r_id
            if global_run_dir.exists():
                summary_path = global_run_dir / "summary.json"
                if summary_path.exists():
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary = json.load(f)
                        metadata["timestamp"] = summary.get("completed_at")

                manifest_path = global_run_dir / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                        metadata["model"] = manifest.get("model")
                        metadata["claims_count"] = manifest.get("claims_count", 0)
            else:
                for claim_dir in self._iter_claim_dirs():
                    run_dir = claim_dir / "runs" / r_id
                    if run_dir.exists():
                        summary_path = run_dir / "logs" / "summary.json"
                        if summary_path.exists():
                            with open(summary_path, "r", encoding="utf-8") as f:
                                summary = json.load(f)
                                metadata["timestamp"] = summary.get("completed_at")
                                metadata["model"] = summary.get("model")
                            break

            runs.append(metadata)

        return runs

    def get_run_summary(self) -> RunSummary:
        if not self.data_dir.exists():
            raise HTTPException(status_code=404, detail="Data directory not found")

        total_claims = 0
        total_docs = 0
        extracted_count = 0
        labeled_count = 0
        quality_gate = {"pass": 0, "warn": 0, "fail": 0}

        for claim_dir in self._iter_claim_dirs():
            docs_dir = claim_dir / "docs"
            if not docs_dir.exists():
                continue

            total_claims += 1
            doc_folders = [d for d in docs_dir.iterdir() if d.is_dir()]
            total_docs += len(doc_folders)

            run_dir = get_latest_run_dir_for_claim(claim_dir)
            if not run_dir:
                continue

            extraction_dir = run_dir / "extraction"
            if extraction_dir.exists():
                for ext_file in extraction_dir.glob("*.json"):
                    extracted_count += 1
                    with open(ext_file, "r", encoding="utf-8") as f:
                        ext_data = json.load(f)
                        status = ext_data.get("quality_gate", {}).get("status", "unknown")
                        if status in quality_gate:
                            quality_gate[status] += 1

            labels_dir = run_dir / "labels"
            if labels_dir.exists():
                labeled_count += len(list(labels_dir.glob("*.labels.json")))

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
        claim_dir = self._find_claim_dir(claim_id)
        if not claim_dir:
            raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

        all_claims = sorted([
            d.name for d in self._iter_claim_dirs()
            if (d / "docs").exists()
        ])

        current_idx = None
        for i, c in enumerate(all_claims):
            if c == claim_dir.name or extract_claim_number(c) == claim_id:
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

        docs_dir = claim_dir / "docs"
        run_dir = get_latest_run_dir_for_claim(claim_dir)
        extraction_dir = run_dir / "extraction" if run_dir else None

        docs = []
        gate_counts = {"pass": 0, "warn": 0, "fail": 0}
        unlabeled_count = 0

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
                            confidence = sum(
                                field.get("confidence", 0) for field in fields
                            ) / len(fields)
                        if quality_status == "pass":
                            gate_counts["pass"] += 1
                        elif quality_status == "warn":
                            gate_counts["warn"] += 1
                        elif quality_status == "fail":
                            gate_counts["fail"] += 1

            # Use storage layer to check for labels (reads from registry/labels/)
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
        if run_dir:
            summary_path = run_dir / "logs" / "summary.json"
            if summary_path.exists():
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
                    run_metadata = {
                        "run_id": run_dir.name,
                        "model": summary.get("model", ""),
                    }

        return ClaimReviewPayload(
            claim_id=extract_claim_number(claim_dir.name),
            folder_name=claim_dir.name,
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

    def _iter_claim_dirs(self):
        if not self.data_dir.exists():
            return []
        return [
            d for d in self.data_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def _find_claim_dir(self, claim_id: str) -> Optional[Path]:
        for d in self._iter_claim_dirs():
            if d.name == claim_id or extract_claim_number(d.name) == claim_id:
                return d
        return None
