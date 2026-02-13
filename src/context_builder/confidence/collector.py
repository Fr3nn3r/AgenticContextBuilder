"""Signal collector for the Composite Confidence Index.

Reads upstream stage results (dicts on the ClaimContext, plus JSON files
on disk for extraction data) and produces a flat list of ``SignalSnapshot``
objects, each normalised to the 0-1 range.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.schemas.confidence import SignalSnapshot

logger = logging.getLogger(__name__)


class ConfidenceCollector:
    """Collects and normalises confidence signals from pipeline outputs.

    All ``collect_*`` methods are fail-safe: if a stage's data is missing
    or malformed the method returns an empty list rather than raising.
    """

    # ── Extraction signals (from disk) ───────────────────────────────

    def collect_extraction(
        self, extraction_results: List[Dict[str, Any]]
    ) -> List[SignalSnapshot]:
        """Collect 4 signals from loaded extraction JSON files.

        Args:
            extraction_results: List of extraction result dicts, one per doc.

        Returns:
            Up to 4 SignalSnapshot objects.
        """
        signals: List[SignalSnapshot] = []
        if not extraction_results:
            return signals

        try:
            # avg_field_confidence
            all_confs: List[float] = []
            for doc in extraction_results:
                for fld in doc.get("fields", []):
                    conf = fld.get("confidence")
                    if conf is not None:
                        all_confs.append(float(conf))
            if all_confs:
                avg = sum(all_confs) / len(all_confs)
                signals.append(SignalSnapshot(
                    signal_name="extraction.avg_field_confidence",
                    raw_value=avg,
                    normalized_value=_clamp01(avg),
                    source_stage="extraction",
                    description="Mean field-level confidence across all docs",
                ))

            # quality_gate_pass_rate
            total_qg = 0
            passed_qg = 0
            for doc in extraction_results:
                qg = doc.get("quality_gate")
                if qg is not None:
                    total_qg += 1
                    if isinstance(qg, dict) and qg.get("status") == "pass":
                        passed_qg += 1
            if total_qg > 0:
                rate = passed_qg / total_qg
                signals.append(SignalSnapshot(
                    signal_name="extraction.quality_gate_pass_rate",
                    raw_value=rate,
                    normalized_value=rate,
                    source_stage="extraction",
                    description="Fraction of docs passing quality gate",
                ))

            # provenance_match_rate
            total_prov = 0
            matched_prov = 0
            good_matches = {"exact", "case_insensitive", "normalized"}
            for doc in extraction_results:
                for fld in doc.get("fields", []):
                    prov = fld.get("provenance") or {}
                    mq = prov.get("match_quality") if isinstance(prov, dict) else None
                    if mq is not None:
                        total_prov += 1
                        if mq in good_matches:
                            matched_prov += 1
            if total_prov > 0:
                rate = matched_prov / total_prov
                signals.append(SignalSnapshot(
                    signal_name="extraction.provenance_match_rate",
                    raw_value=rate,
                    normalized_value=rate,
                    source_stage="extraction",
                    description="Fraction of fields with good provenance match",
                ))

            # verified_evidence_rate
            total_ev = 0
            verified_ev = 0
            for doc in extraction_results:
                for fld in doc.get("fields", []):
                    total_ev += 1
                    if fld.get("has_verified_evidence"):
                        verified_ev += 1
            if total_ev > 0:
                rate = verified_ev / total_ev
                signals.append(SignalSnapshot(
                    signal_name="extraction.verified_evidence_rate",
                    raw_value=rate,
                    normalized_value=rate,
                    source_stage="extraction",
                    description="Fraction of fields with verified evidence",
                ))

        except Exception:
            logger.warning("Error collecting extraction signals", exc_info=True)

        return signals

    # ── Reconciliation signals ───────────────────────────────────────

    def collect_reconciliation(
        self, reconciliation_report: Optional[Dict[str, Any]]
    ) -> List[SignalSnapshot]:
        """Collect 4 signals from the reconciliation report.

        Args:
            reconciliation_report: ReconciliationReport as dict (from context or disk).

        Returns:
            Up to 4 SignalSnapshot objects.
        """
        signals: List[SignalSnapshot] = []
        if not reconciliation_report:
            return signals

        try:
            gate = reconciliation_report.get("gate") or {}

            # provenance_coverage
            pc = gate.get("provenance_coverage")
            if pc is not None:
                signals.append(SignalSnapshot(
                    signal_name="reconciliation.provenance_coverage",
                    raw_value=float(pc),
                    normalized_value=_clamp01(float(pc)),
                    source_stage="reconciliation",
                    description="Provenance coverage ratio from reconciliation gate",
                ))

            # critical_facts_rate
            present = reconciliation_report.get("critical_facts_present") or []
            spec = reconciliation_report.get("critical_facts_spec") or []
            if spec:
                rate = len(present) / len(spec)
                signals.append(SignalSnapshot(
                    signal_name="reconciliation.critical_facts_rate",
                    raw_value=rate,
                    normalized_value=_clamp01(rate),
                    source_stage="reconciliation",
                    description="Fraction of critical facts present",
                ))

            # conflict_rate (inverted: high = good)
            conflicts = reconciliation_report.get("conflicts") or []
            facts_list = reconciliation_report.get("facts") or []
            fact_count = len(facts_list) if facts_list else reconciliation_report.get("fact_count", 0)
            conflict_count = len(conflicts)
            if fact_count > 0:
                raw = conflict_count / fact_count
                inv = 1.0 - raw
                signals.append(SignalSnapshot(
                    signal_name="reconciliation.conflict_rate",
                    raw_value=raw,
                    normalized_value=_clamp01(inv),
                    source_stage="reconciliation",
                    description="1 - (conflicts / facts): higher is better",
                ))

            # gate_status_score
            gs = gate.get("status")
            if gs is not None:
                score_map = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
                score = score_map.get(str(gs).lower(), 0.5)
                signals.append(SignalSnapshot(
                    signal_name="reconciliation.gate_status_score",
                    raw_value=score,
                    normalized_value=score,
                    source_stage="reconciliation",
                    description="Gate status mapped: pass=1, warn=0.5, fail=0",
                ))

        except Exception:
            logger.warning("Error collecting reconciliation signals", exc_info=True)

        return signals

    # ── Coverage signals ─────────────────────────────────────────────

    def collect_coverage(
        self, coverage_analysis: Optional[Dict[str, Any]]
    ) -> List[SignalSnapshot]:
        """Collect 4 signals from coverage analysis.

        Args:
            coverage_analysis: CoverageAnalysisResult as dict.

        Returns:
            Up to 4 SignalSnapshot objects.
        """
        signals: List[SignalSnapshot] = []
        if not coverage_analysis:
            return signals

        try:
            line_items = coverage_analysis.get("line_items") or []

            # structural_match_quality (weighted by total_price)
            # Maps match_method to reliability score instead of using
            # LLM self-reported confidence.
            method_reliability = {
                "rule": 1.0,
                "part_number": 0.95,
                "keyword": 0.80,
                "llm": 0.60,
                "manual": 1.0,
            }
            weighted_sum = 0.0
            weight_total = 0.0
            for item in line_items:
                mm = item.get("match_method")
                tp = item.get("total_price")
                if mm is not None and tp is not None:
                    score = method_reliability.get(mm, 0.60)
                    w = max(float(tp), 0.0)
                    weighted_sum += score * w
                    weight_total += w
            if weight_total > 0:
                avg_mq = weighted_sum / weight_total
                signals.append(SignalSnapshot(
                    signal_name="coverage.structural_match_quality",
                    raw_value=avg_mq,
                    normalized_value=_clamp01(avg_mq),
                    source_stage="coverage",
                    description="Amount-weighted match quality from method type (rule=1.0, keyword=0.80, llm=0.60)",
                ))

            # review_needed_rate (inverted)
            total_items = len(line_items)
            review_needed = sum(
                1 for item in line_items if item.get("review_needed")
            )
            if total_items > 0:
                raw = review_needed / total_items
                inv = 1.0 - raw
                signals.append(SignalSnapshot(
                    signal_name="coverage.review_needed_rate",
                    raw_value=raw,
                    normalized_value=_clamp01(inv),
                    source_stage="coverage",
                    description="1 - (items needing review / total): higher is better",
                ))

            # method_diversity
            methods = set()
            for item in line_items:
                mm = item.get("match_method")
                if mm:
                    methods.add(mm)
            if line_items:
                diversity = len(methods) / 5.0  # 5 possible methods
                signals.append(SignalSnapshot(
                    signal_name="coverage.method_diversity",
                    raw_value=float(len(methods)),
                    normalized_value=_clamp01(diversity),
                    source_stage="coverage",
                    description="Distinct match methods / 5",
                ))

            # primary_repair_method_reliability
            # Maps determination_method to reliability score instead of
            # using LLM self-reported confidence.
            repair_method_reliability = {
                "part_number": 1.0,
                "keyword": 0.85,
                "deterministic": 0.75,
                "llm": 0.60,
                "none": 0.0,
            }
            primary = coverage_analysis.get("primary_repair") or {}
            det_method = primary.get("determination_method")
            if det_method is not None:
                score = repair_method_reliability.get(det_method, 0.60)
                signals.append(SignalSnapshot(
                    signal_name="coverage.primary_repair_method_reliability",
                    raw_value=score,
                    normalized_value=_clamp01(score),
                    source_stage="coverage",
                    description=f"Primary repair reliability from method ({det_method})",
                ))
            elif line_items:
                # If no primary_repair but coverage data exists, emit 0
                signals.append(SignalSnapshot(
                    signal_name="coverage.primary_repair_method_reliability",
                    raw_value=0.0,
                    normalized_value=0.0,
                    source_stage="coverage",
                    description="Primary repair method reliability (not available)",
                ))

            # policy_confirmation_rate (price-weighted)
            # Measures what fraction of covered value is confirmed in policy list.
            # True=1.0, None=0.5 (uncertain), False=0.0
            confirmed_weighted_sum = 0.0
            covered_total_price = 0.0
            for item in line_items:
                status = (item.get("coverage_status") or "").lower()
                if status != "covered":
                    continue
                tp = float(item.get("total_price", 0) or 0)
                if tp <= 0:
                    continue
                plc = item.get("policy_list_confirmed")
                if plc is True:
                    score = 1.0
                elif plc is False:
                    score = 0.0
                else:
                    score = 0.5  # None / uncertain
                confirmed_weighted_sum += score * tp
                covered_total_price += tp
            if covered_total_price > 0:
                pcr = confirmed_weighted_sum / covered_total_price
                signals.append(SignalSnapshot(
                    signal_name="coverage.policy_confirmation_rate",
                    raw_value=pcr,
                    normalized_value=_clamp01(pcr),
                    source_stage="coverage",
                    description="Price-weighted policy list confirmation rate for covered items",
                ))

            # line_item_complexity (ramp curve: more items = more cross-validation)
            # Applied as a multiplier on coverage_reliability, not averaged.
            # Few items means a single misclassification has outsized impact.
            n = len(line_items)
            if n > 0:
                if n <= 3:
                    complexity_score = 0.25
                elif n <= 10:
                    complexity_score = 0.25 + 0.75 * (n - 3) / 7
                else:
                    complexity_score = 1.0
                signals.append(SignalSnapshot(
                    signal_name="coverage.line_item_complexity",
                    raw_value=float(n),
                    normalized_value=round(complexity_score, 4),
                    source_stage="coverage",
                    description="Line item confidence: more items = better cross-validation",
                ))

            # zero_coverage_penalty: multiplier on coverage_reliability.
            # Graded by coverage rate: 0.0 when nothing covered, ramps
            # to 1.0 at 30% item coverage rate.  Claims with very few
            # covered items get a proportional penalty.
            covered_count = sum(
                1 for item in line_items
                if (item.get("coverage_status") or "").lower() == "covered"
            )
            if total_items > 0:
                if covered_count == 0:
                    penalty = 0.0
                else:
                    coverage_rate = covered_count / total_items
                    penalty = min(1.0, coverage_rate / 0.30)
                signals.append(SignalSnapshot(
                    signal_name="coverage.zero_coverage_penalty",
                    raw_value=float(covered_count),
                    normalized_value=round(penalty, 4),
                    source_stage="coverage",
                    description=(
                        f"Coverage rate penalty: {covered_count}/{total_items} "
                        f"items covered (multiplier on coverage_reliability)"
                    ),
                ))

            # payout_materiality: multiplier on coverage_reliability.
            # Catches trivial approvals where only a negligible fraction
            # of the claim is covered (e.g. CHF 157 on CHF 11,900).
            summary = coverage_analysis.get("summary") or {}
            total_claimed = float(summary.get("total_claimed", 0) or 0)
            total_covered = float(
                summary.get("total_covered_before_excess", 0) or 0
            )
            if total_claimed > 0 and covered_count > 0:
                ratio = total_covered / total_claimed
                # Below 20% coverage ratio gets progressively penalised
                materiality = min(1.0, ratio / 0.20)
                signals.append(SignalSnapshot(
                    signal_name="coverage.payout_materiality",
                    raw_value=round(ratio, 4),
                    normalized_value=round(materiality, 4),
                    source_stage="coverage",
                    description=(
                        f"Coverage materiality: {ratio:.1%} of claimed "
                        f"amount covered"
                    ),
                ))

            # parts_coverage_check: averaged into coverage_reliability.
            # When items are covered but none of them are parts, the
            # payout is likely wrong (labor-only with no parts anchor).
            if covered_count > 0:
                covered_parts = sum(
                    1 for item in line_items
                    if (item.get("coverage_status") or "").lower() == "covered"
                    and (item.get("item_type") or "").lower() == "parts"
                )
                parts_check = 1.0 if covered_parts > 0 else 0.3
                signals.append(SignalSnapshot(
                    signal_name="coverage.parts_coverage_check",
                    raw_value=float(covered_parts),
                    normalized_value=parts_check,
                    source_stage="coverage",
                    description=(
                        "1.0 if covered parts exist, 0.3 if only "
                        "labor/fees covered"
                    ),
                ))

        except Exception:
            logger.warning("Error collecting coverage signals", exc_info=True)

        return signals

    # ── Screening signals ────────────────────────────────────────────

    def collect_screening(
        self, screening_result: Optional[Dict[str, Any]]
    ) -> List[SignalSnapshot]:
        """Collect 3 signals from screening results.

        Args:
            screening_result: ScreeningResult as dict.

        Returns:
            Up to 3 SignalSnapshot objects.
        """
        signals: List[SignalSnapshot] = []
        if not screening_result:
            return signals

        try:
            passed = screening_result.get("checks_passed", 0)
            failed = screening_result.get("checks_failed", 0)
            inconclusive = screening_result.get("checks_inconclusive", 0)
            total = passed + failed + inconclusive

            if total > 0:
                # pass_rate
                pr = passed / total
                signals.append(SignalSnapshot(
                    signal_name="screening.pass_rate",
                    raw_value=pr,
                    normalized_value=pr,
                    source_stage="screening",
                    description="Fraction of screening checks that passed",
                ))

                # inconclusive_rate (inverted)
                ir = inconclusive / total
                signals.append(SignalSnapshot(
                    signal_name="screening.inconclusive_rate",
                    raw_value=ir,
                    normalized_value=_clamp01(1.0 - ir),
                    source_stage="screening",
                    description="1 - (inconclusive / total): higher is better",
                ))

            # hard_fail_clarity
            checks = screening_result.get("checks") or []
            has_hard_fail = any(
                c.get("is_hard_fail") and c.get("verdict") == "FAIL"
                for c in checks
            )
            clarity = 0.0 if has_hard_fail else 1.0
            signals.append(SignalSnapshot(
                signal_name="screening.hard_fail_clarity",
                raw_value=clarity,
                normalized_value=clarity,
                source_stage="screening",
                description="1.0 if no hard fails, 0.0 otherwise (data quality signal)",
            ))

        except Exception:
            logger.warning("Error collecting screening signals", exc_info=True)

        return signals

    # ── Assessment signals ───────────────────────────────────────────

    def collect_assessment(
        self, processing_result: Optional[Dict[str, Any]]
    ) -> List[SignalSnapshot]:
        """Collect 3 signals from the assessment / processing result.

        Args:
            processing_result: Assessment result dict from ProcessingStage.

        Returns:
            Up to 3 SignalSnapshot objects.
        """
        signals: List[SignalSnapshot] = []
        if not processing_result:
            return signals

        try:
            # confidence_score
            cs = processing_result.get("confidence_score")
            if cs is not None:
                signals.append(SignalSnapshot(
                    signal_name="assessment.confidence_score",
                    raw_value=float(cs),
                    normalized_value=_clamp01(float(cs)),
                    source_stage="assessment",
                    description="LLM assessment confidence score",
                ))

            # data_gap_penalty (inverted: high = fewer gaps = better)
            data_gaps = processing_result.get("data_gaps") or []
            if data_gaps or cs is not None:
                penalty = 0.0
                severity_weights = {"HIGH": 0.15, "MEDIUM": 0.08, "LOW": 0.03}
                for gap in data_gaps:
                    sev = str(gap.get("severity", "LOW")).upper()
                    penalty += severity_weights.get(sev, 0.03)
                inv = _clamp01(1.0 - penalty)
                signals.append(SignalSnapshot(
                    signal_name="assessment.data_gap_penalty",
                    raw_value=penalty,
                    normalized_value=inv,
                    source_stage="assessment",
                    description="1 - weighted gap penalty: higher is better",
                ))

            # fraud_indicator_penalty (inverted)
            fraud_indicators = processing_result.get("fraud_indicators") or []
            if fraud_indicators or cs is not None:
                penalty = 0.0
                risk_weights = {"HIGH": 0.20, "MEDIUM": 0.10, "LOW": 0.05}
                for fi in fraud_indicators:
                    risk = str(fi.get("risk_level", "LOW")).upper()
                    penalty += risk_weights.get(risk, 0.05)
                inv = _clamp01(1.0 - penalty)
                signals.append(SignalSnapshot(
                    signal_name="assessment.fraud_indicator_penalty",
                    raw_value=penalty,
                    normalized_value=inv,
                    source_stage="assessment",
                    description="1 - weighted fraud indicator penalty: higher is better",
                ))

        except Exception:
            logger.warning("Error collecting assessment signals", exc_info=True)

        return signals

    # ── Coverage verdict concordance ─────────────────────────────────

    def collect_coverage_concordance(
        self,
        coverage_analysis: Optional[Dict[str, Any]],
        verdict: str = "",
    ) -> List[SignalSnapshot]:
        """Compute coverage verdict concordance (DENY only).

        For DENY verdicts, measures how much of the claimed amount
        (by value) is NOT covered -- i.e. how strongly the coverage
        analysis supports the denial.  High concordance means the
        coverage outcome aligns well with the denial decision.

        Only emitted for DENY verdicts; returns empty for other verdicts.

        Args:
            coverage_analysis: CoverageAnalysisResult as dict.
            verdict: Claim verdict (APPROVE, DENY, REFER).

        Returns:
            0 or 1 SignalSnapshot objects.
        """
        signals: List[SignalSnapshot] = []
        if not coverage_analysis or verdict.upper() != "DENY":
            return signals

        try:
            line_items = coverage_analysis.get("line_items") or []
            if not line_items:
                return signals

            total_amount = 0.0
            concordant_amount = 0.0

            for item in line_items:
                price = float(item.get("total_price", 0) or 0)
                if price <= 0:
                    continue
                status = (item.get("coverage_status") or "").lower()
                total_amount += price
                if status == "not_covered":
                    concordant_amount += price

            if total_amount <= 0:
                return signals

            concordance = concordant_amount / total_amount
            signals.append(SignalSnapshot(
                signal_name="coverage.verdict_concordance",
                raw_value=concordance,
                normalized_value=_clamp01(concordance),
                source_stage="coverage",
                description=(
                    "Amount-weighted fraction of NOT_COVERED items "
                    "(higher = stronger denial support)"
                ),
            ))
        except Exception:
            logger.warning("Error collecting coverage concordance", exc_info=True)

        return signals

    # ── Decision signals ─────────────────────────────────────────────

    def collect_decision(
        self, decision_result: Optional[Dict[str, Any]]
    ) -> List[SignalSnapshot]:
        """Collect 2 signals from the decision dossier.

        Args:
            decision_result: DecisionDossier as dict.

        Returns:
            Up to 2 SignalSnapshot objects.
        """
        signals: List[SignalSnapshot] = []
        if not decision_result:
            return signals

        try:
            evals = decision_result.get("clause_evaluations") or []

            # tier1_ratio
            if evals:
                tier1 = sum(
                    1 for e in evals
                    if e.get("evaluability_tier") == 1
                )
                ratio = tier1 / len(evals)
                signals.append(SignalSnapshot(
                    signal_name="decision.tier1_ratio",
                    raw_value=ratio,
                    normalized_value=ratio,
                    source_stage="decision",
                    description="Fraction of clause evaluations at tier 1 (deterministic)",
                ))

            # assumption_reliance (inverted)
            assumptions = decision_result.get("assumptions_used") or []
            unresolved = decision_result.get("unresolved_assumptions") or []
            total_assumptions = len(assumptions)
            if total_assumptions > 0:
                raw = len(unresolved) / total_assumptions
                inv = _clamp01(1.0 - raw)
                signals.append(SignalSnapshot(
                    signal_name="decision.assumption_reliance",
                    raw_value=raw,
                    normalized_value=inv,
                    source_stage="decision",
                    description="1 - (unresolved / total assumptions): higher is better",
                ))
            elif evals:
                # If evaluations exist but no assumptions needed
                signals.append(SignalSnapshot(
                    signal_name="decision.assumption_reliance",
                    raw_value=0.0,
                    normalized_value=1.0,
                    source_stage="decision",
                    description="No assumptions needed (fully deterministic)",
                ))

        except Exception:
            logger.warning("Error collecting decision signals", exc_info=True)

        return signals

    # ── Collect all ──────────────────────────────────────────────────

    def collect_all(
        self,
        extraction_results: Optional[List[Dict[str, Any]]] = None,
        reconciliation_report: Optional[Dict[str, Any]] = None,
        coverage_analysis: Optional[Dict[str, Any]] = None,
        screening_result: Optional[Dict[str, Any]] = None,
        processing_result: Optional[Dict[str, Any]] = None,
        decision_result: Optional[Dict[str, Any]] = None,
        verdict: str = "",
    ) -> List[SignalSnapshot]:
        """Collect all signals from all available stages.

        Args:
            verdict: Claim verdict (APPROVE, DENY, REFER).  Controls
                whether the coverage concordance signal is emitted.

        Returns:
            Flat list of all collected SignalSnapshot objects.
        """
        all_signals: List[SignalSnapshot] = []
        all_signals.extend(self.collect_extraction(extraction_results or []))
        all_signals.extend(self.collect_reconciliation(reconciliation_report))
        all_signals.extend(self.collect_coverage(coverage_analysis))
        all_signals.extend(self.collect_coverage_concordance(coverage_analysis, verdict))
        all_signals.extend(self.collect_screening(screening_result))
        all_signals.extend(self.collect_assessment(processing_result))
        all_signals.extend(self.collect_decision(decision_result))

        # Cross-stage: assumption_density
        # Strongest undiscovered predictor of payout error (r = +0.48).
        # More assumptions per line item = less reliable payout.
        try:
            if decision_result and coverage_analysis:
                assumptions = decision_result.get("assumptions_used") or []
                cov_items = (coverage_analysis.get("line_items") or [])
                n_items = len(cov_items)
                n_assumptions = len(assumptions)
                if n_items > 0:
                    density = n_assumptions / n_items
                    inv = _clamp01(1.0 - density)
                    all_signals.append(SignalSnapshot(
                        signal_name="decision.assumption_density",
                        raw_value=round(density, 4),
                        normalized_value=round(inv, 4),
                        source_stage="decision",
                        description=(
                            f"1 - (assumptions/items): "
                            f"{n_assumptions}/{n_items}"
                        ),
                    ))
        except Exception:
            logger.warning(
                "Error collecting assumption_density signal",
                exc_info=True,
            )

        return all_signals


# ── Helpers ──────────────────────────────────────────────────────────


def _clamp01(v: float) -> float:
    """Clamp a value to [0.0, 1.0]."""
    return max(0.0, min(1.0, v))
