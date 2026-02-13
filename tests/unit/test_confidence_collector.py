"""Unit tests for ConfidenceCollector.

Tests all six collect_* methods plus collect_all, covering full data,
empty/None inputs, and partial/missing fields.

Note: We load the collector module directly via importlib to avoid a
circular import triggered by the confidence package __init__.py
(which eagerly imports ConfidenceStage -> ClaimContext -> confidence).
"""

import importlib.util
from pathlib import Path

import pytest

# Load collector.py directly, bypassing confidence/__init__.py
_collector_path = (
    Path(__file__).resolve().parents[2]
    / "src" / "context_builder" / "confidence" / "collector.py"
)
_spec = importlib.util.spec_from_file_location(
    "context_builder.confidence.collector", _collector_path,
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ConfidenceCollector = _mod.ConfidenceCollector


@pytest.fixture
def collector():
    return ConfidenceCollector()


# ── 1. collect_extraction with full data (5 signals) ─────────────────


def test_collect_extraction_full(collector):
    """Full extraction data produces all 4 signals (avg_doc_type_confidence removed)."""
    extraction_results = [
        {
            "doc_type_confidence": 0.95,
            "quality_gate": {"status": "pass"},
            "fields": [
                {
                    "confidence": 0.9,
                    "provenance": {"match_quality": "exact"},
                    "has_verified_evidence": True,
                },
                {
                    "confidence": 0.8,
                    "provenance": {"match_quality": "normalized"},
                    "has_verified_evidence": False,
                },
            ],
        },
        {
            "doc_type_confidence": 0.85,
            "quality_gate": {"status": "pass"},
            "fields": [
                {
                    "confidence": 0.7,
                    "provenance": {"match_quality": "fuzzy"},
                    "has_verified_evidence": True,
                },
            ],
        },
    ]

    signals = collector.collect_extraction(extraction_results)
    by_name = {s.signal_name: s for s in signals}

    assert len(signals) == 4

    # avg_field_confidence: mean of 0.9, 0.8, 0.7 = 0.8
    s = by_name["extraction.avg_field_confidence"]
    assert s.normalized_value == pytest.approx(0.8, abs=1e-6)
    assert s.source_stage == "extraction"

    # avg_doc_type_confidence is removed (LLM self-reported)
    assert "extraction.avg_doc_type_confidence" not in by_name

    # quality_gate_pass_rate: 2 pass / 2 total = 1.0
    s = by_name["extraction.quality_gate_pass_rate"]
    assert s.normalized_value == pytest.approx(1.0)
    assert s.source_stage == "extraction"

    # provenance_match_rate: 2 good (exact, normalized) / 3 total
    s = by_name["extraction.provenance_match_rate"]
    assert s.normalized_value == pytest.approx(2.0 / 3.0, abs=1e-6)
    assert s.source_stage == "extraction"

    # verified_evidence_rate: 2 verified / 3 total
    s = by_name["extraction.verified_evidence_rate"]
    assert s.normalized_value == pytest.approx(2.0 / 3.0, abs=1e-6)
    assert s.source_stage == "extraction"


# ── 2. collect_extraction with empty list -> empty signals ────────────


def test_collect_extraction_empty_list(collector):
    """Empty extraction_results list returns no signals."""
    signals = collector.collect_extraction([])
    assert signals == []


# ── 3. collect_extraction with missing fields -> partial signals ──────


def test_collect_extraction_missing_fields(collector):
    """Extraction docs with missing fields produce only available signals."""
    extraction_results = [
        {
            # No doc_type_confidence, no quality_gate
            "fields": [
                {
                    "confidence": 0.75,
                    # No provenance, no has_verified_evidence
                },
            ],
        },
    ]

    signals = collector.collect_extraction(extraction_results)
    by_name = {s.signal_name: s for s in signals}

    # avg_field_confidence should exist (confidence=0.75)
    assert "extraction.avg_field_confidence" in by_name
    assert by_name["extraction.avg_field_confidence"].normalized_value == pytest.approx(0.75)

    # avg_doc_type_confidence should NOT exist
    assert "extraction.avg_doc_type_confidence" not in by_name

    # quality_gate_pass_rate should NOT exist
    assert "extraction.quality_gate_pass_rate" not in by_name

    # provenance_match_rate should NOT exist (no provenance data)
    assert "extraction.provenance_match_rate" not in by_name

    # verified_evidence_rate: 0 verified / 1 total = 0.0
    assert "extraction.verified_evidence_rate" in by_name
    assert by_name["extraction.verified_evidence_rate"].normalized_value == pytest.approx(0.0)


# ── 4. collect_reconciliation with full report (4 signals) ────────────


def test_collect_reconciliation_full(collector):
    """Full reconciliation report produces all 4 signals."""
    report = {
        "gate": {
            "provenance_coverage": 0.92,
            "status": "pass",
        },
        "critical_facts_present": ["fact_a", "fact_b"],
        "critical_facts_spec": ["fact_a", "fact_b", "fact_c"],
        "conflicts": [{"id": "c1"}],
        "facts": [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}, {"id": "f4"}],
    }

    signals = collector.collect_reconciliation(report)
    by_name = {s.signal_name: s for s in signals}

    assert len(signals) == 4

    # provenance_coverage = 0.92
    s = by_name["reconciliation.provenance_coverage"]
    assert s.normalized_value == pytest.approx(0.92, abs=1e-6)
    assert s.source_stage == "reconciliation"

    # critical_facts_rate: 2 / 3
    s = by_name["reconciliation.critical_facts_rate"]
    assert s.normalized_value == pytest.approx(2.0 / 3.0, abs=1e-6)
    assert s.source_stage == "reconciliation"

    # conflict_rate: raw = 1/4 = 0.25, inv = 0.75
    s = by_name["reconciliation.conflict_rate"]
    assert s.raw_value == pytest.approx(0.25)
    assert s.normalized_value == pytest.approx(0.75)
    assert s.source_stage == "reconciliation"

    # gate_status_score: pass = 1.0
    s = by_name["reconciliation.gate_status_score"]
    assert s.normalized_value == pytest.approx(1.0)
    assert s.source_stage == "reconciliation"


# ── 5. collect_reconciliation with None -> empty ──────────────────────


def test_collect_reconciliation_none(collector):
    """None reconciliation_report returns empty signals."""
    signals = collector.collect_reconciliation(None)
    assert signals == []


# ── 6. collect_reconciliation with missing gate -> partial ────────────


def test_collect_reconciliation_missing_gate(collector):
    """Report with no gate key still collects non-gate signals."""
    report = {
        # No "gate" key
        "critical_facts_present": ["a"],
        "critical_facts_spec": ["a", "b"],
        "conflicts": [],
        "facts": [{"id": "f1"}, {"id": "f2"}],
    }

    signals = collector.collect_reconciliation(report)
    by_name = {s.signal_name: s for s in signals}

    # No provenance_coverage or gate_status_score (gate is empty/missing)
    assert "reconciliation.provenance_coverage" not in by_name
    assert "reconciliation.gate_status_score" not in by_name

    # critical_facts_rate: 1 / 2 = 0.5
    assert "reconciliation.critical_facts_rate" in by_name
    assert by_name["reconciliation.critical_facts_rate"].normalized_value == pytest.approx(0.5)

    # conflict_rate: 0 conflicts / 2 facts -> raw=0, inv=1.0
    assert "reconciliation.conflict_rate" in by_name
    assert by_name["reconciliation.conflict_rate"].normalized_value == pytest.approx(1.0)


# ── 7. collect_coverage with full analysis (4 signals) ────────────────


def test_collect_coverage_full(collector):
    """Full coverage analysis produces base signals plus new CCI signals."""
    analysis = {
        "line_items": [
            {
                "match_confidence": 0.9,
                "total_price": 1000.0,
                "review_needed": False,
                "match_method": "keyword",
                "coverage_status": "covered",
                "item_type": "parts",
            },
            {
                "match_confidence": 0.6,
                "total_price": 500.0,
                "review_needed": True,
                "match_method": "llm",
                "coverage_status": "not_covered",
                "item_type": "labor",
            },
        ],
        "primary_repair": {
            "determination_method": "keyword",
        },
        "summary": {
            "total_claimed": 1500.0,
            "total_covered_before_excess": 1000.0,
        },
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    # structural_match_quality: weighted by method type
    # keyword=0.80*1000 + llm=0.60*500 = 800+300=1100 / 1500 = 0.7333
    s = by_name["coverage.structural_match_quality"]
    assert s.normalized_value == pytest.approx(1100 / 1500, abs=1e-4)
    assert s.source_stage == "coverage"

    # review_needed_rate: 1 review / 2 total = 0.5, inv = 0.5
    s = by_name["coverage.review_needed_rate"]
    assert s.raw_value == pytest.approx(0.5)
    assert s.normalized_value == pytest.approx(0.5)
    assert s.source_stage == "coverage"

    # method_diversity: 2 methods / 5 = 0.4
    s = by_name["coverage.method_diversity"]
    assert s.raw_value == pytest.approx(2.0)
    assert s.normalized_value == pytest.approx(0.4)
    assert s.source_stage == "coverage"

    # primary_repair_method_reliability: keyword -> 0.85
    s = by_name["coverage.primary_repair_method_reliability"]
    assert s.normalized_value == pytest.approx(0.85, abs=1e-6)
    assert s.source_stage == "coverage"

    # line_item_complexity: 2 items <= 3 -> score 0.25
    s = by_name["coverage.line_item_complexity"]
    assert s.raw_value == pytest.approx(2.0)
    assert s.normalized_value == pytest.approx(0.25)
    assert s.source_stage == "coverage"

    # zero_coverage_penalty: 1/2 = 50% coverage rate, 0.50/0.30 = 1.67 -> 1.0
    s = by_name["coverage.zero_coverage_penalty"]
    assert s.normalized_value == pytest.approx(1.0)

    # payout_materiality: 1000/1500 = 0.667, 0.667/0.20 = 3.33 -> 1.0
    s = by_name["coverage.payout_materiality"]
    assert s.normalized_value == pytest.approx(1.0)

    # parts_coverage_check: 1 covered parts item -> 1.0
    s = by_name["coverage.parts_coverage_check"]
    assert s.normalized_value == pytest.approx(1.0)


def test_collect_coverage_structural_match_quality_methods(collector):
    """structural_match_quality maps each method to its reliability score."""
    analysis = {
        "line_items": [
            {"total_price": 100.0, "match_method": "rule"},
            {"total_price": 100.0, "match_method": "part_number"},
            {"total_price": 100.0, "match_method": "keyword"},
            {"total_price": 100.0, "match_method": "llm"},
            {"total_price": 100.0, "match_method": "manual"},
        ],
        "primary_repair": {"determination_method": "part_number"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    # (1.0 + 0.95 + 0.80 + 0.60 + 1.0) * 100 / 500 = 4.35/5 = 0.87
    s = by_name["coverage.structural_match_quality"]
    expected = (1.0 + 0.95 + 0.80 + 0.60 + 1.0) / 5.0
    assert s.normalized_value == pytest.approx(expected, abs=1e-4)


def test_collect_coverage_primary_repair_method_reliability_mappings(collector):
    """primary_repair_method_reliability maps each determination_method correctly."""
    expected_scores = {
        "part_number": 1.0,
        "keyword": 0.85,
        "deterministic": 0.75,
        "llm": 0.60,
        "none": 0.0,
    }
    for method, expected in expected_scores.items():
        analysis = {
            "line_items": [{"match_method": "rule", "total_price": 100}],
            "primary_repair": {"determination_method": method},
        }
        signals = collector.collect_coverage(analysis)
        by_name = {s.signal_name: s for s in signals}
        s = by_name["coverage.primary_repair_method_reliability"]
        assert s.normalized_value == pytest.approx(expected, abs=1e-6), (
            f"Method {method}: expected {expected}, got {s.normalized_value}"
        )


# ── 7b. line_item_complexity decay curve ──────────────────────────────


@pytest.mark.parametrize("n_items,expected_score", [
    (1, 0.25),    # very few items: floor
    (3, 0.25),    # boundary: still floor
    (4, 0.3571),  # ramp start: 0.25 + 0.75 * (4-3)/7
    (7, 0.6786),  # mid-ramp: 0.25 + 0.75 * (7-3)/7
    (10, 1.0),    # ramp end: 0.25 + 0.75 * (10-3)/7 = 1.0
    (15, 1.0),    # above 10: stays at 1.0
    (30, 1.0),    # well above 10: still 1.0
])
def test_collect_coverage_line_item_complexity_ramp(collector, n_items, expected_score):
    """Line item complexity signal ramps up: more items = higher confidence."""
    line_items = [
        {
            "match_confidence": 0.9,
            "total_price": 100.0,
            "review_needed": False,
            "match_method": "keyword",
        }
        for _ in range(n_items)
    ]
    analysis = {
        "line_items": line_items,
        "primary_repair": {"determination_method": "keyword"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    s = by_name["coverage.line_item_complexity"]
    assert s.raw_value == pytest.approx(float(n_items))
    assert s.normalized_value == pytest.approx(expected_score, abs=1e-4)
    assert s.source_stage == "coverage"


# ── 8. collect_coverage with no line_items -> empty ───────────────────


def test_collect_coverage_no_line_items(collector):
    """Coverage analysis with empty line_items returns no signals."""
    # None input
    assert collector.collect_coverage(None) == []

    # Empty line_items list
    analysis = {"line_items": []}
    signals = collector.collect_coverage(analysis)
    assert signals == []


# ── 9. collect_screening with full result (3 signals) ────────────────


def test_collect_screening_full(collector):
    """Full screening result produces all 3 signals."""
    result = {
        "checks_passed": 7,
        "checks_failed": 2,
        "checks_inconclusive": 1,
        "checks": [
            {"name": "check_a", "verdict": "PASS", "is_hard_fail": False},
            {"name": "check_b", "verdict": "FAIL", "is_hard_fail": False},
        ],
    }

    signals = collector.collect_screening(result)
    by_name = {s.signal_name: s for s in signals}

    assert len(signals) == 3

    # pass_rate: 7 / 10 = 0.7
    s = by_name["screening.pass_rate"]
    assert s.normalized_value == pytest.approx(0.7)
    assert s.source_stage == "screening"

    # inconclusive_rate: raw = 1/10 = 0.1, inv = 0.9
    s = by_name["screening.inconclusive_rate"]
    assert s.raw_value == pytest.approx(0.1)
    assert s.normalized_value == pytest.approx(0.9)
    assert s.source_stage == "screening"

    # hard_fail_clarity: no hard fail present -> 1.0
    s = by_name["screening.hard_fail_clarity"]
    assert s.normalized_value == pytest.approx(1.0)
    assert s.source_stage == "screening"


# ── 10. collect_screening with hard_fail present -> clarity=0 ─────────


def test_collect_screening_hard_fail(collector):
    """Screening with a hard fail sets hard_fail_clarity to 0."""
    result = {
        "checks_passed": 3,
        "checks_failed": 1,
        "checks_inconclusive": 0,
        "checks": [
            {"name": "critical_check", "verdict": "FAIL", "is_hard_fail": True},
            {"name": "normal_check", "verdict": "PASS", "is_hard_fail": False},
        ],
    }

    signals = collector.collect_screening(result)
    by_name = {s.signal_name: s for s in signals}

    s = by_name["screening.hard_fail_clarity"]
    assert s.normalized_value == pytest.approx(0.0)
    assert s.raw_value == pytest.approx(0.0)
    assert s.source_stage == "screening"


# ── 11. collect_assessment with confidence + gaps + fraud (3 signals) ─


def test_collect_assessment_full(collector):
    """Full assessment produces all 3 signals."""
    result = {
        "confidence_score": 0.78,
        "data_gaps": [
            {"severity": "HIGH"},
            {"severity": "LOW"},
        ],
        "fraud_indicators": [
            {"risk_level": "MEDIUM"},
        ],
    }

    signals = collector.collect_assessment(result)
    by_name = {s.signal_name: s for s in signals}

    assert len(signals) == 3

    # confidence_score = 0.78
    s = by_name["assessment.confidence_score"]
    assert s.normalized_value == pytest.approx(0.78, abs=1e-6)
    assert s.source_stage == "assessment"

    # data_gap_penalty: HIGH=0.15 + LOW=0.03 = 0.18, inv = 0.82
    s = by_name["assessment.data_gap_penalty"]
    assert s.raw_value == pytest.approx(0.18)
    assert s.normalized_value == pytest.approx(0.82)
    assert s.source_stage == "assessment"

    # fraud_indicator_penalty: MEDIUM=0.10, inv = 0.90
    s = by_name["assessment.fraud_indicator_penalty"]
    assert s.raw_value == pytest.approx(0.10)
    assert s.normalized_value == pytest.approx(0.90)
    assert s.source_stage == "assessment"


# ── 12. collect_decision with evaluations + assumptions (2 signals) ───


def test_collect_decision_full(collector):
    """Full decision result produces tier1 and assumption signals."""
    result = {
        "clause_evaluations": [
            {"evaluability_tier": 1},
            {"evaluability_tier": 1},
            {"evaluability_tier": 2},
            {"evaluability_tier": 3},
        ],
        "assumptions_used": [
            {"id": "a1"},
            {"id": "a2"},
            {"id": "a3"},
        ],
        "unresolved_assumptions": [
            {"id": "a3"},
        ],
    }

    signals = collector.collect_decision(result)
    by_name = {s.signal_name: s for s in signals}

    assert len(signals) == 2

    # tier1_ratio: 2 tier-1 / 4 total = 0.5
    s = by_name["decision.tier1_ratio"]
    assert s.normalized_value == pytest.approx(0.5)
    assert s.source_stage == "decision"

    # assumption_reliance: raw = 1/3, inv = 2/3
    s = by_name["decision.assumption_reliance"]
    assert s.raw_value == pytest.approx(1.0 / 3.0, abs=1e-6)
    assert s.normalized_value == pytest.approx(2.0 / 3.0, abs=1e-6)
    assert s.source_stage == "decision"


# ── 13. collect_all with mixed data -> combined signals ───────────────


def test_collect_all_mixed(collector):
    """collect_all merges signals from all stages that have data."""
    extraction_results = [
        {
            "doc_type_confidence": 0.90,
            "quality_gate": {"status": "pass"},
            "fields": [
                {
                    "confidence": 0.85,
                    "provenance": {"match_quality": "exact"},
                    "has_verified_evidence": True,
                },
            ],
        },
    ]

    reconciliation_report = {
        "gate": {"provenance_coverage": 0.88, "status": "warn"},
        "critical_facts_present": ["a"],
        "critical_facts_spec": ["a", "b"],
        "conflicts": [],
        "facts": [{"id": "f1"}],
    }

    screening_result = {
        "checks_passed": 5,
        "checks_failed": 0,
        "checks_inconclusive": 0,
        "checks": [],
    }

    signals = collector.collect_all(
        extraction_results=extraction_results,
        reconciliation_report=reconciliation_report,
        coverage_analysis=None,      # omitted
        screening_result=screening_result,
        processing_result=None,       # omitted
        decision_result=None,         # omitted
    )

    stages_present = {s.source_stage for s in signals}
    assert "extraction" in stages_present
    assert "reconciliation" in stages_present
    assert "screening" in stages_present

    # Coverage, assessment, and decision were None/empty -> no signals from them
    assert "coverage" not in stages_present
    assert "assessment" not in stages_present
    assert "decision" not in stages_present

    # Extraction: 4 signals (avg_doc_type_confidence removed)
    extraction_signals = [s for s in signals if s.source_stage == "extraction"]
    assert len(extraction_signals) == 4

    # Reconciliation: 4 signals
    reconciliation_signals = [s for s in signals if s.source_stage == "reconciliation"]
    assert len(reconciliation_signals) == 4

    # Screening: 3 signals (pass_rate, inconclusive_rate, hard_fail_clarity)
    screening_signals = [s for s in signals if s.source_stage == "screening"]
    assert len(screening_signals) == 3

    # Total: 4 + 4 + 3 = 11
    assert len(signals) == 11


# ── 14. collect_coverage_concordance for DENY ────────────────────────


def test_collect_coverage_concordance_deny_all_not_covered(collector):
    """DENY with all items not_covered produces concordance = 1.0."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "not_covered"},
            {"total_price": 300.0, "coverage_status": "not_covered"},
        ],
    }

    signals = collector.collect_coverage_concordance(analysis, verdict="DENY")
    assert len(signals) == 1

    s = signals[0]
    assert s.signal_name == "coverage.verdict_concordance"
    assert s.normalized_value == pytest.approx(1.0)
    assert s.source_stage == "coverage"


def test_collect_coverage_concordance_deny_mixed(collector):
    """DENY with mixed coverage produces concordance based on not_covered amount."""
    analysis = {
        "line_items": [
            {"total_price": 600.0, "coverage_status": "not_covered"},
            {"total_price": 400.0, "coverage_status": "covered"},
        ],
    }

    signals = collector.collect_coverage_concordance(analysis, verdict="DENY")
    assert len(signals) == 1

    # 600 / (600 + 400) = 0.6
    assert signals[0].normalized_value == pytest.approx(0.6)


def test_collect_coverage_concordance_deny_all_covered(collector):
    """DENY where everything is covered produces concordance = 0.0."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "covered"},
        ],
    }

    signals = collector.collect_coverage_concordance(analysis, verdict="DENY")
    assert len(signals) == 1
    assert signals[0].normalized_value == pytest.approx(0.0)


# ── 15. collect_coverage_concordance NOT emitted for APPROVE ─────────


def test_collect_coverage_concordance_approve_empty(collector):
    """APPROVE verdict produces no concordance signal."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "not_covered"},
        ],
    }

    signals = collector.collect_coverage_concordance(analysis, verdict="APPROVE")
    assert signals == []


def test_collect_coverage_concordance_no_verdict_empty(collector):
    """No verdict produces no concordance signal."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "not_covered"},
        ],
    }

    signals = collector.collect_coverage_concordance(analysis, verdict="")
    assert signals == []


def test_collect_coverage_concordance_none_analysis(collector):
    """None coverage analysis returns empty even for DENY."""
    signals = collector.collect_coverage_concordance(None, verdict="DENY")
    assert signals == []


# ── 16. collect_all with verdict passes through to concordance ───────


def test_collect_all_deny_includes_concordance(collector):
    """collect_all with verdict=DENY includes the concordance signal."""
    coverage_analysis = {
        "line_items": [
            {
                "total_price": 100.0,
                "coverage_status": "not_covered",
                "match_confidence": 0.9,
                "match_method": "rule",
            },
        ],
        "primary_repair": {"determination_method": "keyword"},
    }

    signals = collector.collect_all(
        coverage_analysis=coverage_analysis,
        verdict="DENY",
    )

    by_name = {s.signal_name: s for s in signals}
    assert "coverage.verdict_concordance" in by_name
    assert by_name["coverage.verdict_concordance"].normalized_value == pytest.approx(1.0)


def test_collect_all_approve_no_concordance(collector):
    """collect_all with verdict=APPROVE does NOT include concordance."""
    coverage_analysis = {
        "line_items": [
            {
                "total_price": 100.0,
                "coverage_status": "not_covered",
                "match_confidence": 0.9,
                "match_method": "rule",
            },
        ],
        "primary_repair": {"determination_method": "keyword"},
    }

    signals = collector.collect_all(
        coverage_analysis=coverage_analysis,
        verdict="APPROVE",
    )

    by_name = {s.signal_name: s for s in signals}
    assert "coverage.verdict_concordance" not in by_name


# ── 17. policy_confirmation_rate signal ───────────────────────────────


def test_policy_confirmation_rate_all_true(collector):
    """All covered items with policy_list_confirmed=True produces rate=1.0."""
    analysis = {
        "line_items": [
            {
                "total_price": 500.0,
                "coverage_status": "covered",
                "policy_list_confirmed": True,
                "match_method": "llm",
            },
            {
                "total_price": 300.0,
                "coverage_status": "covered",
                "policy_list_confirmed": True,
                "match_method": "rule",
            },
            {
                "total_price": 200.0,
                "coverage_status": "not_covered",
                "match_method": "rule",
            },
        ],
        "primary_repair": {"determination_method": "llm"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.policy_confirmation_rate" in by_name
    s = by_name["coverage.policy_confirmation_rate"]
    assert s.normalized_value == pytest.approx(1.0)
    assert s.source_stage == "coverage"


def test_policy_confirmation_rate_all_false(collector):
    """All covered items with policy_list_confirmed=False produces rate=0.0."""
    analysis = {
        "line_items": [
            {
                "total_price": 400.0,
                "coverage_status": "covered",
                "policy_list_confirmed": False,
                "match_method": "llm",
            },
            {
                "total_price": 600.0,
                "coverage_status": "covered",
                "policy_list_confirmed": False,
                "match_method": "llm",
            },
        ],
        "primary_repair": {"determination_method": "llm"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.policy_confirmation_rate" in by_name
    assert by_name["coverage.policy_confirmation_rate"].normalized_value == pytest.approx(0.0)


def test_policy_confirmation_rate_all_none(collector):
    """All covered items with policy_list_confirmed=None produces rate=0.5."""
    analysis = {
        "line_items": [
            {
                "total_price": 1000.0,
                "coverage_status": "covered",
                "policy_list_confirmed": None,
                "match_method": "llm",
            },
        ],
        "primary_repair": {"determination_method": "llm"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.policy_confirmation_rate" in by_name
    assert by_name["coverage.policy_confirmation_rate"].normalized_value == pytest.approx(0.5)


def test_policy_confirmation_rate_mixed(collector):
    """Mixed policy_list_confirmed values produces weighted average."""
    analysis = {
        "line_items": [
            {
                "total_price": 600.0,
                "coverage_status": "covered",
                "policy_list_confirmed": True,
                "match_method": "rule",
            },
            {
                "total_price": 200.0,
                "coverage_status": "covered",
                "policy_list_confirmed": False,
                "match_method": "llm",
            },
            {
                "total_price": 200.0,
                "coverage_status": "covered",
                "policy_list_confirmed": None,
                "match_method": "llm",
            },
        ],
        "primary_repair": {"determination_method": "llm"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    # (1.0*600 + 0.0*200 + 0.5*200) / 1000 = 700/1000 = 0.7
    assert "coverage.policy_confirmation_rate" in by_name
    assert by_name["coverage.policy_confirmation_rate"].normalized_value == pytest.approx(0.7)


def test_policy_confirmation_rate_no_covered_items(collector):
    """No covered items means no policy_confirmation_rate signal."""
    analysis = {
        "line_items": [
            {
                "total_price": 500.0,
                "coverage_status": "not_covered",
                "match_method": "rule",
            },
        ],
        "primary_repair": {"determination_method": "llm"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.policy_confirmation_rate" not in by_name


def test_policy_confirmation_rate_backward_compat(collector):
    """Items without policy_list_confirmed field default to None (score 0.5)."""
    analysis = {
        "line_items": [
            {
                "total_price": 1000.0,
                "coverage_status": "covered",
                "match_method": "llm",
                # no policy_list_confirmed key
            },
        ],
        "primary_repair": {"determination_method": "llm"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.policy_confirmation_rate" in by_name
    assert by_name["coverage.policy_confirmation_rate"].normalized_value == pytest.approx(0.5)


# ── 18. zero_coverage_penalty signal ─────────────────────────────────


def test_zero_coverage_penalty_with_covered_items(collector):
    """1 of 2 items covered -> coverage_rate=0.5, penalty = min(1.0, 0.5/0.30) = 1.0."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "covered",
             "match_method": "rule", "item_type": "parts"},
            {"total_price": 300.0, "coverage_status": "not_covered",
             "match_method": "rule", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "rule"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.zero_coverage_penalty" in by_name
    # 1/2 = 50% coverage rate, 0.50/0.30 = 1.67, clamped to 1.0
    assert by_name["coverage.zero_coverage_penalty"].normalized_value == pytest.approx(1.0)


def test_zero_coverage_penalty_low_coverage_rate(collector):
    """2 of 10 items covered -> coverage_rate=0.2, penalty = 0.2/0.30 = 0.667."""
    items = [
        {"total_price": 100.0, "coverage_status": "covered",
         "match_method": "rule", "item_type": "parts"}
        for _ in range(2)
    ] + [
        {"total_price": 100.0, "coverage_status": "not_covered",
         "match_method": "rule", "item_type": "parts"}
        for _ in range(8)
    ]
    analysis = {
        "line_items": items,
        "primary_repair": {"determination_method": "rule"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.zero_coverage_penalty" in by_name
    # 2/10 = 20% coverage rate, 0.20/0.30 = 0.667
    assert by_name["coverage.zero_coverage_penalty"].normalized_value == pytest.approx(
        0.667, abs=0.01
    )


def test_zero_coverage_penalty_none_covered(collector):
    """No items covered -> penalty = 0.0 (zeros out coverage_reliability)."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "not_covered",
             "match_method": "rule", "item_type": "parts"},
            {"total_price": 300.0, "coverage_status": "not_covered",
             "match_method": "llm", "item_type": "labor"},
        ],
        "primary_repair": {"determination_method": "rule"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.zero_coverage_penalty" in by_name
    assert by_name["coverage.zero_coverage_penalty"].normalized_value == pytest.approx(0.0)


# ── 19. payout_materiality signal ────────────────────────────────────


def test_payout_materiality_high_coverage(collector):
    """High coverage ratio (>20%) -> materiality = 1.0."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "covered",
             "match_method": "rule", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "rule"},
        "summary": {"total_claimed": 1000.0, "total_covered_before_excess": 500.0},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.payout_materiality" in by_name
    # 500/1000 = 50%, 0.50/0.20 = 2.5, clamped to 1.0
    assert by_name["coverage.payout_materiality"].normalized_value == pytest.approx(1.0)


def test_payout_materiality_trivial_coverage(collector):
    """Trivial coverage ratio (1.3%) -> materiality = 0.066."""
    analysis = {
        "line_items": [
            {"total_price": 157.0, "coverage_status": "covered",
             "match_method": "llm", "item_type": "parts"},
            {"total_price": 11743.0, "coverage_status": "not_covered",
             "match_method": "rule", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "llm"},
        "summary": {"total_claimed": 11900.0, "total_covered_before_excess": 157.0},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.payout_materiality" in by_name
    # 157/11900 = 0.0132, 0.0132/0.20 = 0.066
    s = by_name["coverage.payout_materiality"]
    assert s.normalized_value == pytest.approx(0.066, abs=0.01)


def test_payout_materiality_mid_range_coverage(collector):
    """Mid-range coverage ratio (14%) -> materiality = 0.70."""
    analysis = {
        "line_items": [
            {"total_price": 345.0, "coverage_status": "covered",
             "match_method": "rule", "item_type": "parts"},
            {"total_price": 2128.0, "coverage_status": "not_covered",
             "match_method": "rule", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "rule"},
        "summary": {"total_claimed": 2473.0, "total_covered_before_excess": 345.0},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.payout_materiality" in by_name
    # 345/2473 = 0.1395, 0.1395/0.20 = 0.698
    s = by_name["coverage.payout_materiality"]
    assert s.normalized_value == pytest.approx(0.698, abs=0.01)


def test_payout_materiality_no_covered_items(collector):
    """No covered items -> no materiality signal emitted."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "not_covered",
             "match_method": "rule", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "rule"},
        "summary": {"total_claimed": 500.0, "total_covered_before_excess": 0.0},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.payout_materiality" not in by_name


# ── 20. parts_coverage_check signal ──────────────────────────────────


def test_parts_coverage_check_with_parts(collector):
    """Covered parts exist -> check = 1.0."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "covered",
             "match_method": "rule", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "rule"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.parts_coverage_check" in by_name
    assert by_name["coverage.parts_coverage_check"].normalized_value == pytest.approx(1.0)


def test_parts_coverage_check_labor_only(collector):
    """Only labor covered, no parts -> check = 0.3."""
    analysis = {
        "line_items": [
            {"total_price": 300.0, "coverage_status": "covered",
             "match_method": "llm", "item_type": "labor"},
            {"total_price": 500.0, "coverage_status": "not_covered",
             "match_method": "rule", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "llm"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.parts_coverage_check" in by_name
    assert by_name["coverage.parts_coverage_check"].normalized_value == pytest.approx(0.3)


def test_parts_coverage_check_nothing_covered(collector):
    """No covered items at all -> no parts_coverage_check signal."""
    analysis = {
        "line_items": [
            {"total_price": 500.0, "coverage_status": "not_covered",
             "match_method": "rule", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "rule"},
    }

    signals = collector.collect_coverage(analysis)
    by_name = {s.signal_name: s for s in signals}

    assert "coverage.parts_coverage_check" not in by_name


# ── 21. assumption_density cross-stage signal ────────────────────────


def test_assumption_density_in_collect_all(collector):
    """assumption_density computed when both decision and coverage data present."""
    coverage_analysis = {
        "line_items": [
            {"total_price": 100.0, "match_method": "rule",
             "coverage_status": "covered", "item_type": "parts"},
            {"total_price": 100.0, "match_method": "llm",
             "coverage_status": "covered", "item_type": "labor"},
            {"total_price": 100.0, "match_method": "rule",
             "coverage_status": "not_covered", "item_type": "parts"},
            {"total_price": 100.0, "match_method": "llm",
             "coverage_status": "not_covered", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "rule"},
        "summary": {"total_claimed": 400.0, "total_covered_before_excess": 200.0},
    }
    decision_result = {
        "clause_evaluations": [{"evaluability_tier": 1}],
        "assumptions_used": [{"id": "a1"}, {"id": "a2"}],
        "unresolved_assumptions": [],
    }

    signals = collector.collect_all(
        coverage_analysis=coverage_analysis,
        decision_result=decision_result,
    )
    by_name = {s.signal_name: s for s in signals}

    # density = 2 assumptions / 4 items = 0.5, inv = 0.5
    assert "decision.assumption_density" in by_name
    assert by_name["decision.assumption_density"].normalized_value == pytest.approx(0.5)


def test_assumption_density_missing_decision(collector):
    """No decision_result -> no assumption_density signal."""
    coverage_analysis = {
        "line_items": [
            {"total_price": 100.0, "match_method": "rule",
             "coverage_status": "covered", "item_type": "parts"},
        ],
        "primary_repair": {"determination_method": "rule"},
    }

    signals = collector.collect_all(
        coverage_analysis=coverage_analysis,
        decision_result=None,
    )
    by_name = {s.signal_name: s for s in signals}

    assert "decision.assumption_density" not in by_name

