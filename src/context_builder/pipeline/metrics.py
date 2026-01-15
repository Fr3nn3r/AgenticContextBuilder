"""Metrics computation for pipeline runs.

Computes KPIs for a run against the latest document labels.
These metrics are written to metrics.json after each run completes.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import RunPaths

logger = logging.getLogger(__name__)


def compute_run_metrics(
    run_paths: RunPaths,
    claim_dir: Path,
    baseline_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute KPIs for this run against latest doc labels.

    Args:
        run_paths: Paths for the current run
        claim_dir: Path to claim directory (contains docs/ and runs/)
        baseline_run_id: Optional baseline run ID for comparison

    Returns:
        Dict with computed metrics
    """
    docs_dir = claim_dir / "docs"
    extraction_dir = run_paths.extraction_dir
    # Labels are stored in registry/labels/ (sibling of claims/)
    registry_labels_dir = claim_dir.parent.parent / "registry" / "labels"

    # Collect all doc_ids from extractions in this run
    extraction_files = list(extraction_dir.glob("*.json"))
    doc_ids_in_run = {f.stem for f in extraction_files}

    # Collect all doc_ids with labels (from registry)
    labeled_doc_ids = set()
    for doc_folder in docs_dir.iterdir():
        if doc_folder.is_dir():
            doc_id = doc_folder.name
            labels_path = registry_labels_dir / f"{doc_id}.json"
            if labels_path.exists():
                labeled_doc_ids.add(doc_id)

    # Total docs in claim
    total_doc_ids = {d.name for d in docs_dir.iterdir() if d.is_dir()}

    # Compute coverage metrics
    docs_total = len(total_doc_ids)
    docs_labeled = len(labeled_doc_ids)
    docs_in_run = len(doc_ids_in_run)
    docs_labeled_and_in_run = len(labeled_doc_ids & doc_ids_in_run)

    label_coverage = (docs_labeled / docs_total * 100) if docs_total > 0 else 0
    run_coverage = (docs_labeled_and_in_run / docs_labeled * 100) if docs_labeled > 0 else 0

    # Load extractions and labels for detailed metrics
    field_metrics = _compute_field_metrics(
        extraction_dir, registry_labels_dir, labeled_doc_ids & doc_ids_in_run
    )

    # Build metrics dict
    metrics = {
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "run_id": run_paths.run_root.name,
        "baseline_run_id": baseline_run_id,
        "coverage": {
            "docs_total": docs_total,
            "docs_labeled": docs_labeled,
            "docs_in_run": docs_in_run,
            "docs_labeled_and_in_run": docs_labeled_and_in_run,
            "label_coverage_pct": round(label_coverage, 1),
            "run_coverage_pct": round(run_coverage, 1),
        },
        "field_metrics": field_metrics,
    }

    return metrics


def _compute_field_metrics(
    extraction_dir: Path,
    registry_labels_dir: Path,
    doc_ids: set,
) -> Dict[str, Any]:
    """
    Compute field-level metrics for documents that have both extraction and labels.

    Only includes documents where doc_type_correct is True (not False or missing).
    Documents with wrong doc_type are excluded from accuracy metrics to avoid
    contaminating results with misclassified documents.

    Args:
        extraction_dir: Directory containing extraction JSON files
        registry_labels_dir: Directory containing label JSON files (registry/labels/)
        doc_ids: Set of doc_ids to process

    Returns:
        Dict with field presence, accuracy, and evidence metrics
    """
    if not doc_ids:
        return {
            "total_fields": 0,
            "fields_with_prediction": 0,
            "fields_with_label": 0,
            "required_field_presence_pct": 0,
            "required_field_accuracy_pct": 0,
            "evidence_rate_pct": 0,
            "by_doc_type": {},
            "top_failing_fields": [],
            "docs_excluded_wrong_type": 0,
        }

    # Aggregate counters
    total_required_fields = 0
    required_fields_present = 0
    required_fields_correct = 0
    required_fields_labeled = 0
    total_fields_with_evidence = 0
    total_fields_with_value = 0
    docs_excluded_wrong_type = 0

    # Per doc type counters
    by_doc_type: Dict[str, Dict[str, int]] = defaultdict(lambda: {
        "docs_processed": 0,
        "required_present": 0,
        "required_total": 0,
        "correct": 0,
        "labeled": 0,
        "with_evidence": 0,
        "with_value": 0,
    })

    # Field failure tracking
    field_failures: Dict[str, Dict[str, int]] = defaultdict(lambda: {
        "extractor_miss": 0,
        "incorrect": 0,
        "cannot_verify": 0,
        "evidence_missing": 0,
    })

    for doc_id in doc_ids:
        extraction_path = extraction_dir / f"{doc_id}.json"
        labels_path = registry_labels_dir / f"{doc_id}.json"

        if not extraction_path.exists() or not labels_path.exists():
            continue

        try:
            with open(extraction_path, "r", encoding="utf-8") as f:
                extraction = json.load(f)
            with open(labels_path, "r", encoding="utf-8") as f:
                labels = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load data for {doc_id}: {e}")
            continue

        # CRITICAL: Filter by doc_type_correct
        # Only include docs where doc_type_correct is explicitly True
        # Docs with wrong doc_type contaminate accuracy metrics
        doc_labels = labels.get("doc_labels", {})
        doc_type_correct = doc_labels.get("doc_type_correct")
        if doc_type_correct is not True:
            # Skip docs where doc_type is wrong or unknown
            if doc_type_correct is False:
                docs_excluded_wrong_type += 1
                logger.debug(f"Excluding {doc_id} from metrics: doc_type_correct=False")
            continue

        doc_type = extraction.get("doc", {}).get("doc_type", "unknown")
        dt_counters = by_doc_type[doc_type]
        dt_counters["docs_processed"] += 1

        # Build field lookups
        ext_fields = {f.get("name"): f for f in extraction.get("fields", [])}
        label_fields = {fl.get("field_name"): fl for fl in labels.get("field_labels", [])}

        # Get required fields from extraction metadata or infer
        # For now, count fields with status != "missing" as expected
        for field_name, ext_field in ext_fields.items():
            is_required = ext_field.get("status") != "optional"
            has_value = bool(ext_field.get("value"))
            has_evidence = bool(ext_field.get("provenance"))

            if has_value:
                total_fields_with_value += 1
                dt_counters["with_value"] += 1

            if has_evidence:
                total_fields_with_evidence += 1
                dt_counters["with_evidence"] += 1

            if is_required:
                total_required_fields += 1
                dt_counters["required_total"] += 1

                if has_value:
                    required_fields_present += 1
                    dt_counters["required_present"] += 1

            # Check against label
            label_data = label_fields.get(field_name, {})
            judgement = label_data.get("judgement")

            if judgement:
                required_fields_labeled += 1
                dt_counters["labeled"] += 1

                if judgement == "correct":
                    required_fields_correct += 1
                    dt_counters["correct"] += 1
                elif judgement == "incorrect":
                    field_failures[(doc_type, field_name)]["incorrect"] += 1
                elif judgement == "unknown":
                    field_failures[(doc_type, field_name)]["cannot_verify"] += 1

            # Track extractor misses
            if is_required and not has_value:
                field_failures[(doc_type, field_name)]["extractor_miss"] += 1

            # Track evidence missing
            if has_value and not has_evidence:
                field_failures[(doc_type, field_name)]["evidence_missing"] += 1

    # Compute percentages
    presence_pct = (required_fields_present / total_required_fields * 100) if total_required_fields > 0 else 0
    accuracy_pct = (required_fields_correct / required_fields_labeled * 100) if required_fields_labeled > 0 else 0
    evidence_pct = (total_fields_with_evidence / total_fields_with_value * 100) if total_fields_with_value > 0 else 0

    # Build top failing fields
    top_failing = []
    for (doc_type, field_name), failures in sorted(
        field_failures.items(),
        key=lambda x: sum(x[1].values()),
        reverse=True,
    )[:10]:
        total_failures = sum(failures.values())
        if total_failures > 0:
            top_failing.append({
                "doc_type": doc_type,
                "field_name": field_name,
                "total_failures": total_failures,
                **failures,
            })

    # Build by_doc_type summary
    doc_type_summary = {}
    for doc_type, counters in by_doc_type.items():
        dt_presence = (counters["required_present"] / counters["required_total"] * 100) if counters["required_total"] > 0 else 0
        dt_accuracy = (counters["correct"] / counters["labeled"] * 100) if counters["labeled"] > 0 else 0
        dt_evidence = (counters["with_evidence"] / counters["with_value"] * 100) if counters["with_value"] > 0 else 0

        doc_type_summary[doc_type] = {
            "docs_processed": counters["docs_processed"],
            "presence_pct": round(dt_presence, 1),
            "accuracy_pct": round(dt_accuracy, 1),
            "evidence_pct": round(dt_evidence, 1),
        }

    return {
        "total_fields": total_required_fields,
        "fields_with_prediction": required_fields_present,
        "fields_with_label": required_fields_labeled,
        "required_field_presence_pct": round(presence_pct, 1),
        "required_field_accuracy_pct": round(accuracy_pct, 1),
        "evidence_rate_pct": round(evidence_pct, 1),
        "by_doc_type": doc_type_summary,
        "top_failing_fields": top_failing,
        "docs_excluded_wrong_type": docs_excluded_wrong_type,
    }
