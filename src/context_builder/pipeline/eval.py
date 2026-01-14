"""Run evaluation against canonical truth."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from context_builder.storage import FileStorage
from context_builder.storage.truth_store import TruthStore

logger = logging.getLogger(__name__)


def _resolve_output_paths(output_root: Path) -> Tuple[Path, Path]:
    output_root = Path(output_root)
    if (output_root / "claims").exists():
        return output_root, output_root / "claims"
    if output_root.name == "claims":
        return output_root.parent, output_root
    return output_root.parent, output_root


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _iter_extractions(claims_dir: Path, run_id: str) -> Iterable[Path]:
    for claim_dir in claims_dir.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue
        extraction_dir = claim_dir / "runs" / run_id / "extraction"
        if not extraction_dir.exists():
            continue
        yield from extraction_dir.glob("*.json")


def _evaluate_document(
    extraction: Dict[str, Any],
    truth: Dict[str, Any],
    run_id: str,
    file_md5: str,
) -> Tuple[Dict[str, Any], Dict[str, int]]:
    extraction_fields = {
        f.get("name"): f for f in extraction.get("fields", []) if f.get("name")
    }
    field_results = []
    counts = {
        "fields_total": 0,
        "fields_labeled": 0,
        "correct": 0,
        "incorrect": 0,
        "missing": 0,
        "unverifiable": 0,
    }

    for label in truth.get("field_labels", []):
        field_name = label.get("field_name")
        if not field_name:
            continue

        counts["fields_total"] += 1
        state = label.get("state")
        truth_value = label.get("truth_value")
        ext_field = extraction_fields.get(field_name, {})
        predicted_value = ext_field.get("value")
        normalized_value = ext_field.get("normalized_value") or predicted_value
        has_prediction = bool(normalized_value)
        outcome = None

        if state in ("LABELED", "CONFIRMED"):
            counts["fields_labeled"] += 1
            if not has_prediction:
                outcome = "missing"
                counts["missing"] += 1
            elif normalized_value == truth_value:
                outcome = "correct"
                counts["correct"] += 1
            else:
                outcome = "incorrect"
                counts["incorrect"] += 1
        elif state == "UNVERIFIABLE":
            outcome = "unverifiable"
            counts["unverifiable"] += 1

        field_results.append({
            "field_name": field_name,
            "state": state,
            "truth_value": truth_value,
            "predicted_value": predicted_value,
            "normalized_value": normalized_value,
            "outcome": outcome,
        })

    doc_eval = {
        "schema_version": "eval_v1",
        "run_id": run_id,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "doc_id": extraction.get("doc", {}).get("doc_id"),
        "claim_id": extraction.get("doc", {}).get("claim_id"),
        "doc_type": extraction.get("doc", {}).get("doc_type"),
        "file_md5": file_md5,
        "doc_labels": truth.get("doc_labels", {}),
        "field_summary": counts,
        "fields": field_results,
        "source_doc_ref": truth.get("source_doc_ref", {}),
    }

    return doc_eval, counts


def evaluate_run(output_root: Path, run_id: str) -> Dict[str, Any]:
    """Evaluate a run against canonical truth by file_md5."""
    base_root, claims_dir = _resolve_output_paths(output_root)
    storage = FileStorage(base_root)
    truth_store = TruthStore(base_root)

    eval_dir = base_root / "runs" / run_id / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "schema_version": "eval_summary_v1",
        "run_id": run_id,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "docs_total": 0,
        "docs_evaluated": 0,
        "docs_skipped_no_truth": 0,
        "docs_skipped_missing_file_md5": 0,
        "fields_total": 0,
        "fields_labeled": 0,
        "correct": 0,
        "incorrect": 0,
        "missing": 0,
        "unverifiable": 0,
    }

    for extraction_path in _iter_extractions(claims_dir, run_id):
        summary["docs_total"] += 1

        try:
            with open(extraction_path, "r", encoding="utf-8") as f:
                extraction = json.load(f)
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("Failed to load extraction %s: %s", extraction_path, exc)
            continue

        doc_id = extraction.get("doc", {}).get("doc_id") or extraction_path.stem
        doc_bundle = storage.get_doc(doc_id)
        file_md5 = None
        if doc_bundle:
            file_md5 = doc_bundle.metadata.get("file_md5")
        if not file_md5:
            file_md5 = extraction.get("run", {}).get("input_hashes", {}).get("file_md5")

        if not file_md5:
            summary["docs_skipped_missing_file_md5"] += 1
            continue

        truth = truth_store.get_truth_by_file_md5(file_md5)
        if not truth:
            summary["docs_skipped_no_truth"] += 1
            continue

        doc_eval, counts = _evaluate_document(extraction, truth, run_id, file_md5)
        _atomic_write_json(eval_dir / f"{doc_id}.json", doc_eval)

        summary["docs_evaluated"] += 1
        summary["fields_total"] += counts["fields_total"]
        summary["fields_labeled"] += counts["fields_labeled"]
        summary["correct"] += counts["correct"]
        summary["incorrect"] += counts["incorrect"]
        summary["missing"] += counts["missing"]
        summary["unverifiable"] += counts["unverifiable"]

    _atomic_write_json(eval_dir / "summary.json", summary)
    return summary
