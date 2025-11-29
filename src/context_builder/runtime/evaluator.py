"""
Logic Adaptor - Component 3 of the schema-driven architecture.

Responsibility: Orchestrate the execution of rules.

SOLID Principle: Dependency Inversion Principle (DIP)
High-level modules (UI/Workflow) do not depend on low-level modules (json-logic library).
Both depend on the IEvaluator abstraction.

Benefit: If we switch from json-logic to C++ engine or cloud API, the rest of the
application (UI/Controllers) remains untouched.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import time

try:
    from json_logic import jsonLogic
except ImportError:
    raise ImportError(
        "json-logic library not found. Install with: uv add json-logic"
    )


class IEvaluator(ABC):
    """
    Abstract interface for rule evaluation engines.

    Defines the contract for executing policy rules against claim data.
    Stateless: accepts (Rules + Data) and returns (Decision).
    """

    @abstractmethod
    def evaluate(self, policy_rules: Dict[str, Any], claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate policy rules against claim data.

        Args:
            policy_rules: Logic JSON loaded from file (contains transpiled_data.rules)
            claim_data: Nested claim data (output from ClaimMapper.inflate())

        Returns:
            Raw evaluation result with structure:
            {
                "limits": [...],        # Rules of type "limit" with results
                "conditions": [...],    # Rules of type "condition" with results
                "exclusions": [...],    # Rules of type "exclusion" with results
                "deductibles": [...],   # Rules of type "deductible" with results
                "metadata": {...}       # Execution metadata
            }
        """
        pass


class NeuroSymbolicEvaluator(IEvaluator):
    """
    Concrete implementation using json-logic library.

    Executes JSON Logic rules against claim data and aggregates results by rule type.
    """

    def evaluate(self, policy_rules: Dict[str, Any], claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all rules using json-logic and aggregate by type.

        Args:
            policy_rules: Logic JSON with transpiled_data.rules
            claim_data: Nested claim data from ClaimMapper

        Returns:
            Raw evaluation result aggregated by rule type
        """
        start_time = time.time()

        # Extract rules from policy
        rules = policy_rules.get("transpiled_data", {}).get("rules", [])

        # Aggregate results by type
        results = {
            "limits": [],
            "conditions": [],
            "exclusions": [],
            "deductibles": [],
            "metadata": {
                "engine_version": "1.0.0",
                "total_rules": len(rules),
                "execution_time_ms": 0
            }
        }

        # Execute each rule
        for rule in rules:
            rule_id = rule.get("id", "unknown")
            rule_name = rule.get("name", "Unknown Rule")
            rule_type = rule.get("type", "unknown")
            logic_def = rule.get("logic", {})
            reasoning = rule.get("reasoning", "")
            source_ref = rule.get("source_ref", "")

            try:
                # Execute the JSON Logic
                result_value = jsonLogic(logic_def, claim_data)

                # Build result object
                rule_result = {
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "status": self._determine_status(rule_type, result_value),
                    "result_value": result_value,
                    "reasoning": reasoning,
                    "source_ref": source_ref
                }

                # Add to appropriate category
                if rule_type == "limit":
                    results["limits"].append(rule_result)
                elif rule_type == "condition":
                    results["conditions"].append(rule_result)
                elif rule_type == "exclusion":
                    results["exclusions"].append(rule_result)
                elif rule_type == "deductible":
                    results["deductibles"].append(rule_result)

            except Exception as e:
                # Log error but continue processing other rules
                error_result = {
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "status": "ERROR",
                    "error": str(e),
                    "reasoning": reasoning,
                    "source_ref": source_ref
                }

                # Still add to appropriate category for visibility
                if rule_type == "limit":
                    results["limits"].append(error_result)
                elif rule_type == "condition":
                    results["conditions"].append(error_result)
                elif rule_type == "exclusion":
                    results["exclusions"].append(error_result)
                elif rule_type == "deductible":
                    results["deductibles"].append(error_result)

        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        results["metadata"]["execution_time_ms"] = execution_time_ms

        return results

    def _determine_status(self, rule_type: str, result_value: Any) -> str:
        """
        Determine rule status based on type and result value.

        Logic:
        - For limits/deductibles: "APPLIED" if numeric value returned
        - For conditions: "PASS" if true, "FAIL" if false
        - For exclusions: "TRIGGERED" if true, "NOT_TRIGGERED" if false

        Args:
            rule_type: Type of rule (limit, condition, exclusion, deductible)
            result_value: Result from JSON Logic execution

        Returns:
            Status string
        """
        if rule_type in ("limit", "deductible"):
            if isinstance(result_value, (int, float)) and result_value > 0:
                return "APPLIED"
            else:
                return "NOT_APPLIED"

        elif rule_type == "condition":
            if result_value is True:
                return "PASS"
            elif result_value is False:
                return "FAIL"
            else:
                return "INDETERMINATE"

        elif rule_type == "exclusion":
            if result_value is True:
                return "TRIGGERED"
            elif result_value is False:
                return "NOT_TRIGGERED"
            else:
                return "INDETERMINATE"

        else:
            return "UNKNOWN"
