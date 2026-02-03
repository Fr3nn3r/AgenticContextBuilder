"""Dashboard service for aggregating claim data with assessment and ground truth."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Mapping from check names to human-readable result codes
_CHECK_RESULT_CODES: Dict[str, str] = {
    "component_coverage": "Parts not covered",
    "service_compliance": "Service non-compliance",
    "policy_validity": "Policy expired",
    "mileage": "Mileage exceeded",
    "damage_date": "Pre-existing damage",
    "shop_authorization": "Unauthorized shop",
    "vehicle_id": "VIN mismatch",
}


class DashboardService:
    """Aggregates claim data with assessment results and ground truth."""

    def __init__(self, claims_dir: Path):
        self.claims_dir = claims_dir
        self.workspace_path = claims_dir.parent

    def _load_ground_truth(self) -> Dict[str, Dict[str, Any]]:
        """Load ground truth data keyed by claim_id."""
        gt_path = self.workspace_path / "config" / "ground_truth.json"
        if not gt_path.exists():
            logger.warning(f"Ground truth not found: {gt_path}")
            return {}
        try:
            with open(gt_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {c["claim_id"]: c for c in data.get("claims", [])}
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load ground truth: {e}")
            return {}

    def _load_latest_assessment(
        self, claim_id: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Load the latest assessment for a claim.

        Returns (assessment_data, claim_run_id) or (None, None).
        """
        claim_runs_dir = self.claims_dir / claim_id / "claim_runs"
        if not claim_runs_dir.exists():
            # Fallback to context/assessment.json
            legacy = self.claims_dir / claim_id / "context" / "assessment.json"
            if legacy.exists():
                try:
                    with open(legacy, "r", encoding="utf-8") as f:
                        return json.load(f), None
                except (json.JSONDecodeError, IOError):
                    pass
            return None, None

        latest = None
        latest_ts = ""
        latest_run_id = None

        for run_dir in claim_runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            af = run_dir / "assessment.json"
            if not af.exists():
                continue
            try:
                with open(af, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ts = data.get("assessment_timestamp", "")
                if ts > latest_ts:
                    latest_ts = ts
                    latest = data
                    latest_run_id = run_dir.name
            except (json.JSONDecodeError, IOError):
                continue

        return latest, latest_run_id

    def _derive_result_code(self, assessment: Dict[str, Any]) -> str:
        """Derive a human-readable result code from assessment checks."""
        decision = assessment.get("decision", "")
        if decision == "APPROVE" or decision == "APPROVED":
            return "Approved"

        checks = assessment.get("checks", [])
        failed_reasons = []
        for check in checks:
            if check.get("result") == "FAIL":
                check_name = check.get("check_name", "")
                readable = _CHECK_RESULT_CODES.get(check_name)
                if readable and readable not in failed_reasons:
                    failed_reasons.append(readable)

        if failed_reasons:
            return " + ".join(failed_reasons)

        if decision == "REJECT" or decision == "DENIED":
            return "Rejected"
        if decision == "REFER_TO_HUMAN":
            return "Refer to human"
        return ""

    def _get_inconclusive_warnings(self, assessment: Dict[str, Any]) -> List[str]:
        """Get check names with INCONCLUSIVE results."""
        warnings = []
        for check in assessment.get("checks", []):
            if check.get("result") == "INCONCLUSIVE":
                warnings.append(check.get("check_name", "Unknown check"))
        return warnings

    def _normalize_decision(self, decision: Optional[str]) -> Optional[str]:
        """Normalize decision strings for comparison."""
        if not decision:
            return None
        d = decision.upper().strip()
        if d in ("APPROVE", "APPROVED"):
            return "APPROVE"
        if d in ("REJECT", "DENIED", "DENY"):
            return "REJECT"
        if d in ("REFER_TO_HUMAN", "REFER"):
            return "REFER_TO_HUMAN"
        return d

    def _get_documents(self, claim_id: str) -> List[Dict[str, Any]]:
        """Get document list for a claim."""
        docs_dir = self.claims_dir / claim_id / "docs"
        if not docs_dir.exists():
            return []

        docs = []
        for doc_dir in docs_dir.iterdir():
            if not doc_dir.is_dir():
                continue
            meta_path = doc_dir / "meta" / "doc.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                docs.append({
                    "doc_id": doc_dir.name,
                    "filename": meta.get("original_filename", doc_dir.name),
                    "doc_type": meta.get("doc_type", "unknown"),
                    "extraction_run_id": meta.get("extraction_run_id"),
                })
            except (json.JSONDecodeError, IOError):
                docs.append({
                    "doc_id": doc_dir.name,
                    "filename": doc_dir.name,
                    "doc_type": "unknown",
                    "extraction_run_id": None,
                })
        return docs

    def list_claims(self) -> List[Dict[str, Any]]:
        """Get enriched claim data for all claims in the workspace."""
        if not self.claims_dir.exists():
            return []

        gt_data = self._load_ground_truth()
        results = []

        for claim_dir in sorted(self.claims_dir.iterdir()):
            if not claim_dir.is_dir():
                continue
            claim_id = claim_dir.name
            # Skip non-claim folders
            if claim_id.startswith(".") or claim_id in ("runs",):
                continue

            docs = self._get_documents(claim_id)
            assessment, claim_run_id = self._load_latest_assessment(claim_id)
            gt = gt_data.get(claim_id, {})

            # Assessment fields
            decision = None
            confidence = None
            result_code = None
            inconclusive_warnings: List[str] = []
            checks_passed = 0
            checks_failed = 0
            checks_inconclusive = 0
            payout = None
            currency = "CHF"
            assessment_method = None

            if assessment:
                decision = assessment.get("decision")
                confidence_raw = assessment.get("confidence_score", 0)
                if isinstance(confidence_raw, (int, float)):
                    confidence = (
                        confidence_raw * 100
                        if confidence_raw <= 1.0
                        else confidence_raw
                    )
                result_code = self._derive_result_code(assessment)
                inconclusive_warnings = self._get_inconclusive_warnings(assessment)
                assessment_method = assessment.get("assessment_method")

                # Count check results
                for check in assessment.get("checks", []):
                    r = check.get("result", "").upper()
                    if r == "PASS":
                        checks_passed += 1
                    elif r == "FAIL":
                        checks_failed += 1
                    elif r in ("INCONCLUSIVE", "N/A"):
                        checks_inconclusive += 1

                payout_data = assessment.get("payout")
                if isinstance(payout_data, dict):
                    payout = payout_data.get("final_payout")
                    currency = payout_data.get("currency", "CHF")
                elif isinstance(payout_data, (int, float)):
                    payout = payout_data

            # Ground truth fields
            gt_decision = gt.get("decision")
            gt_payout = gt.get("total_approved_amount")
            gt_denial_reason = gt.get("denial_reason")
            gt_vehicle = gt.get("vehicle")
            gt_coverage_notes = gt.get("coverage_notes")
            claim_date = gt.get("date")

            # Match comparison
            decision_match = None
            payout_diff = None
            norm_decision = self._normalize_decision(decision)
            norm_gt = self._normalize_decision(gt_decision)
            if norm_decision and norm_gt:
                decision_match = norm_decision == norm_gt
            if payout is not None and gt_payout is not None:
                payout_diff = round(payout - gt_payout, 2)

            # Ground truth doc
            gt_doc_path = claim_dir / "ground_truth" / "Claim_Decision.pdf"
            has_gt_doc = gt_doc_path.exists()

            results.append({
                "claim_id": claim_id,
                "folder_name": claim_id,
                "claim_date": claim_date,
                "doc_count": len(docs),
                "decision": decision,
                "confidence": confidence,
                "result_code": result_code,
                "inconclusive_warnings": inconclusive_warnings,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "checks_inconclusive": checks_inconclusive,
                "payout": payout,
                "currency": currency,
                "assessment_method": assessment_method,
                "claim_run_id": claim_run_id,
                "gt_decision": gt_decision,
                "gt_payout": gt_payout,
                "gt_denial_reason": gt_denial_reason,
                "gt_vehicle": gt_vehicle,
                "gt_coverage_notes": gt_coverage_notes,
                "decision_match": decision_match,
                "payout_diff": payout_diff,
                "has_ground_truth_doc": has_gt_doc,
                "documents": docs,
            })

        return results

    def get_claim_detail(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Get expanded detail data for a single claim."""
        claim_dir = self.claims_dir / claim_id
        if not claim_dir.exists():
            return None

        gt_data = self._load_ground_truth()
        gt = gt_data.get(claim_id, {})

        # Find latest claim run
        _, claim_run_id = self._load_latest_assessment(claim_id)

        # Load coverage analysis
        coverage_items: List[Dict[str, Any]] = []
        coverage_summary = None
        payout_calculation = None
        screening_checks: List[Dict[str, Any]] = []
        assessment_checks: List[Dict[str, Any]] = []
        screening_payout = None

        if claim_run_id:
            run_dir = claim_dir / "claim_runs" / claim_run_id

            # Coverage analysis
            cov_path = run_dir / "coverage_analysis.json"
            if cov_path.exists():
                try:
                    with open(cov_path, "r", encoding="utf-8") as f:
                        cov_data = json.load(f)
                    coverage_items = cov_data.get("line_items", [])
                    coverage_summary = cov_data.get("summary")
                except (json.JSONDecodeError, IOError):
                    pass

            # Assessment payout
            assess_path = run_dir / "assessment.json"
            if assess_path.exists():
                try:
                    with open(assess_path, "r", encoding="utf-8") as f:
                        assess_data = json.load(f)
                    payout_data = assess_data.get("payout")
                    if isinstance(payout_data, dict):
                        payout_calculation = payout_data
                    assessment_checks = assess_data.get("checks", [])
                except (json.JSONDecodeError, IOError):
                    pass

            # Screening
            screen_path = run_dir / "screening.json"
            if screen_path.exists():
                try:
                    with open(screen_path, "r", encoding="utf-8") as f:
                        screen_data = json.load(f)
                    screening_checks = screen_data.get("checks", [])
                    screening_payout = screen_data.get("payout")
                except (json.JSONDecodeError, IOError):
                    pass

        # Compute parts/labor from coverage_items (works on existing data)
        sys_parts_gross = 0.0
        sys_labor_gross = 0.0
        for item in coverage_items:
            if item.get("coverage_status") == "covered":
                price = item.get("total_price", 0.0)
                if item.get("item_type") == "parts":
                    sys_parts_gross += price
                elif item.get("item_type") == "labor":
                    sys_labor_gross += price

        # Get coverage_percent
        coverage_pct = None
        if screening_payout:
            coverage_pct = screening_payout.get("coverage_percent")
        elif payout_calculation:
            coverage_pct = payout_calculation.get("coverage_percent")

        # Rate-adjusted values (to match GT convention where rate is pre-applied)
        sys_parts_adjusted = round(sys_parts_gross * coverage_pct / 100.0, 2) if coverage_pct else None
        sys_labor_adjusted = round(sys_labor_gross * coverage_pct / 100.0, 2) if coverage_pct else None
        sys_total_adjusted = round((sys_parts_adjusted or 0) + (sys_labor_adjusted or 0), 2) if coverage_pct else None

        vat_rate_pct = None
        if screening_payout:
            vat_rate_pct = screening_payout.get("vat_rate_pct")
        if vat_rate_pct is None and payout_calculation:
            vat_rate_pct = payout_calculation.get("vat_rate_pct")

        return {
            "claim_id": claim_id,
            "coverage_items": coverage_items,
            "coverage_summary": coverage_summary,
            "payout_calculation": payout_calculation,
            "gt_parts_approved": gt.get("parts_approved"),
            "gt_labor_approved": gt.get("labor_approved"),
            "gt_total_material_labor": gt.get("total_material_labor_approved"),
            "gt_vat_rate_pct": gt.get("vat_rate_pct"),
            "gt_deductible": gt.get("deductible"),
            "gt_total_approved": gt.get("total_approved_amount"),
            "gt_reimbursement_rate_pct": gt.get("reimbursement_rate_pct"),
            "screening_checks": screening_checks,
            "assessment_checks": assessment_checks,
            "sys_parts_gross": round(sys_parts_gross, 2),
            "sys_labor_gross": round(sys_labor_gross, 2),
            "sys_parts_adjusted": sys_parts_adjusted,
            "sys_labor_adjusted": sys_labor_adjusted,
            "sys_total_adjusted": sys_total_adjusted,
            "sys_vat_rate_pct": vat_rate_pct,
            "screening_payout": screening_payout,
        }

    def get_ground_truth_doc_path(self, claim_id: str) -> Optional[Path]:
        """Get path to ground truth PDF for a claim."""
        gt_path = self.claims_dir / claim_id / "ground_truth" / "Claim_Decision.pdf"
        if gt_path.exists():
            return gt_path
        return None
