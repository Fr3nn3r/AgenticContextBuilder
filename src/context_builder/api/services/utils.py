"""Shared helpers for API services."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_loss_type_from_folder(folder_name: str) -> str:
    """Extract loss type from claim folder name."""
    folder_upper = folder_name.upper()
    if "ROBO_TOTAL" in folder_upper or "ROBO TOTAL" in folder_upper:
        return "Theft - Total Loss"
    if "ROBO_PARCIAL" in folder_upper:
        return "Theft - Partial"
    if "COLISION" in folder_upper or "COLLISION" in folder_upper:
        return "Collision"
    if "INCENDIO" in folder_upper:
        return "Fire"
    if "VANDALISMO" in folder_upper:
        return "Vandalism"
    return "Other"


def extract_claim_number(folder_name: str) -> str:
    """Extract claim number from folder name (e.g., '24-01-VH-7054124')."""
    match = re.search(r"(\d{2}-\d{2}-VH-\d+)", folder_name)
    return match.group(1) if match else folder_name


def _is_run_dir(name: str) -> bool:
    """Check if directory name matches a run naming convention."""
    return name.startswith("run_") or name.startswith("BATCH-")


def get_latest_run_dir_for_claim(claim_dir: Path) -> Optional[Path]:
    """Get the most recent run directory for a claim."""
    runs_dir = claim_dir / "runs"
    if not runs_dir.exists():
        return None

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir() and _is_run_dir(d.name)],
        reverse=True,
    )
    return run_dirs[0] if run_dirs else None


def get_latest_run_id_for_claim(claim_dir: Path) -> Optional[str]:
    """Get the most recent run ID for a claim.

    Args:
        claim_dir: Path to the claim directory.

    Returns:
        Run ID string if found, None otherwise.
    """
    run_dir = get_latest_run_dir_for_claim(claim_dir)
    return run_dir.name if run_dir else None


def get_run_dir_by_id(claim_dir: Path, run_id: str) -> Optional[Path]:
    """Get a specific run directory by ID for a claim."""
    runs_dir = claim_dir / "runs"
    if not runs_dir.exists():
        return None

    run_dir = runs_dir / run_id
    if run_dir.exists() and run_dir.is_dir():
        return run_dir
    return None


def get_global_runs_dir(data_dir: Path) -> Path:
    """Get the global runs directory (output/runs/)."""
    return data_dir.parent / "runs"


def calculate_risk_score(extraction_data: Dict[str, Any]) -> int:
    """Calculate risk score based on extraction quality and completeness."""
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

    missing = len(quality.get("missing_required_fields", []))
    base += missing * 5

    reasons = len(quality.get("reasons", []))
    base += reasons * 3

    return min(100, max(0, base))


def extract_amount_from_extraction(extraction_data: Dict[str, Any]) -> Optional[float]:
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


def format_completed_date(timestamp: str) -> Dict[str, Optional[str]]:
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
