"""Unit tests for the NSA screener check logic.

These tests reimplement the check logic locally (same pattern as test_nsa_enricher.py)
to avoid importing from the gitignored workspace file.

Each test class covers one screening check, testing PASS/FAIL/SKIPPED/INCONCLUSIVE
verdicts, hard-fail flags, and evidence.
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pytest

from context_builder.schemas.screening import (
    CheckVerdict,
    ScreeningCheck,
    ScreeningPayoutCalculation,
    ScreeningResult,
)


# ── Reimplemented helpers (matching workspace screener) ───────────────


def _make_facts(*name_value_pairs):
    """Build a list of fact dicts from (name, value) pairs."""
    return [{"name": n, "value": v} for n, v in name_value_pairs]


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

# ── Brand normalization (mirrors screener.py) ────────────────────────

BRAND_NORMALIZATION: Dict[str, str] = {
    "volkswagen": "volkswagen",
    "vw": "volkswagen",
    "mercedes": "mercedes_benz",
    "mercedes-benz": "mercedes_benz",
    "cupra": "seat_cupra",
    "seat": "seat_cupra",
    "škoda": "skoda",
    "skoda": "skoda",
    "bmw": "bmw",
    "audi": "audi",
    "opel": "opel",
    "ford": "ford",
    "hyundai": "hyundai",
    "toyota": "toyota",
    "dacia": "dacia",
    "renault": "renault",
    "kia": "kia",
    "peugeot": "peugeot",
    "citroen": "citroen",
    "citroën": "citroen",
    "volvo": "volvo",
    "fiat": "fiat",
    "nissan": "nissan",
    "mazda": "mazda",
    "mini": "mini",
}

FUEL_TYPE_NORMALIZATION: Dict[str, str] = {
    "bleifrei": "petrol",
    "sans plomb": "petrol",
    "essence": "petrol",
    "benzin": "petrol",
    "super": "petrol",
    "petrol": "petrol",
    "diesel": "diesel",
    "electrique": "electric",
    "électrique": "electric",
    "elektrisch": "electric",
    "elektro": "electric",
    "electric": "electric",
    "hybride": "hybrid",
    "hybride essence": "hybrid",
    "hybrid": "hybrid",
}

_FALLBACK_INTERVAL = {"km_max": 30000, "months_max": 24, "system_type": "fallback"}


def _normalize_brand(make: Optional[str]) -> Optional[str]:
    """Normalize vehicle make to service_requirements key."""
    if not make:
        return None
    make_lower = make.strip().lower()
    if make_lower in BRAND_NORMALIZATION:
        return BRAND_NORMALIZATION[make_lower]
    for key, value in BRAND_NORMALIZATION.items():
        if key in make_lower:
            return value
    return None


def _normalize_fuel_type(fuel: Optional[str]) -> str:
    """Normalize fuel type to interval key."""
    if not fuel:
        return "petrol"
    fuel_lower = fuel.strip().lower()
    if fuel_lower in FUEL_TYPE_NORMALIZATION:
        return FUEL_TYPE_NORMALIZATION[fuel_lower]
    for key, value in FUEL_TYPE_NORMALIZATION.items():
        if key in fuel_lower:
            return value
    return "petrol"


def _resolve_service_interval(
    brand_data: Dict[str, Any], fuel_type: str
) -> Dict[str, Any]:
    """Navigate brand JSON to get {km_max, months_max, system_type}."""
    intervals = brand_data.get("intervals", {})
    system_type = brand_data.get("service_system", "fixed")

    if fuel_type == "electric" and "electric" in intervals:
        iv = intervals["electric"]
        return {
            "km_max": iv.get("km", iv.get("km_max", 30000)),
            "months_max": iv.get("months", iv.get("months_max", 24)),
            "system_type": "electric",
        }
    if fuel_type == "hybrid" and "hybrid" in intervals:
        iv = intervals["hybrid"]
        return {
            "km_max": iv.get("km", iv.get("km_max", 15000)),
            "months_max": iv.get("months", iv.get("months_max", 12)),
            "system_type": "hybrid",
        }
    if system_type == "dual" and "fixed" in intervals:
        iv = intervals["fixed"]
        return {
            "km_max": iv.get("km", 15000),
            "months_max": iv.get("months", 12),
            "system_type": "dual",
        }
    if "service_a" in intervals:
        iv = intervals["service_a"]
        return {
            "km_max": iv.get("km", 25000),
            "months_max": iv.get("months", 12),
            "system_type": "flexible",
        }
    if fuel_type == "petrol" and "ecoboost_petrol" in intervals:
        iv = intervals["ecoboost_petrol"]
        return {
            "km_max": iv.get("km_max", iv.get("km", 24000)),
            "months_max": iv.get("months", iv.get("months_max", 12)),
            "system_type": "flexible",
        }
    if fuel_type in intervals:
        iv = intervals[fuel_type]
        return {
            "km_max": iv.get("km", iv.get("km_max", 20000)),
            "months_max": iv.get("months", iv.get("months_max", 12)),
            "system_type": system_type,
        }
    if system_type == "flexible":
        max_km = 0
        max_months = 0
        for key, iv in intervals.items():
            if key == "electric":
                continue
            km = iv.get("km_max", iv.get("km", 0))
            months = iv.get("months_max", iv.get("months", 0))
            max_km = max(max_km, km)
            max_months = max(max_months, months)
        if max_km > 0 and max_months > 0:
            return {"km_max": max_km, "months_max": max_months, "system_type": "flexible"}
    for key, iv in intervals.items():
        if key == "electric":
            continue
        return {
            "km_max": iv.get("km", iv.get("km_max", 20000)),
            "months_max": iv.get("months", iv.get("months_max", 12)),
            "system_type": system_type,
        }
    return dict(_FALLBACK_INTERVAL)


# ── Reimplemented check functions ─────────────────────────────────────


def _normalize_policy_number(value: str) -> str:
    """Normalize a policy number: strip to digits, remove leading zeros."""
    digits = re.sub(r"[^0-9]", "", value)
    return digits.lstrip("0") or "0"


def check_0_policy_enforcement(
    facts: List[Dict], rejected_policies: set
) -> ScreeningCheck:
    """Check 0: Policy enforcement."""
    policy_number = _get_fact(facts, "policy_number")

    evidence = {"policy_number": policy_number}

    if not policy_number:
        return ScreeningCheck(
            check_id="0", check_name="policy_enforcement",
            verdict=CheckVerdict.SKIPPED, reason="No policy number available",
            evidence=evidence, is_hard_fail=True,
        )

    normalized = _normalize_policy_number(policy_number)
    evidence["normalized_policy_number"] = normalized

    if normalized in rejected_policies:
        return ScreeningCheck(
            check_id="0", check_name="policy_enforcement",
            verdict=CheckVerdict.FAIL,
            reason=f"Policy {policy_number} is not enforced",
            evidence=evidence, is_hard_fail=True,
        )

    return ScreeningCheck(
        check_id="0", check_name="policy_enforcement",
        verdict=CheckVerdict.PASS,
        reason=f"Policy {policy_number} is enforced",
        evidence=evidence, is_hard_fail=True,
    )


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
    facts: List[Dict],
    service_entries: List[Dict],
    brands: Optional[Dict[str, Any]] = None,
) -> ScreeningCheck:
    """Check 4b: Service compliance (manufacturer-aware).

    Uses brand + fuel type to resolve manufacturer interval.
    Tolerance: PASS <=1.0x, INCONCLUSIVE 1.0-1.5x, FAIL >1.5x.
    Unknown brand auto-downgrades PASS → INCONCLUSIVE.
    """
    claim_date = _parse_date(_get_fact(facts, "document_date"))
    vehicle_make = _get_fact(facts, "vehicle_make")
    vehicle_fuel_type = _get_fact(facts, "vehicle_fuel_type")

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

    # Parse and sort
    parsed: List[Tuple[date, Dict]] = []
    for entry in service_entries:
        svc_date = _parse_date(entry.get("service_date"))
        if svc_date:
            parsed.append((svc_date, entry))
    parsed.sort(key=lambda x: x[0])

    if not parsed:
        return ScreeningCheck(
            check_id="4b", check_name="service_compliance",
            verdict=CheckVerdict.SKIPPED, reason="Unparseable service dates",
            is_hard_fail=False,
        )

    # Find last service before claim
    last_before: Optional[Tuple[date, Dict]] = None
    for svc_date, entry in parsed:
        if svc_date <= claim_date:
            last_before = (svc_date, entry)
    if last_before is None:
        last_before = parsed[0]

    most_recent = last_before[0]
    most_recent_entry = last_before[1]

    # Resolve interval
    brand_key = _normalize_brand(vehicle_make)
    fuel_key = _normalize_fuel_type(vehicle_fuel_type)
    brand_known = brand_key is not None
    fallback_used = False

    if brands is None:
        brands = {}

    if brand_key and brand_key in brands:
        interval = _resolve_service_interval(brands[brand_key], fuel_key)
    else:
        interval = dict(_FALLBACK_INTERVAL)
        fallback_used = True

    months_max = interval["months_max"]
    km_max = interval["km_max"]

    # Time compliance
    days_gap = (claim_date - most_recent).days
    months_gap = round(days_gap / 30.44, 1)
    time_ratio = round(months_gap / months_max, 2) if months_max > 0 else 999.0

    if time_ratio <= 1.0:
        time_verdict = CheckVerdict.PASS
    elif time_ratio <= 1.5:
        time_verdict = CheckVerdict.INCONCLUSIVE
    else:
        time_verdict = CheckVerdict.FAIL

    # Mileage compliance
    mileage_verdict = None
    odometer = _parse_int(
        _get_fact(facts, "odometer_km") or _get_fact(facts, "vehicle_current_km")
    )
    service_km = _parse_int(most_recent_entry.get("mileage_km"))
    if odometer is not None and service_km is not None and km_max > 0:
        km_gap = odometer - service_km
        km_ratio = round(km_gap / km_max, 2) if km_max > 0 else 999.0
        if km_ratio <= 1.0:
            mileage_verdict = CheckVerdict.PASS
        elif km_ratio <= 1.5:
            mileage_verdict = CheckVerdict.INCONCLUSIVE
        else:
            mileage_verdict = CheckVerdict.FAIL

    # Combined verdict
    verdict_order = {CheckVerdict.PASS: 0, CheckVerdict.INCONCLUSIVE: 1, CheckVerdict.FAIL: 2}
    combined = time_verdict
    if mileage_verdict is not None:
        if verdict_order.get(mileage_verdict, 0) > verdict_order.get(combined, 0):
            combined = mileage_verdict

    # Unknown brand: PASS → INCONCLUSIVE
    if not brand_known and combined == CheckVerdict.PASS:
        combined = CheckVerdict.INCONCLUSIVE

    # Inter-service gap analysis
    chronic_non_maintenance = False
    if len(parsed) >= 2:
        excessive = 0
        for i in range(1, len(parsed)):
            gap_days = (parsed[i][0] - parsed[i - 1][0]).days
            gap_months = round(gap_days / 30.44, 1)
            gap_ratio = round(gap_months / months_max, 2) if months_max > 0 else 0
            if gap_ratio > 2.0:
                excessive += 1
        chronic_non_maintenance = excessive >= 2

    requires_llm = combined != CheckVerdict.PASS

    return ScreeningCheck(
        check_id="4b", check_name="service_compliance",
        verdict=combined, reason="service compliance",
        is_hard_fail=False, requires_llm=requires_llm,
        evidence={
            "brand_known": brand_known,
            "fallback_interval_used": fallback_used,
            "chronic_non_maintenance": chronic_non_maintenance,
        },
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


class TestNormalizePolicyNumber:
    """Tests for policy number normalization."""

    def test_plain_digits(self):
        assert _normalize_policy_number("619533") == "619533"

    def test_leading_zeros_stripped(self):
        assert _normalize_policy_number("00619533") == "619533"

    def test_dashes_stripped(self):
        assert _normalize_policy_number("619-533") == "619533"

    def test_dots_stripped(self):
        assert _normalize_policy_number("619.533") == "619533"

    def test_spaces_stripped(self):
        assert _normalize_policy_number("619 533") == "619533"

    def test_whitespace_trimmed(self):
        assert _normalize_policy_number("  619533  ") == "619533"

    def test_mixed_separators(self):
        assert _normalize_policy_number("0-619.533 ") == "619533"

    def test_all_zeros(self):
        assert _normalize_policy_number("000") == "0"

    def test_single_zero(self):
        assert _normalize_policy_number("0") == "0"

    def test_letters_stripped(self):
        assert _normalize_policy_number("POL-619533") == "619533"


class TestCheck0PolicyEnforcement:
    """Tests for Check 0: Policy enforcement status."""

    REJECTED = {"619533", "615796"}

    def test_pass_valid_policy(self):
        facts = [{"name": "policy_number", "value": "700001"}]
        result = check_0_policy_enforcement(facts, self.REJECTED)
        assert result.verdict == CheckVerdict.PASS
        assert result.is_hard_fail is True
        assert result.check_id == "0"

    def test_fail_rejected_619533(self):
        facts = [{"name": "policy_number", "value": "619533"}]
        result = check_0_policy_enforcement(facts, self.REJECTED)
        assert result.verdict == CheckVerdict.FAIL
        assert result.is_hard_fail is True

    def test_fail_rejected_615796(self):
        facts = [{"name": "policy_number", "value": "615796"}]
        result = check_0_policy_enforcement(facts, self.REJECTED)
        assert result.verdict == CheckVerdict.FAIL
        assert result.is_hard_fail is True

    def test_skipped_no_policy_number(self):
        facts = []
        result = check_0_policy_enforcement(facts, self.REJECTED)
        assert result.verdict == CheckVerdict.SKIPPED
        assert result.is_hard_fail is True

    def test_normalization_with_leading_zeros(self):
        facts = [{"name": "policy_number", "value": "00619533"}]
        result = check_0_policy_enforcement(facts, self.REJECTED)
        assert result.verdict == CheckVerdict.FAIL

    def test_normalization_with_dashes(self):
        facts = [{"name": "policy_number", "value": "619-533"}]
        result = check_0_policy_enforcement(facts, self.REJECTED)
        assert result.verdict == CheckVerdict.FAIL

    def test_normalization_with_spaces(self):
        facts = [{"name": "policy_number", "value": "619 533"}]
        result = check_0_policy_enforcement(facts, self.REJECTED)
        assert result.verdict == CheckVerdict.FAIL

    def test_hard_fail_triggers_auto_reject(self):
        """Check 0 FAIL should trigger auto-reject in ScreeningResult."""
        facts = [{"name": "policy_number", "value": "619533"}]
        check = check_0_policy_enforcement(facts, self.REJECTED)
        assert check.verdict == CheckVerdict.FAIL

        result = ScreeningResult(
            claim_id="CLM-TEST",
            screening_timestamp="2026-02-03T10:00:00Z",
            checks=[check],
        )
        result.recompute_counts()
        assert result.auto_reject is True
        assert "0" in result.hard_fails


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


class TestBrandNormalization:
    """Tests for _normalize_brand helper."""

    def test_exact_volkswagen(self):
        assert _normalize_brand("Volkswagen") == "volkswagen"

    def test_vw_abbreviation(self):
        assert _normalize_brand("VW") == "volkswagen"

    def test_mercedes_benz(self):
        assert _normalize_brand("Mercedes-Benz") == "mercedes_benz"

    def test_mercedes_short(self):
        assert _normalize_brand("Mercedes") == "mercedes_benz"

    def test_skoda_with_diacritic(self):
        assert _normalize_brand("Škoda") == "skoda"

    def test_substring_fallback(self):
        assert _normalize_brand("Volkswagen AG") == "volkswagen"

    def test_unknown_brand(self):
        assert _normalize_brand("Lamborghini") is None

    def test_none_input(self):
        assert _normalize_brand(None) is None

    def test_empty_string(self):
        assert _normalize_brand("") is None

    def test_cupra(self):
        assert _normalize_brand("CUPRA") == "seat_cupra"

    def test_seat(self):
        assert _normalize_brand("Seat") == "seat_cupra"


class TestFuelTypeNormalization:
    """Tests for _normalize_fuel_type helper."""

    def test_diesel(self):
        assert _normalize_fuel_type("Diesel") == "diesel"

    def test_bleifrei(self):
        assert _normalize_fuel_type("Bleifrei") == "petrol"

    def test_sans_plomb(self):
        assert _normalize_fuel_type("Sans Plomb") == "petrol"

    def test_electrique(self):
        assert _normalize_fuel_type("Électrique") == "electric"

    def test_hybride(self):
        assert _normalize_fuel_type("Hybride") == "hybrid"

    def test_none_defaults_petrol(self):
        assert _normalize_fuel_type(None) == "petrol"

    def test_unknown_defaults_petrol(self):
        assert _normalize_fuel_type("LPG") == "petrol"

    def test_substring_match(self):
        assert _normalize_fuel_type("Super Bleifrei 98") == "petrol"


class TestResolveServiceInterval:
    """Tests for _resolve_service_interval helper."""

    VW_BRAND = {
        "service_system": "dual",
        "intervals": {
            "fixed": {"km": 15000, "months": 12},
            "longlife_petrol": {"km_min": 15000, "km_max": 30000, "months_max": 24},
            "electric": {"km": 30000, "months": 24},
        },
    }

    MERCEDES_BRAND = {
        "service_system": "flexible",
        "intervals": {
            "service_a": {"km": 25000, "months": 12},
            "service_b": {"km": 25000, "months": 12},
            "electric": {"km": 25000, "months": 24},
        },
    }

    FORD_BRAND = {
        "service_system": "flexible",
        "intervals": {
            "ecoboost_petrol": {"km_min": 10000, "km_max": 24000, "months": 12},
            "diesel": {"km": 20000, "months": 12},
            "electric": {"km": 30000, "months": 24},
        },
    }

    TOYOTA_BRAND = {
        "service_system": "fixed",
        "intervals": {
            "petrol": {"km": 15000, "months": 12},
            "diesel": {"km": 15000, "months": 12},
            "hybrid": {"km": 15000, "months": 12},
        },
    }

    def test_vw_dual_uses_fixed(self):
        result = _resolve_service_interval(self.VW_BRAND, "petrol")
        assert result["km_max"] == 15000
        assert result["months_max"] == 12
        assert result["system_type"] == "dual"

    def test_vw_electric(self):
        result = _resolve_service_interval(self.VW_BRAND, "electric")
        assert result["km_max"] == 30000
        assert result["months_max"] == 24
        assert result["system_type"] == "electric"

    def test_mercedes_uses_service_a(self):
        result = _resolve_service_interval(self.MERCEDES_BRAND, "diesel")
        assert result["km_max"] == 25000
        assert result["months_max"] == 12
        assert result["system_type"] == "flexible"

    def test_ford_petrol_uses_ecoboost(self):
        result = _resolve_service_interval(self.FORD_BRAND, "petrol")
        assert result["km_max"] == 24000
        assert result["months_max"] == 12

    def test_ford_diesel_direct(self):
        result = _resolve_service_interval(self.FORD_BRAND, "diesel")
        assert result["km_max"] == 20000
        assert result["months_max"] == 12

    def test_toyota_hybrid(self):
        result = _resolve_service_interval(self.TOYOTA_BRAND, "hybrid")
        assert result["km_max"] == 15000
        assert result["months_max"] == 12
        assert result["system_type"] == "hybrid"

    def test_empty_intervals_returns_fallback(self):
        result = _resolve_service_interval({"intervals": {}}, "petrol")
        assert result["km_max"] == 30000
        assert result["months_max"] == 24


class TestCheck4bServiceCompliance:
    """Tests for Check 4b: Service compliance (manufacturer-aware)."""

    # Sample brand data for tests
    VW_BRANDS = {
        "volkswagen": {
            "service_system": "dual",
            "intervals": {
                "fixed": {"km": 15000, "months": 12},
                "electric": {"km": 30000, "months": 24},
            },
        },
    }

    BMW_BRANDS = {
        "bmw": {
            "service_system": "flexible",
            "intervals": {
                "petrol": {"km_min": 15000, "km_max": 25000, "months_max": 24},
                "diesel": {"km_min": 10000, "km_max": 25000, "months_max": 24},
                "electric": {"km": 30000, "months": 24},
            },
        },
    }

    # ── SKIPPED tests (unchanged) ───────────────────────────────────

    def test_skipped_no_entries(self):
        facts = [{"name": "document_date", "value": "15.06.2025"}]
        result = check_4b_service_compliance(facts, [])
        assert result.verdict == CheckVerdict.SKIPPED

    def test_skipped_no_claim_date(self):
        facts = []
        entries = [{"service_date": "2025-01-15"}]
        result = check_4b_service_compliance(facts, entries)
        assert result.verdict == CheckVerdict.SKIPPED

    def test_skipped_unparseable_dates(self):
        facts = [{"name": "document_date", "value": "15.06.2025"}]
        entries = [{"service_date": "not-a-date"}]
        result = check_4b_service_compliance(facts, entries)
        assert result.verdict == CheckVerdict.SKIPPED

    # ── Known brand: VW (dual, 12mo) ────────────────────────────────

    def test_vw_pass_within_12_months(self):
        """VW fixed=12 months. Service 6 months ago → PASS."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "Volkswagen"},
            {"name": "vehicle_fuel_type", "value": "Diesel"},
        ]
        entries = [{"service_date": "2025-01-15"}]
        result = check_4b_service_compliance(facts, entries, self.VW_BRANDS)
        assert result.verdict == CheckVerdict.PASS
        assert result.evidence["brand_known"] is True

    def test_vw_inconclusive_13_months(self):
        """VW fixed=12mo. Service 13mo ago → ratio ~1.08 → INCONCLUSIVE."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "VW"},
            {"name": "vehicle_fuel_type", "value": "Benzin"},
        ]
        entries = [{"service_date": "2024-05-01"}]
        result = check_4b_service_compliance(facts, entries, self.VW_BRANDS)
        assert result.verdict == CheckVerdict.INCONCLUSIVE

    def test_vw_fail_20_months(self):
        """VW fixed=12mo. Service 20mo ago → ratio ~1.67 → FAIL."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "VW"},
            {"name": "vehicle_fuel_type", "value": "Bleifrei"},
        ]
        entries = [{"service_date": "2023-10-15"}]
        result = check_4b_service_compliance(facts, entries, self.VW_BRANDS)
        assert result.verdict == CheckVerdict.FAIL
        assert result.requires_llm is True

    # ── Known brand: BMW (flexible, 24mo) ───────────────────────────

    def test_bmw_pass_within_24_months(self):
        """BMW CBS=24mo max. Service 18mo ago → PASS."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "BMW"},
            {"name": "vehicle_fuel_type", "value": "Diesel"},
        ]
        entries = [{"service_date": "2024-01-01"}]
        result = check_4b_service_compliance(facts, entries, self.BMW_BRANDS)
        assert result.verdict == CheckVerdict.PASS

    def test_bmw_inconclusive_30_months(self):
        """BMW CBS=24mo. Service 30mo ago → ratio ~1.25 → INCONCLUSIVE."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "BMW"},
            {"name": "vehicle_fuel_type", "value": "Benzin"},
        ]
        entries = [{"service_date": "2022-12-15"}]
        result = check_4b_service_compliance(facts, entries, self.BMW_BRANDS)
        assert result.verdict == CheckVerdict.INCONCLUSIVE

    def test_bmw_fail_40_months(self):
        """BMW CBS=24mo. Service 40mo ago → ratio ~1.67 → FAIL."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "BMW"},
            {"name": "vehicle_fuel_type", "value": "Diesel"},
        ]
        entries = [{"service_date": "2022-02-15"}]
        result = check_4b_service_compliance(facts, entries, self.BMW_BRANDS)
        assert result.verdict == CheckVerdict.FAIL

    # ── Unknown brand: fallback 24mo, auto-downgrade ────────────────

    def test_unknown_brand_downgrades_pass_to_inconclusive(self):
        """Unknown brand uses 24mo fallback. 6mo gap → PASS downgraded to INCONCLUSIVE."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "Lamborghini"},
        ]
        entries = [{"service_date": "2025-01-15"}]
        result = check_4b_service_compliance(facts, entries)
        assert result.verdict == CheckVerdict.INCONCLUSIVE
        assert result.evidence["brand_known"] is False
        assert result.evidence["fallback_interval_used"] is True

    def test_unknown_brand_fail_stays_fail(self):
        """Unknown brand, 40mo gap → FAIL (not downgraded)."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "Lamborghini"},
        ]
        entries = [{"service_date": "2022-02-15"}]
        result = check_4b_service_compliance(facts, entries)
        assert result.verdict == CheckVerdict.FAIL

    def test_no_make_uses_fallback(self):
        """No vehicle_make at all → fallback + INCONCLUSIVE."""
        facts = [{"name": "document_date", "value": "15.06.2025"}]
        entries = [{"service_date": "2025-01-15"}]
        result = check_4b_service_compliance(facts, entries)
        assert result.verdict == CheckVerdict.INCONCLUSIVE
        assert result.evidence["brand_known"] is False

    # ── Mileage compliance ──────────────────────────────────────────

    def test_mileage_overrides_time_verdict(self):
        """Time PASS but mileage FAIL → combined FAIL."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "Volkswagen"},
            {"name": "vehicle_fuel_type", "value": "Diesel"},
            {"name": "odometer_km", "value": "50000"},
        ]
        # Service was 6mo ago (time PASS) but only 10,000 km at service
        # km_gap = 50000 - 10000 = 40000, ratio = 40000/15000 = 2.67 → FAIL
        entries = [{"service_date": "2025-01-15", "mileage_km": "10000"}]
        result = check_4b_service_compliance(facts, entries, self.VW_BRANDS)
        assert result.verdict == CheckVerdict.FAIL

    def test_mileage_within_limit(self):
        """Both time and mileage within limits → PASS."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "Volkswagen"},
            {"name": "vehicle_fuel_type", "value": "Diesel"},
            {"name": "odometer_km", "value": "55000"},
        ]
        entries = [{"service_date": "2025-01-15", "mileage_km": "45000"}]
        result = check_4b_service_compliance(facts, entries, self.VW_BRANDS)
        assert result.verdict == CheckVerdict.PASS

    # ── Chronic non-maintenance ─────────────────────────────────────

    def test_chronic_non_maintenance_detected(self):
        """2+ inter-service gaps > 2x interval → chronic flag."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "Volkswagen"},
            {"name": "vehicle_fuel_type", "value": "Diesel"},
        ]
        # VW fixed=12mo. Gaps: 30mo, 30mo, 6mo → 2 gaps > 24mo (2x12)
        entries = [
            {"service_date": "2020-01-01"},
            {"service_date": "2022-07-01"},
            {"service_date": "2025-01-01"},
            {"service_date": "2025-06-01"},  # last before claim
        ]
        result = check_4b_service_compliance(facts, entries, self.VW_BRANDS)
        assert result.evidence["chronic_non_maintenance"] is True

    def test_no_chronic_with_regular_service(self):
        """Regular 11-month services → no chronic flag."""
        facts = [
            {"name": "document_date", "value": "15.06.2025"},
            {"name": "vehicle_make", "value": "Volkswagen"},
            {"name": "vehicle_fuel_type", "value": "Diesel"},
        ]
        entries = [
            {"service_date": "2024-01-01"},
            {"service_date": "2024-06-01"},
            {"service_date": "2025-01-15"},
        ]
        result = check_4b_service_compliance(facts, entries, self.VW_BRANDS)
        assert result.evidence["chronic_non_maintenance"] is False


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


# ── Reimplemented Check 5 — consumes primary_repair from coverage analyzer ────


def check_5_component_coverage(
    determination_method: str = "none",
    primary_description: Optional[str] = None,
    primary_category: Optional[str] = None,
    primary_is_covered: Optional[bool] = None,
    primary_confidence: float = 0.0,
    items_covered: int = 0,
    items_not_covered: int = 0,
    items_review_needed: int = 0,
) -> ScreeningCheck:
    """Reimplemented Check 5 consuming primary_repair from coverage analyzer.

    Mirrors the simplified logic in workspaces/nsa/config/screening/screener.py.
    """
    evidence = {
        "items_covered": items_covered,
        "items_not_covered": items_not_covered,
        "items_review_needed": items_review_needed,
    }

    if determination_method == "none":
        evidence["determination_method"] = determination_method
        return ScreeningCheck(
            check_id="5", check_name="component_coverage",
            verdict=CheckVerdict.INCONCLUSIVE,
            reason="Could not determine primary repair component — referring for review",
            evidence=evidence, is_hard_fail=True, requires_llm=True,
        )

    evidence["primary_component"] = primary_description
    evidence["primary_component_category"] = primary_category
    evidence["primary_component_status"] = (
        "covered" if primary_is_covered else "not_covered"
    )
    evidence["determination_method"] = determination_method
    evidence["primary_confidence"] = primary_confidence

    if primary_is_covered is True:
        return ScreeningCheck(
            check_id="5", check_name="component_coverage",
            verdict=CheckVerdict.PASS,
            reason=(
                f"Primary repair '{primary_description}' is covered "
                f"({primary_category}, method={determination_method})"
            ),
            evidence=evidence, is_hard_fail=True,
        )

    if primary_is_covered is False and primary_confidence >= 0.80:
        return ScreeningCheck(
            check_id="5", check_name="component_coverage",
            verdict=CheckVerdict.FAIL,
            reason=(
                f"Primary repair '{primary_description}' is not covered "
                f"(confidence={primary_confidence:.2f})"
            ),
            evidence=evidence, is_hard_fail=True,
        )

    # Low confidence or uncertain → INCONCLUSIVE (refer)
    return ScreeningCheck(
        check_id="5", check_name="component_coverage",
        verdict=CheckVerdict.INCONCLUSIVE,
        reason=(
            f"Primary repair '{primary_description}' coverage uncertain "
            f"(confidence={primary_confidence:.2f}) — referring for review"
        ),
        evidence=evidence, is_hard_fail=True, requires_llm=True,
    )


class TestCheck5ComponentCoverage:
    """Tests for Check 5: Component coverage consuming primary_repair."""

    def test_covered_primary_passes(self):
        """COVERED primary repair → PASS."""
        result = check_5_component_coverage(
            determination_method="deterministic",
            primary_description="Zahnriemen",
            primary_is_covered=True,
            primary_confidence=0.90,
            primary_category="engine",
        )
        assert result.verdict == CheckVerdict.PASS
        assert result.is_hard_fail is True

    def test_not_covered_high_confidence_fails(self):
        """NOT_COVERED + confidence 0.95 → FAIL."""
        result = check_5_component_coverage(
            determination_method="deterministic",
            primary_description="Turbo part",
            primary_is_covered=False,
            primary_confidence=0.95,
            primary_category="turbo_supercharger",
        )
        assert result.verdict == CheckVerdict.FAIL
        assert result.is_hard_fail is True

    def test_not_covered_low_confidence_inconclusive(self):
        """NOT_COVERED + confidence 0.40 → INCONCLUSIVE (refer)."""
        result = check_5_component_coverage(
            determination_method="deterministic",
            primary_description="Pignon distribution",
            primary_is_covered=False,
            primary_confidence=0.40,
            primary_category="engine",
        )
        assert result.verdict == CheckVerdict.INCONCLUSIVE
        assert result.requires_llm is True
        assert result.is_hard_fail is True

    def test_determination_none_inconclusive(self):
        """determination_method='none' → INCONCLUSIVE (refer)."""
        result = check_5_component_coverage(
            determination_method="none",
        )
        assert result.verdict == CheckVerdict.INCONCLUSIVE
        assert result.requires_llm is True

    def test_repair_context_covered_passes(self):
        """Repair context determination with is_covered=True → PASS."""
        result = check_5_component_coverage(
            determination_method="repair_context",
            primary_description="Steuerkette ersetzen",
            primary_is_covered=True,
            primary_confidence=0.80,
            primary_category="engine",
        )
        assert result.verdict == CheckVerdict.PASS

    def test_inconclusive_does_not_trigger_auto_reject(self):
        """INCONCLUSIVE check should NOT trigger auto_reject in ScreeningResult."""
        inconclusive_check = check_5_component_coverage(
            determination_method="none",
        )
        assert inconclusive_check.verdict == CheckVerdict.INCONCLUSIVE

        result = ScreeningResult(
            claim_id="CLM-TEST",
            screening_timestamp="2026-01-29T10:00:00Z",
            checks=[inconclusive_check],
        )
        result.recompute_counts()
        assert result.auto_reject is False
        assert result.hard_fails == []

    def test_hard_fail_still_triggers_auto_reject(self):
        """FAIL check should still trigger auto_reject."""
        fail_check = check_5_component_coverage(
            determination_method="deterministic",
            primary_description="Turbo part",
            primary_is_covered=False,
            primary_confidence=0.95,
            primary_category="turbo_supercharger",
        )
        assert fail_check.verdict == CheckVerdict.FAIL

        result = ScreeningResult(
            claim_id="CLM-TEST",
            screening_timestamp="2026-01-29T10:00:00Z",
            checks=[fail_check],
        )
        result.recompute_counts()
        assert result.auto_reject is True
        assert "5" in result.hard_fails

    def test_is_covered_none_low_confidence_inconclusive(self):
        """is_covered=None + low confidence → INCONCLUSIVE."""
        result = check_5_component_coverage(
            determination_method="deterministic",
            primary_description="Some part",
            primary_is_covered=None,
            primary_confidence=0.40,
        )
        assert result.verdict == CheckVerdict.INCONCLUSIVE
