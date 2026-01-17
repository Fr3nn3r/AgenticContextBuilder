"""Seed script to populate evolution data for the Pipeline Evolution Dashboard.

This creates realistic version bundles showing pipeline evolution over time:
- Growing scope (more doc types and fields)
- Improving accuracy
- Different extraction spec versions
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
WORKSPACE_DIR = Path(__file__).parent.parent / "workspaces" / "default"
BUNDLES_DIR = WORKSPACE_DIR / "version_bundles"
RUNS_DIR = WORKSPACE_DIR / "runs"

# Evolution stages - simulating pipeline development over time
EVOLUTION_STAGES = [
    {
        "version": "v0.1",
        "days_ago": 30,
        "spec_hash": "a1b2c3d4e5f6",
        "contextbuilder_version": "0.1.0",
        "model_name": "gpt-4o-mini",
        "doc_types": ["fnol_form"],
        "fields_by_type": {
            "fnol_form": 8,
        },
        "accuracy_rate": 65.0,
        "correct": 52,
        "incorrect": 18,
        "missing": 10,
    },
    {
        "version": "v0.2",
        "days_ago": 21,
        "spec_hash": "b2c3d4e5f6g7",
        "contextbuilder_version": "0.1.0",
        "model_name": "gpt-4o-mini",
        "doc_types": ["fnol_form", "id_document", "vehicle_registration"],
        "fields_by_type": {
            "fnol_form": 10,
            "id_document": 5,
            "vehicle_registration": 6,
        },
        "accuracy_rate": 68.5,
        "correct": 89,
        "incorrect": 22,
        "missing": 19,
    },
    {
        "version": "v0.3",
        "days_ago": 14,
        "spec_hash": "c3d4e5f6g7h8",
        "contextbuilder_version": "0.1.0",
        "model_name": "gpt-4o",
        "doc_types": ["fnol_form", "id_document", "vehicle_registration", "police_report", "damage_evidence"],
        "fields_by_type": {
            "fnol_form": 12,
            "id_document": 6,
            "vehicle_registration": 8,
            "police_report": 4,
            "damage_evidence": 6,
        },
        "accuracy_rate": 74.2,
        "correct": 178,
        "incorrect": 38,
        "missing": 24,
    },
    {
        "version": "v0.4",
        "days_ago": 7,
        "spec_hash": "d4e5f6g7h8i9",
        "contextbuilder_version": "0.2.0",
        "model_name": "gpt-4o",
        "doc_types": ["fnol_form", "id_document", "vehicle_registration", "police_report",
                      "damage_evidence", "medical_report", "insurance_policy"],
        "fields_by_type": {
            "fnol_form": 14,
            "id_document": 7,
            "vehicle_registration": 9,
            "police_report": 5,
            "damage_evidence": 8,
            "medical_report": 12,
            "insurance_policy": 4,
        },
        "accuracy_rate": 78.8,
        "correct": 315,
        "incorrect": 52,
        "missing": 33,
    },
    {
        "version": "v0.5",
        "days_ago": 1,
        "spec_hash": "e5f6g7h8i9j0",
        "contextbuilder_version": "0.2.0",
        "model_name": "gpt-4o",
        "doc_types": ["fnol_form", "id_document", "vehicle_registration", "police_report",
                      "damage_evidence", "medical_report", "insurance_policy", "invoice", "customer_comm"],
        "fields_by_type": {
            "fnol_form": 14,
            "id_document": 7,
            "vehicle_registration": 9,
            "police_report": 5,
            "damage_evidence": 8,
            "medical_report": 17,
            "insurance_policy": 5,
            "invoice": 4,
            "customer_comm": 14,
        },
        "accuracy_rate": 82.4,
        "correct": 412,
        "incorrect": 56,
        "missing": 32,
    },
]


def create_bundle(stage: dict) -> tuple[str, dict]:
    """Create a version bundle for a stage."""
    now = datetime.utcnow()
    created_at = now - timedelta(days=stage["days_ago"])

    run_id = f"run_{created_at.strftime('%Y%m%d_%H%M%S')}_{stage['spec_hash'][:7]}"
    bundle_id = f"vb_{uuid.uuid4().hex[:12]}"

    total_fields = sum(stage["fields_by_type"].values())

    bundle = {
        "bundle_id": bundle_id,
        "created_at": created_at.isoformat() + "Z",
        "git_commit": f"{uuid.uuid4().hex[:40]}",
        "git_dirty": False,
        "contextbuilder_version": stage["contextbuilder_version"],
        "extractor_version": "v1.0.0",
        "model_name": stage["model_name"],
        "model_version": None,
        "prompt_template_hash": f"{uuid.uuid4().hex[:64]}",
        "extraction_spec_hash": stage["spec_hash"] + "0" * 52,  # Pad to full hash length
        "scope_snapshot": {
            "doc_types": stage["doc_types"],
            "total_fields": total_fields,
            "fields_by_type": stage["fields_by_type"],
        }
    }

    return run_id, bundle


def create_eval_summary(stage: dict) -> dict:
    """Create an eval summary for a stage."""
    return {
        "correct": stage["correct"],
        "incorrect": stage["incorrect"],
        "missing": stage["missing"],
        "docs_evaluated": stage["correct"] + stage["incorrect"] + stage["missing"],
        "accuracy_rate": stage["accuracy_rate"],
        "created_at": (datetime.utcnow() - timedelta(days=stage["days_ago"])).isoformat() + "Z",
    }


def seed_evolution_data():
    """Seed the evolution data."""
    print("Seeding evolution data...")

    # Ensure directories exist
    BUNDLES_DIR.mkdir(parents=True, exist_ok=True)

    for stage in EVOLUTION_STAGES:
        run_id, bundle = create_bundle(stage)

        # Create bundle directory and file
        bundle_dir = BUNDLES_DIR / run_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        bundle_path = bundle_dir / "bundle.json"
        with open(bundle_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)
        print(f"Created bundle: {bundle_path}")

        # Create eval summary
        run_dir = RUNS_DIR / run_id
        eval_dir = run_dir / "eval"
        eval_dir.mkdir(parents=True, exist_ok=True)

        eval_summary = create_eval_summary(stage)
        eval_path = eval_dir / "summary.json"
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump(eval_summary, f, indent=2)
        print(f"Created eval summary: {eval_path}")

        # Create run summary
        run_summary = {
            "run_id": run_id,
            "status": "completed",
            "claims_discovered": stage["correct"] + stage["incorrect"],
            "claims_processed": stage["correct"] + stage["incorrect"],
            "docs_total": stage["correct"] + stage["incorrect"] + stage["missing"],
            "completed_at": bundle["created_at"],
        }
        run_summary_path = run_dir / "summary.json"
        with open(run_summary_path, "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2)
        print(f"Created run summary: {run_summary_path}")

    print(f"\nSeeded {len(EVOLUTION_STAGES)} evolution stages.")
    print("Restart the API server to see the data in the Evolution Dashboard.")


if __name__ == "__main__":
    seed_evolution_data()
