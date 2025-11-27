"""
Utility to transpile normalized JSON Logic to standard JSON Logic format.

Converts the LLM-friendly normalized format with 'op' and 'args' fields:
    {"op": "==", "args": [{"op": "var", "args": ["claim.cause"]}, "fire"]}

To the standard JSON Logic format:
    {"==": [{"var": "claim.cause"}, "fire"]}

This separation allows the LLM to work with a strict schema while still
producing standard JSON Logic output for existing interpreters.
"""

from typing import Dict, Any, List, Union
import logging

logger = logging.getLogger(__name__)


def to_standard_json_logic(node: Dict[str, Any]) -> Union[Dict[str, Any], Any]:
    """
    Convert a normalized LogicNode to standard JSON Logic format.

    Args:
        node: Dictionary representing a LogicNode with 'op' and 'args' keys,
              or a primitive value (str, int, float, bool, None)

    Returns:
        Standard JSON Logic object or primitive value

    Example:
        >>> node = {"op": "==", "args": [{"op": "var", "args": ["claim.cause"]}, "fire"]}
        >>> to_standard_json_logic(node)
        {"==": [{"var": "claim.cause"}, "fire"]}
    """
    # Base case: if not a dict, it's a primitive value
    if not isinstance(node, dict):
        return node

    # Check if this is a LogicNode (has 'op' and 'args')
    if "op" not in node or "args" not in node:
        # Not a LogicNode, return as-is (shouldn't happen with strict schema)
        logger.warning(f"Unexpected node structure (missing op/args): {node}")
        return node

    op = node["op"]
    args = node["args"]

    # Recursively convert all arguments
    converted_args = [to_standard_json_logic(arg) for arg in args]

    # Return standard JSON Logic format: {operator: [args]}
    return {op: converted_args}


def transpile_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transpile a RuleDefinition from normalized to standard JSON Logic.

    Args:
        rule: Dictionary representing a RuleDefinition with 'logic' field

    Returns:
        Rule dictionary with transpiled 'logic' field

    Example:
        >>> rule = {
        ...     "id": "rule_001",
        ...     "description": "Fire coverage",
        ...     "source_ref": "Section 2.1",
        ...     "logic": {"op": "==", "args": [{"op": "var", "args": ["claim.cause"]}, "fire"]}
        ... }
        >>> transpiled = transpile_rule(rule)
        >>> transpiled["logic"]
        {"==": [{"var": "claim.cause"}, "fire"]}
    """
    transpiled_rule = rule.copy()
    transpiled_rule["logic"] = to_standard_json_logic(rule["logic"])
    return transpiled_rule


def transpile_policy_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transpile a complete PolicyAnalysis from normalized to standard JSON Logic.

    Args:
        analysis: Dictionary representing PolicyAnalysis with 'rules' list

    Returns:
        Analysis dictionary with all rules transpiled

    Example:
        >>> analysis = {
        ...     "chain_of_thought": "Analysis of fire coverage...",
        ...     "rules": [
        ...         {
        ...             "id": "rule_001",
        ...             "description": "Fire coverage",
        ...             "source_ref": "Section 2.1",
        ...             "logic": {"op": "==", "args": [{"op": "var", "args": ["claim.cause"]}, "fire"]}
        ...         }
        ...     ]
        ... }
        >>> transpiled = transpile_policy_analysis(analysis)
        >>> transpiled["rules"][0]["logic"]
        {"==": [{"var": "claim.cause"}, "fire"]}
    """
    transpiled_analysis = analysis.copy()
    transpiled_analysis["rules"] = [
        transpile_rule(rule) for rule in analysis.get("rules", [])
    ]
    return transpiled_analysis
