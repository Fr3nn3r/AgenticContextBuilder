"""State module: check processing state for idempotency."""

import json
import logging
from pathlib import Path
from typing import Optional

from context_builder.pipeline.paths import get_claim_paths

logger = logging.getLogger(__name__)


def is_claim_processed(output_base: Path, claim_id: str) -> bool:
    """
    Check if a claim has been successfully processed.

    Looks for runs/<run_id>/logs/summary.json with status success or partial.

    Args:
        output_base: Base output directory
        claim_id: Claim identifier

    Returns:
        True if claim has been processed (success or partial)
    """
    claim_paths = get_claim_paths(output_base, claim_id)
    runs_dir = claim_paths.runs_dir

    if not runs_dir.exists():
        return False

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        summary_file = run_dir / "logs" / "summary.json"
        if not summary_file.exists():
            continue

        try:
            with open(summary_file, encoding="utf-8") as f:
                summary = json.load(f)
                status = summary.get("status")
                if status in ("success", "partial"):
                    logger.debug(f"Claim {claim_id} already processed (run: {run_dir.name})")
                    return True
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read summary {summary_file}: {e}")
            continue

    return False


def get_latest_run(output_base: Path, claim_id: str) -> Optional[str]:
    """
    Get the most recent run ID for a claim.

    Args:
        output_base: Base output directory
        claim_id: Claim identifier

    Returns:
        Run ID string or None if no runs exist
    """
    claim_paths = get_claim_paths(output_base, claim_id)
    runs_dir = claim_paths.runs_dir

    if not runs_dir.exists():
        return None

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )

    return run_dirs[0].name if run_dirs else None


def is_doc_extracted(
    output_base: Path,
    claim_id: str,
    run_id: str,
    doc_id: str,
) -> bool:
    """
    Check if a document was extracted in a specific run.

    Args:
        output_base: Base output directory
        claim_id: Claim identifier
        run_id: Run identifier
        doc_id: Document identifier

    Returns:
        True if extraction/<doc_id>.json exists
    """
    claim_paths = get_claim_paths(output_base, claim_id)
    extraction_path = claim_paths.runs_dir / run_id / "extraction" / f"{doc_id}.json"
    return extraction_path.exists()
