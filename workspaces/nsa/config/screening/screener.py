"""NSA-specific screener with warranty insurance checks.

This screener implements the Screener protocol and provides:
- 9 deterministic checks (policy validity, VIN, mileage, coverage, etc.)
- Coverage analysis integration
- Shop authorization lookup (merged from enrichment stage)
- Payout calculation with deductible and VAT
- Auto-reject on hard-fail checks

Usage:
    The screener is automatically discovered by ScreeningStage when placed at:
    {workspace}/config/screening/screener.py
"""

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from context_builder.coverage.analyzer import CoverageAnalyzer
from context_builder.coverage.schemas import CoverageAnalysisResult, CoverageStatus
from context_builder.schemas.reconciliation import ReconciliationReport
from context_builder.schemas.screening import (
    CheckVerdict,
    ScreeningCheck,
    ScreeningPayoutCalculation,
    ScreeningResult,
)

logger = logging.getLogger(__name__)

# ── NSA-specific constants ───────────────────────────────────────────

COMPANY_INDICATORS = {
    "AG", "SA", "GmbH", "Sàrl", "Ltd", "Inc", "S.A.", "Corp", "KG", "Co.",
    "Sagl", "LLC", "SARL", "Srl",
}

ASSISTANCE_KEYWORDS = [
    "ERSATZFAHRZEUG", "MIETWAGEN", "RENTAL", "LEIHWAGEN",
    "ABSCHLEPP", "TOWING", "PANNENHILFE", "REMORQUAGE",
]

SWISS_VAT_RATE = 0.081


# ── Utility helpers (imported from core) ─────────────────────────────

def _get_fact(facts: List[Dict], name: str) -> Optional[str]:
    """Get a fact value by name, with suffix match fallback."""
    for f in facts:
        if f.get("name") == name:
            return f.get("value")
    for f in facts:
        fact_name = f.get("name", "")
        if fact_name.endswith("." + name):
            return f.get("value")
    return None


def _get_structured_fact(facts: List[Dict], name: str) -> Optional[Any]:
    """Get a fact's structured_value by name, with suffix match fallback."""
    for f in facts:
        if f.get("name") == name:
            return f.get("structured_value")
    for f in facts:
        fact_name = f.get("name", "")
        if fact_name.endswith("." + name):
            return f.get("structured_value")
    return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Parse ISO (YYYY-MM-DD) and European (DD.MM.YYYY) date strings."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, IndexError):
        pass
    try:
        return datetime.strptime(value[:10], "%d.%m.%Y").date()
    except (ValueError, IndexError):
        pass
    return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    """Parse numeric string to int (handles 74'359, 74,359)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None
    cleaned = value.replace("'", "").replace(",", "").replace("\u2019", "").strip()
    match = re.match(r"^[\d]+", cleaned)
    if match:
        return int(match.group())
    return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Parse numeric/percent string to float.

    Handles European formats where comma is decimal separator and
    space/apostrophe is thousands separator:
    - "300,00 CHF" → 300.0
    - "8 000,00 CHF" → 8000.0
    - "74'359.50" → 74359.5
    - "10 %" → 10.0
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    # Remove currency/unit suffixes and whitespace
    cleaned = value.strip()

    # Remove thousands separators (space, apostrophe, right single quote)
    cleaned = cleaned.replace(" ", "").replace("'", "").replace("\u2019", "")

    # Handle European decimal comma: replace comma with period
    # But only if there's no period already (to avoid breaking "74359.50")
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")

    # Extract number (including decimal)
    match = re.search(r"([\d]+(?:\.[\d]+)?)", cleaned)
    if match:
        return float(match.group(1))
    return None


# ── NSA Screener ─────────────────────────────────────────────────────


class NSAScreener:
    """NSA-specific screener with warranty insurance checks.

    Implements 9 deterministic checks, coverage analysis, payout calculation,
    and auto-reject logic for warranty insurance claims.

    This screener now handles shop authorization lookup internally
    (merged from enrichment stage in Phase 6 cleanup).
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self._analyzer: Optional[CoverageAnalyzer] = None
        self._assumptions: Optional[Dict[str, Any]] = None

    def _load_assumptions(self) -> Dict[str, Any]:
        """Load assumptions.json from workspace config (cached)."""
        if self._assumptions is not None:
            return self._assumptions

        assumptions_path = self.workspace_path / "config" / "assumptions.json"

        if not assumptions_path.exists():
            logger.warning(f"No assumptions.json found at {assumptions_path}")
            self._assumptions = {}
            return self._assumptions

        try:
            with open(assumptions_path, "r", encoding="utf-8") as f:
                self._assumptions = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load assumptions: {e}")
            self._assumptions = {}

        return self._assumptions

    def _get_analyzer(self) -> CoverageAnalyzer:
        """Get or create coverage analyzer from workspace config."""
        if self._analyzer is not None:
            return self._analyzer

        config_dir = self.workspace_path / "config" / "coverage"
        config_files = list(config_dir.glob("*_coverage_config.yaml")) if config_dir.exists() else []

        if config_files:
            self._analyzer = CoverageAnalyzer.from_config_path(
                config_files[0], workspace_path=self.workspace_path
            )
            logger.info(f"Loaded coverage config from {config_files[0]}")
        else:
            self._analyzer = CoverageAnalyzer(workspace_path=self.workspace_path)
            logger.info("Using default coverage analyzer config")

        return self._analyzer

    def screen(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        reconciliation_report: Optional[ReconciliationReport] = None,
        claim_run_id: Optional[str] = None,
        on_llm_start: Optional[Callable[[int], None]] = None,
        on_llm_progress: Optional[Callable[[int], None]] = None,
    ) -> Tuple[ScreeningResult, Optional[CoverageAnalysisResult]]:
        """Run all 9 NSA checks + coverage + payout.

        Args:
            claim_id: Claim identifier.
            aggregated_facts: Enriched aggregated facts dict.
            reconciliation_report: Reconciliation report (for VIN conflicts).
            claim_run_id: Claim run ID for coverage analysis.
            on_llm_start: Optional callback when LLM calls start (total count).
            on_llm_progress: Optional callback for LLM progress (increment).

        Returns:
            Tuple of (ScreeningResult, CoverageAnalysisResult or None).
        """
        facts = aggregated_facts.get("facts", [])
        # Use `or {}` to handle both missing key AND null value
        structured = aggregated_facts.get("structured_data") or {}

        checks: List[ScreeningCheck] = []
        coverage_result: Optional[CoverageAnalysisResult] = None

        # ── Run coverage analysis first (needed for check 5) ──────────
        try:
            coverage_result = self._run_coverage_analysis(
                claim_id, aggregated_facts, claim_run_id,
                on_llm_start=on_llm_start,
                on_llm_progress=on_llm_progress,
            )
        except Exception as e:
            logger.warning(f"Coverage analysis failed: {e}")

        # ── Run all checks ────────────────────────────────────────────
        checks.append(self._check_1_policy_validity(facts))
        checks.append(self._check_1b_damage_date(facts))
        checks.append(self._check_2_vin_consistency(reconciliation_report))
        checks.append(self._check_2b_owner_match(facts))
        checks.append(self._check_3_mileage(facts))
        checks.append(self._check_4a_shop_auth(facts))
        checks.append(self._check_4b_service_compliance(facts, structured))
        checks.append(self._check_5_component_coverage(coverage_result))
        checks.append(self._check_5b_assistance_items(structured))

        # ── Build result ──────────────────────────────────────────────
        result = ScreeningResult(
            claim_id=claim_id,
            screening_timestamp=datetime.utcnow().isoformat(),
            checks=checks,
        )

        # Set coverage_analysis_ref if coverage was computed
        if coverage_result is not None:
            result.coverage_analysis_ref = "coverage_analysis.json"

        # Recompute counts and auto-reject from checks
        result.recompute_counts()

        # ── Payout calculation ────────────────────────────────────────
        try:
            payout = self._calculate_payout(facts, coverage_result)
            result.payout = payout
        except Exception as e:
            logger.warning(f"Payout calculation failed: {e}")
            result.payout_error = str(e)

        # Set auto-reject reason
        if result.auto_reject:
            result.auto_reject_reason = (
                f"Hard fail on check(s): {', '.join(sorted(result.hard_fails))}"
            )

        return result, coverage_result

    # ── Coverage analysis ─────────────────────────────────────────────

    def _run_coverage_analysis(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        claim_run_id: Optional[str],
        on_llm_start: Optional[Callable[[int], None]] = None,
        on_llm_progress: Optional[Callable[[int], None]] = None,
    ) -> Optional[CoverageAnalysisResult]:
        """Run coverage analysis using CoverageAnalyzer."""
        facts = aggregated_facts.get("facts", [])
        # Use `or {}` to handle both missing key AND null value
        structured = aggregated_facts.get("structured_data") or {}

        # Extract line items
        line_items = structured.get("line_items", [])
        if not line_items:
            logger.info("No line items found, skipping coverage analysis")
            return None

        # Extract covered components
        covered_components = _get_structured_fact(facts, "covered_components") or {}
        if not isinstance(covered_components, dict):
            covered_components = {}

        # Extract vehicle km
        km_str = _get_fact(facts, "odometer_km") or _get_fact(facts, "vehicle_current_km")
        vehicle_km = _parse_int(km_str)

        # Extract coverage scale
        coverage_scale = _get_structured_fact(facts, "coverage_scale")
        if not isinstance(coverage_scale, list):
            coverage_scale = None

        # Extract excess info
        excess_percent = _parse_float(_get_fact(facts, "excess_percent"))
        excess_minimum = _parse_float(_get_fact(facts, "excess_minimum"))

        # Run analysis
        analyzer = self._get_analyzer()
        return analyzer.analyze(
            claim_id=claim_id,
            line_items=line_items,
            covered_components=covered_components,
            vehicle_km=vehicle_km,
            coverage_scale=coverage_scale,
            excess_percent=excess_percent,
            excess_minimum=excess_minimum,
            claim_run_id=claim_run_id,
            on_llm_start=on_llm_start,
            on_llm_progress=on_llm_progress,
        )

    # ── Check 1: Policy validity ──────────────────────────────────────

    def _check_1_policy_validity(self, facts: List[Dict]) -> ScreeningCheck:
        """Check if claim date falls within policy period."""
        policy_start = _parse_date(_get_fact(facts, "start_date"))
        policy_end = _parse_date(_get_fact(facts, "end_date"))
        claim_date = _parse_date(_get_fact(facts, "document_date"))

        evidence = {
            "policy_start": str(policy_start) if policy_start else None,
            "policy_end": str(policy_end) if policy_end else None,
            "claim_date": str(claim_date) if claim_date else None,
        }

        if not policy_start or not policy_end or not claim_date:
            return ScreeningCheck(
                check_id="1",
                check_name="policy_validity",
                verdict=CheckVerdict.SKIPPED,
                reason="Missing date data for policy validity check",
                evidence=evidence,
                is_hard_fail=True,
            )

        if policy_start <= claim_date <= policy_end:
            return ScreeningCheck(
                check_id="1",
                check_name="policy_validity",
                verdict=CheckVerdict.PASS,
                reason=f"Claim date {claim_date} is within policy period {policy_start} to {policy_end}",
                evidence=evidence,
                is_hard_fail=True,
            )
        else:
            return ScreeningCheck(
                check_id="1",
                check_name="policy_validity",
                verdict=CheckVerdict.FAIL,
                reason=f"Claim date {claim_date} is outside policy period {policy_start} to {policy_end}",
                evidence=evidence,
                is_hard_fail=True,
            )

    # ── Check 1b: Damage date ─────────────────────────────────────────

    def _check_1b_damage_date(self, facts: List[Dict]) -> ScreeningCheck:
        """Check if damage date falls within policy period (clear cases only)."""
        policy_start = _parse_date(_get_fact(facts, "start_date"))
        policy_end = _parse_date(_get_fact(facts, "end_date"))
        damage_date = _parse_date(_get_fact(facts, "damage_date"))

        evidence = {
            "policy_start": str(policy_start) if policy_start else None,
            "policy_end": str(policy_end) if policy_end else None,
            "damage_date": str(damage_date) if damage_date else None,
        }

        if not damage_date:
            return ScreeningCheck(
                check_id="1b",
                check_name="damage_date",
                verdict=CheckVerdict.SKIPPED,
                reason="No damage date available",
                evidence=evidence,
                is_hard_fail=True,
            )

        if not policy_start or not policy_end:
            return ScreeningCheck(
                check_id="1b",
                check_name="damage_date",
                verdict=CheckVerdict.SKIPPED,
                reason="Missing policy dates for damage date check",
                evidence=evidence,
                is_hard_fail=True,
            )

        if policy_start <= damage_date <= policy_end:
            return ScreeningCheck(
                check_id="1b",
                check_name="damage_date",
                verdict=CheckVerdict.PASS,
                reason=f"Damage date {damage_date} is within policy period",
                evidence=evidence,
                is_hard_fail=True,
            )
        else:
            return ScreeningCheck(
                check_id="1b",
                check_name="damage_date",
                verdict=CheckVerdict.FAIL,
                reason=f"Damage date {damage_date} is outside policy period {policy_start} to {policy_end}",
                evidence=evidence,
                is_hard_fail=True,
            )

    # ── Check 2: VIN consistency ──────────────────────────────────────

    def _check_2_vin_consistency(
        self, reconciliation_report: Optional[ReconciliationReport]
    ) -> ScreeningCheck:
        """Check for VIN conflicts across documents."""
        if reconciliation_report is None:
            return ScreeningCheck(
                check_id="2",
                check_name="vin_consistency",
                verdict=CheckVerdict.SKIPPED,
                reason="No reconciliation report available",
                is_hard_fail=False,
            )

        # Look for VIN-related conflicts
        vin_conflicts = []
        for conflict in reconciliation_report.conflicts:
            name_lower = conflict.fact_name.lower()
            if "vin" in name_lower or "chassis" in name_lower or "fahrgestell" in name_lower:
                vin_conflicts.append({
                    "fact_name": conflict.fact_name,
                    "values": conflict.values,
                })

        evidence = {
            "vin_conflicts": vin_conflicts,
            "total_conflicts": len(reconciliation_report.conflicts),
        }

        if not vin_conflicts:
            return ScreeningCheck(
                check_id="2",
                check_name="vin_consistency",
                verdict=CheckVerdict.PASS,
                reason="No VIN conflicts found across documents",
                evidence=evidence,
                is_hard_fail=False,
            )
        else:
            return ScreeningCheck(
                check_id="2",
                check_name="vin_consistency",
                verdict=CheckVerdict.FAIL,
                reason=f"VIN conflict: {len(vin_conflicts)} conflict(s) found across documents",
                evidence=evidence,
                is_hard_fail=False,
                requires_llm=True,
            )

    # ── Check 2b: Owner match ─────────────────────────────────────────

    def _check_2b_owner_match(self, facts: List[Dict]) -> ScreeningCheck:
        """Check if policyholder name matches vehicle owner name."""
        policyholder = _get_fact(facts, "policyholder_name")
        owner = _get_fact(facts, "owner_name")

        evidence = {
            "policyholder_name": policyholder,
            "owner_name": owner,
        }

        if not policyholder or not owner:
            return ScreeningCheck(
                check_id="2b",
                check_name="owner_match",
                verdict=CheckVerdict.SKIPPED,
                reason="Owner or policyholder name not available",
                evidence=evidence,
                is_hard_fail=False,
            )

        # Normalize for comparison
        ph_norm = policyholder.strip().lower()
        ow_norm = owner.strip().lower()

        # Exact match (case-insensitive)
        if ph_norm == ow_norm:
            return ScreeningCheck(
                check_id="2b",
                check_name="owner_match",
                verdict=CheckVerdict.PASS,
                reason="Policyholder and owner names match exactly",
                evidence=evidence,
                is_hard_fail=False,
            )

        # Substring match (one contains the other)
        if ph_norm in ow_norm or ow_norm in ph_norm:
            return ScreeningCheck(
                check_id="2b",
                check_name="owner_match",
                verdict=CheckVerdict.PASS,
                reason="Policyholder and owner names have a substring match",
                evidence=evidence,
                is_hard_fail=False,
            )

        # No match → INCONCLUSIVE (needs LLM review)
        return ScreeningCheck(
            check_id="2b",
            check_name="owner_match",
            verdict=CheckVerdict.INCONCLUSIVE,
            reason=f"Policyholder '{policyholder}' does not match owner '{owner}'",
            evidence=evidence,
            is_hard_fail=False,
            requires_llm=True,
        )

    # ── Check 3: Mileage ──────────────────────────────────────────────

    def _check_3_mileage(self, facts: List[Dict]) -> ScreeningCheck:
        """Check if current odometer is within policy mileage limit."""
        km_limit_str = _get_fact(facts, "km_limited_to")
        odometer_str = _get_fact(facts, "odometer_km") or _get_fact(facts, "vehicle_current_km")

        km_limit = _parse_int(km_limit_str)
        odometer = _parse_int(odometer_str)

        evidence = {
            "km_limited_to": km_limit,
            "current_odometer": odometer,
            "km_limit_raw": km_limit_str,
            "odometer_raw": odometer_str,
        }

        if km_limit is None or odometer is None:
            return ScreeningCheck(
                check_id="3",
                check_name="mileage",
                verdict=CheckVerdict.SKIPPED,
                reason="Missing mileage data",
                evidence=evidence,
                is_hard_fail=True,
            )

        if odometer <= km_limit:
            return ScreeningCheck(
                check_id="3",
                check_name="mileage",
                verdict=CheckVerdict.PASS,
                reason=f"Odometer {odometer:,} km is within limit of {km_limit:,} km",
                evidence=evidence,
                is_hard_fail=True,
            )
        else:
            return ScreeningCheck(
                check_id="3",
                check_name="mileage",
                verdict=CheckVerdict.FAIL,
                reason=f"Odometer {odometer:,} km exceeds limit of {km_limit:,} km",
                evidence=evidence,
                is_hard_fail=True,
            )

    # ── Shop authorization lookup ────────────────────────────────────

    def _lookup_shop_authorization(self, shop_name: Optional[str]) -> Dict[str, Any]:
        """Lookup shop authorization status from assumptions.json.

        This method was moved from the enrichment stage in Phase 6 cleanup.

        Returns a dict with:
        - lookup_method: "exact_name", "pattern", or "not_found"
        - authorized: True, False, or None
        - action: what to do if not found
        """
        assumptions = self._load_assumptions()
        partners = assumptions.get("authorized_partners", {})

        if not shop_name:
            return {
                "lookup_method": "not_found",
                "authorized": None,
                "action": partners.get("_default_if_unknown", "REFER_TO_HUMAN"),
                "reason": "No shop name provided",
            }

        # Try exact name match first
        by_name = partners.get("by_name", {})
        for name, info in by_name.items():
            if name.lower() in shop_name.lower() or shop_name.lower() in name.lower():
                result = info.copy()
                result["lookup_method"] = "exact_name"
                result["matched_name"] = name
                return result

        # Try pattern matching
        by_pattern = partners.get("by_pattern", [])
        for pattern_info in by_pattern:
            pattern = pattern_info.get("pattern", "")
            try:
                if re.match(pattern, shop_name, re.IGNORECASE):
                    result = pattern_info.copy()
                    result["lookup_method"] = "pattern"
                    return result
            except re.error:
                continue

        # Not found
        return {
            "lookup_method": "not_found",
            "authorized": None,
            "action": partners.get("_default_if_unknown", "REFER_TO_HUMAN"),
            "reason": "Shop not found in authorized partners list",
        }

    # ── Check 4a: Shop authorization ──────────────────────────────────

    def _check_4a_shop_auth(self, facts: List[Dict]) -> ScreeningCheck:
        """Check shop authorization by looking up the garage name.

        This check now performs its own lookup (merged from enrichment stage
        in Phase 6 cleanup) rather than relying on pre-enriched data.
        """
        # Get shop name from facts
        shop_name = _get_fact(facts, "garage_name")

        # Perform authorization lookup
        shop_auth = self._lookup_shop_authorization(shop_name)

        evidence = {
            "shop_name": shop_name,
            "lookup_method": shop_auth.get("lookup_method"),
            "authorized": shop_auth.get("authorized"),
        }

        if not shop_name:
            return ScreeningCheck(
                check_id="4a",
                check_name="shop_authorization",
                verdict=CheckVerdict.SKIPPED,
                reason="No garage name found in facts",
                evidence=evidence,
                is_hard_fail=False,
            )

        authorized = shop_auth.get("authorized")

        if authorized is True:
            return ScreeningCheck(
                check_id="4a",
                check_name="shop_authorization",
                verdict=CheckVerdict.PASS,
                reason=f"Shop '{shop_name}' is authorized ({shop_auth.get('lookup_method', 'unknown')} match)",
                evidence=evidence,
                is_hard_fail=False,
            )
        elif authorized is False:
            return ScreeningCheck(
                check_id="4a",
                check_name="shop_authorization",
                verdict=CheckVerdict.FAIL,
                reason=f"Shop '{shop_name}' is NOT authorized",
                evidence=evidence,
                is_hard_fail=False,
                requires_llm=True,
            )
        else:
            return ScreeningCheck(
                check_id="4a",
                check_name="shop_authorization",
                verdict=CheckVerdict.INCONCLUSIVE,
                reason=f"Shop '{shop_name}' authorization unknown",
                evidence=evidence,
                is_hard_fail=False,
                requires_llm=True,
            )

    # ── Check 4b: Service compliance ──────────────────────────────────

    def _check_4b_service_compliance(
        self, facts: List[Dict], structured: Dict[str, Any]
    ) -> ScreeningCheck:
        """Check if vehicle has been serviced within 36 months."""
        claim_date = _parse_date(_get_fact(facts, "document_date"))
        service_entries = structured.get("service_entries", [])

        if not service_entries:
            return ScreeningCheck(
                check_id="4b",
                check_name="service_compliance",
                verdict=CheckVerdict.SKIPPED,
                reason="No service history data",
                evidence={"service_count": 0},
                is_hard_fail=False,
            )

        if not claim_date:
            return ScreeningCheck(
                check_id="4b",
                check_name="service_compliance",
                verdict=CheckVerdict.SKIPPED,
                reason="No claim date for service gap calculation",
                evidence={"service_count": len(service_entries)},
                is_hard_fail=False,
            )

        # Find most recent service date
        most_recent: Optional[date] = None
        most_recent_str: Optional[str] = None
        for entry in service_entries:
            svc_date_str = entry.get("service_date")
            svc_date = _parse_date(svc_date_str)
            if svc_date and (most_recent is None or svc_date > most_recent):
                most_recent = svc_date
                most_recent_str = svc_date_str

        if most_recent is None:
            return ScreeningCheck(
                check_id="4b",
                check_name="service_compliance",
                verdict=CheckVerdict.SKIPPED,
                reason="Could not parse any service dates",
                evidence={"service_count": len(service_entries)},
                is_hard_fail=False,
            )

        days_gap = (claim_date - most_recent).days

        evidence = {
            "last_service_date": most_recent_str,
            "claim_date": str(claim_date),
            "days_since_last_service": days_gap,
            "service_count": len(service_entries),
        }

        if days_gap <= 1095:  # 36 months
            return ScreeningCheck(
                check_id="4b",
                check_name="service_compliance",
                verdict=CheckVerdict.PASS,
                reason=f"Last service {days_gap} days ago (within 36 months)",
                evidence=evidence,
                is_hard_fail=False,
            )
        else:
            return ScreeningCheck(
                check_id="4b",
                check_name="service_compliance",
                verdict=CheckVerdict.FAIL,
                reason=f"Last service {days_gap} days ago (exceeds 36-month limit)",
                evidence=evidence,
                is_hard_fail=False,
                requires_llm=True,
            )

    # ── Check 5: Component coverage ───────────────────────────────────

    def _check_5_component_coverage(
        self, coverage_result: Optional[CoverageAnalysisResult]
    ) -> ScreeningCheck:
        """Check if primary repair component is covered by policy.

        The primary repair is the highest-value parts item. If this item
        is not covered, the check FAILS even if other items are covered.
        This prevents approving claims where the main repair is excluded.
        """
        if coverage_result is None:
            return ScreeningCheck(
                check_id="5",
                check_name="component_coverage",
                verdict=CheckVerdict.SKIPPED,
                reason="No coverage analysis available",
                is_hard_fail=True,
            )

        summary = coverage_result.summary
        evidence = {
            "items_covered": summary.items_covered,
            "items_not_covered": summary.items_not_covered,
            "items_review_needed": summary.items_review_needed,
            "total_covered_before_excess": summary.total_covered_before_excess,
            "total_not_covered": summary.total_not_covered,
        }

        # Find the primary repair: highest-value parts item
        primary_repair = None
        for item in coverage_result.line_items:
            if item.item_type == "parts":
                if primary_repair is None or (item.total_price or 0) > (primary_repair.total_price or 0):
                    primary_repair = item

        # If no parts items, fall back to highest-value item overall
        if primary_repair is None:
            for item in coverage_result.line_items:
                if primary_repair is None or (item.total_price or 0) > (primary_repair.total_price or 0):
                    primary_repair = item

        if primary_repair is None:
            return ScreeningCheck(
                check_id="5",
                check_name="component_coverage",
                verdict=CheckVerdict.SKIPPED,
                reason="No line items to evaluate coverage",
                evidence=evidence,
                is_hard_fail=True,
            )

        # Add primary repair info to evidence
        evidence["primary_component"] = primary_repair.description
        evidence["primary_component_price"] = primary_repair.total_price
        evidence["primary_component_status"] = (
            primary_repair.coverage_status.value if primary_repair.coverage_status else None
        )
        if primary_repair.coverage_category:
            evidence["primary_component_category"] = primary_repair.coverage_category

        # Check primary repair coverage status
        if primary_repair.coverage_status == CoverageStatus.COVERED:
            return ScreeningCheck(
                check_id="5",
                check_name="component_coverage",
                verdict=CheckVerdict.PASS,
                reason=f"Primary repair '{primary_repair.description}' ({primary_repair.total_price:.0f} CHF) is covered ({primary_repair.coverage_category})",
                evidence=evidence,
                is_hard_fail=True,
            )

        if primary_repair.coverage_status == CoverageStatus.NOT_COVERED:
            confidence = primary_repair.match_confidence or 0
            low_confidence = confidence < 0.80

            # Check if the item's category is actually covered by this policy
            covered_cats = (
                [c.lower() for c in coverage_result.inputs.covered_categories]
                if coverage_result.inputs else []
            )
            item_cat = (primary_repair.coverage_category or "").lower()
            category_is_covered = item_cat and any(
                item_cat in c or c in item_cat for c in covered_cats
            )

            should_demote = low_confidence or category_is_covered

            if should_demote:
                evidence["demotion_reason"] = (
                    "low_confidence" if low_confidence
                    else "category_covered_component_not_listed"
                )
                evidence["primary_match_confidence"] = confidence
                evidence["primary_match_method"] = (
                    primary_repair.match_method.value
                    if primary_repair.match_method else None
                )
                return ScreeningCheck(
                    check_id="5",
                    check_name="component_coverage",
                    verdict=CheckVerdict.INCONCLUSIVE,
                    reason=(
                        f"Primary repair '{primary_repair.description}' "
                        f"({primary_repair.total_price:.0f} CHF) coverage uncertain "
                        f"(confidence={confidence:.2f}) - deferring to LLM"
                    ),
                    evidence=evidence,
                    is_hard_fail=True,
                    requires_llm=True,
                )

            # High confidence + uncovered category = hard fail
            return ScreeningCheck(
                check_id="5",
                check_name="component_coverage",
                verdict=CheckVerdict.FAIL,
                reason=f"Primary repair '{primary_repair.description}' ({primary_repair.total_price:.0f} CHF) is not covered",
                evidence=evidence,
                is_hard_fail=True,
            )

        # REVIEW_NEEDED or unknown status
        if primary_repair.coverage_status == CoverageStatus.REVIEW_NEEDED or summary.items_review_needed > 0:
            return ScreeningCheck(
                check_id="5",
                check_name="component_coverage",
                verdict=CheckVerdict.INCONCLUSIVE,
                reason=f"Primary repair '{primary_repair.description}' needs review for coverage determination",
                evidence=evidence,
                is_hard_fail=True,
                requires_llm=True,
            )

        return ScreeningCheck(
            check_id="5",
            check_name="component_coverage",
            verdict=CheckVerdict.SKIPPED,
            reason="Could not determine primary repair coverage status",
            evidence=evidence,
            is_hard_fail=True,
        )

    # ── Check 5b: Assistance items ────────────────────────────────────

    def _check_5b_assistance_items(self, structured: Dict[str, Any]) -> ScreeningCheck:
        """Check for rental car / towing / assistance items in line items."""
        line_items = structured.get("line_items", [])
        if not line_items:
            return ScreeningCheck(
                check_id="5b",
                check_name="assistance_items",
                verdict=CheckVerdict.SKIPPED,
                reason="No line items to check for assistance",
                is_hard_fail=False,
            )

        found_items = []
        for item in line_items:
            desc = (item.get("description") or "").upper()
            for keyword in ASSISTANCE_KEYWORDS:
                if keyword in desc:
                    found_items.append({
                        "description": item.get("description"),
                        "keyword": keyword,
                        "total_price": item.get("total_price", 0),
                    })
                    break  # One keyword per item is enough

        evidence = {
            "assistance_items_found": len(found_items),
            "items": found_items[:5],  # Cap evidence size
        }

        if not found_items:
            return ScreeningCheck(
                check_id="5b",
                check_name="assistance_items",
                verdict=CheckVerdict.PASS,
                reason="No assistance/rental/towing items found",
                evidence=evidence,
                is_hard_fail=False,
            )
        else:
            total = sum(i["total_price"] for i in found_items)
            return ScreeningCheck(
                check_id="5b",
                check_name="assistance_items",
                verdict=CheckVerdict.INCONCLUSIVE,
                reason=f"Found {len(found_items)} assistance item(s) totaling CHF {total:.2f} — needs review",
                evidence=evidence,
                is_hard_fail=False,
                requires_llm=True,
            )

    # ── Payout calculation ────────────────────────────────────────────

    def _calculate_payout(
        self,
        facts: List[Dict],
        coverage_result: Optional[CoverageAnalysisResult],
    ) -> Optional[ScreeningPayoutCalculation]:
        """Calculate deterministic payout from screening data.

        NSA Formula (matches decision letters):
        1. covered_total from coverage.summary.total_covered_before_excess
        2. Cap at max_coverage if exceeded
        3. Add VAT (8.1%) to get subtotal
        4. Deductible: MAX(subtotal * excess_percent/100, excess_minimum)
        5. Final payout = subtotal - deductible
        6. For companies: remove VAT from final payout
        """
        if coverage_result is None:
            return None

        summary = coverage_result.summary
        covered_total = summary.total_covered_before_excess
        not_covered_total = summary.total_not_covered

        # Coverage percent from analysis
        coverage_percent = summary.coverage_percent

        # Max coverage cap
        max_coverage_str = _get_fact(facts, "max_coverage")
        max_coverage = _parse_float(max_coverage_str)
        max_coverage_applied = False
        capped_amount = covered_total

        if max_coverage is not None and covered_total > max_coverage:
            capped_amount = max_coverage
            max_coverage_applied = True

        # Add VAT to get subtotal (NSA adds VAT before calculating deductible)
        vat_amount = capped_amount * SWISS_VAT_RATE
        subtotal_with_vat = capped_amount + vat_amount

        # Deductible is calculated on VAT-inclusive subtotal
        excess_percent_str = _get_fact(facts, "excess_percent")
        excess_minimum_str = _get_fact(facts, "excess_minimum")
        deductible_percent = _parse_float(excess_percent_str)
        deductible_minimum = _parse_float(excess_minimum_str)

        deductible_amount = 0.0
        if deductible_percent is not None:
            deductible_amount = subtotal_with_vat * deductible_percent / 100.0
        if deductible_minimum is not None:
            deductible_amount = max(deductible_amount, deductible_minimum)

        after_deductible = max(0.0, subtotal_with_vat - deductible_amount)

        # Policyholder type (company vs individual) → VAT treatment
        policyholder_name = _get_fact(facts, "policyholder_name") or ""
        policyholder_type = self._determine_policyholder_type(policyholder_name)

        vat_adjusted = False
        vat_deduction = 0.0
        final_payout = after_deductible

        # For companies, remove VAT from final payout
        if policyholder_type == "company" and after_deductible > 0:
            vat_adjusted = True
            vat_deduction = after_deductible - (after_deductible / (1 + SWISS_VAT_RATE))
            final_payout = after_deductible - vat_deduction

        # Round all amounts
        return ScreeningPayoutCalculation(
            covered_total=round(covered_total, 2),
            not_covered_total=round(not_covered_total, 2),
            coverage_percent=coverage_percent,
            max_coverage=max_coverage,
            max_coverage_applied=max_coverage_applied,
            capped_amount=round(capped_amount, 2),
            vat_amount=round(vat_amount, 2),
            subtotal_with_vat=round(subtotal_with_vat, 2),
            deductible_percent=deductible_percent,
            deductible_minimum=deductible_minimum,
            deductible_amount=round(deductible_amount, 2),
            after_deductible=round(after_deductible, 2),
            policyholder_type=policyholder_type,
            vat_adjusted=vat_adjusted,
            vat_deduction=round(vat_deduction, 2),
            final_payout=round(final_payout, 2),
        )

    def _determine_policyholder_type(self, name: str) -> str:
        """Determine if policyholder is a company or individual.

        Returns 'company' if name contains any company indicator, else 'individual'.
        """
        if not name:
            return "individual"
        # Check for company indicators (case-insensitive word boundary)
        name_upper = name.upper()
        for indicator in COMPANY_INDICATORS:
            # Check with word boundary-like logic: indicator at start/end or surrounded by non-alnum
            if indicator.upper() in name_upper:
                return "company"
        return "individual"
