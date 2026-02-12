"""Assessment storage service for loading and saving claim assessments.

This service handles file I/O for assessment data (loading, saving, versioning).
For running assessments, see ClaimAssessmentService in claim_assessment.py.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AssessmentStorageService:
    """Service for loading and saving claim assessment data (file I/O).

    This handles:
    - Loading assessment JSON files
    - Saving assessment versions with history
    - Transforming assessment data for UI display

    For running assessments (reconciliation + checks + payout calculation),
    use ClaimAssessmentService instead.
    """

    def __init__(self, claims_dir: Path):
        """Initialize the assessment service.

        Args:
            claims_dir: Path to the claims directory (e.g., workspaces/nsa/claims)
        """
        self.claims_dir = claims_dir
        self.workspace_path = claims_dir.parent  # {workspace}/ root

    def _get_assessment_path(self, claim_id: str) -> Path:
        """Get the path to a claim's assessment file."""
        return self.claims_dir / claim_id / "context" / "assessment.json"

    def _get_assessments_dir(self, claim_id: str) -> Path:
        """Get the path to a claim's assessments history directory."""
        return self.claims_dir / claim_id / "context" / "assessments"

    def _get_assessments_index_path(self, claim_id: str) -> Path:
        """Get the path to a claim's assessments index file."""
        return self._get_assessments_dir(claim_id) / "index.json"

    def _get_claim_runs_dir(self, claim_id: str) -> Path:
        """Get the path to a claim's claim_runs directory."""
        return self.claims_dir / claim_id / "claim_runs"

    def _load_assessments_index(self, claim_id: str) -> Dict[str, Any]:
        """Load the assessments index, creating empty structure if missing."""
        index_path = self._get_assessments_index_path(claim_id)
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load assessments index: {e}")
        return {"assessments": []}

    def _save_assessments_index(self, claim_id: str, index: Dict[str, Any]) -> None:
        """Save the assessments index file."""
        index_path = self._get_assessments_index_path(claim_id)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

    def save_assessment(
        self,
        claim_id: str,
        assessment_data: Dict[str, Any],
        prompt_version: Optional[str] = None,
        extraction_bundle_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save a new assessment with versioned history.

        Creates a timestamped file in assessments/ directory, updates index.json,
        and copies to assessment.json for backwards compatibility.

        Args:
            claim_id: The claim ID
            assessment_data: Raw assessment data to save
            prompt_version: Optional prompt version string
            extraction_bundle_id: Optional extraction bundle identifier

        Returns:
            Assessment metadata including id, filename, timestamp
        """
        # Generate timestamp and assessment ID
        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y-%m-%dT%H-%M-%S")
        version_str = prompt_version or "unknown"
        assessment_id = f"{timestamp_str}_v{version_str}"
        filename = f"{assessment_id}.json"

        # Ensure directory exists
        assessments_dir = self._get_assessments_dir(claim_id)
        assessments_dir.mkdir(parents=True, exist_ok=True)

        # Add metadata to assessment
        assessment_with_meta = {
            **assessment_data,
            "assessment_id": assessment_id,
            "assessment_timestamp": now.isoformat(),
            "prompt_version": prompt_version,
            "extraction_bundle_id": extraction_bundle_id,
        }

        # Save versioned file
        versioned_path = assessments_dir / filename
        with open(versioned_path, "w", encoding="utf-8") as f:
            json.dump(assessment_with_meta, f, indent=2)
        logger.info(f"Saved assessment to {versioned_path}")

        # Update index
        index = self._load_assessments_index(claim_id)

        # Mark all existing as not current
        for entry in index["assessments"]:
            entry["is_current"] = False

        # Add new entry
        new_entry = {
            "id": assessment_id,
            "filename": filename,
            "timestamp": now.isoformat(),
            "prompt_version": prompt_version,
            "extraction_bundle_id": extraction_bundle_id,
            "recommendation": assessment_data.get("recommendation"),
            "confidence_score": assessment_data.get("confidence_score"),
            "is_current": True,
        }
        index["assessments"].append(new_entry)
        self._save_assessments_index(claim_id, index)

        # Copy to assessment.json for backwards compatibility
        main_path = self._get_assessment_path(claim_id)
        main_path.parent.mkdir(parents=True, exist_ok=True)
        with open(main_path, "w", encoding="utf-8") as f:
            json.dump(assessment_with_meta, f, indent=2)
        logger.info(f"Updated main assessment at {main_path}")

        return new_entry

    def get_assessment_by_id(
        self, claim_id: str, assessment_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load a specific assessment by its ID.

        Checks claim_runs/{assessment_id}/assessment.json first, then falls
        back to context/assessments/ for legacy data.

        Args:
            claim_id: The claim ID
            assessment_id: The assessment ID (claim run ID or timestamp_version format)

        Returns:
            Transformed assessment, or None if not found
        """
        # Primary: try claim_runs/{assessment_id}/assessment.json
        claim_run_path = self._get_claim_runs_dir(claim_id) / assessment_id / "assessment.json"
        if claim_run_path.exists():
            try:
                with open(claim_run_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return self._transform_assessment(data)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load assessment from claim_run {assessment_id}: {e}")

        # Fallback: try context/assessments/ (legacy)
        index = self._load_assessments_index(claim_id)
        entry = next(
            (a for a in index["assessments"] if a["id"] == assessment_id), None
        )
        if not entry:
            logger.debug(f"Assessment {assessment_id} not found in index or claim_runs")
            return None

        assessment_path = self._get_assessments_dir(claim_id) / entry["filename"]
        if not assessment_path.exists():
            logger.warning(f"Assessment file missing: {assessment_path}")
            return None

        try:
            with open(assessment_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._transform_assessment(data)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load assessment {assessment_id}: {e}")
            return None

    def _parse_check_number(self, check_number: Any) -> int:
        """Parse check_number to integer, handling strings like '1b'.

        Args:
            check_number: The check number (int or str like '1b')

        Returns:
            Integer check number (extracts leading digits from strings)
        """
        if isinstance(check_number, int):
            return check_number
        if isinstance(check_number, str):
            # Extract leading digits from strings like "1b", "2a", etc.
            match = re.match(r"(\d+)", check_number)
            if match:
                return int(match.group(1))
        return 0

    def _transform_check(self, check: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a check from file format to frontend format.

        Args:
            check: Raw check from assessment.json

        Returns:
            Transformed check matching frontend AssessmentCheck type
        """
        # Map result to valid frontend values: PASS, FAIL, INCONCLUSIVE
        # Backend may return "N/A" which frontend doesn't handle
        result = check.get("result", "INCONCLUSIVE")
        if result not in ("PASS", "FAIL", "INCONCLUSIVE"):
            result = "INCONCLUSIVE"

        return {
            "check_number": self._parse_check_number(check.get("check_number", 0)),
            "check_name": check.get("check_name", ""),
            "result": result,
            "details": check.get("details", ""),
            "evidence_refs": check.get("evidence_refs", []),
        }

    def _transform_assumption(self, assumption: Dict[str, Any]) -> Dict[str, Any]:
        """Transform an assumption from file format to frontend format.

        Args:
            assumption: Raw assumption from assessment.json

        Returns:
            Transformed assumption matching frontend AssessmentAssumption type
        """
        # Handle confidence_impact -> impact transformation (lowercase)
        impact = assumption.get("confidence_impact") or assumption.get("impact", "medium")
        if isinstance(impact, str):
            impact = impact.lower()

        return {
            "check_number": self._parse_check_number(assumption.get("check_number", 0)),
            "field": assumption.get("field", ""),
            "assumed_value": assumption.get("assumed_value", ""),
            "reason": assumption.get("reason", ""),
            "impact": impact,
        }

    def _transform_fraud_indicator(self, indicator: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a fraud indicator from file format to frontend format.

        Args:
            indicator: Raw fraud indicator from assessment.json

        Returns:
            Transformed fraud indicator matching frontend FraudIndicator type
        """
        return {
            "indicator": indicator.get("indicator", ""),
            "severity": indicator.get("severity", "medium"),
            "details": indicator.get("details", ""),
        }

    def _transform_payout(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform payout preserving full breakdown.

        Args:
            data: Raw data from assessment.json

        Returns:
            Full payout breakdown dict, or None if no payout data
        """
        payout = data.get("payout")
        if not isinstance(payout, dict):
            if isinstance(payout, (int, float)):
                return {"final_payout": payout, "currency": data.get("currency")}
            return None

        return {
            "total_claimed": payout.get("total_claimed"),
            "non_covered_deductions": payout.get("non_covered_deductions"),
            "covered_subtotal": payout.get("covered_subtotal"),
            "coverage_percent": payout.get("coverage_percent"),
            "after_coverage": payout.get("after_coverage"),
            "deductible": payout.get("deductible"),
            "final_payout": payout.get("final_payout"),
            "currency": payout.get("currency") or data.get("currency"),
        }

    def _transform_assessment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform assessment.json data to frontend ClaimAssessment format.

        Key transformations:
        - assessment_timestamp -> assessed_at
        - payout.final_payout -> payout (number)
        - check_number "1b" -> 1 (parse to int)
        - assumptions[].confidence_impact -> assumptions[].impact (lowercase)
        - confidence_score 0-1 -> 0-100 (percentage for frontend)

        Args:
            data: Raw data from assessment.json

        Returns:
            Transformed assessment matching frontend ClaimAssessment type
        """
        # Extract payout value from nested structure
        payout = None
        if isinstance(data.get("payout"), dict):
            payout = data["payout"].get("final_payout")
        elif isinstance(data.get("payout"), (int, float)):
            payout = data["payout"]

        # Convert confidence_score from decimal (0-1) to percentage (0-100)
        # Frontend ScoreBadge expects percentages
        confidence_score = data.get("confidence_score", 0.0)
        if isinstance(confidence_score, (int, float)) and confidence_score <= 1.0:
            confidence_score = confidence_score * 100

        # Extract currency from payout structure or top-level
        currency = None
        if isinstance(data.get("payout"), dict):
            currency = data["payout"].get("currency")
        if not currency:
            currency = data.get("currency")

        return {
            "claim_id": data.get("claim_id", ""),
            "recommendation": data.get("recommendation", "REFER_TO_HUMAN"),
            "confidence_score": confidence_score,
            "checks": [self._transform_check(c) for c in data.get("checks", [])],
            "assumptions": [self._transform_assumption(a) for a in data.get("assumptions", [])],
            "payout": payout,
            "currency": currency,
            "payout_breakdown": self._transform_payout(data),
            "recommendation_rationale": data.get("recommendation_rationale"),
            "fraud_indicators": [
                self._transform_fraud_indicator(f) for f in data.get("fraud_indicators", [])
            ],
            "recommendations": data.get("recommendations", []),
            "assessed_at": data.get("assessment_timestamp"),
        }

    def _get_feedback_path(self, claim_id: str) -> Path:
        """Get the path to a claim's current assessment feedback file."""
        return self.claims_dir / claim_id / "context" / "assessment_feedback.json"

    def save_feedback(self, claim_id: str, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save feedback for the current assessment.

        Writes feedback to both the current assessment feedback file and
        a versioned copy alongside the assessment in the assessments directory.

        Args:
            claim_id: The claim ID
            feedback_data: Dict with rating, comment, username

        Returns:
            The saved feedback dict
        """
        # Load current assessment to get assessment_id
        assessment_path = self._get_assessment_path(claim_id)
        assessment_id = None
        if assessment_path.exists():
            try:
                with open(assessment_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                assessment_id = data.get("assessment_id")
            except (json.JSONDecodeError, IOError):
                pass

        # If no legacy assessment, check claim_runs for latest
        if not assessment_id:
            claim_runs_dir = self._get_claim_runs_dir(claim_id)
            if claim_runs_dir.exists():
                latest_timestamp = ""
                for run_dir in claim_runs_dir.iterdir():
                    if not run_dir.is_dir():
                        continue
                    af = run_dir / "assessment.json"
                    if not af.exists():
                        continue
                    try:
                        with open(af, "r", encoding="utf-8") as f:
                            d = json.load(f)
                        ts = d.get("assessment_timestamp", "")
                        if ts > latest_timestamp:
                            latest_timestamp = ts
                            assessment_id = d.get("assessment_id") or run_dir.name
                    except (json.JSONDecodeError, IOError):
                        continue

        now = datetime.now(timezone.utc)
        feedback = {
            "claim_id": claim_id,
            "assessment_id": assessment_id,
            "rating": feedback_data["rating"],
            "comment": feedback_data.get("comment", ""),
            "username": feedback_data["username"],
            "submitted_at": now.isoformat(),
        }

        # Write current feedback file
        feedback_path = self._get_feedback_path(claim_id)
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        with open(feedback_path, "w", encoding="utf-8") as f:
            json.dump(feedback, f, indent=2)
        logger.info(f"Saved assessment feedback to {feedback_path}")

        # Also write versioned feedback alongside the assessment
        if assessment_id:
            versioned_path = self._get_assessments_dir(claim_id) / f"{assessment_id}_feedback.json"
            versioned_path.parent.mkdir(parents=True, exist_ok=True)
            with open(versioned_path, "w", encoding="utf-8") as f:
                json.dump(feedback, f, indent=2)

        return feedback

    def get_feedback(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Get feedback for the current assessment (if any).

        Args:
            claim_id: The claim ID

        Returns:
            Feedback dict or None if no feedback exists
        """
        feedback_path = self._get_feedback_path(claim_id)
        if not feedback_path.exists():
            return None
        try:
            with open(feedback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load assessment feedback: {e}")
            return None

    def get_assessment(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Load and transform the latest assessment to frontend format.

        Checks claim_runs/ for the most recent assessment first, then falls
        back to context/assessment.json for legacy data.

        Args:
            claim_id: The claim ID to load assessment for

        Returns:
            Transformed assessment matching frontend ClaimAssessment type,
            or None if no assessment exists
        """
        # Primary: find latest assessment from claim_runs/
        claim_runs_dir = self._get_claim_runs_dir(claim_id)
        if claim_runs_dir.exists():
            latest_assessment = None
            latest_timestamp = ""

            for run_dir in claim_runs_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                assessment_file = run_dir / "assessment.json"
                if not assessment_file.exists():
                    continue

                try:
                    with open(assessment_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    timestamp = data.get("assessment_timestamp", "")
                    if timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_assessment = data
                except (json.JSONDecodeError, IOError):
                    continue

            if latest_assessment:
                return self._transform_assessment(latest_assessment)

        # Fallback: read from context/assessment.json (legacy)
        assessment_path = self._get_assessment_path(claim_id)
        if not assessment_path.exists():
            logger.debug(f"Assessment file not found: {assessment_path}")
            return None

        try:
            with open(assessment_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._transform_assessment(data)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse assessment file {assessment_path}: {e}")
            return None
        except IOError as e:
            logger.warning(f"Failed to read assessment file {assessment_path}: {e}")
            return None

    def get_assessment_history(self, claim_id: str) -> List[Dict[str, Any]]:
        """Return all assessment history entries for a claim.

        Reads from claim_runs/ directories, finding all runs that have an
        assessment.json file. Falls back to context/assessments/ index if
        no claim_runs exist.

        Args:
            claim_id: The claim ID to load assessment history for

        Returns:
            List of AssessmentHistoryEntry dicts, newest first, or empty list
        """
        # Primary: read from claim_runs/ directory
        claim_runs_dir = self._get_claim_runs_dir(claim_id)
        if claim_runs_dir.exists():
            history = []
            for run_dir in claim_runs_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                assessment_file = run_dir / "assessment.json"
                if not assessment_file.exists():
                    continue

                try:
                    with open(assessment_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Transform the assessment for counts
                    transformed = self._transform_assessment(data)
                    checks = transformed.get("checks", [])
                    checks_total = len(checks)
                    checks_passed = sum(1 for c in checks if c.get("result") == "PASS")

                    # Convert confidence_score to percentage if needed
                    confidence = data.get("confidence_score", 0)
                    if isinstance(confidence, (int, float)) and confidence <= 1.0:
                        confidence = confidence * 100

                    # Extract payout value
                    payout = None
                    if isinstance(data.get("payout"), dict):
                        payout = data["payout"].get("final_payout")
                    elif isinstance(data.get("payout"), (int, float)):
                        payout = data["payout"]

                    history.append({
                        "run_id": run_dir.name,
                        "timestamp": data.get("assessment_timestamp"),
                        "recommendation": data.get("recommendation"),
                        "confidence_score": confidence,
                        "payout": payout,
                        "prompt_version": data.get("prompt_version"),
                        "extraction_bundle_id": data.get("extraction_bundle_id"),
                        "is_current": False,  # Will mark newest below
                        "check_count": checks_total,
                        "pass_count": checks_passed,
                        "fail_count": checks_total - checks_passed,
                        "assumption_count": len(transformed.get("assumptions", [])),
                    })
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to load assessment from {run_dir.name}: {e}")
                    continue

            # Sort by timestamp (newest first) and mark first as current
            if history:
                history.sort(
                    key=lambda x: x.get("timestamp") or "",
                    reverse=True
                )
                history[0]["is_current"] = True
                return history

        # Fallback: read from context/assessments/index.json (legacy)
        index = self._load_assessments_index(claim_id)
        if index["assessments"]:
            history = []
            for entry in reversed(index["assessments"]):  # Newest first
                assessment = self.get_assessment_by_id(claim_id, entry["id"])
                checks_passed = 0
                checks_total = 0
                assumption_count = 0

                if assessment:
                    checks_passed = sum(
                        1
                        for c in assessment.get("checks", [])
                        if c.get("result") == "PASS"
                    )
                    checks_total = len(assessment.get("checks", []))
                    assumption_count = len(assessment.get("assumptions", []))

                confidence = entry.get("confidence_score", 0)
                if isinstance(confidence, (int, float)) and confidence <= 1.0:
                    confidence = confidence * 100

                history.append({
                    "run_id": entry.get("id"),
                    "timestamp": entry.get("timestamp"),
                    "recommendation": entry.get("recommendation"),
                    "confidence_score": confidence,
                    "payout": assessment.get("payout") if assessment else None,
                    "prompt_version": entry.get("prompt_version"),
                    "extraction_bundle_id": entry.get("extraction_bundle_id"),
                    "is_current": entry.get("is_current", False),
                    "check_count": checks_total,
                    "pass_count": checks_passed,
                    "fail_count": checks_total - checks_passed,
                    "assumption_count": assumption_count,
                })
            return history

        # Final fallback: wrap current assessment as single entry
        assessment = self.get_assessment(claim_id)
        if assessment is None:
            return []

        checks = assessment.get("checks", [])
        checks_total = len(checks)
        checks_passed = sum(1 for c in checks if c.get("result") == "PASS")

        return [
            {
                "run_id": None,
                "timestamp": assessment.get("assessed_at"),
                "recommendation": assessment.get("recommendation"),
                "confidence_score": assessment.get("confidence_score"),
                "payout": assessment.get("payout"),
                "prompt_version": None,
                "extraction_bundle_id": None,
                "is_current": True,
                "check_count": checks_total,
                "pass_count": checks_passed,
                "fail_count": checks_total - checks_passed,
                "assumption_count": len(assessment.get("assumptions", [])),
            }
        ]

    def get_latest_evaluation(self) -> Optional[Dict[str, Any]]:
        """Load most recent assessment evaluation file and transform for frontend.

        Checks both legacy assessment_eval_*.json files and newer
        eval_*/summary.json directories, returning whichever is most recent.

        Returns:
            Transformed evaluation matching frontend AssessmentEvaluation type,
            or None if no evaluation files exist.
        """
        eval_dir = self.workspace_path / "eval"
        if not eval_dir.exists():
            logger.debug(f"Eval directory not found: {eval_dir}")
            return None

        # Candidate 1: legacy assessment_eval_*.json files
        legacy_files = sorted(eval_dir.glob("assessment_eval_*.json"), reverse=True)
        legacy_ts = ""
        if legacy_files:
            # Extract timestamp from filename: assessment_eval_YYYYMMDD_HHMMSS.json
            legacy_ts = legacy_files[0].stem.replace("assessment_eval_", "")

        # Candidate 2: newer eval_*/summary.json directories
        eval_dirs = sorted(
            [
                d
                for d in eval_dir.iterdir()
                if d.is_dir()
                and d.name.startswith("eval_")
                and (d / "summary.json").exists()
            ],
            key=lambda d: d.name,
            reverse=True,
        )
        eval_dir_ts = ""
        if eval_dirs:
            # Extract timestamp from dirname: eval_YYYYMMDD_HHMMSS
            eval_dir_ts = eval_dirs[0].name.replace("eval_", "")

        # Pick whichever is newer (timestamps are sortable strings)
        if not legacy_ts and not eval_dir_ts:
            logger.debug("No assessment eval files found")
            return None

        if eval_dir_ts > legacy_ts:
            # Use newer eval directory format
            summary_path = eval_dirs[0] / "summary.json"
            logger.info(f"Loading latest evaluation (dir): {eval_dirs[0].name}")
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return self._transform_eval_dir_summary(data, eval_dirs[0].name)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read eval dir summary {summary_path}: {e}")
                return None
        else:
            # Use legacy assessment_eval_*.json format
            latest_file = legacy_files[0]
            logger.info(f"Loading latest evaluation (legacy): {latest_file.name}")
            try:
                with open(latest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return self._transform_evaluation(data, latest_file.stem)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read evaluation file {latest_file}: {e}")
                return None

    def _transform_eval_dir_summary(
        self, data: Dict[str, Any], eval_id: str
    ) -> Dict[str, Any]:
        """Transform eval_*/summary.json data to frontend AssessmentEvaluation format.

        The newer eval format stores aggregate stats (no per-claim results).
        Maps APPROVE/DENY to APPROVE/REJECT for frontend compatibility.

        Args:
            data: Raw data from eval_*/summary.json
            eval_id: Evaluation ID (directory name)

        Returns:
            Transformed evaluation matching frontend AssessmentEvaluation type
        """
        total = data.get("total_claims", data.get("processed_claims", 0))
        accuracy = data.get("decision_accuracy", 0.0)

        # Build 3x3 confusion matrix from 2x2 approve/deny data
        approve_correct = data.get("gt_approved_correct", 0)
        approve_wrong = data.get("gt_approved_wrong", 0)
        deny_correct = data.get("gt_denied_correct", 0)
        deny_wrong = data.get("gt_denied_wrong", 0)

        matrix = {
            "APPROVE": {
                "APPROVE": approve_correct,
                "REJECT": approve_wrong,
                "REFER_TO_HUMAN": 0,
            },
            "REJECT": {
                "APPROVE": deny_wrong,
                "REJECT": deny_correct,
                "REFER_TO_HUMAN": 0,
            },
            "REFER_TO_HUMAN": {
                "APPROVE": 0,
                "REJECT": 0,
                "REFER_TO_HUMAN": 0,
            },
        }

        # Compute precision from the matrix
        approve_precision = self._compute_precision(matrix, "APPROVE")
        reject_precision = self._compute_precision(matrix, "REJECT")

        # Parse timestamp from eval_id (eval_YYYYMMDD_HHMMSS)
        ts_str = eval_id.replace("eval_", "")
        try:
            ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            timestamp = ts.isoformat()
        except ValueError:
            timestamp = ""

        return {
            "eval_id": eval_id,
            "timestamp": timestamp,
            "confusion_matrix": {
                "matrix": matrix,
                "total_evaluated": total,
                "decision_accuracy": round(accuracy * 100, 1) if accuracy <= 1 else accuracy,
            },
            "results": [],  # No per-claim results in this format
            "summary": {
                "total_claims": total,
                "accuracy_rate": round(accuracy * 100, 1) if accuracy <= 1 else accuracy,
                "approve_precision": round(approve_precision * 100, 1),
                "reject_precision": round(reject_precision * 100, 1),
                "refer_rate": 0.0,
            },
        }

    def _transform_evaluation(
        self, data: Dict[str, Any], eval_id: str
    ) -> Dict[str, Any]:
        """Transform evaluation file data to frontend AssessmentEvaluation format.

        Args:
            data: Raw data from assessment_eval_*.json
            eval_id: Evaluation ID (filename stem)

        Returns:
            Transformed evaluation matching frontend AssessmentEvaluation type
        """
        # Extract confusion matrix
        raw_matrix = data.get("confusion_matrix", {})
        matrix = raw_matrix.get("matrix", {})
        total_evaluated = raw_matrix.get("total_evaluated", 0)
        decision_accuracy = raw_matrix.get("decision_accuracy", 0.0)

        # Transform results: map eval file fields to frontend fields
        results = []
        for r in data.get("results", []):
            results.append({
                "claim_id": r.get("claim_id", ""),
                "predicted": r.get("ai_decision", "REFER_TO_HUMAN"),
                "actual": r.get("expected_decision", "REFER_TO_HUMAN"),
                "is_correct": r.get("passed", False),
                "confidence_score": r.get("confidence_score", 0.0),
                "assumption_count": 0,  # Not in eval file, default to 0
            })

        # Compute precision metrics from confusion matrix
        # Matrix is indexed as [actual][predicted]
        approve_precision = self._compute_precision(matrix, "APPROVE")
        reject_precision = self._compute_precision(matrix, "REJECT")
        refer_rate = self._compute_refer_rate(results)

        # Build summary - convert decimals to percentages for frontend
        raw_summary = data.get("summary", {})
        accuracy = raw_summary.get("accuracy", decision_accuracy)
        summary = {
            "total_claims": raw_summary.get("total_claims", len(results)),
            "accuracy_rate": round(accuracy * 100, 1) if accuracy <= 1 else accuracy,
            "approve_precision": round(approve_precision * 100, 1),
            "reject_precision": round(reject_precision * 100, 1),
            "refer_rate": round(refer_rate * 100, 1),
        }

        return {
            "eval_id": eval_id,
            "timestamp": data.get("evaluated_at", ""),
            "confusion_matrix": {
                "matrix": matrix,
                "total_evaluated": total_evaluated,
                "decision_accuracy": round(decision_accuracy * 100, 1) if decision_accuracy <= 1 else decision_accuracy,
            },
            "results": results,
            "summary": summary,
        }

    def _compute_precision(
        self, matrix: Dict[str, Dict[str, int]], decision: str
    ) -> float:
        """Compute precision for a specific decision type.

        Precision = TP / (TP + FP)
        TP = matrix[decision][decision]  (predicted correct)
        FP = sum of matrix[other][decision] for other != decision

        Args:
            matrix: Confusion matrix indexed as [actual][predicted]
            decision: Decision type ("APPROVE", "REJECT", "REFER_TO_HUMAN")

        Returns:
            Precision value between 0.0 and 1.0, or 0.0 if no predictions
        """
        # True positives: actual=decision, predicted=decision
        tp = matrix.get(decision, {}).get(decision, 0)

        # False positives: actual!=decision, predicted=decision
        fp = 0
        for actual, predictions in matrix.items():
            if actual != decision:
                fp += predictions.get(decision, 0)

        total = tp + fp
        if total == 0:
            return 0.0
        return tp / total

    def _compute_refer_rate(self, results: List[Dict[str, Any]]) -> float:
        """Compute the rate of REFER_TO_HUMAN predictions.

        Args:
            results: List of evaluation results

        Returns:
            Refer rate between 0.0 and 1.0
        """
        if not results:
            return 0.0

        refer_count = sum(
            1 for r in results if r.get("predicted") == "REFER_TO_HUMAN"
        )
        return refer_count / len(results)


# Backwards compatibility alias (deprecated - use AssessmentStorageService)
AssessmentService = AssessmentStorageService
