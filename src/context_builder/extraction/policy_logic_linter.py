"""
Policy Logic Linter - Runtime guardrail for validating extracted policy logic.

Validates normalized JSON logic against:
- Syntax rules (NULL bugs, operator arg counts, tautologies)
- UDM vocabulary (schema-defined paths + attributes.* namespaces)
- Schema enum constraints (strict validation)

Runs after Pydantic validation as an in-memory quality gate.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ViolationType(str, Enum):
    """Types of validation violations."""
    NULL_BUG = "NULL_BUG"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    VOCAB_ERROR = "VOCAB_ERROR"
    ENUM_ERROR = "ENUM_ERROR"


class Severity(str, Enum):
    """Violation severity levels."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"


@dataclass
class ValidationError:
    """Structured validation error."""
    rule_id: str
    rule_name: str
    type: ViolationType
    severity: Severity
    message: str
    variable: Optional[str] = None
    invalid_value: Optional[Any] = None
    operator: Optional[str] = None
    location: Optional[str] = None  # JSON path in logic tree


@dataclass
class ValidationReport:
    """Complete validation report with summary and violations."""
    summary: Dict[str, int]
    violations: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": self.summary,
            "violations": [asdict(v) for v in self.violations] if isinstance(self.violations[0] if self.violations else None, ValidationError) else self.violations
        }


# Operator argument count validation rules
OPERATOR_ARG_COUNTS = {
    # Comparison operators (binary)
    "==": 2,
    "!=": 2,
    ">": 2,
    ">=": 2,
    "<": 2,
    "<=": 2,

    # Logical operators
    "and": lambda n: n >= 2,  # Variadic: at least 2 args
    "or": lambda n: n >= 2,   # Variadic: at least 2 args
    "not": 1,

    # Membership
    "in": 2,  # [value, list]

    # Arithmetic (for limit/deductible calculations)
    "+": lambda n: n >= 2,
    "-": lambda n: n >= 2,
    "*": lambda n: n >= 2,
    "/": 2,
    "min": lambda n: n >= 1,
    "max": lambda n: n >= 1,

    # Conditional
    "if": 3,  # [condition, then_value, else_value]
}


def _load_schema_enums(schema_path: Optional[str] = None) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """
    Load enum definitions and valid UDM paths from extended schema.

    Args:
        schema_path: Path to extended_standard_claim_schema.json
                    If None, auto-detects from package structure

    Returns:
        Tuple of (schema_enums dict, valid_paths set)
    """
    if schema_path is None:
        schema_path = str(Path(__file__).parent.parent / "schemas" / "extended_standard_claim_schema.json")

    if not Path(schema_path).exists():
        logger.warning(f"Schema file not found: {schema_path}")
        return {}, set()

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)

        schema_enums = {}
        valid_paths = set()

        def extract_schema_info(obj: Dict[str, Any], path: str = ""):
            """Recursively extract enums and valid paths from schema."""
            if not isinstance(obj, dict):
                return

            # Add current path to valid paths
            if path:
                valid_paths.add(path)

            # Check for enum
            if "enum" in obj:
                schema_enums[path] = set(obj["enum"])

            # Handle additionalProperties (dynamic attributes namespace)
            if "additionalProperties" in obj and isinstance(obj["additionalProperties"], dict):
                # Allow any key under this path (e.g., claim.header.attributes.*)
                valid_paths.add(f"{path}.*")

            # Recurse into properties
            if "properties" in obj:
                for key, value in obj["properties"].items():
                    new_path = f"{path}.{key}" if path else key
                    extract_schema_info(value, new_path)

            # Handle array items
            if obj.get("type") == "array" and "items" in obj:
                items = obj["items"]
                if isinstance(items, dict):
                    # Array notation: path[]
                    array_path = f"{path}[]"
                    valid_paths.add(array_path)

                    if "properties" in items:
                        for key, value in items["properties"].items():
                            item_path = f"{array_path}.{key}"
                            extract_schema_info(value, item_path)

        extract_schema_info(schema)

        logger.debug(f"Loaded {len(schema_enums)} enum definitions and {len(valid_paths)} valid paths from schema")
        return schema_enums, valid_paths

    except Exception as e:
        logger.warning(f"Error loading schema: {e}")
        return {}, set()


def _is_var_node(node: Any) -> bool:
    """Check if node is a variable reference (normalized format)."""
    if isinstance(node, dict):
        # Normalized format: {"op": "var", "args": ["claim.x"]}
        if node.get("op") == "var":
            return True
    return False


def _get_var_name(node: Dict) -> str:
    """Extract variable name from variable node (normalized format)."""
    if node.get("op") == "var":
        args = node.get("args", [])
        return args[0] if args else "unknown"
    return "unknown"


def _is_valid_vocab(var_path: str, valid_paths: Set[str]) -> bool:
    """
    Check if variable path is valid according to tiered validation rules.

    Validation hierarchy (case-sensitive):
    1. Exact UDM match: Standard schema paths (e.g., claim.header.jurisdiction)
    2. Wildcard match: Schema paths with .* (e.g., claim.header.attributes.*)
    3. Array notation: Paths with [] (e.g., claim.parties.claimants[].role)
    4. Custom variables: Tier 3 custom concepts (claim.custom.*)
    5. Attributes pattern: Policy-specific attributes anywhere (*.attributes.*)

    Args:
        var_path: Variable path to validate (e.g., "claim.header.jurisdiction")
        valid_paths: Set of valid paths from schema (includes .* wildcards)

    Returns:
        True if path is valid, False otherwise
    """
    # Check 1: Exact UDM match
    if var_path in valid_paths:
        logger.debug(f"Variable '{var_path}' passed validation: exact UDM match")
        return True

    # Check 2: Wildcard match for schema-defined dynamic attributes
    # Example: claim.header.attributes.trip_type matches claim.header.attributes.*
    path_parts = var_path.split(".")
    for i in range(len(path_parts)):
        prefix = ".".join(path_parts[:i+1])
        if f"{prefix}.*" in valid_paths:
            logger.debug(f"Variable '{var_path}' passed validation: wildcard match ({prefix}.*)")
            return True

    # Check 3: Array notation (e.g., claim.parties.claimants[].role)
    # Replace [] with exact match
    if "[]" not in var_path:
        # Try adding [] at different positions
        for i in range(len(path_parts)):
            test_path = ".".join(path_parts[:i]) + "[]." + ".".join(path_parts[i:])
            if test_path in valid_paths or _is_valid_vocab(test_path, valid_paths):
                logger.debug(f"Variable '{var_path}' passed validation: array notation match")
                return True

    # Check 4: Tier 3 Custom Variables (claim.custom.*)
    # Allows policy-specific concepts not in standard schema
    if var_path.startswith("claim.custom."):
        logger.debug(f"Variable '{var_path}' passed validation: claim.custom.* pattern (Tier 3)")
        return True

    # Check 5: Attributes pattern anywhere in path (*.attributes.*)
    # Allows policy-specific attributes in any context (incident, coverage, claimant, etc.)
    if ".attributes." in var_path:
        logger.debug(f"Variable '{var_path}' passed validation: .attributes.* pattern (policy-specific)")
        return True

    return False


def _is_tautology(op: str, args: List[Any]) -> bool:
    """
    Detect tautological comparisons (always true or always false).

    Examples:
    - {"op": "==", "args": [5, 5]} -> True (always true)
    - {"op": "!=", "args": ["foo", "foo"]} -> True (always false)
    - {"op": "in", "args": ["x", []]} -> True (always false)
    """
    if op == "==" and len(args) == 2:
        # Both args are constants and equal
        if not _is_var_node(args[0]) and not _is_var_node(args[1]):
            return args[0] == args[1]

    elif op == "!=" and len(args) == 2:
        # Both args are constants and equal (always false)
        if not _is_var_node(args[0]) and not _is_var_node(args[1]):
            return args[0] == args[1]

    elif op == "in" and len(args) == 2:
        # Checking membership in empty list (always false)
        if isinstance(args[1], list) and len(args[1]) == 0:
            return True

    return False


def _detect_common_patterns(node: Dict, rule_id: str, rule_name: str, location: str) -> List[ValidationError]:
    """
    Detect common LLM failure patterns and provide specific remediation.

    Patterns detected:
    - Operator as string value (e.g., comparing to ">=" instead of using >= operator)
    - Double variable nesting (e.g., {"op": "var", "args": [{"op": "var", ...}]})

    Args:
        node: Logic node to check
        rule_id: ID of rule being validated
        rule_name: Name of rule being validated
        location: JSON path location in tree

    Returns:
        List of ValidationError objects for detected patterns
    """
    violations = []

    if not isinstance(node, dict) or "op" not in node:
        return violations

    op = node.get("op")
    args = node.get("args", [])

    # Pattern 1: Operator as string value
    if op in ["==", "!=", "in"]:
        operator_strings = {">=", "<=", ">", "<", "==", "!=", "if", "and", "or", "in", "not"}
        for arg in args:
            if isinstance(arg, str) and arg in operator_strings:
                violations.append(ValidationError(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    type=ViolationType.SYNTAX_ERROR,
                    severity=Severity.CRITICAL,
                    message=f"TYPE ERROR: You are using an operator ('{arg}') as a string value. You likely meant to use the operator itself, not compare against it. Example: Instead of {{'op': '==', 'args': [var, '>=']}} (comparing to string '>='), use {{'op': '>=', 'args': [var, value]}} (actual comparison).",
                    operator=op,
                    location=location,
                    invalid_value=arg
                ))

    # Pattern 2: Double variable nesting
    if op == "var" and len(args) > 0:
        first_arg = args[0]
        if isinstance(first_arg, dict) and first_arg.get("op") == "var":
            violations.append(ValidationError(
                rule_id=rule_id,
                rule_name=rule_name,
                type=ViolationType.SYNTAX_ERROR,
                severity=Severity.CRITICAL,
                message=f"SYNTAX ERROR: Double-nested variables detected at {location}. You don't need to wrap a 'var' operator inside another 'var' operator. Simplify: Instead of {{'op': 'var', 'args': [{{'op': 'var', 'args': ['name']}}]}}, use {{'op': 'var', 'args': ['name']}}.",
                operator=op,
                location=location
            ))

    return violations


def _validate_syntax(node: Dict, rule_id: str, rule_name: str, location: str = "root") -> List[ValidationError]:
    """
    Validate syntax of a single logic node.

    Checks:
    - NULL bug: {"op": "in", "args": [var, [..., null]]}
    - Operator argument counts
    - Tautologies

    Args:
        node: Logic node to validate
        rule_id: ID of rule being validated
        rule_name: Name of rule being validated
        location: JSON path location in tree (for error reporting)

    Returns:
        List of ValidationError objects
    """
    violations = []

    if not isinstance(node, dict) or "op" not in node:
        return violations

    op = node.get("op")
    args = node.get("args", [])

    # Check NULL bug
    if op == "in" and len(args) >= 2:
        second_arg = args[1]
        # Check if second arg IS null or CONTAINS null
        if second_arg is None:
            violations.append(ValidationError(
                rule_id=rule_id,
                rule_name=rule_name,
                type=ViolationType.NULL_BUG,
                severity=Severity.CRITICAL,
                message="CRITICAL ERROR: You output 'null' as the list argument in an 'in' operator. This crashes the execution engine. You MUST replace 'null' with an explicit list of Custom Strings describing the missing concept (e.g., ['claim.custom.unspecified_cause']).",
                operator=op,
                location=location,
                invalid_value=None
            ))
        elif isinstance(second_arg, list) and None in second_arg:
            violations.append(ValidationError(
                rule_id=rule_id,
                rule_name=rule_name,
                type=ViolationType.NULL_BUG,
                severity=Severity.CRITICAL,
                message="CRITICAL ERROR: You included 'null' inside a list for the 'in' operator. This crashes the execution engine. You MUST replace 'null' with an explicit Custom String describing the missing concept (e.g., 'claim.custom.unspecified_cause').",
                operator=op,
                location=location,
                invalid_value=None
            ))

    # Check operator argument counts
    if op in OPERATOR_ARG_COUNTS:
        expected = OPERATOR_ARG_COUNTS[op]
        actual = len(args)

        # Handle callable validators (variadic operators)
        if callable(expected):
            if not expected(actual):
                # Provide operator-specific instructions
                if op in ["and", "or"]:
                    message = f"SYNTAX ERROR: The '{op}' operator requires at least 2 arguments. You provided {actual}. This may indicate incorrect nesting or missing arguments."
                else:
                    message = f"SYNTAX ERROR: The '{op}' operator is malformed. It requires at least 2 arguments. You provided {actual}. Check for nesting errors or missing arguments."

                violations.append(ValidationError(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    type=ViolationType.SYNTAX_ERROR,
                    severity=Severity.CRITICAL,
                    message=message,
                    operator=op,
                    location=location
                ))
        elif expected != actual:
            # Provide operator-specific prescriptive instructions
            if op == "if":
                message = f"SYNTAX ERROR: The 'if' operator strictly requires exactly 3 arguments: [condition, true_value, false_value]. You provided {actual}. Common mistake: You likely flattened multiple conditions directly into the 'if' args. Wrap multiple conditions in an 'and' or 'or' operator. Example: {{'op': 'if', 'args': [{{'op': 'and', 'args': [cond1, cond2]}}, true_val, false_val]}}"
            elif op == "in":
                message = f"SYNTAX ERROR: The 'in' operator requires exactly 2 arguments: [element, list_of_values]. You provided {actual}. Ensure the second argument is a list, not individual values."
            elif op in ["==", "!=", ">", ">=", "<", "<="]:
                message = f"SYNTAX ERROR: The comparison operator '{op}' requires exactly 2 arguments: [left, right]. You provided {actual}."
            else:
                message = f"SYNTAX ERROR: The '{op}' operator expects exactly {expected} arguments, got {actual}. Check your logic tree structure for nesting errors."

            violations.append(ValidationError(
                rule_id=rule_id,
                rule_name=rule_name,
                type=ViolationType.SYNTAX_ERROR,
                severity=Severity.CRITICAL,
                message=message,
                operator=op,
                location=location
            ))

    # Check tautologies
    if _is_tautology(op, args):
        violations.append(ValidationError(
            rule_id=rule_id,
            rule_name=rule_name,
            type=ViolationType.SYNTAX_ERROR,
            severity=Severity.WARNING,
            message=f"LOGIC WARNING: This rule compares constant values that always produce the same result (e.g., true == true or 'x' in []). This creates an 'Always True' or 'Always False' rule. If you meant to flag a concept you can't test programmatically, use the 'human_flag' operator instead. Otherwise, replace with actual variable comparisons.",
            operator=op,
            location=location
        ))

    # Check for common LLM failure patterns
    pattern_violations = _detect_common_patterns(node, rule_id, rule_name, location)
    violations.extend(pattern_violations)

    return violations


def _validate_vocabulary(
    node: Dict,
    rule_id: str,
    rule_name: str,
    valid_paths: Set[str],
    schema_enums: Dict[str, Set[str]],
    location: str = "root"
) -> List[ValidationError]:
    """
    Validate UDM vocabulary and enum constraints.

    Checks:
    - Variable paths exist in schema or follow attributes.* pattern
    - Values match schema enums (strict validation)

    Args:
        node: Logic node to validate
        rule_id: ID of rule being validated
        rule_name: Name of rule being validated
        valid_paths: Set of valid UDM paths from schema
        schema_enums: Dict mapping paths to valid enum values
        location: JSON path location in tree

    Returns:
        List of ValidationError objects
    """
    violations = []

    if not isinstance(node, dict):
        return violations

    # Check variable references
    if _is_var_node(node):
        var_name = _get_var_name(node)

        # Validate against schema vocabulary
        if not _is_valid_vocab(var_name, valid_paths):
            # Extract the last part of the variable name for suggestions
            var_suffix = var_name.split('.')[-1] if '.' in var_name else var_name

            violations.append(ValidationError(
                rule_id=rule_id,
                rule_name=rule_name,
                type=ViolationType.VOCAB_ERROR,
                severity=Severity.CRITICAL,
                message=f"UNKNOWN VARIABLE: '{var_name}' does not exist in the Standard UDM. OPTIONS: (1) Check for spelling errors against the UDM Context. (2) If this is a policy-specific attribute (e.g., trip type, equipment type), rename it to 'incident.attributes.{var_suffix}'. (3) If it is a completely new insurance concept not in the standard schema, rename it to 'claim.custom.{var_suffix}'.",
                variable=var_name,
                location=location
            ))

    # Check enum values in comparison operators
    if "op" in node:
        op = node.get("op")
        args = node.get("args", [])

        if op in ["==", "!=", "in"] and len(args) >= 2:
            var_node = None
            value = None

            # Identify variable and value
            if _is_var_node(args[0]):
                var_node = args[0]
                value = args[1]
            elif _is_var_node(args[1]):
                var_node = args[1]
                value = args[0]

            if var_node:
                var_name = _get_var_name(var_node)

                # Check enum constraint (strict validation)
                if var_name in schema_enums:
                    valid_values = schema_enums[var_name]

                    # Handle list values (for 'in' operator)
                    values_to_check = value if isinstance(value, list) else [value]

                    for val in values_to_check:
                        if val is None:
                            continue  # NULL bugs caught by syntax validation

                        if val not in valid_values:
                            violations.append(ValidationError(
                                rule_id=rule_id,
                                rule_name=rule_name,
                                type=ViolationType.ENUM_ERROR,
                                severity=Severity.CRITICAL,
                                message=f"INVALID ENUM VALUE: '{val}' is not allowed for '{var_name}'. Valid options are: {sorted(valid_values)}. INSTRUCTIONS: Select the closest semantic match from the valid list OR use a Tier 3 Custom Variable (e.g., 'claim.custom.{val}') if this concept is legally distinct and cannot be mapped to existing values.",
                                variable=var_name,
                                invalid_value=val,
                                location=location
                            ))

    return violations


def _traverse_and_validate(
    node: Any,
    rule_id: str,
    rule_name: str,
    valid_paths: Set[str],
    schema_enums: Dict[str, Set[str]],
    location: str = "root"
) -> List[ValidationError]:
    """
    Recursively traverse logic tree and collect all violations.

    Args:
        node: Current node in logic tree
        rule_id: ID of rule being validated
        rule_name: Name of rule being validated
        valid_paths: Set of valid UDM paths
        schema_enums: Dict of enum constraints
        location: Current location in tree

    Returns:
        List of all ValidationError objects found
    """
    violations = []

    # Handle lists
    if isinstance(node, list):
        for i, item in enumerate(node):
            violations.extend(_traverse_and_validate(
                item, rule_id, rule_name, valid_paths, schema_enums, f"{location}[{i}]"
            ))
        return violations

    # Handle non-dict nodes
    if not isinstance(node, dict):
        return violations

    # Validate current node (syntax)
    violations.extend(_validate_syntax(node, rule_id, rule_name, location))

    # Validate current node (vocabulary)
    violations.extend(_validate_vocabulary(node, rule_id, rule_name, valid_paths, schema_enums, location))

    # Recurse into args
    if "op" in node and "args" in node:
        args = node["args"]
        for i, arg in enumerate(args):
            violations.extend(_traverse_and_validate(
                arg, rule_id, rule_name, valid_paths, schema_enums, f"{location}.args[{i}]"
            ))

    return violations


def validate_rules(
    rules_data: Dict[str, Any],
    schema_path: Optional[str] = None
) -> ValidationReport:
    """
    Validate extracted policy rules (in-memory, exhaustive).

    Main entry point for PolicyLinter. Validates normalized JSON logic after
    Pydantic validation as a runtime guardrail.

    Args:
        rules_data: Dictionary containing rules (from PolicyAnalysis.model_dump())
                   Expected formats:
                   - {"rules": [{"id": ..., "logic": {...}}, ...]}
                   - {"extracted_data": {"rules": [...]}} (file format)
        schema_path: Optional path to extended_standard_claim_schema.json

    Returns:
        ValidationReport with summary and detailed violations

    Example:
        >>> report = validate_rules(policy_analysis_dict)
        >>> if report.summary["violations"] > 0:
        ...     logger.warning(f"Found {report.summary['violations']} violations")
    """
    # Load schema enums and valid paths
    schema_enums, valid_paths = _load_schema_enums(schema_path)

    # Extract rules list (handle both direct and wrapped formats)
    if "extracted_data" in rules_data:
        # File format: {"extracted_data": {"rules": [...]}}
        rules = rules_data["extracted_data"].get("rules", [])
    else:
        # Direct format: {"rules": [...]}
        rules = rules_data.get("rules", [])

    # Collect all violations (exhaustive)
    all_violations = []

    for rule in rules:
        rule_id = rule.get("id", "unknown")
        rule_name = rule.get("name", "unknown")
        logic_tree = rule.get("logic", {})

        # Validate this rule's logic tree
        rule_violations = _traverse_and_validate(
            logic_tree,
            rule_id,
            rule_name,
            valid_paths,
            schema_enums,
            location=f"rule[{rule_id}].logic"
        )

        all_violations.extend(rule_violations)

    # Build summary
    summary = {
        "total_rules": len(rules),
        "violations": len(all_violations),
        "clean_rules": len(rules) - len(set(v.rule_id for v in all_violations)),
        "critical_violations": sum(1 for v in all_violations if v.severity == Severity.CRITICAL),
        "warnings": sum(1 for v in all_violations if v.severity == Severity.WARNING)
    }

    # Convert violations to dicts for JSON serialization
    violation_dicts = [asdict(v) for v in all_violations]

    # Create report
    report = ValidationReport(
        summary=summary,
        violations=violation_dicts
    )

    logger.info(
        f"Validation complete: {summary['violations']} violations found "
        f"({summary['critical_violations']} critical, {summary['warnings']} warnings)"
    )

    return report


def save_validation_report(
    report: ValidationReport,
    output_path: str,
    retry_count: int = 0,
    filename: Optional[str] = None
) -> None:
    """
    Save validation report to JSON file.

    Args:
        report: ValidationReport to save
        output_path: Path to output JSON file
        retry_count: Retry attempt number (for filename, ignored if filename provided)
        filename: Optional custom filename. If None, uses default pattern.

    Example filenames:
        - Default: policy_logic_audit_report_retry_0.json
        - Custom: audit_report.json, chunk_001_audit_report.json
    """
    # Build filename
    output_path_obj = Path(output_path)
    if filename is None:
        # Default pattern with retry count
        filename = f"policy_logic_audit_report_retry_{retry_count}.json"

    full_path = output_path_obj.parent / filename

    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"Saved validation report to: {full_path}")

    except Exception as e:
        logger.error(f"Failed to save validation report: {e}")
