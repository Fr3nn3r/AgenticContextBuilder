"""Backfill evidence for existing extraction files.

Reprocesses extraction results to fill missing character offsets
and run validation checks.

Uses Azure DI table data when available for precise cell-level matching.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from context_builder.schemas.extraction_result import ExtractionResult, PageContent
from context_builder.extraction.evidence_resolver import resolve_evidence_offsets
from context_builder.extraction.validators import validate_extraction

logger = logging.getLogger(__name__)


def _load_azure_di(doc_dir: Path) -> Optional[Dict[str, Any]]:
    """Load Azure DI data for a document if available.

    Args:
        doc_dir: Path to document directory

    Returns:
        Azure DI data dict or None
    """
    azure_di_path = doc_dir / "text" / "raw" / "azure_di.json"
    if azure_di_path.exists():
        try:
            with open(azure_di_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.debug(f"Failed to load Azure DI: {e}")
    return None


def backfill_extraction(
    extraction_path: Path,
    pages_path: Path,
    azure_di_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Backfill evidence for a single extraction file.

    Args:
        extraction_path: Path to extraction JSON file
        pages_path: Path to pages.json
        azure_di_path: Optional path to azure_di.json for table-aware matching
        dry_run: If True, don't write changes

    Returns:
        Stats about what was updated
    """
    # Load extraction
    with open(extraction_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = ExtractionResult.model_validate(data)

    # Load pages if not embedded or empty
    if not result.pages:
        with open(pages_path, "r", encoding="utf-8") as f:
            pages_data = json.load(f)
        result.pages = [PageContent.model_validate(p) for p in pages_data]

    # Load Azure DI for table-aware matching
    azure_di = None
    if azure_di_path and azure_di_path.exists():
        try:
            with open(azure_di_path, "r", encoding="utf-8") as f:
                azure_di = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.debug(f"Failed to load Azure DI from {azure_di_path}: {e}")

    # Count before
    before_verified = sum(
        1 for f in result.fields
        if getattr(f, 'has_verified_evidence', False)
    )
    before_with_provenance = sum(
        1 for f in result.fields
        if f.provenance
    )

    # Resolve offsets with Azure DI support
    result = resolve_evidence_offsets(result, azure_di)

    # Run validation
    validations = validate_extraction(result)
    result.extraction_meta = result.extraction_meta or {}
    result.extraction_meta["validation"] = {
        "passed": all(v.passed for v in validations),
        "checks": [{"rule": v.rule, "passed": v.passed} for v in validations]
    }

    # Count after
    after_verified = sum(1 for f in result.fields if f.has_verified_evidence)
    after_with_provenance = sum(1 for f in result.fields if f.provenance)

    stats = {
        "file": str(extraction_path),
        "fields_total": len(result.fields),
        "verified_before": before_verified,
        "verified_after": after_verified,
        "provenance_before": before_with_provenance,
        "provenance_after": after_with_provenance,
        "validation_passed": result.extraction_meta["validation"]["passed"],
        "used_azure_di": azure_di is not None,
        "dry_run": dry_run,
    }

    if not dry_run:
        with open(extraction_path, "w", encoding="utf-8") as f:
            json.dump(
                result.model_dump(exclude_none=True, by_alias=True),
                f,
                indent=2,
                ensure_ascii=False,
            )

    return stats


def backfill_workspace(
    claims_dir: Path,
    dry_run: bool = False,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backfill all extractions in a workspace.

    Searches for extractions in:
    1. claims/{claim_id}/runs/{run_id}/extraction/{doc_id}.json (new format)
    2. claims/{claim_id}/docs/{doc_id}/*.extraction.json (legacy format)

    Args:
        claims_dir: Path to claims directory
        dry_run: If True, don't write changes
        run_id: Optional specific run ID to backfill (if None, finds latest)

    Returns:
        Aggregate stats
    """
    stats: Dict[str, Any] = {
        "processed": 0,
        "improved": 0,
        "provenance_added": 0,
        "errors": [],
    }

    if not claims_dir.exists():
        logger.warning(f"Claims directory not found: {claims_dir}")
        return stats

    for claim_dir in claims_dir.iterdir():
        if not claim_dir.is_dir():
            continue

        claim_id = claim_dir.name
        docs_dir = claim_dir / "docs"
        runs_dir = claim_dir / "runs"

        # Strategy 1: Search in runs directory (new format)
        if runs_dir.exists():
            # Find run(s) to process
            run_dirs = []
            if run_id:
                specific_run = runs_dir / run_id
                if specific_run.exists():
                    run_dirs = [specific_run]
            else:
                # Get all run directories, sorted by name (latest first)
                run_dirs = sorted(
                    [d for d in runs_dir.iterdir() if d.is_dir()],
                    key=lambda x: x.name,
                    reverse=True,
                )
                # Only process the latest run
                if run_dirs:
                    run_dirs = [run_dirs[0]]

            for run_dir in run_dirs:
                extraction_dir = run_dir / "extraction"
                if not extraction_dir.exists():
                    continue

                for ext_file in extraction_dir.glob("*.json"):
                    doc_id = ext_file.stem
                    doc_dir = docs_dir / doc_id if docs_dir.exists() else None

                    # Find pages.json
                    pages_file = None
                    if doc_dir and doc_dir.exists():
                        pages_file = doc_dir / "text" / "pages.json"
                        if not pages_file.exists():
                            pages_file = doc_dir / "pages.json"
                            if not pages_file.exists():
                                pages_file = None

                    if not pages_file:
                        logger.debug(f"No pages.json for {ext_file}")
                        continue

                    # Find Azure DI data
                    azure_di_path = None
                    if doc_dir and doc_dir.exists():
                        azure_di_path = doc_dir / "text" / "raw" / "azure_di.json"
                        if not azure_di_path.exists():
                            azure_di_path = None

                    try:
                        result = backfill_extraction(
                            ext_file, pages_file, azure_di_path, dry_run
                        )
                        stats["processed"] += 1

                        if result["verified_after"] > result["verified_before"]:
                            stats["improved"] += 1

                        prov_added = result["provenance_after"] - result["provenance_before"]
                        if prov_added > 0:
                            stats["provenance_added"] += prov_added
                            logger.info(
                                f"[{claim_id}/{doc_id}] Added provenance for {prov_added} fields "
                                f"({result['provenance_before']} -> {result['provenance_after']})"
                                + (" [Azure DI tables]" if result.get("used_azure_di") else "")
                            )
                    except Exception as e:
                        logger.error(f"Failed to backfill {ext_file}: {e}")
                        stats["errors"].append({"file": str(ext_file), "error": str(e)})

        # Strategy 2: Search in docs directory (legacy format)
        if docs_dir.exists():
            for doc_dir in docs_dir.iterdir():
                if not doc_dir.is_dir():
                    continue

                # Find extraction files in doc directory
                for ext_file in doc_dir.glob("*.extraction.json"):
                    pages_file = doc_dir / "text" / "pages.json"
                    if not pages_file.exists():
                        pages_file = doc_dir / "pages.json"
                        if not pages_file.exists():
                            logger.debug(f"No pages.json for {ext_file}")
                            continue

                    # Find Azure DI data
                    azure_di_path = doc_dir / "text" / "raw" / "azure_di.json"
                    if not azure_di_path.exists():
                        azure_di_path = None

                    try:
                        result = backfill_extraction(
                            ext_file, pages_file, azure_di_path, dry_run
                        )
                        stats["processed"] += 1

                        if result["verified_after"] > result["verified_before"]:
                            stats["improved"] += 1

                        prov_added = result["provenance_after"] - result["provenance_before"]
                        if prov_added > 0:
                            stats["provenance_added"] += prov_added
                            logger.info(
                                f"[{claim_id}/{doc_dir.name}] Added provenance for {prov_added} fields"
                                + (" [Azure DI tables]" if result.get("used_azure_di") else "")
                            )
                    except Exception as e:
                        logger.error(f"Failed to backfill {ext_file}: {e}")
                        stats["errors"].append({"file": str(ext_file), "error": str(e)})

    return stats
