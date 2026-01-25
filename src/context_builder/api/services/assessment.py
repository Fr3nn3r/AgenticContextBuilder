"""Assessment service for loading and transforming claim assessments."""

import json
import logging
import re
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
        """Return current assessment as single history entry.

        Currently, we only store the latest assessment, so history
        is just the current assessment wrapped in a list.

        Args:
            claim_id: The claim ID to load assessment history for

        Returns:
            List containing single AssessmentHistoryEntry, or empty list
            if no assessment exists
        """
        assessment = self.get_assessment(claim_id)

        if assessment is None:
            return []

        # Return current assessment as single history entry
        # Note: confidence_score is already converted to percentage in get_assessment()
        return [
            {
                "timestamp": assessment.get("assessed_at"),
                "decision": assessment.get("decision"),
                "confidence_score": assessment.get("confidence_score"),
                "payout": assessment.get("payout"),
                "checks_passed": sum(
                    1 for c in assessment.get("checks", []) if c.get("result") == "PASS"
                ),
                "checks_total": len(assessment.get("checks", [])),
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
