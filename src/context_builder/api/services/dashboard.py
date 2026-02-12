"""Dashboard service for aggregating claim data with assessment and ground truth."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Module-level cache for list_claims results (keyed by claims_dir path).
_list_claims_cache: Dict[str, Any] = {}
_CACHE_TTL_SECONDS = 30

_DEFAULT_DASHBOARD_CONFIG: Dict[str, Any] = {
    "ground_truth_path": "config/ground_truth.json",
    "ground_truth_doc_filename": "Claim_Decision.pdf",
    "default_currency": "CHF",
    "result_code_labels": {
        "component_coverage": "Parts not covered",
        "service_compliance": "Service non-compliance",
        "policy_validity": "Policy expired",
        "mileage": "Mileage exceeded",
        "damage_date": "Pre-existing damage",
        "shop_authorization": "Unauthorized shop",
        "vehicle_id": "VIN mismatch",
    },
}


class DashboardService:
    """Aggregates claim data with assessment results and ground truth."""

    def __init__(self, claims_dir: Path):
        self.claims_dir = claims_dir
        self.workspace_path = claims_dir.parent
        self._dashboard_config: Optional[Dict[str, Any]] = None

    def _load_dashboard_config(self) -> Dict[str, Any]:
        """Load optional dashboard config from workspace config."""
        if self._dashboard_config is not None:
            return self._dashboard_config

        config_path = self.workspace_path / "config" / "dashboard.json"
        config = dict(_DEFAULT_DASHBOARD_CONFIG)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    override = json.load(f)
                if isinstance(override, dict):
                    config.update(override)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load dashboard config: {e}")
        self._dashboard_config = config
        return config

    def _resolve_path(self, path_value: str) -> Path:
        """Resolve a workspace-relative path value."""
        path = Path(path_value)
        if path.is_absolute():
            return path
        return self.workspace_path / path

    def _get_result_code_map(self) -> Dict[str, str]:
        """Get check-name-to-label mapping for result codes."""
        config = self._load_dashboard_config()
        mapping = config.get("result_code_labels", {})
        return mapping if isinstance(mapping, dict) else {}

    def _load_ground_truth(self) -> Dict[str, Dict[str, Any]]:
        """Load ground truth data keyed by claim_id."""
        config = self._load_dashboard_config()
        gt_path_value = config.get("ground_truth_path", "config/ground_truth.json")
        gt_path = self._resolve_path(gt_path_value)
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

    def _load_datasets(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Load dataset assignments and labels.

        Returns (assignments, labels) where:
          assignments maps claim_id -> dataset_id
          labels maps dataset_id -> human-readable label
        If file is missing or malformed, returns ({}, {}).
        """
        ds_path = self.workspace_path / "config" / "datasets.json"
        if not ds_path.exists():
            return {}, {}
        try:
            with open(ds_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            labels = {d["id"]: d["label"] for d in data.get("datasets", [])}
            assignments = data.get("assignments", {})
            return assignments, labels
        except (json.JSONDecodeError, IOError, KeyError):
            return {}, {}

    def _load_latest_assessment(
        self, claim_id: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Load the latest assessment for a claim.

        Returns (assessment_data, claim_run_id) or (None, None).
        Uses sorted directory names (descending) to pick the latest run
        and only reads that single assessment.json file.
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

        # Sort run dirs descending by name (timestamp-based names) and pick
        # the first one with an assessment.json — avoids reading ALL runs.
        run_dirs = sorted(
            (d for d in claim_runs_dir.iterdir() if d.is_dir()),
            key=lambda d: d.name,
            reverse=True,
        )
        for run_dir in run_dirs:
            af = run_dir / "assessment.json"
            if not af.exists():
                continue
            try:
                with open(af, "r", encoding="utf-8") as f:
                    return json.load(f), run_dir.name
            except (json.JSONDecodeError, IOError):
                continue

        return None, None

    def _derive_result_code(
        self, assessment: Dict[str, Any], decision: Optional[str] = None,
    ) -> str:
        """Derive a human-readable result code from assessment checks.

        Args:
            assessment: Assessment data dict (for check results).
            decision: Authoritative verdict (from dossier). Falls back to
                assessment recommendation if not provided.
        """
        decision = decision or assessment.get("recommendation", "")
        if decision == "APPROVE" or decision == "APPROVED":
            return "Approved"

        checks = assessment.get("checks", [])
        failed_reasons = []
        code_map = self._get_result_code_map()
        for check in checks:
            if check.get("result") == "FAIL":
                check_name = check.get("check_name", "")
                readable = code_map.get(check_name)
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

    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load a JSON file, returning None on missing/corrupt."""
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _get_fact_value(self, facts_data: Optional[Dict[str, Any]], name: str) -> Optional[str]:
        """Search facts list by name, returning value or normalized_value."""
        if not facts_data:
            return None
        for fact in facts_data.get("facts", []):
            if fact.get("name") == name:
                return fact.get("value") or fact.get("normalized_value")
        return None

    def _find_latest_dossier(self, run_dir: Path) -> Optional[Path]:
        """Find the latest decision_dossier_v*.json in a run directory."""
        candidates = sorted(run_dir.glob("decision_dossier_v*.json"))
        return candidates[-1] if candidates else None

    def _build_rationale(self, dossier: Dict[str, Any], verdict: Optional[str]) -> Optional[str]:
        """Build a human-readable rationale from dossier data."""
        strip_prefix = lambda s: (
            s if not s else
            s.replace("Claim approved.", "").replace("Claim denied.", "")
            .replace("Claim approved", "").replace("Claim denied", "").strip()
        ) or None

        if dossier.get("verdict_reason"):
            result = strip_prefix(dossier["verdict_reason"])
            if result:
                return result

        if verdict == "DENY":
            failed = dossier.get("failed_clauses", [])
            if failed:
                refs = [
                    c.get("clause_reference", c) if isinstance(c, dict) else str(c)
                    for c in failed
                ]
                return ", ".join(refs)

        evals = dossier.get("clause_evaluations", [])
        if evals:
            passed = sum(
                1 for e in evals if (e.get("verdict") or "").upper() == "PASS"
            )
            assumed = sum(1 for e in evals if e.get("assumption_used") is not None)
            parts = [f"{passed}/{len(evals)} passed"]
            if assumed > 0:
                parts.append(f"{assumed} assumed")
            return ", ".join(parts)

        return None

    def _count_documents(self, claim_id: str) -> int:
        """Count documents for a claim (fast — no file reads, just directory listing)."""
        docs_dir = self.claims_dir / claim_id / "docs"
        if not docs_dir.exists():
            return 0
        return sum(1 for d in docs_dir.iterdir() if d.is_dir())

    def list_claims(self) -> List[Dict[str, Any]]:
        """Get enriched claim data for all claims in the workspace."""
        global _list_claims_cache

        if not self.claims_dir.exists():
            return []

        # Check module-level cache
        cache_key = str(self.claims_dir)
        cached = _list_claims_cache.get(cache_key)
        if cached and cached["expires_at"] > time.monotonic():
            return cached["data"]

        gt_data = self._load_ground_truth()
        ds_assignments, ds_labels = self._load_datasets()
        config = self._load_dashboard_config()
        default_currency = config.get("default_currency", "CHF")
        gt_doc_filename = config.get(
            "ground_truth_doc_filename", "Claim_Decision.pdf"
        )
        results = []

        for claim_dir in sorted(self.claims_dir.iterdir()):
            if not claim_dir.is_dir():
                continue
            claim_id = claim_dir.name
            # Skip non-claim folders
            if claim_id.startswith(".") or claim_id in ("runs",):
                continue

            doc_count = self._count_documents(claim_id)
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
            currency = default_currency
            assessment_method = None

            if assessment:
                # decision is populated from dossier below, not from assessment
                confidence_raw = assessment.get("confidence_score", 0)
                if isinstance(confidence_raw, (int, float)):
                    confidence = (
                        confidence_raw * 100
                        if confidence_raw <= 1.0
                        else confidence_raw
                    )
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
                    currency = payout_data.get("currency", default_currency)
                elif isinstance(payout_data, (int, float)):
                    payout = payout_data

            # Workbench enrichment (facts, dossier, screening)
            policy_number = None
            wb_vehicle = None
            event_date = None
            wb_verdict = None
            verdict_reason = None
            cci_score = None
            cci_band = None
            wb_screening_payout = None
            has_dossier = False

            if claim_run_id:
                run_dir = claim_dir / "claim_runs" / claim_run_id

                # 1. Load claim_facts
                facts_data = self._load_json(run_dir / "claim_facts.json")
                if facts_data:
                    policy_number = self._get_fact_value(facts_data, "policy_number")
                    make = self._get_fact_value(facts_data, "vehicle_make") or self._get_fact_value(facts_data, "make")
                    model = self._get_fact_value(facts_data, "vehicle_model") or self._get_fact_value(facts_data, "model")
                    wb_vehicle = " ".join(filter(None, [make, model])) or None
                    event_date = self._get_fact_value(facts_data, "cost_estimate.document_date")

                # 2. Find latest dossier
                dossier_path = self._find_latest_dossier(run_dir)
                if dossier_path:
                    has_dossier = True
                    dossier_data = self._load_json(dossier_path)
                    if dossier_data:
                        wb_verdict = (dossier_data.get("claim_verdict") or "").upper() or None
                        verdict_reason = self._build_rationale(dossier_data, wb_verdict)
                        cci = dossier_data.get("confidence_index")
                        if isinstance(cci, dict):
                            cci_score = cci.get("composite_score")
                            cci_band = cci.get("band")

                # 3. Screening payout (only for non-DENY)
                if wb_verdict != "DENY" and payout is None:
                    screen_data = self._load_json(run_dir / "screening.json")
                    if screen_data:
                        sp = screen_data.get("payout")
                        if isinstance(sp, dict):
                            wb_screening_payout = sp.get("final_payout")

            # Set decision from dossier verdict (authoritative source)
            decision = wb_verdict

            # Derive result code using authoritative decision
            if assessment:
                result_code = self._derive_result_code(assessment, decision=decision)

            # Ground truth fields
            gt_decision = gt.get("decision")
            gt_payout = gt.get("total_approved_amount")
            gt_denial_reason = gt.get("denial_reason")
            gt_vehicle = gt.get("vehicle")
            gt_coverage_notes = gt.get("coverage_notes")
            claim_date = gt.get("date")

            # Match comparison — decision is already set from dossier (authoritative)
            decision_match = None
            payout_diff = None
            norm_decision = self._normalize_decision(decision)
            norm_gt = self._normalize_decision(gt_decision)
            if norm_decision and norm_gt:
                decision_match = norm_decision == norm_gt
            if payout is not None and gt_payout is not None:
                payout_diff = round(payout - gt_payout, 2)

            # Ground truth doc
            gt_doc_path = claim_dir / "ground_truth" / gt_doc_filename
            has_gt_doc = gt_doc_path.exists()

            results.append({
                "claim_id": claim_id,
                "folder_name": claim_id,
                "claim_date": claim_date,
                "doc_count": doc_count,
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
                "policy_number": policy_number,
                "vehicle": wb_vehicle,
                "event_date": event_date,
                "verdict": wb_verdict,
                "verdict_reason": verdict_reason,
                "cci_score": cci_score,
                "cci_band": cci_band,
                "screening_payout": wb_screening_payout,
                "has_dossier": has_dossier,
                "gt_decision": gt_decision,
                "gt_payout": gt_payout,
                "gt_denial_reason": gt_denial_reason,
                "gt_vehicle": gt_vehicle,
                "gt_coverage_notes": gt_coverage_notes,
                "decision_match": decision_match,
                "payout_diff": payout_diff,
                "has_ground_truth_doc": has_gt_doc,
                "dataset_id": ds_assignments.get(claim_id),
                "dataset_label": ds_labels.get(ds_assignments.get(claim_id, ""), None),
                "documents": [],
            })

        # Store in module-level cache
        _list_claims_cache[cache_key] = {
            "data": results,
            "expires_at": time.monotonic() + _CACHE_TTL_SECONDS,
        }

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

        # VAT amounts (computed from subtotal × rate)
        sys_vat_amount = None
        if sys_total_adjusted is not None and vat_rate_pct:
            sys_vat_amount = round(sys_total_adjusted * vat_rate_pct / 100.0, 2)

        gt_total_ml = gt.get("total_material_labor_approved")
        gt_vat_rate = gt.get("vat_rate_pct")
        gt_vat_amount = None
        if gt_total_ml is not None and gt_vat_rate:
            gt_vat_amount = round(gt_total_ml * gt_vat_rate / 100.0, 2)

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
            "sys_vat_amount": sys_vat_amount,
            "gt_vat_amount": gt_vat_amount,
            "screening_payout": screening_payout,
        }

    def get_ground_truth_doc_path(self, claim_id: str) -> Optional[Path]:
        """Get path to ground truth PDF for a claim."""
        gt_doc_filename = self._load_dashboard_config().get(
            "ground_truth_doc_filename", "Claim_Decision.pdf"
        )
        gt_path = self.claims_dir / claim_id / "ground_truth" / gt_doc_filename
        if gt_path.exists():
            return gt_path
        return None
