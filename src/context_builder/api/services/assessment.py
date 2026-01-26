"""Assessment service for loading and transforming claim assessments."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AssessmentService:
    """Service for loading and transforming claim assessment data."""

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
            "decision": assessment_data.get("decision"),
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

        Args:
            claim_id: The claim ID
            assessment_id: The assessment ID (timestamp_version format)

        Returns:
            Transformed assessment, or None if not found
        """
        index = self._load_assessments_index(claim_id)

        # Find entry in index
        entry = next(
            (a for a in index["assessments"] if a["id"] == assessment_id), None
        )
        if not entry:
            logger.debug(f"Assessment {assessment_id} not found in index")
            return None

        # Load from file
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
            "decision": data.get("decision", "REFER_TO_HUMAN"),
            "confidence_score": confidence_score,
            "checks": [self._transform_check(c) for c in data.get("checks", [])],
            "assumptions": [self._transform_assumption(a) for a in data.get("assumptions", [])],
            "payout": payout,
            "currency": currency,
            "payout_breakdown": self._transform_payout(data),
            "decision_rationale": data.get("decision_rationale"),
            "fraud_indicators": [
                self._transform_fraud_indicator(f) for f in data.get("fraud_indicators", [])
            ],
            "recommendations": data.get("recommendations", []),
            "assessed_at": data.get("assessment_timestamp"),
        }

    def get_assessment(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Load and transform assessment.json to frontend format.

        Args:
            claim_id: The claim ID to load assessment for

        Returns:
            Transformed assessment matching frontend ClaimAssessment type,
            or None if file doesn't exist or can't be parsed
        """
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

        Reads from assessments/index.json if available, falling back to
        wrapping the current assessment as a single entry.

        Args:
            claim_id: The claim ID to load assessment history for

        Returns:
            List of AssessmentHistoryEntry dicts, newest first, or empty list
        """
        index = self._load_assessments_index(claim_id)

        # If we have versioned history, use it
        if index["assessments"]:
            history = []
            for entry in reversed(index["assessments"]):  # Newest first
                # Load full assessment to get check counts
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

                # Convert confidence_score to percentage if needed
                confidence = entry.get("confidence_score", 0)
                if isinstance(confidence, (int, float)) and confidence <= 1.0:
                    confidence = confidence * 100

                history.append({
                    "run_id": entry.get("id"),
                    "timestamp": entry.get("timestamp"),
                    "decision": entry.get("decision"),
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

        # Fallback: wrap current assessment as single entry
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
                "decision": assessment.get("decision"),
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

        Reads from {workspace}/eval/assessment_eval_*.json and transforms
        the data to match the frontend AssessmentEvaluation type.

        Returns:
            Transformed evaluation matching frontend AssessmentEvaluation type,
            or None if no evaluation files exist.
        """
        eval_dir = self.workspace_path / "eval"
        if not eval_dir.exists():
            logger.debug(f"Eval directory not found: {eval_dir}")
            return None

        # Find latest eval file (sorted by name = sorted by timestamp)
        eval_files = sorted(eval_dir.glob("assessment_eval_*.json"), reverse=True)
        if not eval_files:
            logger.debug("No assessment eval files found")
            return None

        latest_file = eval_files[0]
        logger.info(f"Loading latest evaluation: {latest_file.name}")

        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._transform_evaluation(data, latest_file.stem)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse evaluation file {latest_file}: {e}")
            return None
        except IOError as e:
            logger.warning(f"Failed to read evaluation file {latest_file}: {e}")
            return None

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
