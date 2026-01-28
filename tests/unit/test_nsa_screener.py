"""Unit tests for the NSA screener check logic.

These tests reimplement the check logic locally (same pattern as test_nsa_enricher.py)
to avoid importing from the gitignored workspace file.

Each test class covers one screening check, testing PASS/FAIL/SKIPPED/INCONCLUSIVE
verdicts, hard-fail flags, and evidence.
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pytest

from context_builder.schemas.screening import (
    CheckVerdict,
    ScreeningCheck,
    ScreeningPayoutCalculation,
    ScreeningResult,
)


# ── Reimplemented helpers (matching workspace screener) ───────────────


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


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Parse ISO and European date strings."""
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
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.replace("'", "").replace(",", "").replace("\u2019", "").strip()
    match = re.search(r"([\d]+(?:\.[\d]+)?)", cleaned)
    if match:
        return float(match.group(1))
    return None


COMPANY_INDICATORS = {
    "AG", "SA", "GmbH", "Sàrl", "Ltd", "Inc", "S.A.", "Corp", "KG", "Co.",
    "Sagl", "LLC", "SARL", "Srl",
}

ASSISTANCE_KEYWORDS = [
    "ERSATZFAHRZEUG", "MIETWAGEN", "RENTAL", "LEIHWAGEN",
    "ABSCHLEPP", "TOWING", "PANNENHILFE", "REMORQUAGE",
]

SWISS_VAT_RATE = 0.081


# ── Reimplemented check functions ─────────────────────────────────────


def check_1_policy_validity(facts: List[Dict]) -> ScreeningCheck:
    """Check 1: Policy validity."""
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
            check_id="1", check_name="policy_validity",
            verdict=CheckVerdict.SKIPPED, reason="Missing date data",
            evidence=evidence, is_hard_fail=True,
        )
    if policy_start <= claim_date <= policy_end:
        return ScreeningCheck(
            check_id="1", check_name="policy_validity",
            verdict=CheckVerdict.PASS, reason="Within policy period",
            evidence=evidence, is_hard_fail=True,
        )
    return ScreeningCheck(
        check_id="1", check_name="policy_validity",
        verdict=CheckVerdict.FAIL, reason="Outside policy period",
        evidence=evidence, is_hard_fail=True,
    )


def check_1b_damage_date(facts: List[Dict]) -> ScreeningCheck:
    """Check 1b: Damage date."""
    policy_start = _parse_date(_get_fact(facts, "start_date"))
    policy_end = _parse_date(_get_fact(facts, "end_date"))
    damage_date = _parse_date(_get_fact(facts, "damage_date"))

    evidence = {
        "policy_start": str(policy_start) if policy_start else None,
        "policy_end": str(policy_end) if policy_end else None,
        "damage_date": str(damage_date) if damage_date else None,
    }

    if not damage_date or not policy_start or not policy_end:
        return ScreeningCheck(
            check_id="1b", check_name="damage_date",
            verdict=CheckVerdict.SKIPPED, reason="Missing date data",
            evidence=evidence, is_hard_fail=True,
        )
    if policy_start <= damage_date <= policy_end:
        return ScreeningCheck(
            check_id="1b", check_name="damage_date",
            verdict=CheckVerdict.PASS, reason="Within policy period",
            evidence=evidence, is_hard_fail=True,
        )
    return ScreeningCheck(
        check_id="1b", check_name="damage_date",
        verdict=CheckVerdict.FAIL, reason="Outside policy period",
        evidence=evidence, is_hard_fail=True,
    )


def check_2_vin_consistency(conflicts: List[Dict]) -> ScreeningCheck:
    """Check 2: VIN consistency."""
    vin_conflicts = [
        c for c in conflicts
        if any(kw in c.get("fact_name", "").lower()
               for kw in ("vin", "chassis", "fahrgestell"))
    ]
    if not vin_conflicts:
        return ScreeningCheck(
            check_id="2", check_name="vin_consistency",
            verdict=CheckVerdict.PASS, reason="No VIN conflicts",
            is_hard_fail=False,
        )
    return ScreeningCheck(
        check_id="2", check_name="vin_consistency",
        verdict=CheckVerdict.FAIL,
        reason=f"{len(vin_conflicts)} VIN conflict(s)",
        is_hard_fail=False, requires_llm=True,
    )


def check_2b_owner_match(facts: List[Dict]) -> ScreeningCheck:
    """Check 2b: Owner match."""
    policyholder = _get_fact(facts, "policyholder_name")
    owner = _get_fact(facts, "owner_name")

    if not policyholder or not owner:
        return ScreeningCheck(
            check_id="2b", check_name="owner_match",
            verdict=CheckVerdict.SKIPPED, reason="Missing names",
            is_hard_fail=False,
        )
    ph_norm = policyholder.strip().lower()
    ow_norm = owner.strip().lower()

    if ph_norm == ow_norm:
        return ScreeningCheck(
            check_id="2b", check_name="owner_match",
            verdict=CheckVerdict.PASS, reason="Exact match",
            is_hard_fail=False,
        )
    if ph_norm in ow_norm or ow_norm in ph_norm:
        return ScreeningCheck(
            check_id="2b", check_name="owner_match",
            verdict=CheckVerdict.PASS, reason="Substring match",
            is_hard_fail=False,
        )
    return ScreeningCheck(
        check_id="2b", check_name="owner_match",
        verdict=CheckVerdict.INCONCLUSIVE, reason="No match",
        is_hard_fail=False, requires_llm=True,
    )


def check_3_mileage(facts: List[Dict]) -> ScreeningCheck:
    """Check 3: Mileage."""
    km_limit = _parse_int(_get_fact(facts, "km_limited_to"))
    odometer = _parse_int(
        _get_fact(facts, "odometer_km") or _get_fact(facts, "vehicle_current_km")
    )
    if km_limit is None or odometer is None:
        return ScreeningCheck(
            check_id="3", check_name="mileage",
            verdict=CheckVerdict.SKIPPED, reason="Missing mileage data",
            is_hard_fail=True,
        )
    if odometer <= km_limit:
        return ScreeningCheck(
            check_id="3", check_name="mileage",
            verdict=CheckVerdict.PASS, reason="Within limit",
            is_hard_fail=True,
        )
    return ScreeningCheck(
        check_id="3", check_name="mileage",
        verdict=CheckVerdict.FAIL, reason="Exceeds limit",
        is_hard_fail=True,
    )


def check_4a_shop_auth(shop_auth: Dict) -> ScreeningCheck:
    """Check 4a: Shop authorization."""
    if not shop_auth:
        return ScreeningCheck(
            check_id="4a", check_name="shop_authorization",
            verdict=CheckVerdict.SKIPPED, reason="No shop auth data",
            is_hard_fail=False,
        )
    authorized = shop_auth.get("authorized")
    if authorized is True:
        return ScreeningCheck(
            check_id="4a", check_name="shop_authorization",
            verdict=CheckVerdict.PASS, reason="Authorized",
            is_hard_fail=False,
        )
    if authorized is False:
        return ScreeningCheck(
            check_id="4a", check_name="shop_authorization",
            verdict=CheckVerdict.FAIL, reason="Not authorized",
            is_hard_fail=False, requires_llm=True,
        )
    return ScreeningCheck(
        check_id="4a", check_name="shop_authorization",
        verdict=CheckVerdict.INCONCLUSIVE, reason="Unknown",
        is_hard_fail=False, requires_llm=True,
    )


def check_4b_service_compliance(
    facts: List[Dict], service_entries: List[Dict]
) -> ScreeningCheck:
    """Check 4b: Service compliance."""
    claim_date = _parse_date(_get_fact(facts, "document_date"))
    if not service_entries:
        return ScreeningCheck(
            check_id="4b", check_name="service_compliance",
            verdict=CheckVerdict.SKIPPED, reason="No service data",
            is_hard_fail=False,
        )
    if not claim_date:
        return ScreeningCheck(
            check_id="4b", check_name="service_compliance",
            verdict=CheckVerdict.SKIPPED, reason="No claim date",
            is_hard_fail=False,
        )
    most_recent = None
    for entry in service_entries:
        svc_date = _parse_date(entry.get("service_date"))
        if svc_date and (most_recent is None or svc_date > most_recent):
            most_recent = svc_date
    if most_recent is None:
        return ScreeningCheck(
            check_id="4b", check_name="service_compliance",
            verdict=CheckVerdict.SKIPPED, reason="Unparseable service dates",
            is_hard_fail=False,
        )
    days_gap = (claim_date - most_recent).days
    if days_gap <= 365:
        return ScreeningCheck(
            check_id="4b", check_name="service_compliance",
            verdict=CheckVerdict.PASS,
            reason=f"Service {days_gap} days ago",
            is_hard_fail=False,
        )
    return ScreeningCheck(
        check_id="4b", check_name="service_compliance",
        verdict=CheckVerdict.FAIL,
        reason=f"Service gap {days_gap} days",
        is_hard_fail=False, requires_llm=True,
    )


def check_5b_assistance(line_items: List[Dict]) -> ScreeningCheck:
    """Check 5b: Assistance items."""
    if not line_items:
        return ScreeningCheck(
            check_id="5b", check_name="assistance_items",
            verdict=CheckVerdict.SKIPPED, reason="No line items",
            is_hard_fail=False,
        )
    found = []
    for item in line_items:
        desc = (item.get("description") or "").upper()
        for kw in ASSISTANCE_KEYWORDS:
            if kw in desc:
                found.append(item)
                break
    if not found:
        return ScreeningCheck(
            check_id="5b", check_name="assistance_items",
            verdict=CheckVerdict.PASS, reason="None found",
            is_hard_fail=False,
        )
    return ScreeningCheck(
        check_id="5b", check_name="assistance_items",
        verdict=CheckVerdict.INCONCLUSIVE,
        reason=f"Found {len(found)} assistance item(s)",
        is_hard_fail=False, requires_llm=True,
    )


def determine_policyholder_type(name: str) -> str:
    """Determine policyholder type: 'company' or 'individual'."""
    if not name:
        return "individual"
    name_upper = name.upper()
    for indicator in COMPANY_INDICATORS:
        if indicator.upper() in name_upper:
            return "company"
    return "individual"


def calculate_payout(
    covered_total: float,
    not_covered_total: float,
    coverage_percent: Optional[float],
    max_coverage: Optional[float],
    deductible_percent: Optional[float],
    deductible_minimum: Optional[float],
    policyholder_type: str,
) -> ScreeningPayoutCalculation:
    """Calculate payout following NSA formula."""
    max_coverage_applied = False
    capped_amount = covered_total
    if max_coverage is not None and covered_total > max_coverage:
        capped_amount = max_coverage
        max_coverage_applied = True

    deductible_amount = 0.0
    if deductible_percent is not None:
        deductible_amount = capped_amount * deductible_percent / 100.0
    if deductible_minimum is not None:
        deductible_amount = max(deductible_amount, deductible_minimum)

    after_deductible = max(0.0, capped_amount - deductible_amount)

    vat_adjusted = False
    vat_deduction = 0.0
    final_payout = after_deductible

    if policyholder_type == "company" and after_deductible > 0:
        vat_adjusted = True
        vat_deduction = after_deductible - (after_deductible / (1 + SWISS_VAT_RATE))
        final_payout = after_deductible - vat_deduction

    return ScreeningPayoutCalculation(
        covered_total=round(covered_total, 2),
        not_covered_total=round(not_covered_total, 2),
        coverage_percent=coverage_percent,
        max_coverage=max_coverage,
        max_coverage_applied=max_coverage_applied,
        capped_amount=round(capped_amount, 2),
        deductible_percent=deductible_percent,
        deductible_minimum=deductible_minimum,
        deductible_amount=round(deductible_amount, 2),
        after_deductible=round(after_deductible, 2),
        policyholder_type=policyholder_type,
        vat_adjusted=vat_adjusted,
        vat_deduction=round(vat_deduction, 2),
        final_payout=round(final_payout, 2),
    )


# ── Test classes ──────────────────────────────────────────────────────


class TestCheck1PolicyValidity:
    """Tests for Check 1: Policy validity."""

    def test_pass_within_period(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "document_date", "value": "15.06.2025"},
        ]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.PASS
        assert result.is_hard_fail is True

    def test_pass_on_start_date(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "document_date", "value": "01.01.2025"},
        ]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_pass_on_end_date(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "document_date", "value": "31.12.2025"},
        ]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_fail_before_start(self):
        facts = [
            {"name": "start_date", "value": "01.06.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "document_date", "value": "15.05.2025"},
        ]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.FAIL
        assert result.is_hard_fail is True

    def test_fail_after_end(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "document_date", "value": "01.01.2026"},
        ]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.FAIL

    def test_skipped_missing_claim_date(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
        ]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.SKIPPED

    def test_skipped_missing_policy_dates(self):
        facts = [{"name": "document_date", "value": "15.06.2025"}]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.SKIPPED

    def test_iso_date_format(self):
        facts = [
            {"name": "start_date", "value": "2025-01-01"},
            {"name": "end_date", "value": "2025-12-31"},
            {"name": "document_date", "value": "2025-06-15"},
        ]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_prefixed_document_date(self):
        """Should find document_date even when prefixed with doc type."""
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "cost_estimate.document_date", "value": "15.06.2025"},
        ]
        result = check_1_policy_validity(facts)
        assert result.verdict == CheckVerdict.PASS


class TestCheck1bDamageDate:
    """Tests for Check 1b: Damage date."""

    def test_pass_within_period(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "damage_date", "value": "15.06.2025"},
        ]
        result = check_1b_damage_date(facts)
        assert result.verdict == CheckVerdict.PASS
        assert result.is_hard_fail is True

    def test_fail_outside_period(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "damage_date", "value": "15.06.2024"},
        ]
        result = check_1b_damage_date(facts)
        assert result.verdict == CheckVerdict.FAIL
        assert result.is_hard_fail is True

    def test_skipped_no_damage_date(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
        ]
        result = check_1b_damage_date(facts)
        assert result.verdict == CheckVerdict.SKIPPED

    def test_skipped_no_policy_dates(self):
        facts = [{"name": "damage_date", "value": "15.06.2025"}]
        result = check_1b_damage_date(facts)
        assert result.verdict == CheckVerdict.SKIPPED

    def test_on_boundary_passes(self):
        facts = [
            {"name": "start_date", "value": "01.01.2025"},
            {"name": "end_date", "value": "31.12.2025"},
            {"name": "damage_date", "value": "31.12.2025"},
        ]
        result = check_1b_damage_date(facts)
        assert result.verdict == CheckVerdict.PASS


class TestCheck2VinConsistency:
    """Tests for Check 2: VIN consistency."""

    def test_pass_no_conflicts(self):
        result = check_2_vin_consistency([])
        assert result.verdict == CheckVerdict.PASS
        assert result.is_hard_fail is False

    def test_pass_non_vin_conflicts(self):
        conflicts = [{"fact_name": "policyholder_name", "values": ["A", "B"]}]
        result = check_2_vin_consistency(conflicts)
        assert result.verdict == CheckVerdict.PASS

    def test_fail_vin_conflict(self):
        conflicts = [
            {"fact_name": "vin_number", "values": ["WBA123", "WBA456"]},
        ]
        result = check_2_vin_consistency(conflicts)
        assert result.verdict == CheckVerdict.FAIL
        assert result.requires_llm is True

    def test_fail_chassis_conflict(self):
        conflicts = [
            {"fact_name": "chassis_number", "values": ["ABC", "DEF"]},
        ]
        result = check_2_vin_consistency(conflicts)
        assert result.verdict == CheckVerdict.FAIL

    def test_fail_fahrgestell_conflict(self):
        conflicts = [
            {"fact_name": "fahrgestell_nr", "values": ["X", "Y"]},
        ]
        result = check_2_vin_consistency(conflicts)
        assert result.verdict == CheckVerdict.FAIL


class TestCheck2bOwnerMatch:
    """Tests for Check 2b: Owner match."""

    def test_pass_exact_match(self):
        facts = [
            {"name": "policyholder_name", "value": "Hans Müller"},
            {"name": "owner_name", "value": "Hans Müller"},
        ]
        result = check_2b_owner_match(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_pass_case_insensitive(self):
        facts = [
            {"name": "policyholder_name", "value": "HANS MÜLLER"},
            {"name": "owner_name", "value": "Hans Müller"},
        ]
        result = check_2b_owner_match(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_pass_substring(self):
        facts = [
            {"name": "policyholder_name", "value": "Hans"},
            {"name": "owner_name", "value": "Hans Müller"},
        ]
        result = check_2b_owner_match(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_pass_reverse_substring(self):
        facts = [
            {"name": "policyholder_name", "value": "Hans Müller AG"},
            {"name": "owner_name", "value": "Müller"},
        ]
        result = check_2b_owner_match(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_inconclusive_no_match(self):
        facts = [
            {"name": "policyholder_name", "value": "Hans Müller"},
            {"name": "owner_name", "value": "Peter Schmidt"},
        ]
        result = check_2b_owner_match(facts)
        assert result.verdict == CheckVerdict.INCONCLUSIVE
        assert result.requires_llm is True

    def test_skipped_missing_names(self):
        facts = [{"name": "policyholder_name", "value": "Hans"}]
        result = check_2b_owner_match(facts)
        assert result.verdict == CheckVerdict.SKIPPED


class TestCheck3Mileage:
    """Tests for Check 3: Mileage."""

    def test_pass_under_limit(self):
        facts = [
            {"name": "km_limited_to", "value": "150000"},
            {"name": "odometer_km", "value": "100000"},
        ]
        result = check_3_mileage(facts)
        assert result.verdict == CheckVerdict.PASS
        assert result.is_hard_fail is True

    def test_pass_at_limit(self):
        facts = [
            {"name": "km_limited_to", "value": "150000"},
            {"name": "odometer_km", "value": "150000"},
        ]
        result = check_3_mileage(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_fail_over_limit(self):
        facts = [
            {"name": "km_limited_to", "value": "150000"},
            {"name": "odometer_km", "value": "160000"},
        ]
        result = check_3_mileage(facts)
        assert result.verdict == CheckVerdict.FAIL
        assert result.is_hard_fail is True

    def test_skipped_no_limit(self):
        facts = [{"name": "odometer_km", "value": "100000"}]
        result = check_3_mileage(facts)
        assert result.verdict == CheckVerdict.SKIPPED

    def test_skipped_no_odometer(self):
        facts = [{"name": "km_limited_to", "value": "150000"}]
        result = check_3_mileage(facts)
        assert result.verdict == CheckVerdict.SKIPPED

    def test_swiss_number_format(self):
        facts = [
            {"name": "km_limited_to", "value": "150'000"},
            {"name": "odometer_km", "value": "74'359"},
        ]
        result = check_3_mileage(facts)
        assert result.verdict == CheckVerdict.PASS

    def test_fallback_to_vehicle_current_km(self):
        facts = [
            {"name": "km_limited_to", "value": "150000"},
            {"name": "vehicle_current_km", "value": "100000"},
        ]
        result = check_3_mileage(facts)
        assert result.verdict == CheckVerdict.PASS


class TestCheck4aShopAuth:
    """Tests for Check 4a: Shop authorization."""

    def test_pass_authorized(self):
        result = check_4a_shop_auth({"authorized": True, "lookup_method": "exact_name"})
        assert result.verdict == CheckVerdict.PASS

    def test_fail_not_authorized(self):
        result = check_4a_shop_auth({"authorized": False})
        assert result.verdict == CheckVerdict.FAIL
        assert result.requires_llm is True

    def test_inconclusive_unknown(self):
        result = check_4a_shop_auth({"authorized": None})
        assert result.verdict == CheckVerdict.INCONCLUSIVE

    def test_skipped_no_data(self):
        result = check_4a_shop_auth({})
        assert result.verdict == CheckVerdict.SKIPPED


class TestCheck4bServiceCompliance:
    """Tests for Check 4b: Service compliance."""

    def test_pass_recent_service(self):
        facts = [{"name": "document_date", "value": "15.06.2025"}]
        entries = [{"service_date": "2025-01-15"}]
        result = check_4b_service_compliance(facts, entries)
        assert result.verdict == CheckVerdict.PASS

    def test_fail_service_gap(self):
        facts = [{"name": "document_date", "value": "15.06.2025"}]
        entries = [{"service_date": "2023-01-01"}]
        result = check_4b_service_compliance(facts, entries)
        assert result.verdict == CheckVerdict.FAIL
        assert result.requires_llm is True

    def test_skipped_no_entries(self):
        facts = [{"name": "document_date", "value": "15.06.2025"}]
        result = check_4b_service_compliance(facts, [])
        assert result.verdict == CheckVerdict.SKIPPED

    def test_skipped_no_claim_date(self):
        facts = []
        entries = [{"service_date": "2025-01-15"}]
        result = check_4b_service_compliance(facts, entries)
        assert result.verdict == CheckVerdict.SKIPPED


class TestCheck5bAssistance:
    """Tests for Check 5b: Assistance items."""

    def test_pass_no_assistance(self):
        items = [{"description": "Ölfilter", "total_price": 50}]
        result = check_5b_assistance(items)
        assert result.verdict == CheckVerdict.PASS

    def test_inconclusive_rental(self):
        items = [{"description": "Mietwagen 3 Tage", "total_price": 300}]
        result = check_5b_assistance(items)
        assert result.verdict == CheckVerdict.INCONCLUSIVE
        assert result.requires_llm is True

    def test_inconclusive_towing(self):
        items = [{"description": "Abschleppkosten", "total_price": 200}]
        result = check_5b_assistance(items)
        assert result.verdict == CheckVerdict.INCONCLUSIVE

    def test_skipped_no_items(self):
        result = check_5b_assistance([])
        assert result.verdict == CheckVerdict.SKIPPED

    def test_case_insensitive(self):
        items = [{"description": "ersatzfahrzeug Klein", "total_price": 150}]
        result = check_5b_assistance(items)
        assert result.verdict == CheckVerdict.INCONCLUSIVE


class TestPayoutCalculation:
    """Tests for payout calculation."""

    def test_basic_payout(self):
        payout = calculate_payout(
            covered_total=5000,
            not_covered_total=500,
            coverage_percent=None,
            max_coverage=None,
            deductible_percent=10,
            deductible_minimum=200,
            policyholder_type="individual",
        )
        assert payout.covered_total == 5000
        assert payout.capped_amount == 5000
        assert payout.deductible_amount == 500  # 5000 * 10% = 500 > 200 min
        assert payout.after_deductible == 4500
        assert payout.vat_adjusted is False
        assert payout.final_payout == 4500

    def test_max_coverage_cap(self):
        payout = calculate_payout(
            covered_total=15000,
            not_covered_total=0,
            coverage_percent=None,
            max_coverage=10000,
            deductible_percent=None,
            deductible_minimum=None,
            policyholder_type="individual",
        )
        assert payout.max_coverage_applied is True
        assert payout.capped_amount == 10000
        assert payout.final_payout == 10000

    def test_no_cap_when_under(self):
        payout = calculate_payout(
            covered_total=5000,
            not_covered_total=0,
            coverage_percent=None,
            max_coverage=10000,
            deductible_percent=None,
            deductible_minimum=None,
            policyholder_type="individual",
        )
        assert payout.max_coverage_applied is False
        assert payout.capped_amount == 5000

    def test_deductible_minimum_applied(self):
        payout = calculate_payout(
            covered_total=1000,
            not_covered_total=0,
            coverage_percent=None,
            max_coverage=None,
            deductible_percent=5,  # 5% of 1000 = 50, but min is 200
            deductible_minimum=200,
            policyholder_type="individual",
        )
        assert payout.deductible_amount == 200
        assert payout.after_deductible == 800

    def test_company_vat_deduction(self):
        payout = calculate_payout(
            covered_total=4000,
            not_covered_total=0,
            coverage_percent=None,
            max_coverage=None,
            deductible_percent=None,
            deductible_minimum=None,
            policyholder_type="company",
        )
        assert payout.vat_adjusted is True
        assert payout.vat_deduction > 0
        # After deductible = 4000
        # VAT deduction = 4000 - 4000/1.081
        expected_vat = 4000 - (4000 / 1.081)
        assert abs(payout.vat_deduction - round(expected_vat, 2)) < 0.01
        assert payout.final_payout == round(4000 - payout.vat_deduction, 2)

    def test_individual_no_vat(self):
        payout = calculate_payout(
            covered_total=4000,
            not_covered_total=0,
            coverage_percent=None,
            max_coverage=None,
            deductible_percent=None,
            deductible_minimum=None,
            policyholder_type="individual",
        )
        assert payout.vat_adjusted is False
        assert payout.vat_deduction == 0
        assert payout.final_payout == 4000

    def test_zero_covered(self):
        payout = calculate_payout(
            covered_total=0,
            not_covered_total=5000,
            coverage_percent=None,
            max_coverage=None,
            deductible_percent=10,
            deductible_minimum=200,
            policyholder_type="individual",
        )
        assert payout.final_payout == 0

    def test_combined_cap_deductible_vat(self):
        """Full pipeline: cap → deductible → VAT."""
        payout = calculate_payout(
            covered_total=20000,
            not_covered_total=1000,
            coverage_percent=60.0,
            max_coverage=15000,
            deductible_percent=10,
            deductible_minimum=500,
            policyholder_type="company",
        )
        assert payout.max_coverage_applied is True
        assert payout.capped_amount == 15000
        assert payout.deductible_amount == 1500  # 15000 * 10% = 1500 > 500 min
        assert payout.after_deductible == 13500
        assert payout.vat_adjusted is True
        assert payout.final_payout > 0
        assert payout.final_payout < 13500  # VAT reduced it


class TestAutoReject:
    """Tests for auto-reject based on hard fails."""

    def test_hard_fail_triggers_auto_reject(self):
        result = ScreeningResult(
            claim_id="CLM-001",
            screening_timestamp="2026-01-28T10:00:00Z",
            checks=[
                ScreeningCheck(
                    check_id="1", check_name="policy_validity",
                    verdict=CheckVerdict.FAIL, reason="Outside",
                    is_hard_fail=True,
                ),
                ScreeningCheck(
                    check_id="2", check_name="vin_consistency",
                    verdict=CheckVerdict.PASS, reason="OK",
                    is_hard_fail=False,
                ),
            ],
        )
        result.recompute_counts()
        assert result.auto_reject is True
        assert "1" in result.hard_fails

    def test_non_hard_fail_does_not_reject(self):
        result = ScreeningResult(
            claim_id="CLM-001",
            screening_timestamp="2026-01-28T10:00:00Z",
            checks=[
                ScreeningCheck(
                    check_id="2", check_name="vin_consistency",
                    verdict=CheckVerdict.FAIL, reason="Conflict",
                    is_hard_fail=False,
                ),
            ],
        )
        result.recompute_counts()
        assert result.auto_reject is False
        assert result.hard_fails == []

    def test_multiple_hard_fails(self):
        result = ScreeningResult(
            claim_id="CLM-001",
            screening_timestamp="2026-01-28T10:00:00Z",
            checks=[
                ScreeningCheck(
                    check_id="1", check_name="policy_validity",
                    verdict=CheckVerdict.FAIL, reason="Outside",
                    is_hard_fail=True,
                ),
                ScreeningCheck(
                    check_id="3", check_name="mileage",
                    verdict=CheckVerdict.FAIL, reason="Over",
                    is_hard_fail=True,
                ),
            ],
        )
        result.recompute_counts()
        assert result.auto_reject is True
        assert sorted(result.hard_fails) == ["1", "3"]

    def test_all_pass_no_reject(self):
        result = ScreeningResult(
            claim_id="CLM-001",
            screening_timestamp="2026-01-28T10:00:00Z",
            checks=[
                ScreeningCheck(
                    check_id="1", check_name="policy_validity",
                    verdict=CheckVerdict.PASS, reason="OK",
                    is_hard_fail=True,
                ),
                ScreeningCheck(
                    check_id="3", check_name="mileage",
                    verdict=CheckVerdict.PASS, reason="OK",
                    is_hard_fail=True,
                ),
            ],
        )
        result.recompute_counts()
        assert result.auto_reject is False

    def test_skipped_hard_fail_does_not_reject(self):
        """SKIPPED on a hard-fail check should NOT trigger auto-reject."""
        result = ScreeningResult(
            claim_id="CLM-001",
            screening_timestamp="2026-01-28T10:00:00Z",
            checks=[
                ScreeningCheck(
                    check_id="1", check_name="policy_validity",
                    verdict=CheckVerdict.SKIPPED, reason="Missing data",
                    is_hard_fail=True,
                ),
            ],
        )
        result.recompute_counts()
        assert result.auto_reject is False


class TestPolicyholderType:
    """Tests for policyholder type detection."""

    def test_individual(self):
        assert determine_policyholder_type("Hans Müller") == "individual"

    def test_company_ag(self):
        assert determine_policyholder_type("ABC Motoren AG") == "company"

    def test_company_gmbh(self):
        assert determine_policyholder_type("Test GmbH") == "company"

    def test_company_sa(self):
        assert determine_policyholder_type("Société SA") == "company"

    def test_company_sarl(self):
        assert determine_policyholder_type("Test Sàrl") == "company"

    def test_empty_name(self):
        assert determine_policyholder_type("") == "individual"

    def test_company_ltd(self):
        assert determine_policyholder_type("Company Ltd") == "company"
