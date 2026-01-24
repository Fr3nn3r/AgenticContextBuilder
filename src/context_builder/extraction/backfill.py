"""Backfill evidence for existing extraction files.

Reprocesses extraction results to fill missing character offsets
and run validation checks.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from context_builder.schemas.extraction_result import ExtractionResult, PageContent
from context_builder.extraction.evidence_resolver import resolve_evidence_offsets
from context_builder.extraction.validators import validate_extraction

logger = logging.getLogger(__name__)


def backfill_extraction(
    extraction_path: Path,
    pages_path: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Backfill evidence for a single extraction file.

    Args:
        extraction_path: Path to *.extraction.json
        pages_path: Path to pages.json
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

    # Count before
    before_verified = sum(
        1 for f in result.fields
        if getattr(f, 'has_verified_evidence', False)
    )

    # Resolve offsets
    result = resolve_evidence_offsets(result)

    # Run validation
    validations = validate_extraction(result)
    result.extraction_meta = result.extraction_meta or {}
    result.extraction_meta["validation"] = {
        "passed": all(v.passed for v in validations),
        "checks": [{"rule": v.rule, "passed": v.passed} for v in validations]
    }

    # Count after
    after_verified = sum(1 for f in result.fields if f.has_verified_evidence)

    stats = {
        "file": str(extraction_path),
        "fields_total": len(result.fields),
        "verified_before": before_verified,
        "verified_after": after_verified,
        "validation_passed": result.extraction_meta["validation"]["passed"],
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
) -> Dict[str, Any]:
    """
    Backfill all extractions in a workspace.

    Args:
        claims_dir: Path to claims directory
        dry_run: If True, don't write changes

    Returns:
        Aggregate stats
    """
    stats: Dict[str, Any] = {"processed": 0, "improved": 0, "errors": []}

    if not claims_dir.exists():
        logger.warning(f"Claims directory not found: {claims_dir}")
        return stats

    for claim_dir in claims_dir.iterdir():
        if not claim_dir.is_dir():
            continue

        docs_dir = claim_dir / "docs"
        if not docs_dir.exists():
            continue

        for doc_dir in docs_dir.iterdir():
            if not doc_dir.is_dir():
                continue

            # Find extraction files
            for ext_file in doc_dir.glob("*.extraction.json"):
                pages_file = doc_dir / "text" / "pages.json"
                if not pages_file.exists():
                    # Try alternative location
                    pages_file = doc_dir / "pages.json"
                    if not pages_file.exists():
                        logger.debug(f"No pages.json for {ext_file}")
                        continue

                try:
                    result = backfill_extraction(ext_file, pages_file, dry_run)
                    stats["processed"] += 1
                    if result["verified_after"] > result["verified_before"]:
                        stats["improved"] += 1
                        logger.info(
                            f"Improved {ext_file.name}: "
                            f"{result['verified_before']} -> {result['verified_after']} verified fields"
                        )
                except Exception as e:
                    logger.error(f"Failed to backfill {ext_file}: {e}")
                    stats["errors"].append({"file": str(ext_file), "error": str(e)})

    return stats
