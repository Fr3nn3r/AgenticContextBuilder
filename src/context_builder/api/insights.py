"""
Calibration Insights aggregation logic.

Computes metrics from extraction results and labels to answer:
- What is working? What is failing?
- Why is it failing? (extractor miss, normalization, evidence, doc type)
- What should we improve next? (highest ROI)

Scope: 3 supported doc types (loss_notice, police_report, insurance_policy)
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from enum import Enum


# Supported doc types for insights
SUPPORTED_DOC_TYPES = ["loss_notice", "police_report", "insurance_policy"]

# Baseline settings file
BASELINE_FILE = ".insights_baseline.json"


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
    gate_status: Optional[str]
    outcome: str
    review_url: str


@dataclass
class RunInfo:
    """Information about a single extraction run."""
    run_id: str
    timestamp: Optional[str]
    model: str
    extractor_version: str
    prompt_version: str
    docs_count: int
    extracted_count: int
    labeled_count: int
    # KPI snapshot
    presence_rate: float = 0.0
    accuracy_rate: float = 0.0
    evidence_rate: float = 0.0


class InsightsAggregator:
    """
    Aggregates extraction results and labels into insights metrics.
    """

    def __init__(self, data_dir: Path, run_id: Optional[str] = None):
        self.data_dir = data_dir
        self.run_id = run_id  # None means "latest"
        self.field_records: List[FieldRecord] = []
        self.doc_records: List[DocRecord] = []
        self.specs: Dict[str, Any] = {}
        self.run_metadata: Dict[str, Any] = {}
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

            # Get specific run or latest
            if self.run_id:
                run_dir = self._get_run_dir_by_id(claim_dir, self.run_id)
            else:
                run_dir = self._get_latest_run_dir(claim_dir)

            extraction_dir = run_dir / "extraction" if run_dir else None
            # Note: labels are now loaded from docs/{doc_id}/labels/latest.json (run-independent)

            # Collect run metadata from first claim with this run
            if run_dir and not self.run_metadata:
                self._load_run_metadata(run_dir)

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

                # Load extraction (from run directory)
                extraction = None
                if extraction_dir:
                    ext_path = extraction_dir / f"{doc_id}.json"
                    if ext_path.exists():
                        with open(ext_path, "r", encoding="utf-8") as f:
                            extraction = json.load(f)

                # Load labels (from docs/{doc_id}/labels/latest.json - run-independent)
                labels = None
                labels_path = doc_folder / "labels" / "latest.json"
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
        if extraction:
            qg = extraction.get("quality_gate", {})
            gate_status = qg.get("status")

        # Extract doc-level info from labels
        doc_type_correct = None
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

    def _get_run_dir_by_id(self, claim_dir: Path, run_id: str) -> Optional[Path]:
        """Get a specific run directory by ID."""
        runs_dir = claim_dir / "runs"
        if not runs_dir.exists():
            return None
        run_dir = runs_dir / run_id
        if run_dir.exists() and run_dir.is_dir():
            return run_dir
        return None

    def _load_run_metadata(self, run_dir: Path) -> None:
        """Load run metadata from summary.json."""
        summary_path = run_dir / "logs" / "summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
                self.run_metadata = {
                    "run_id": run_dir.name,
                    "timestamp": summary.get("completed_at"),
                    "model": summary.get("model", ""),
                    "extractor_version": summary.get("extractor_version", ""),
                    "prompt_version": summary.get("prompt_version", ""),
                    "docs_processed": summary.get("docs_processed", 0),
                }
        else:
            self.run_metadata = {
                "run_id": run_dir.name,
                "timestamp": None,
                "model": "",
                "extractor_version": "",
                "prompt_version": "",
                "docs_processed": 0,
            }

    def _extract_claim_number(self, folder_name: str) -> str:
        """Extract claim number from folder name."""
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

        # Run coverage: docs with extraction in this run / labeled docs
        # A doc has extraction if it has at least one field with a prediction
        docs_with_extraction = len({r.doc_id for r in self.field_records if r.has_prediction})
        if docs_reviewed > 0:
            run_coverage = docs_with_extraction / docs_reviewed
        else:
            run_coverage = 0.0

        return {
            "docs_total": total_docs,
            "docs_reviewed": docs_reviewed,
            "docs_doc_type_wrong": docs_doc_type_wrong,
            "required_field_presence_rate": round(presence_rate * 100, 1),
            "required_field_accuracy": round(accuracy * 100, 1),
            "evidence_rate": round(evidence_rate * 100, 1),
            "run_coverage": round(run_coverage * 100, 1),
            "docs_with_extraction": docs_with_extraction,
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
            if evidence_missing > extractor_miss and evidence_missing > incorrect:
                fix_bucket = "Improve provenance capture"
            elif extractor_miss > incorrect:
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
                "gate_status": r.gate_status,
                "outcome": r.outcome.value if r.outcome else None,
                "doc_type_correct": r.doc_type_correct,
                "review_url": review_url,
            })

        return examples

    def get_run_metadata(self) -> Dict[str, Any]:
        """Get metadata for the current run."""
        self.load_data()
        return {
            **self.run_metadata,
            "docs_total": len(self.doc_records),
            "docs_reviewed": len([d for d in self.doc_records if d.has_labels]),
        }


# =============================================================================
# Run Management Functions
# =============================================================================

def list_all_runs(data_dir: Path) -> List[Dict[str, Any]]:
    """
    List all extraction runs with their metadata and KPIs.
    Reads from global runs directory (output/runs/) when available.
    Falls back to scanning claim folders for backwards compatibility.
    Returns runs sorted by timestamp (newest first).
    """
    runs_map: Dict[str, Dict[str, Any]] = {}

    if not data_dir.exists():
        return []

    # First, try global runs directory (new structure)
    global_runs_dir = data_dir.parent / "runs"
    if global_runs_dir.exists():
        for run_dir in global_runs_dir.iterdir():
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue
            # Only include runs with .complete marker
            if not (run_dir / ".complete").exists():
                continue

            run_id = run_dir.name
            runs_map[run_id] = {
                "run_id": run_id,
                "timestamp": None,
                "model": "",
                "extractor_version": "",
                "prompt_version": "",
                "claims_count": 0,
                "docs_count": 0,
                "extracted_count": 0,
                "labeled_count": 0,
            }

            # Read from global manifest
            manifest_path = run_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    runs_map[run_id]["model"] = manifest.get("model", "")
                    runs_map[run_id]["claims_count"] = manifest.get("claims_count", 0)

            # Read from global summary
            summary_path = run_dir / "summary.json"
            if summary_path.exists():
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
                    runs_map[run_id]["timestamp"] = summary.get("completed_at")
                    runs_map[run_id]["docs_count"] = summary.get("docs_total", 0)
                    runs_map[run_id]["extracted_count"] = summary.get("docs_success", 0)

        # If we found global runs, use them
        if runs_map:
            runs = list(runs_map.values())
            runs.sort(key=lambda r: r["timestamp"] or "", reverse=True)
            # Calculate KPIs for each run
            for run in runs:
                aggregator = InsightsAggregator(data_dir, run_id=run["run_id"])
                try:
                    overview = aggregator.get_overview()
                    run["presence_rate"] = overview.get("required_field_presence_rate", 0)
                    run["accuracy_rate"] = overview.get("required_field_accuracy", 0)
                    run["evidence_rate"] = overview.get("evidence_rate", 0)
                except Exception:
                    run["presence_rate"] = 0
                    run["accuracy_rate"] = 0
                    run["evidence_rate"] = 0
            return runs

    # Fallback: scan claim folders for backwards compatibility
    for claim_dir in data_dir.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue

        runs_dir = claim_dir / "runs"
        if not runs_dir.exists():
            continue

        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue

            run_id = run_dir.name
            if run_id not in runs_map:
                runs_map[run_id] = {
                    "run_id": run_id,
                    "timestamp": None,
                    "model": "",
                    "extractor_version": "",
                    "prompt_version": "",
                    "claims_count": 0,
                    "docs_count": 0,
                    "extracted_count": 0,
                    "labeled_count": 0,
                }

            runs_map[run_id]["claims_count"] += 1

            # Try to get metadata from summary.json
            summary_path = run_dir / "logs" / "summary.json"
            if summary_path.exists() and not runs_map[run_id]["timestamp"]:
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
                    runs_map[run_id]["timestamp"] = summary.get("completed_at")
                    runs_map[run_id]["model"] = summary.get("model", "")
                    runs_map[run_id]["extractor_version"] = summary.get("extractor_version", "")
                    runs_map[run_id]["prompt_version"] = summary.get("prompt_version", "")

            # Count extractions
            extraction_dir = run_dir / "extraction"
            if extraction_dir.exists():
                runs_map[run_id]["extracted_count"] += len(list(extraction_dir.glob("*.json")))

            # Count docs and labels (labels are at docs/{doc_id}/labels/latest.json - run-independent)
            docs_dir = claim_dir / "docs"
            if docs_dir.exists():
                for doc_folder in docs_dir.iterdir():
                    if doc_folder.is_dir():
                        runs_map[run_id]["docs_count"] += 1
                        labels_path = doc_folder / "labels" / "latest.json"
                        if labels_path.exists():
                            runs_map[run_id]["labeled_count"] += 1

    # Convert to list and sort by timestamp (newest first)
    runs = list(runs_map.values())
    runs.sort(key=lambda r: r["timestamp"] or "", reverse=True)

    # Calculate KPIs for each run
    for run in runs:
        aggregator = InsightsAggregator(data_dir, run_id=run["run_id"])
        try:
            overview = aggregator.get_overview()
            run["presence_rate"] = overview.get("required_field_presence_rate", 0)
            run["accuracy_rate"] = overview.get("required_field_accuracy", 0)
            run["evidence_rate"] = overview.get("evidence_rate", 0)
        except Exception:
            run["presence_rate"] = 0
            run["accuracy_rate"] = 0
            run["evidence_rate"] = 0

    return runs


def compare_runs(data_dir: Path, baseline_run_id: str, current_run_id: str) -> Dict[str, Any]:
    """
    Compare two runs and compute deltas.

    Returns:
    - overview_deltas: delta for each KPI
    - priority_changes: fields that improved/regressed
    - doc_type_deltas: per doc type metric changes
    """
    baseline = InsightsAggregator(data_dir, run_id=baseline_run_id)
    current = InsightsAggregator(data_dir, run_id=current_run_id)

    baseline_overview = baseline.get_overview()
    current_overview = current.get_overview()

    baseline_priorities = baseline.get_priorities(limit=20)
    current_priorities = current.get_priorities(limit=20)

    baseline_doc_types = baseline.get_doc_type_metrics()
    current_doc_types = current.get_doc_type_metrics()

    # Compute overview deltas
    overview_deltas = {}
    for key in ["required_field_presence_rate", "required_field_accuracy", "evidence_rate",
                "docs_reviewed", "docs_doc_type_wrong"]:
        baseline_val = baseline_overview.get(key, 0)
        current_val = current_overview.get(key, 0)
        delta = current_val - baseline_val if isinstance(current_val, (int, float)) else 0
        overview_deltas[key] = {
            "baseline": baseline_val,
            "current": current_val,
            "delta": round(delta, 1) if isinstance(delta, float) else delta,
        }

    # Compute priority changes
    baseline_priority_set = {(p["doc_type"], p["field_name"]) for p in baseline_priorities}
    current_priority_set = {(p["doc_type"], p["field_name"]) for p in current_priorities}

    # Fields that were in baseline but not in current (improved)
    improved = [
        {"doc_type": dt, "field_name": fn, "status": "improved"}
        for dt, fn in baseline_priority_set - current_priority_set
    ]

    # Fields that are in current but not in baseline (regressed)
    regressed = [
        {"doc_type": dt, "field_name": fn, "status": "regressed"}
        for dt, fn in current_priority_set - baseline_priority_set
    ]

    # Fields in both - compare affected counts
    for p in current_priorities:
        key = (p["doc_type"], p["field_name"])
        if key in baseline_priority_set:
            baseline_p = next((bp for bp in baseline_priorities
                              if bp["doc_type"] == p["doc_type"] and bp["field_name"] == p["field_name"]), None)
            if baseline_p:
                delta = p["affected_docs"] - baseline_p["affected_docs"]
                if delta != 0:
                    regressed.append({
                        "doc_type": p["doc_type"],
                        "field_name": p["field_name"],
                        "status": "regressed" if delta > 0 else "improved",
                        "delta": delta,
                    })

    # Compute doc type deltas
    doc_type_deltas = []
    baseline_dt_map = {dt["doc_type"]: dt for dt in baseline_doc_types}
    for dt in current_doc_types:
        baseline_dt = baseline_dt_map.get(dt["doc_type"], {})
        doc_type_deltas.append({
            "doc_type": dt["doc_type"],
            "presence_delta": round(dt.get("required_field_presence_pct", 0) - baseline_dt.get("required_field_presence_pct", 0), 1),
            "accuracy_delta": round(dt.get("required_field_accuracy_pct", 0) - baseline_dt.get("required_field_accuracy_pct", 0), 1),
            "evidence_delta": round(dt.get("evidence_rate_pct", 0) - baseline_dt.get("evidence_rate_pct", 0), 1),
        })

    return {
        "baseline_run_id": baseline_run_id,
        "current_run_id": current_run_id,
        "baseline_metadata": baseline.get_run_metadata(),
        "current_metadata": current.get_run_metadata(),
        "overview_deltas": overview_deltas,
        "priority_changes": improved + regressed,
        "doc_type_deltas": doc_type_deltas,
    }


def get_baseline(data_dir: Path) -> Optional[str]:
    """Get the current baseline run ID."""
    baseline_path = data_dir / BASELINE_FILE
    if baseline_path.exists():
        with open(baseline_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("baseline_run_id")
    return None


def set_baseline(data_dir: Path, run_id: str) -> None:
    """Set a run as the baseline."""
    baseline_path = data_dir / BASELINE_FILE
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump({"baseline_run_id": run_id, "set_at": datetime.now().isoformat()}, f)


def clear_baseline(data_dir: Path) -> None:
    """Clear the baseline setting."""
    baseline_path = data_dir / BASELINE_FILE
    if baseline_path.exists():
        baseline_path.unlink()


def list_detailed_runs(data_dir: Path) -> List[Dict[str, Any]]:
    """
    List all extraction runs with detailed metadata including phase metrics.
    Aggregates per-claim summaries to compute phase-level data.

    Returns list of DetailedRunInfo sorted by timestamp (newest first).
    """
    detailed_runs = []

    if not data_dir.exists():
        return []

    # Check global runs directory first
    global_runs_dir = data_dir.parent / "runs"
    if not global_runs_dir.exists():
        return []

    for run_dir in global_runs_dir.iterdir():
        if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
            continue
        # Only include runs with .complete marker
        if not (run_dir / ".complete").exists():
            continue

        run_id = run_dir.name
        run_info = {
            "run_id": run_id,
            "timestamp": None,
            "model": "",
            "status": "complete",
            "duration_seconds": None,
            "claims_count": 0,
            "docs_total": 0,
            "docs_success": 0,
            "docs_failed": 0,
            "phases": {
                "ingestion": {
                    "discovered": 0,
                    "ingested": 0,
                    "skipped": 0,
                    "failed": 0,
                    "duration_ms": None,
                },
                "classification": {
                    "classified": 0,
                    "low_confidence": 0,
                    "distribution": {},
                    "duration_ms": None,
                },
                "extraction": {
                    "attempted": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "duration_ms": None,
                },
                "quality_gate": {
                    "pass": 0,
                    "warn": 0,
                    "fail": 0,
                },
            },
        }

        # Read from global manifest
        manifest_path = run_dir / "manifest.json"
        claim_run_paths = []
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                run_info["model"] = manifest.get("model", "")
                run_info["claims_count"] = manifest.get("claims_count", 0)
                # Get list of claim run paths for aggregation
                # Paths in manifest are relative to project root (e.g., output/claims/...)
                for claim in manifest.get("claims", []):
                    path_str = claim.get("claim_run_path", "")
                    if path_str:
                        claim_path = Path(path_str)
                        # If path is not absolute, it's relative to project root
                        if not claim_path.is_absolute():
                            # Check if path already exists relative to cwd
                            if not claim_path.exists():
                                # Try relative to data_dir.parent.parent (project root)
                                claim_path = data_dir.parent.parent / claim_path
                        claim_run_paths.append(claim_path)

        # Read from global summary
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
                run_info["timestamp"] = summary.get("completed_at")
                run_info["docs_total"] = summary.get("docs_total", 0)
                run_info["docs_success"] = summary.get("docs_success", 0)
                run_info["docs_failed"] = summary.get("docs_total", 0) - summary.get("docs_success", 0)

                # Determine status
                if summary.get("status") == "success":
                    run_info["status"] = "complete"
                elif summary.get("claims_failed", 0) > 0:
                    run_info["status"] = "partial"
                else:
                    run_info["status"] = "complete"

        # Aggregate per-claim summaries for phase metrics
        total_time_ms = 0
        for claim_run_path in claim_run_paths:
            claim_summary_path = claim_run_path / "logs" / "summary.json"
            if not claim_summary_path.exists():
                continue

            try:
                with open(claim_summary_path, "r", encoding="utf-8") as f:
                    claim_summary = json.load(f)

                # Ingestion metrics from aggregates
                aggregates = claim_summary.get("aggregates", {})
                run_info["phases"]["ingestion"]["discovered"] += aggregates.get("discovered", 0)
                run_info["phases"]["ingestion"]["ingested"] += aggregates.get("processed", 0)
                run_info["phases"]["ingestion"]["skipped"] += aggregates.get("skipped", 0)
                run_info["phases"]["ingestion"]["failed"] += aggregates.get("failed", 0)

                # Extraction metrics from stats
                stats = claim_summary.get("stats", {})
                run_info["phases"]["extraction"]["attempted"] += stats.get("total", 0)
                run_info["phases"]["extraction"]["succeeded"] += stats.get("success", 0)
                run_info["phases"]["extraction"]["failed"] += stats.get("errors", 0)

                # Processing time
                if claim_summary.get("processing_time_seconds"):
                    total_time_ms += int(claim_summary["processing_time_seconds"] * 1000)

                # Per-document data for classification and quality gate
                for doc in claim_summary.get("documents", []):
                    doc_type = doc.get("doc_type_predicted")
                    if doc_type:
                        run_info["phases"]["classification"]["classified"] += 1
                        dist = run_info["phases"]["classification"]["distribution"]
                        dist[doc_type] = dist.get(doc_type, 0) + 1

                    # Quality gate from extraction results
                    extraction_path = doc.get("output_paths", {}).get("extraction")
                    if extraction_path:
                        ext_full_path = claim_run_path / extraction_path
                        if ext_full_path.exists():
                            try:
                                with open(ext_full_path, "r", encoding="utf-8") as ef:
                                    ext_result = json.load(ef)
                                    qg = ext_result.get("quality_gate", {})
                                    gate_status = qg.get("status", "").lower()
                                    if gate_status == "pass":
                                        run_info["phases"]["quality_gate"]["pass"] += 1
                                    elif gate_status == "warn":
                                        run_info["phases"]["quality_gate"]["warn"] += 1
                                    elif gate_status == "fail":
                                        run_info["phases"]["quality_gate"]["fail"] += 1
                            except (json.JSONDecodeError, IOError):
                                pass

            except (json.JSONDecodeError, IOError):
                continue

        # Set total duration
        if total_time_ms > 0:
            run_info["duration_seconds"] = round(total_time_ms / 1000, 1)

        detailed_runs.append(run_info)

    # Sort by timestamp (newest first)
    detailed_runs.sort(key=lambda r: r["timestamp"] or "", reverse=True)
    return detailed_runs
