"""Service for Decision Dossier operations.

Provides access to decision dossier versions, clause registry,
and re-evaluation with assumption overrides.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.pipeline.claim_stages.decision import (
    DefaultDecisionEngine,
    load_engine_from_workspace,
)
from context_builder.storage.claim_run import ClaimRunStorage

logger = logging.getLogger(__name__)


class DecisionDossierService:
    """Service for reading, listing, and re-evaluating decision dossiers."""

    def __init__(self, claims_dir: Path, workspace_path: Path):
        self.claims_dir = claims_dir
        self.workspace_path = workspace_path

    def _find_claim_folder(self, claim_id: str) -> Optional[Path]:
        """Find the claim folder for a given claim ID."""
        if (self.claims_dir / claim_id).exists():
            return self.claims_dir / claim_id

        for folder in self.claims_dir.iterdir():
            if folder.is_dir() and claim_id in folder.name:
                return folder

        return None

    def _get_latest_claim_run_id(self, claim_folder: Path) -> Optional[str]:
        """Get the most recent claim run ID."""
        runs_dir = claim_folder / "claim_runs"
        if not runs_dir.exists():
            return None

        run_dirs = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        return run_dirs[0].name if run_dirs else None

    def _find_dossier_files(
        self, claim_folder: Path, claim_run_id: Optional[str] = None
    ) -> List[Path]:
        """Find all decision_dossier_v*.json files for a claim."""
        if claim_run_id:
            run_dir = claim_folder / "claim_runs" / claim_run_id
            if run_dir.exists():
                return sorted(run_dir.glob("decision_dossier_v*.json"))
            return []

        # Search all claim runs
        all_files = []
        runs_dir = claim_folder / "claim_runs"
        if runs_dir.exists():
            for run_dir in runs_dir.iterdir():
                if run_dir.is_dir():
                    all_files.extend(run_dir.glob("decision_dossier_v*.json"))

        return sorted(all_files, key=lambda f: f.stat().st_mtime)

    def get_latest_dossier(
        self, claim_id: str, claim_run_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the highest-version dossier for a claim.

        Args:
            claim_id: Claim identifier.
            claim_run_id: Optional claim run ID (uses latest if not specified).

        Returns:
            Dossier dict, or None if not found.
        """
        claim_folder = self._find_claim_folder(claim_id)
        if not claim_folder:
            return None

        if not claim_run_id:
            claim_run_id = self._get_latest_claim_run_id(claim_folder)
        if not claim_run_id:
            return None

        files = self._find_dossier_files(claim_folder, claim_run_id)
        if not files:
            return None

        # Return the highest version (last in sorted list)
        try:
            with open(files[-1], "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read dossier {files[-1]}: {e}")
            return None

    def list_versions(
        self, claim_id: str, claim_run_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return metadata for all dossier versions.

        Args:
            claim_id: Claim identifier.
            claim_run_id: Optional claim run ID.

        Returns:
            List of version metadata dicts.
        """
        claim_folder = self._find_claim_folder(claim_id)
        if not claim_folder:
            return []

        if not claim_run_id:
            claim_run_id = self._get_latest_claim_run_id(claim_folder)
        if not claim_run_id:
            return []

        files = self._find_dossier_files(claim_folder, claim_run_id)
        versions = []

        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                versions.append({
                    "version": data.get("version", 0),
                    "claim_verdict": data.get("claim_verdict"),
                    "evaluation_timestamp": data.get("evaluation_timestamp"),
                    "engine_id": data.get("engine_id"),
                    "failed_clauses_count": len(data.get("failed_clauses", [])),
                    "unresolved_count": len(data.get("unresolved_assumptions", [])),
                    "claim_run_id": claim_run_id,
                    "filename": f.name,
                })
            except Exception as e:
                logger.warning(f"Failed to read dossier metadata from {f}: {e}")

        return versions

    def get_version(
        self, claim_id: str, version: int, claim_run_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Read a specific dossier version.

        Args:
            claim_id: Claim identifier.
            version: Version number.
            claim_run_id: Optional claim run ID.

        Returns:
            Dossier dict, or None if not found.
        """
        claim_folder = self._find_claim_folder(claim_id)
        if not claim_folder:
            return None

        if not claim_run_id:
            claim_run_id = self._get_latest_claim_run_id(claim_folder)
        if not claim_run_id:
            return None

        run_dir = claim_folder / "claim_runs" / claim_run_id
        dossier_path = run_dir / f"decision_dossier_v{version}.json"

        if not dossier_path.exists():
            return None

        try:
            with open(dossier_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read dossier v{version}: {e}")
            return None

    def evaluate_with_assumptions(
        self,
        claim_id: str,
        assumptions: Dict[str, bool],
        claim_run_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Re-run the decision engine with overridden assumptions.

        Args:
            claim_id: Claim identifier.
            assumptions: Assumption overrides {clause_reference: bool}.
            claim_run_id: Optional claim run ID.

        Returns:
            New dossier dict, or None if evaluation failed.
        """
        claim_folder = self._find_claim_folder(claim_id)
        if not claim_folder:
            return None

        if not claim_run_id:
            claim_run_id = self._get_latest_claim_run_id(claim_folder)
        if not claim_run_id:
            return None

        # Load engine
        engine = load_engine_from_workspace(self.workspace_path)
        if engine is None:
            engine = DefaultDecisionEngine(self.workspace_path)

        # Load aggregated facts
        run_dir = claim_folder / "claim_runs" / claim_run_id
        facts = self._load_json(run_dir / "claim_facts.json")

        # Load screening result
        screening = self._load_json(run_dir / "screening.json")

        # Load coverage analysis
        coverage = self._load_json(run_dir / "coverage_analysis.json")

        # Load processing result (assessment)
        processing = self._load_json(run_dir / "assessment.json")

        if not facts:
            logger.warning(f"No claim facts found for {claim_id} in run {claim_run_id}")
            return None

        try:
            # Run evaluation with assumptions
            dossier = engine.evaluate(
                claim_id=claim_id,
                aggregated_facts=facts,
                screening_result=screening,
                coverage_analysis=coverage,
                processing_result=processing,
                assumptions=assumptions,
            )

            # Convert Pydantic model to dict if needed
            if hasattr(dossier, "model_dump"):
                dossier = dossier.model_dump()

            # Determine next version
            existing = self._find_dossier_files(claim_folder, claim_run_id)
            max_version = 0
            for f in existing:
                try:
                    v = int(f.stem.split("_v")[-1])
                    max_version = max(max_version, v)
                except (ValueError, IndexError):
                    continue

            next_version = max_version + 1
            dossier["version"] = next_version

            # Write new version
            storage = ClaimRunStorage(claim_folder)
            filename = f"decision_dossier_v{next_version}.json"
            storage.write_to_claim_run(claim_run_id, filename, dossier)

            logger.info(
                f"Wrote {filename} for {claim_id} (assumptions override)"
            )
            return dossier

        except Exception as e:
            logger.error(f"Decision evaluation failed for {claim_id}: {e}")
            return None

    def get_clause_registry(self) -> List[Dict[str, Any]]:
        """Load and return the clause registry from the engine.

        Returns:
            List of denial clause definitions.
        """
        engine = load_engine_from_workspace(self.workspace_path)
        if engine is None:
            return []

        try:
            return engine.get_clause_registry()
        except Exception as e:
            logger.error(f"Failed to get clause registry: {e}")
            return []

    def list_claims_with_dossiers(self) -> List[str]:
        """Return claim IDs that have at least one decision dossier file.

        Scans all claim directories for decision_dossier_v*.json in their
        latest claim run.
        """
        result = []
        if not self.claims_dir.exists():
            return result

        for claim_folder in sorted(self.claims_dir.iterdir()):
            if not claim_folder.is_dir():
                continue
            claim_run_id = self._get_latest_claim_run_id(claim_folder)
            if not claim_run_id:
                continue
            run_dir = claim_folder / "claim_runs" / claim_run_id
            dossier_files = list(run_dir.glob("decision_dossier_v*.json"))
            if dossier_files:
                result.append(claim_folder.name)

        return result

    def get_workbench_data(
        self, claim_id: str, claim_run_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Return aggregated data for the Claims Workbench view.

        Bundles claim facts, screening, coverage analysis, and decision
        dossier into a single response for the frontend.
        """
        claim_folder = self._find_claim_folder(claim_id)
        if not claim_folder:
            return None

        if not claim_run_id:
            claim_run_id = self._get_latest_claim_run_id(claim_folder)
        if not claim_run_id:
            return None

        run_dir = claim_folder / "claim_runs" / claim_run_id

        facts = self._load_json(run_dir / "claim_facts.json")
        screening = self._load_json(run_dir / "screening.json")
        coverage = self._load_json(run_dir / "coverage_analysis.json")
        assessment = self._load_json(run_dir / "assessment.json")

        # Get latest dossier
        dossier_files = self._find_dossier_files(claim_folder, claim_run_id)
        dossier = None
        if dossier_files:
            dossier = self._load_json(dossier_files[-1])

        # List documents
        docs_dir = claim_folder / "docs"
        documents = []
        if docs_dir.exists():
            for f in sorted(docs_dir.iterdir()):
                if f.is_file():
                    documents.append({
                        "filename": f.name,
                        "size_kb": round(f.stat().st_size / 1024, 1),
                    })

        return {
            "claim_id": claim_id,
            "claim_run_id": claim_run_id,
            "facts": facts,
            "screening": screening,
            "coverage": coverage,
            "assessment": assessment,
            "dossier": dossier,
            "documents": documents,
        }

    @staticmethod
    def _load_json(path: Path) -> Optional[Dict[str, Any]]:
        """Load a JSON file, returning None on error."""
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
