"""
Calibration Insights aggregation logic.

Computes metrics from extraction results and labels to answer:
- What is working? What is failing?
- Why is it failing? (extractor miss, normalization, evidence, doc type, needs vision)
- What should we improve next? (highest ROI)

Scope: 3 supported doc types (loss_notice, police_report, insurance_policy)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from enum import Enum


# Supported doc types for insights
SUPPORTED_DOC_TYPES = ["loss_notice", "police_report", "insurance_policy"]


class FieldOutcome(str, Enum):
    """Outcome classification for a (doc, field) pair."""
    CORRECT = "correct"
    EXTRACTOR_MISS = "extractor_miss"
    INCORRECT = "incorrect"
    CORRECT_ABSENT = "correct_absent"  # Label says wrong but field absent (rare)
    CANNOT_VERIFY = "cannot_verify"
    EVIDENCE_MISSING = "evidence_missing"  # Overlay tag


@dataclass
class FieldRecord:
    """Joined record for a single (doc_id, field_name) pair."""
    doc_id: str
    claim_id: str
    doc_type: str
    field_name: str
    is_required: bool
    # Extraction data
    has_prediction: bool
    predicted_value: Optional[str]
    normalized_value: Optional[str]
    has_evidence: bool
    confidence: float
    # Label data
    has_label: bool
    judgement: Optional[str]  # "correct", "incorrect", "unknown", or None
    correct_value: Optional[str]
    # Doc-level data
    doc_type_correct: Optional[bool]  # True, False, or None (unsure/missing)
    text_readable: Optional[str]  # "good", "warn", "poor"
    needs_vision: bool
    gate_status: Optional[str]  # "pass", "warn", "fail"
    # Metadata
    filename: str
    # Derived
    outcome: Optional[FieldOutcome] = None
    evidence_missing_tag: bool = False


@dataclass
class DocRecord:
    """Document-level record."""
    doc_id: str
    claim_id: str
    doc_type: str
    filename: str
    doc_type_correct: Optional[bool]
    text_readable: Optional[str]
    needs_vision: bool
    gate_status: Optional[str]
    has_labels: bool
    field_count: int = 0
    labeled_field_count: int = 0


@dataclass
class FieldMetrics:
    """Metrics for a single field within a doc type."""
    doc_type: str
    field_name: str
    is_required: bool
    # Counts
    docs_total: int = 0  # Docs with this field in spec
    docs_labeled: int = 0  # Docs where field has a label
    docs_with_prediction: int = 0  # Docs where field was extracted
    docs_with_evidence: int = 0  # Docs where field has provenance
    # Outcome counts
    correct_count: int = 0
    incorrect_count: int = 0
    extractor_miss_count: int = 0
    cannot_verify_count: int = 0
    evidence_missing_count: int = 0
    # Derived rates (computed after aggregation)
    presence_rate: float = 0.0
    accuracy: float = 0.0
    evidence_rate: float = 0.0
    cannot_verify_rate: float = 0.0


@dataclass
class DocTypeMetrics:
    """Metrics for a doc type."""
    doc_type: str
    docs_reviewed: int = 0
    docs_doc_type_wrong: int = 0
    docs_needs_vision: int = 0
    docs_text_good: int = 0
    docs_text_warn: int = 0
    docs_text_poor: int = 0
    docs_gate_pass: int = 0
    docs_gate_warn: int = 0
    docs_gate_fail: int = 0
    # Field-level aggregates
    required_field_presence_avg: float = 0.0
    required_field_accuracy_avg: float = 0.0
    evidence_rate_avg: float = 0.0
    top_failing_field: Optional[str] = None


@dataclass
class PriorityItem:
    """A prioritized (doc_type, field) for improvement."""
    doc_type: str
    field_name: str
    is_required: bool
    affected_docs: int
    # Failure breakdown
    extractor_miss: int = 0
    incorrect: int = 0
    evidence_missing: int = 0
    cannot_verify: int = 0
    # Priority score
    priority_score: float = 0.0
    # Recommended fix
    fix_bucket: str = ""


@dataclass
class Example:
    """An example case for drilldown."""
    claim_id: str
    doc_id: str
    filename: str
    doc_type: str
    field_name: str
    predicted_value: Optional[str]
    normalized_value: Optional[str]
    judgement: Optional[str]
    has_evidence: bool
    needs_vision: bool
    gate_status: Optional[str]
    text_readable: Optional[str]
    outcome: str
    review_url: str


class InsightsAggregator:
    """
    Aggregates extraction results and labels into insights metrics.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.field_records: List[FieldRecord] = []
        self.doc_records: List[DocRecord] = []
        self.specs: Dict[str, Any] = {}
        self._loaded = False

    def load_data(self) -> None:
        """Load all extraction results and labels."""
        if self._loaded:
            return

        self._load_specs()
        self._load_documents()
        self._classify_outcomes()
        self._loaded = True

    def _load_specs(self) -> None:
        """Load doc type specs."""
        try:
            from context_builder.extraction.spec_loader import get_spec, list_available_specs
            available = list_available_specs()
            for doc_type in SUPPORTED_DOC_TYPES:
                if doc_type in available:
                    spec = get_spec(doc_type)
                    self.specs[doc_type] = {
                        "required_fields": spec.required_fields,
                        "optional_fields": spec.optional_fields,
                        "all_fields": spec.all_fields,
                    }
        except ImportError:
            pass

    def _load_documents(self) -> None:
        """Load all documents with their extractions and labels."""
        if not self.data_dir.exists():
            return

        for claim_dir in self.data_dir.iterdir():
            if not claim_dir.is_dir() or claim_dir.name.startswith("."):
                continue

            docs_dir = claim_dir / "docs"
            if not docs_dir.exists():
                continue

            # Get latest run
            run_dir = self._get_latest_run_dir(claim_dir)
            extraction_dir = run_dir / "extraction" if run_dir else None
            labels_dir = run_dir / "labels" if run_dir else None

            for doc_folder in docs_dir.iterdir():
                if not doc_folder.is_dir():
                    continue

                doc_id = doc_folder.name
                meta_path = doc_folder / "meta" / "doc.json"
                if not meta_path.exists():
                    continue

                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)

                doc_type = meta.get("doc_type", "unknown")
                filename = meta.get("original_filename", "Unknown")
                claim_id = self._extract_claim_number(claim_dir.name)

                # Skip unsupported doc types
                if doc_type not in SUPPORTED_DOC_TYPES:
                    continue

                # Load extraction
                extraction = None
                if extraction_dir:
                    ext_path = extraction_dir / f"{doc_id}.json"
                    if ext_path.exists():
                        with open(ext_path, "r", encoding="utf-8") as f:
                            extraction = json.load(f)

                # Load labels
                labels = None
                if labels_dir:
                    labels_path = labels_dir / f"{doc_id}.labels.json"
                    if labels_path.exists():
                        with open(labels_path, "r", encoding="utf-8") as f:
                            labels = json.load(f)

                self._process_document(
                    doc_id, claim_id, doc_type, filename, extraction, labels
                )

    def _process_document(
        self,
        doc_id: str,
        claim_id: str,
        doc_type: str,
        filename: str,
        extraction: Optional[Dict],
        labels: Optional[Dict],
    ) -> None:
        """Process a single document and create records."""
        # Extract doc-level info from extraction
        gate_status = None
        needs_vision = False
        if extraction:
            qg = extraction.get("quality_gate", {})
            gate_status = qg.get("status")
            needs_vision = qg.get("needs_vision_fallback", False)

        # Extract doc-level info from labels
        doc_type_correct = None
        text_readable = None
        has_labels = labels is not None

        if labels:
            doc_labels = labels.get("doc_labels", {})
            # Handle both bool and string formats
            dtc = doc_labels.get("doc_type_correct")
            if isinstance(dtc, bool):
                doc_type_correct = dtc
            elif dtc == "yes" or dtc is True:
                doc_type_correct = True
            elif dtc == "no" or dtc is False:
                doc_type_correct = False
            # else: None (unsure or missing)
            text_readable = doc_labels.get("text_readable")

        # Build field label lookup
        field_labels = {}
        if labels:
            for fl in labels.get("field_labels", []):
                field_labels[fl.get("field_name")] = fl

        # Build extraction field lookup
        ext_fields = {}
        if extraction:
            for ef in extraction.get("fields", []):
                ext_fields[ef.get("name")] = ef

        # Get all fields from spec
        spec = self.specs.get(doc_type, {})
        all_fields = spec.get("all_fields", [])
        required_fields = set(spec.get("required_fields", []))

        # Create records for all fields
        field_count = 0
        labeled_field_count = 0

        for field_name in all_fields:
            is_required = field_name in required_fields
            ext_field = ext_fields.get(field_name, {})
            label_data = field_labels.get(field_name, {})

            # Extraction info
            has_prediction = bool(ext_field.get("value"))
            predicted_value = ext_field.get("value")
            normalized_value = ext_field.get("normalized_value")
            confidence = ext_field.get("confidence", 0.0)
            provenance = ext_field.get("provenance", [])
            has_evidence = len(provenance) > 0 and any(
                p.get("text_quote") for p in provenance
            )

            # Label info
            has_label = bool(label_data)
            judgement = label_data.get("judgement")
            correct_value = label_data.get("correct_value")

            field_count += 1
            if has_label:
                labeled_field_count += 1

            record = FieldRecord(
                doc_id=doc_id,
                claim_id=claim_id,
                doc_type=doc_type,
                field_name=field_name,
                is_required=is_required,
                has_prediction=has_prediction,
                predicted_value=predicted_value,
                normalized_value=normalized_value,
                has_evidence=has_evidence,
                confidence=confidence,
                has_label=has_label,
                judgement=judgement,
                correct_value=correct_value,
                doc_type_correct=doc_type_correct,
                text_readable=text_readable,
                needs_vision=needs_vision,
                gate_status=gate_status,
                filename=filename,
            )
            self.field_records.append(record)

        # Create doc record
        doc_record = DocRecord(
            doc_id=doc_id,
            claim_id=claim_id,
            doc_type=doc_type,
            filename=filename,
            doc_type_correct=doc_type_correct,
            text_readable=text_readable,
            needs_vision=needs_vision,
            gate_status=gate_status,
            has_labels=has_labels,
            field_count=field_count,
            labeled_field_count=labeled_field_count,
        )
        self.doc_records.append(doc_record)

    def _classify_outcomes(self) -> None:
        """Classify outcomes for all field records."""
        for record in self.field_records:
            if not record.has_label:
                record.outcome = None
                continue

            # Outcome classification
            if record.judgement == "correct":
                if record.has_prediction:
                    record.outcome = FieldOutcome.CORRECT
                else:
                    record.outcome = FieldOutcome.EXTRACTOR_MISS
            elif record.judgement == "incorrect":
                if record.has_prediction:
                    record.outcome = FieldOutcome.INCORRECT
                else:
                    record.outcome = FieldOutcome.CORRECT_ABSENT
            elif record.judgement == "unknown":
                record.outcome = FieldOutcome.CANNOT_VERIFY
            else:
                record.outcome = None

            # Evidence missing overlay
            if record.has_prediction and not record.has_evidence:
                record.evidence_missing_tag = True

    def _get_latest_run_dir(self, claim_dir: Path) -> Optional[Path]:
        """Get the most recent run directory for a claim."""
        runs_dir = claim_dir / "runs"
        if not runs_dir.exists():
            return None
        run_dirs = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("run_")],
            reverse=True
        )
        return run_dirs[0] if run_dirs else None

    def _extract_claim_number(self, folder_name: str) -> str:
        """Extract claim number from folder name."""
        import re
        match = re.search(r'(\d{2}-\d{2}-VH-\d+)', folder_name)
        return match.group(1) if match else folder_name

    # -------------------------------------------------------------------------
    # Aggregation methods
    # -------------------------------------------------------------------------

    def get_overview(self) -> Dict[str, Any]:
        """Get overview KPIs."""
        self.load_data()

        # Filter to docs where doc_type is correct (for field metrics)
        valid_docs = {r.doc_id for r in self.doc_records if r.doc_type_correct is True}
        valid_records = [r for r in self.field_records if r.doc_id in valid_docs]

        # Doc-level counts
        total_docs = len(self.doc_records)
        docs_reviewed = len([d for d in self.doc_records if d.has_labels])
        docs_doc_type_wrong = len([d for d in self.doc_records if d.doc_type_correct is False])
        docs_needs_vision = len([d for d in self.doc_records if d.needs_vision])

        # Text quality distribution
        docs_text_good = len([d for d in self.doc_records if d.text_readable == "good"])
        docs_text_warn = len([d for d in self.doc_records if d.text_readable == "warn"])
        docs_text_poor = len([d for d in self.doc_records if d.text_readable == "poor"])

        # Field-level metrics (only for valid docs with labels)
        labeled_required = [r for r in valid_records if r.is_required and r.has_label]

        # Presence rate (among required fields)
        if labeled_required:
            presence_rate = sum(1 for r in labeled_required if r.has_prediction) / len(labeled_required)
        else:
            presence_rate = 0.0

        # Accuracy (among required fields with correct/incorrect judgement)
        accuracy_denom = [r for r in labeled_required if r.judgement in ("correct", "incorrect")]
        if accuracy_denom:
            accuracy_numer = [r for r in accuracy_denom if r.outcome == FieldOutcome.CORRECT]
            accuracy = len(accuracy_numer) / len(accuracy_denom)
        else:
            accuracy = 0.0

        # Evidence rate (among extracted fields)
        extracted = [r for r in valid_records if r.has_prediction]
        if extracted:
            evidence_rate = sum(1 for r in extracted if r.has_evidence) / len(extracted)
        else:
            evidence_rate = 0.0

        return {
            "docs_total": total_docs,
            "docs_reviewed": docs_reviewed,
            "docs_doc_type_wrong": docs_doc_type_wrong,
            "docs_needs_vision": docs_needs_vision,
            "docs_text_good": docs_text_good,
            "docs_text_warn": docs_text_warn,
            "docs_text_poor": docs_text_poor,
            "required_field_presence_rate": round(presence_rate * 100, 1),
            "required_field_accuracy": round(accuracy * 100, 1),
            "evidence_rate": round(evidence_rate * 100, 1),
        }

    def get_doc_type_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics per doc type."""
        self.load_data()

        results = []
        for doc_type in SUPPORTED_DOC_TYPES:
            type_docs = [d for d in self.doc_records if d.doc_type == doc_type]
            if not type_docs:
                continue

            docs_reviewed = len([d for d in type_docs if d.has_labels])
            docs_doc_type_wrong = len([d for d in type_docs if d.doc_type_correct is False])
            docs_needs_vision = len([d for d in type_docs if d.needs_vision])

            # Valid docs for field metrics
            valid_doc_ids = {d.doc_id for d in type_docs if d.doc_type_correct is True}
            type_records = [r for r in self.field_records
                           if r.doc_type == doc_type and r.doc_id in valid_doc_ids]

            # Required fields
            required_records = [r for r in type_records if r.is_required and r.has_label]

            # Presence
            if required_records:
                presence = sum(1 for r in required_records if r.has_prediction) / len(required_records)
            else:
                presence = 0.0

            # Accuracy
            accuracy_denom = [r for r in required_records if r.judgement in ("correct", "incorrect")]
            if accuracy_denom:
                accuracy = len([r for r in accuracy_denom if r.outcome == FieldOutcome.CORRECT]) / len(accuracy_denom)
            else:
                accuracy = 0.0

            # Evidence
            extracted = [r for r in type_records if r.has_prediction]
            evidence = sum(1 for r in extracted if r.has_evidence) / len(extracted) if extracted else 0.0

            # Top failing field
            field_failures = {}
            for r in type_records:
                if r.outcome in (FieldOutcome.EXTRACTOR_MISS, FieldOutcome.INCORRECT):
                    field_failures[r.field_name] = field_failures.get(r.field_name, 0) + 1
            top_field = max(field_failures, key=field_failures.get) if field_failures else None

            results.append({
                "doc_type": doc_type,
                "docs_reviewed": docs_reviewed,
                "docs_doc_type_wrong": docs_doc_type_wrong,
                "docs_doc_type_wrong_pct": round(docs_doc_type_wrong / len(type_docs) * 100, 1) if type_docs else 0,
                "docs_needs_vision": docs_needs_vision,
                "docs_needs_vision_pct": round(docs_needs_vision / len(type_docs) * 100, 1) if type_docs else 0,
                "required_field_presence_pct": round(presence * 100, 1),
                "required_field_accuracy_pct": round(accuracy * 100, 1),
                "evidence_rate_pct": round(evidence * 100, 1),
                "top_failing_field": top_field,
            })

        return results

    def get_priorities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get prioritized list of (doc_type, field) to improve."""
        self.load_data()

        # Only consider docs where doc_type is correct
        valid_docs = {r.doc_id for r in self.doc_records if r.doc_type_correct is True}
        valid_records = [r for r in self.field_records if r.doc_id in valid_docs and r.has_label]

        # Group by (doc_type, field_name)
        groups: Dict[Tuple[str, str], List[FieldRecord]] = {}
        for r in valid_records:
            key = (r.doc_type, r.field_name)
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        priorities = []
        for (doc_type, field_name), records in groups.items():
            spec = self.specs.get(doc_type, {})
            is_required = field_name in spec.get("required_fields", [])

            # Count outcomes
            extractor_miss = len([r for r in records if r.outcome == FieldOutcome.EXTRACTOR_MISS])
            incorrect = len([r for r in records if r.outcome == FieldOutcome.INCORRECT])
            evidence_missing = len([r for r in records if r.evidence_missing_tag])
            cannot_verify = len([r for r in records if r.outcome == FieldOutcome.CANNOT_VERIFY])

            affected = extractor_miss + incorrect
            if affected == 0:
                continue

            # Priority score: weighted by severity
            score = (extractor_miss * 3) + (incorrect * 3) + (evidence_missing * 2) + (cannot_verify * 1)

            # Determine fix bucket
            # Get text quality of affected docs
            affected_doc_ids = {r.doc_id for r in records if r.outcome in (FieldOutcome.EXTRACTOR_MISS, FieldOutcome.INCORRECT)}
            affected_doc_records = [d for d in self.doc_records if d.doc_id in affected_doc_ids]
            needs_vision_count = len([d for d in affected_doc_records if d.needs_vision])
            text_poor_count = len([d for d in affected_doc_records if d.text_readable in ("warn", "poor")])

            if evidence_missing > extractor_miss and evidence_missing > incorrect:
                fix_bucket = "Improve provenance capture"
            elif extractor_miss > incorrect:
                if needs_vision_count > len(affected_doc_ids) * 0.5:
                    fix_bucket = "Improve OCR/vision fallback"
                elif text_poor_count > len(affected_doc_ids) * 0.5:
                    fix_bucket = "Improve text quality"
                else:
                    fix_bucket = "Improve span finding / extraction prompt"
            else:
                fix_bucket = "Improve extraction accuracy"

            priorities.append({
                "doc_type": doc_type,
                "field_name": field_name,
                "is_required": is_required,
                "affected_docs": affected,
                "total_labeled": len(records),
                "extractor_miss": extractor_miss,
                "incorrect": incorrect,
                "evidence_missing": evidence_missing,
                "cannot_verify": cannot_verify,
                "priority_score": score,
                "fix_bucket": fix_bucket,
            })

        # Sort by priority score descending
        priorities.sort(key=lambda p: p["priority_score"], reverse=True)
        return priorities[:limit]

    def get_field_details(self, doc_type: str, field_name: str) -> Dict[str, Any]:
        """Get detailed breakdown for a specific (doc_type, field)."""
        self.load_data()

        valid_docs = {r.doc_id for r in self.doc_records if r.doc_type_correct is True}
        records = [
            r for r in self.field_records
            if r.doc_type == doc_type
            and r.field_name == field_name
            and r.doc_id in valid_docs
        ]

        spec = self.specs.get(doc_type, {})
        is_required = field_name in spec.get("required_fields", [])

        total = len(records)
        labeled = len([r for r in records if r.has_label])
        with_prediction = len([r for r in records if r.has_prediction])
        with_evidence = len([r for r in records if r.has_evidence])

        # Outcome counts
        correct = len([r for r in records if r.outcome == FieldOutcome.CORRECT])
        incorrect = len([r for r in records if r.outcome == FieldOutcome.INCORRECT])
        extractor_miss = len([r for r in records if r.outcome == FieldOutcome.EXTRACTOR_MISS])
        cannot_verify = len([r for r in records if r.outcome == FieldOutcome.CANNOT_VERIFY])
        evidence_missing = len([r for r in records if r.evidence_missing_tag])

        return {
            "doc_type": doc_type,
            "field_name": field_name,
            "is_required": is_required,
            "total_docs": total,
            "labeled_docs": labeled,
            "with_prediction": with_prediction,
            "with_evidence": with_evidence,
            "breakdown": {
                "correct": correct,
                "incorrect": incorrect,
                "extractor_miss": extractor_miss,
                "cannot_verify": cannot_verify,
                "evidence_missing": evidence_missing,
            },
            "rates": {
                "presence_pct": round(with_prediction / total * 100, 1) if total else 0,
                "evidence_pct": round(with_evidence / with_prediction * 100, 1) if with_prediction else 0,
                "accuracy_pct": round(correct / (correct + incorrect) * 100, 1) if (correct + incorrect) else 0,
            }
        }

    def get_examples(
        self,
        doc_type: Optional[str] = None,
        field_name: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get example cases for drilldown."""
        self.load_data()

        records = self.field_records

        # Apply filters
        if doc_type:
            records = [r for r in records if r.doc_type == doc_type]
        if field_name:
            records = [r for r in records if r.field_name == field_name]
        if outcome:
            if outcome == "evidence_missing":
                records = [r for r in records if r.evidence_missing_tag]
            else:
                try:
                    outcome_enum = FieldOutcome(outcome)
                    records = [r for r in records if r.outcome == outcome_enum]
                except ValueError:
                    pass

        # Only include labeled records
        records = [r for r in records if r.has_label]

        # Limit
        records = records[:limit]

        examples = []
        for r in records:
            review_url = f"/claims/{r.claim_id}/review?doc_id={r.doc_id}&field={r.field_name}"
            examples.append({
                "claim_id": r.claim_id,
                "doc_id": r.doc_id,
                "filename": r.filename,
                "doc_type": r.doc_type,
                "field_name": r.field_name,
                "predicted_value": r.predicted_value,
                "normalized_value": r.normalized_value,
                "judgement": r.judgement,
                "has_evidence": r.has_evidence,
                "needs_vision": r.needs_vision,
                "gate_status": r.gate_status,
                "text_readable": r.text_readable,
                "outcome": r.outcome.value if r.outcome else None,
                "doc_type_correct": r.doc_type_correct,
                "review_url": review_url,
            })

        return examples
