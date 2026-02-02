"""Index builder for creating JSONL registry indexes from filesystem.

Scans output folders and builds indexes for fast lookups.
Supports both full rebuilds and incremental updates.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .index_reader import (
    DOC_INDEX_FILE,
    LABEL_INDEX_FILE,
    RUN_INDEX_FILE,
    CLAIMS_INDEX_FILE,
    REGISTRY_META_FILE,
    write_jsonl,
    read_jsonl,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Incremental Index Update Functions
# -----------------------------------------------------------------------------


def append_doc_entry(registry_dir: Path, doc_entry: dict) -> bool:
    """Append a single document entry to the doc index.

    Args:
        registry_dir: Path to registry directory.
        doc_entry: Document entry dict matching doc_index schema.

    Returns:
        True if entry was appended successfully.
    """
    doc_index_path = registry_dir / DOC_INDEX_FILE
    if not doc_index_path.exists():
        logger.debug("Doc index does not exist, skipping append")
        return False

    try:
        with open(doc_index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(doc_entry, ensure_ascii=False, default=str) + "\n")
        logger.debug(f"Appended doc {doc_entry.get('doc_id')} to index")
        return True
    except IOError as e:
        logger.warning(f"Failed to append to doc index: {e}")
        return False


def append_run_entry(registry_dir: Path, run_entry: dict) -> bool:
    """Append a single run entry to the run index.

    Args:
        registry_dir: Path to registry directory.
        run_entry: Run entry dict matching run_index schema.

    Returns:
        True if entry was appended successfully.
    """
    run_index_path = registry_dir / RUN_INDEX_FILE
    if not run_index_path.exists():
        logger.debug("Run index does not exist, skipping append")
        return False

    try:
        with open(run_index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_entry, ensure_ascii=False, default=str) + "\n")
        logger.debug(f"Appended run {run_entry.get('run_id')} to index")
        return True
    except IOError as e:
        logger.warning(f"Failed to append to run index: {e}")
        return False


def upsert_label_entry(registry_dir: Path, label_entry: dict) -> bool:
    """Update or insert a label entry in the label index.

    If doc_id exists, updates the entry. Otherwise appends.

    Args:
        registry_dir: Path to registry directory.
        label_entry: Label entry dict matching label_index schema.

    Returns:
        True if entry was upserted successfully.
    """
    label_index_path = registry_dir / LABEL_INDEX_FILE
    if not label_index_path.exists():
        # Create new file with single entry
        try:
            registry_dir.mkdir(parents=True, exist_ok=True)
            with open(label_index_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(label_entry, ensure_ascii=False, default=str) + "\n")
            logger.debug(f"Created label index with doc {label_entry.get('doc_id')}")
            return True
        except IOError as e:
            logger.warning(f"Failed to create label index: {e}")
            return False

    try:
        doc_id = label_entry.get("doc_id")
        updated = False
        new_records = []

        # Read existing entries and update if found
        for record in read_jsonl(label_index_path):
            if record.get("doc_id") == doc_id:
                new_records.append(label_entry)
                updated = True
            else:
                new_records.append(record)

        # If not found, append
        if not updated:
            new_records.append(label_entry)

        # Write back
        write_jsonl(label_index_path, new_records)
        logger.debug(f"Upserted label for doc {doc_id}")
        return True
    except IOError as e:
        logger.warning(f"Failed to upsert label index: {e}")
        return False


def update_registry_meta(registry_dir: Path) -> bool:
    """Update registry metadata with current counts.

    Args:
        registry_dir: Path to registry directory.

    Returns:
        True if metadata was updated successfully.
    """
    meta_path = registry_dir / REGISTRY_META_FILE
    doc_index_path = registry_dir / DOC_INDEX_FILE
    label_index_path = registry_dir / LABEL_INDEX_FILE
    run_index_path = registry_dir / RUN_INDEX_FILE

    try:
        # Count entries in each index
        doc_count = sum(1 for _ in read_jsonl(doc_index_path))
        label_count = sum(1 for _ in read_jsonl(label_index_path))
        run_count = sum(1 for _ in read_jsonl(run_index_path))

        # Count unique claims from doc index
        claim_ids = set()
        for record in read_jsonl(doc_index_path):
            claim_ids.add(record.get("claim_id") or record.get("claim_folder"))

        meta = {
            "built_at": datetime.now().isoformat() + "Z",
            "doc_count": doc_count,
            "label_count": label_count,
            "run_count": run_count,
            "claim_count": len(claim_ids),
        }

        registry_dir.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        logger.debug(f"Updated registry meta: {doc_count} docs, {run_count} runs")
        return True
    except IOError as e:
        logger.warning(f"Failed to update registry meta: {e}")
        return False


# -----------------------------------------------------------------------------
# Full Index Build Functions
# -----------------------------------------------------------------------------


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
        # Support both legacy run_* and new BATCH-* formats
        if not (run_folder.name.startswith("run_") or run_folder.name.startswith("BATCH-")):
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


def _is_run_dir(name: str) -> bool:
    """Check if directory name matches a run naming convention."""
    return name.startswith("run_") or name.startswith("BATCH-")


def _get_latest_run_id(claim_dir: Path) -> Optional[str]:
    """Get the latest run ID for a claim directory."""
    runs_dir = claim_dir / "runs"
    if not runs_dir.exists():
        return None
    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir() and _is_run_dir(d.name)],
        reverse=True,
    )
    return run_dirs[0].name if run_dirs else None


def _extract_claim_number(folder_name: str) -> str:
    """Extract claim number from folder name."""
    match = re.search(r"(\d{2}-\d{2}-VH-\d+)", folder_name)
    return match.group(1) if match else folder_name


def _parse_loss_type(folder_name: str) -> str:
    """Extract loss type from claim folder name."""
    upper = folder_name.upper()
    if "ROBO_TOTAL" in upper or "ROBO TOTAL" in upper:
        return "Theft - Total Loss"
    if "ROBO_PARCIAL" in upper:
        return "Theft - Partial"
    if "COLISION" in upper or "COLLISION" in upper:
        return "Collision"
    if "INCENDIO" in upper:
        return "Fire"
    if "VANDALISMO" in upper:
        return "Vandalism"
    return "Other"


def _calculate_risk_score(extraction_data: dict) -> int:
    """Calculate risk score based on extraction quality."""
    if not extraction_data:
        return 50
    quality = extraction_data.get("quality_gate", {})
    status = quality.get("status", "warn")
    if status == "pass":
        base = 20
    elif status == "warn":
        base = 45
    else:
        base = 70
    base += len(quality.get("missing_required_fields", [])) * 5
    base += len(quality.get("reasons", [])) * 3
    return min(100, max(0, base))


def _extract_amount(extraction_data: dict) -> Optional[float]:
    """Extract monetary amount from extraction fields."""
    if not extraction_data:
        return None
    fields = extraction_data.get("fields", [])
    amount_fields = ["valor_asegurado", "valor_item", "sum_insured", "amount", "value"]
    for field in fields:
        name = field.get("name", "").lower()
        if any(af in name for af in amount_fields):
            value = field.get("normalized_value") or field.get("value")
            if value:
                try:
                    cleaned = re.sub(r"[^\d.]", "", str(value))
                    return float(cleaned)
                except (ValueError, TypeError):
                    continue
    return None


def _format_completed_date(timestamp: str) -> dict:
    """Format run completion timestamp for UI display."""
    if not timestamp:
        return {"closed_date": None, "last_processed": None}
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return {
            "closed_date": dt.strftime("%d %b %Y"),
            "last_processed": dt.strftime("%Y-%m-%d %H:%M"),
        }
    except Exception:
        return {"closed_date": None, "last_processed": None}


def build_claims_index(claims_dir: Path, output_dir: Path) -> list[dict]:
    """Build claims index with fully-computed ClaimSummary records.

    Pre-computes all per-claim data (risk scores, amounts, flags, gate counts,
    label counts) so that the /api/claims endpoint can read a single file
    instead of performing N+1 filesystem operations.

    Args:
        claims_dir: Path to claims directory (output/claims/).
        output_dir: Path to output directory (output/).

    Returns:
        List of claim summary dicts matching ClaimSummary schema.
    """
    records = []

    if not claims_dir.exists():
        return records

    for claim_folder in sorted(claims_dir.iterdir()):
        if not claim_folder.is_dir() or claim_folder.name.startswith("."):
            continue

        docs_dir = claim_folder / "docs"
        if not docs_dir.exists():
            continue

        # Collect doc info
        doc_types = set()
        doc_count = 0
        for doc_dir in docs_dir.iterdir():
            if not doc_dir.is_dir():
                continue
            doc_json = doc_dir / "meta" / "doc.json"
            if not doc_json.exists():
                continue
            doc_count += 1
            try:
                with open(doc_json, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                doc_types.add(meta.get("doc_type", "unknown"))
            except (json.JSONDecodeError, IOError):
                doc_types.add("unknown")

        if doc_count == 0:
            continue

        folder_name = claim_folder.name
        claim_number = _extract_claim_number(folder_name)

        # Find latest run
        run_id = _get_latest_run_id(claim_folder)

        extracted_count = 0
        total_risk_score = 0
        total_amount = 0.0
        flags_count = 0
        closed_date = None
        last_processed = None
        gate_pass_count = 0
        gate_warn_count = 0
        gate_fail_count = 0

        if run_id:
            run_dir = claim_folder / "runs" / run_id

            # Read run summary for dates (check logs/summary.json first, then manifest.json)
            completed_at = ""
            summary_path = run_dir / "logs" / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary = json.load(f)
                    completed_at = summary.get("completed_at", "")
                except (json.JSONDecodeError, IOError):
                    pass
            if not completed_at:
                manifest_path = run_dir / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                        completed_at = manifest.get("ended_at", "")
                    except (json.JSONDecodeError, IOError):
                        pass
            if completed_at:
                dates = _format_completed_date(completed_at)
                closed_date = dates["closed_date"]
                last_processed = dates["last_processed"]

            # Read extractions
            extractions_dir = run_dir / "extraction"
            if extractions_dir.exists():
                for ext_file in extractions_dir.iterdir():
                    if not ext_file.name.endswith(".json"):
                        continue
                    try:
                        with open(ext_file, "r", encoding="utf-8") as f:
                            ext_data = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        continue

                    extracted_count += 1
                    total_risk_score += _calculate_risk_score(ext_data)

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

                    amount = _extract_amount(ext_data)
                    if amount:
                        total_amount = max(total_amount, amount)

        # Count labels
        labeled_count = 0
        for doc_dir in docs_dir.iterdir():
            if not doc_dir.is_dir():
                continue
            if (doc_dir / "labels" / "latest.json").exists():
                labeled_count += 1

        avg_risk = total_risk_score // max(extracted_count, 1)
        status = "Reviewed" if labeled_count > 0 else "Not Reviewed"
        in_run = run_id is not None and extracted_count > 0

        records.append({
            "claim_id": claim_number,
            "folder_name": folder_name,
            "doc_count": doc_count,
            "doc_types": sorted(doc_types),
            "extracted_count": extracted_count,
            "labeled_count": labeled_count,
            "lob": "MOTOR",
            "risk_score": avg_risk,
            "loss_type": _parse_loss_type(folder_name),
            "amount": total_amount if total_amount > 0 else None,
            "currency": "USD",
            "flags_count": flags_count,
            "status": status,
            "closed_date": closed_date,
            "gate_pass_count": gate_pass_count,
            "gate_warn_count": gate_warn_count,
            "gate_fail_count": gate_fail_count,
            "last_processed": last_processed,
            "in_run": in_run,
        })

    logger.info(f"Built claims index with {len(records)} claims")
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
    claims_records = build_claims_index(claims_dir, output_dir)

    # Count unique claims
    claim_ids = set()
    for rec in doc_records:
        claim_ids.add(rec.get("claim_id") or rec.get("claim_folder"))

    # Write indexes
    doc_path = registry_dir / DOC_INDEX_FILE
    label_path = registry_dir / LABEL_INDEX_FILE
    run_path = registry_dir / RUN_INDEX_FILE
    claims_path = registry_dir / CLAIMS_INDEX_FILE
    meta_path = registry_dir / REGISTRY_META_FILE

    write_jsonl(doc_path, doc_records)
    write_jsonl(label_path, label_records)
    write_jsonl(run_path, run_records)
    write_jsonl(claims_path, claims_records)

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
