"""
Result Interpreter - Component 4 of the schema-driven architecture.

Responsibility: Translate raw engine output into human-readable decisions.

SOLID Principle: Single Responsibility Principle (SRP)
The Engine decides what happened; the Interpreter decides how to show it.

Separation of Concerns:
- Engine returns raw IDs and codes (e.g., exclusion_triggered: ["watercraft_length"])
- Interpreter maps codes to messages (e.g., "Coverage denied because...")
- Interpreter applies color coding (APPROVED=green, DENIED=red, REFERRAL_NEEDED=orange)
"""

from typing import Dict, Any, List


class ResultInterpreter:
    """
    Interprets raw engine output into rich, human-readable result format.

    Output Structure:
    {
      "summary": {
        "status": "APPROVED" | "DENIED" | "REFERRAL_NEEDED",
        "primary_message": "...",
        "color_code": "green" | "red" | "orange"
      },
      "financials": {
        "applicable_limit": {...},
        "applicable_deductible": {...}
      },
      "reasoning_trace": {
        "triggers": [...],      # Rules that passed
        "red_flags": [...]      # Exclusions triggered
      },
      "metadata": {...}
    }
    """

    def interpret(
        self,
        raw_engine_output: Dict[str, Any],
        policy_rules: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Transform raw engine output into rich result format.

        Args:
            raw_engine_output: Output from IEvaluator.evaluate()
            policy_rules: Optional policy rules for additional context

        Returns:
            Rich result dictionary with summary, financials, reasoning_trace, metadata
        """
        # Extract components from raw output
        limits = raw_engine_output.get("limits", [])
        conditions = raw_engine_output.get("conditions", [])
        exclusions = raw_engine_output.get("exclusions", [])
        deductibles = raw_engine_output.get("deductibles", [])
        metadata = raw_engine_output.get("metadata", {})

        # Determine overall status
        status, primary_message, color_code = self._determine_status(
            limits, conditions, exclusions, deductibles
        )

        # Extract financials
        financials = self._extract_financials(limits, deductibles)

        # Build reasoning trace
        reasoning_trace = self._build_reasoning_trace(conditions, exclusions)

        # Assemble rich result
        result = {
            "summary": {
                "status": status,
                "primary_message": primary_message,
                "color_code": color_code
            },
            "financials": financials,
            "reasoning_trace": reasoning_trace,
            "metadata": metadata
        }

        return result

    def _determine_status(
        self,
        limits: List[Dict],
        conditions: List[Dict],
        exclusions: List[Dict],
        deductibles: List[Dict]
    ) -> tuple[str, str, str]:
        """
        Determine overall claim status based on rule results.

        Decision Logic:
        - DENIED: Any exclusion is TRIGGERED
        - REFERRAL_NEEDED: Any condition is FAIL or INDETERMINATE, or any rule has ERROR
        - APPROVED: All conditions PASS, no exclusions triggered

        Returns:
            Tuple of (status, primary_message, color_code)
        """
        # Check for exclusions
        triggered_exclusions = [
            exc for exc in exclusions
            if exc.get("status") == "TRIGGERED"
        ]

        if triggered_exclusions:
            exclusion_names = ", ".join([exc.get("rule_name", "Unknown") for exc in triggered_exclusions])
            return (
                "DENIED",
                f"Coverage excluded due to: {exclusion_names}",
                "red"
            )

        # Check for failed conditions
        failed_conditions = [
            cond for cond in conditions
            if cond.get("status") in ("FAIL", "INDETERMINATE")
        ]

        if failed_conditions:
            condition_names = ", ".join([cond.get("rule_name", "Unknown") for cond in failed_conditions])
            return (
                "REFERRAL_NEEDED",
                f"Manual review required - conditions not met: {condition_names}",
                "orange"
            )

        # Check for errors
        all_rules = limits + conditions + exclusions + deductibles
        error_rules = [rule for rule in all_rules if rule.get("status") == "ERROR"]

        if error_rules:
            return (
                "REFERRAL_NEEDED",
                f"Manual review required - {len(error_rules)} rule(s) encountered errors",
                "orange"
            )

        # Check if no limits applied
        applied_limits = [lim for lim in limits if lim.get("status") == "APPLIED"]
        if not applied_limits:
            return (
                "REFERRAL_NEEDED",
                "Manual review required - no coverage limits determined",
                "orange"
            )

        # All conditions passed, no exclusions triggered
        return (
            "APPROVED",
            "Claim is eligible for coverage under this policy",
            "green"
        )

    def _extract_financials(
        self,
        limits: List[Dict],
        deductibles: List[Dict]
    ) -> Dict[str, Any]:
        """
        Extract applicable financial amounts from limits and deductibles.

        Args:
            limits: List of limit rule results
            deductibles: List of deductible rule results

        Returns:
            Dictionary with applicable_limit and applicable_deductible
        """
        financials = {
            "applicable_limit": None,
            "applicable_deductible": None
        }

        # Find the highest applied limit
        applied_limits = [
            lim for lim in limits
            if lim.get("status") == "APPLIED" and isinstance(lim.get("result_value"), (int, float))
        ]

        if applied_limits:
            # Take the highest limit (most generous coverage)
            highest_limit = max(applied_limits, key=lambda x: x.get("result_value", 0))
            financials["applicable_limit"] = {
                "amount": highest_limit.get("result_value"),
                "currency": self._extract_currency(highest_limit.get("rule_name", "")),
                "category": highest_limit.get("rule_name", "Coverage Limit")
            }

        # Find the applicable deductible
        applied_deductibles = [
            ded for ded in deductibles
            if ded.get("status") == "APPLIED" and isinstance(ded.get("result_value"), (int, float))
        ]

        if applied_deductibles:
            # Take the first applied deductible
            applicable_ded = applied_deductibles[0]
            financials["applicable_deductible"] = {
                "amount": applicable_ded.get("result_value"),
                "currency": self._extract_currency(applicable_ded.get("rule_name", ""))
            }

        return financials

    def _build_reasoning_trace(
        self,
        conditions: List[Dict],
        exclusions: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Build reasoning trace with triggers (passed rules) and red_flags (exclusions).

        Args:
            conditions: List of condition rule results
            exclusions: List of exclusion rule results

        Returns:
            Dictionary with triggers and red_flags lists
        """
        triggers = []
        red_flags = []

        # Add passed conditions as triggers
        for condition in conditions:
            if condition.get("status") == "PASS":
                triggers.append({
                    "rule_name": condition.get("rule_name", "Unknown"),
                    "status": "PASS",
                    "description": condition.get("reasoning", "Condition met")
                })

        # Add triggered exclusions as red flags
        for exclusion in exclusions:
            if exclusion.get("status") == "TRIGGERED":
                red_flags.append({
                    "rule_name": exclusion.get("rule_name", "Unknown"),
                    "status": "TRIGGERED",
                    "description": exclusion.get("reasoning", "Exclusion applies")
                })

        return {
            "triggers": triggers,
            "red_flags": red_flags
        }

    def _extract_currency(self, text: str) -> str:
        """
        Extract currency code from rule name or description.

        Simple heuristic: look for common currency codes (CAD, USD, EUR, GBP).

        Args:
            text: Rule name or description

        Returns:
            Currency code (default "CAD" if not found)
        """
        common_currencies = ["CAD", "USD", "EUR", "GBP", "AUD", "CHF"]

        text_upper = text.upper()
        for currency in common_currencies:
            if currency in text_upper:
                return currency

        # Default to CAD (common for Canadian insurance)
        return "CAD"
