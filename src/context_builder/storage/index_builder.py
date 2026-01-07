"""Index builder for creating JSONL registry indexes from filesystem.

Scans output folders and builds indexes for fast lookups.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .index_reader import (
    DOC_INDEX_FILE,
    LABEL_INDEX_FILE,
    RUN_INDEX_FILE,
    REGISTRY_META_FILE,
    write_jsonl,
)

logger = logging.getLogger(__name__)


def build_doc_index(claims_dir: Path) -> list[dict]:
    """Build document index by scanning all claims.

    Args:
        claims_dir: Path to claims directory (output/claims/).

    Returns:
        List of document index records.
    """
    records = []

    if not claims_dir.exists():
        logger.warning(f"Claims directory does not exist: {claims_dir}")
        return records

    for claim_folder in sorted(claims_dir.iterdir()):
        if not claim_folder.is_dir():
            continue
        if claim_folder.name.startswith("."):
            continue

        docs_dir = claim_folder / "docs"
        if not docs_dir.exists():
            continue

        for doc_folder in sorted(docs_dir.iterdir()):
            if not doc_folder.is_dir():
                continue

            doc_json_path = doc_folder / "meta" / "doc.json"
            if not doc_json_path.exists():
                logger.debug(f"No doc.json found in {doc_folder}")
                continue

            try:
                with open(doc_json_path, "r", encoding="utf-8") as f:
                    doc_meta = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read {doc_json_path}: {e}")
                continue

            # Extract claim_id from doc.json if present, else use folder name
            claim_id = doc_meta.get("claim_id") or claim_folder.name

            # Check artifact availability
            source_dir = doc_folder / "source"
            has_pdf = any(source_dir.glob("*.pdf")) if source_dir.exists() else False
            has_images = (
                any(source_dir.glob("*.png"))
                or any(source_dir.glob("*.jpg"))
                or any(source_dir.glob("*.jpeg"))
            ) if source_dir.exists() else False

            pages_json = doc_folder / "text" / "pages.json"
            has_text = pages_json.exists()

            record = {
                "doc_id": doc_meta.get("doc_id", doc_folder.name),
                "claim_id": claim_id,
                "claim_folder": claim_folder.name,
                "doc_type": doc_meta.get("doc_type", "unknown"),
                "filename": doc_meta.get("original_filename", ""),
                "source_type": doc_meta.get("source_type", "unknown"),
                "language": doc_meta.get("language", "unknown"),
                "page_count": doc_meta.get("page_count", 1),
                "has_pdf": has_pdf,
                "has_text": has_text,
                "has_images": has_images,
                "doc_root": str(doc_folder.relative_to(claims_dir.parent)),
                "created_at": doc_meta.get("created_at"),
            }
            records.append(record)

    logger.info(f"Built doc index with {len(records)} documents")
    return records


def build_label_index(claims_dir: Path) -> list[dict]:
    """Build label index by scanning all label files.

    Args:
        claims_dir: Path to claims directory (output/claims/).

    Returns:
        List of label index records.
    """
    records = []

    if not claims_dir.exists():
        return records

    for claim_folder in sorted(claims_dir.iterdir()):
        if not claim_folder.is_dir():
            continue
        if claim_folder.name.startswith("."):
            continue

        docs_dir = claim_folder / "docs"
        if not docs_dir.exists():
            continue

        for doc_folder in sorted(docs_dir.iterdir()):
            if not doc_folder.is_dir():
                continue

            label_path = doc_folder / "labels" / "latest.json"
            if not label_path.exists():
                continue

            try:
                with open(label_path, "r", encoding="utf-8") as f:
                    label_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read {label_path}: {e}")
                continue

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

            # Get claim_id from label or infer from folder
            claim_id = label_data.get("claim_id") or claim_folder.name

            record = {
                "doc_id": label_data.get("doc_id", doc_folder.name),
                "claim_id": claim_id,
                "has_label": True,
                "labeled_count": labeled_count,
                "unverifiable_count": unverifiable_count,
                "unlabeled_count": unlabeled_count,
                "updated_at": updated_at,
            }
            records.append(record)

    logger.info(f"Built label index with {len(records)} labeled documents")
    return records


def build_run_index(output_dir: Path) -> list[dict]:
    """Build run index by scanning global runs directory.

    Args:
        output_dir: Path to output directory (output/).

    Returns:
        List of run index records.
    """
    records = []

    runs_dir = output_dir / "runs"
    if not runs_dir.exists():
        logger.warning(f"Runs directory does not exist: {runs_dir}")
        return records

    for run_folder in sorted(runs_dir.iterdir()):
        if not run_folder.is_dir():
            continue
        if not run_folder.name.startswith("run_"):
            continue

        # Only index complete runs
        complete_marker = run_folder / ".complete"
        if not complete_marker.exists():
            logger.debug(f"Skipping incomplete run: {run_folder.name}")
            continue

        # Read manifest for metadata
        manifest_path = run_folder / "manifest.json"
        summary_path = run_folder / "summary.json"

        manifest = {}
        summary = {}

        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read {manifest_path}: {e}")

        if summary_path.exists():
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read {summary_path}: {e}")

        # Build record from available data
        record = {
            "run_id": run_folder.name,
            "status": summary.get("status", "complete"),
            "started_at": manifest.get("started_at"),
            "ended_at": manifest.get("ended_at") or summary.get("completed_at"),
            "claims_count": manifest.get("claims_count", summary.get("claims_processed", 0)),
            "docs_count": summary.get("docs_total", summary.get("docs_success", 0)),
            "run_root": str(run_folder.relative_to(output_dir.parent)),
        }
        records.append(record)

    logger.info(f"Built run index with {len(records)} runs")
    return records


def build_all_indexes(
    output_dir: Path,
    registry_dir: Optional[Path] = None,
) -> dict:
    """Build all indexes and write to registry directory.

    Args:
        output_dir: Path to output directory (output/).
        registry_dir: Optional custom registry directory.
            Default: output/registry/

    Returns:
        Dictionary with build statistics.
    """
    claims_dir = output_dir / "claims"
    if registry_dir is None:
        registry_dir = output_dir / "registry"

    logger.info(f"Building indexes from {output_dir}")
    logger.info(f"Registry directory: {registry_dir}")

    # Create registry directory
    registry_dir.mkdir(parents=True, exist_ok=True)

    # Build each index
    doc_records = build_doc_index(claims_dir)
    label_records = build_label_index(claims_dir)
    run_records = build_run_index(output_dir)

    # Count unique claims
    claim_ids = set()
    for rec in doc_records:
        claim_ids.add(rec.get("claim_id") or rec.get("claim_folder"))

    # Write indexes
    doc_path = registry_dir / DOC_INDEX_FILE
    label_path = registry_dir / LABEL_INDEX_FILE
    run_path = registry_dir / RUN_INDEX_FILE
    meta_path = registry_dir / REGISTRY_META_FILE

    write_jsonl(doc_path, doc_records)
    write_jsonl(label_path, label_records)
    write_jsonl(run_path, run_records)

    # Write registry metadata
    meta = {
        "built_at": datetime.now().isoformat() + "Z",
        "doc_count": len(doc_records),
        "label_count": len(label_records),
        "run_count": len(run_records),
        "claim_count": len(claim_ids),
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    logger.info(f"Index build complete:")
    logger.info(f"  Documents: {len(doc_records)}")
    logger.info(f"  Labels: {len(label_records)}")
    logger.info(f"  Runs: {len(run_records)}")
    logger.info(f"  Claims: {len(claim_ids)}")

    return meta
