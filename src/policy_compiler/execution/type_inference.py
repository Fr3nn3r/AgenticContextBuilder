"""Type Inference Engine for Form Generator.

Analyzes JSON Logic usage patterns to infer field types with conservative rules.
"""

import re
from typing import Dict, Set, List, Any, Optional
from collections import defaultdict


class FieldUsage:
    """Tracks usage patterns for a single variable."""

    def __init__(self, var_path: str):
        self.var_path = var_path
        self.operators_used: Set[str] = set()
        self.compared_values: List[Any] = []
        self.context_usage: List[str] = []  # if_condition, logical, arithmetic

    def add_comparison(self, operator: str, value: Any):
        """Record a comparison operation."""
        self.operators_used.add(operator)
        if value is not None:
            self.compared_values.append(value)

    def add_context(self, context: str):
        """Record usage context (e.g., 'if_condition', 'logical')."""
        self.context_usage.append(context)


class TypeInferenceEngine:
    """Infers field types from JSON Logic usage patterns."""

    # Operator categories
    BOOLEAN_OPERATORS = {"and", "or", "not", "!"}
    COMPARISON_OPERATORS = {"==", "!=", ">", ">=", "<", "<="}
    NUMERIC_OPERATORS = {"+", "-", "*", "/", "%", "min", "max"}
    ARRAY_OPERATORS = {"in", "map", "filter", "reduce", "all", "some", "none"}

    # Date/time field name patterns
    DATE_PATTERNS = [
        r".*_at$",  # created_at, updated_at, loss_at
        r".*_date$",  # start_date, end_date
        r"^date_.*",  # date_of_loss
    ]

    def __init__(self):
        self.field_usage: Dict[str, FieldUsage] = {}

    def analyze_logic(self, logic_node: Any, parent_context: Optional[str] = None) -> None:
        """Recursively analyze JSON Logic tree to collect usage patterns.

        Supports both formats:
        - Normalized: {"op": "var", "args": ["path"]}
        - JsonLogic: {"var": ["path"]} or {"var": "path"}

        Args:
            logic_node: Current node in logic tree (dict, list, or scalar)
            parent_context: Context from parent operator (e.g., 'if_condition')
        """
        if isinstance(logic_node, dict):
            # Check if this is normalized format (has "op" key)
            if "op" in logic_node:
                self._analyze_normalized_format(logic_node, parent_context)
            else:
                # JsonLogic format: operator is the key
                self._analyze_jsonlogic_format(logic_node, parent_context)

        elif isinstance(logic_node, list):
            # Recurse into list items
            for item in logic_node:
                self.analyze_logic(item, parent_context)

    def _analyze_normalized_format(self, logic_node: dict, parent_context: Optional[str]) -> None:
        """Analyze normalized format: {"op": "...", "args": [...]}."""
        op = logic_node.get("op")
        args = logic_node.get("args", [])

        if op == "var":
            # Variable reference - record usage
            var_path = args[0] if args else None
            if var_path and isinstance(var_path, str):
                self._record_var_usage(var_path, parent_context)

        elif op in self.COMPARISON_OPERATORS:
            # Comparison: extract variable and compared value
            self._analyze_comparison(op, args, parent_context)

        elif op in self.BOOLEAN_OPERATORS:
            # Logical operators
            for arg in args:
                self.analyze_logic(arg, "logical")

        elif op in self.NUMERIC_OPERATORS:
            # Arithmetic operators
            for arg in args:
                self.analyze_logic(arg, "arithmetic")

        elif op == "if":
            # If: [condition, true_value, false_value]
            if len(args) >= 1:
                self.analyze_logic(args[0], "if_condition")
            if len(args) >= 2:
                self.analyze_logic(args[1], parent_context)
            if len(args) >= 3:
                self.analyze_logic(args[2], parent_context)

        elif op == "in":
            # In: [element, list]
            if len(args) >= 2:
                self.analyze_logic(args[0], "in_element")
                # Extract enum options from list
                if isinstance(args[1], list):
                    self._analyze_in_operator(args[0], args[1])

        else:
            # Generic: recurse into all args
            for arg in args:
                self.analyze_logic(arg, parent_context)

    def _analyze_jsonlogic_format(self, logic_node: dict, parent_context: Optional[str]) -> None:
        """Analyze JsonLogic format: {"operator": [...]}."""
        # In JsonLogic, each key is an operator
        for op, value in logic_node.items():
            # Normalize value to list
            args = value if isinstance(value, list) else [value]

            if op == "var":
                # Variable reference
                var_path = args[0] if args and isinstance(args[0], str) else None
                if var_path:
                    self._record_var_usage(var_path, parent_context)

            elif op in self.COMPARISON_OPERATORS:
                # Comparison
                self._analyze_comparison(op, args, parent_context)

            elif op in self.BOOLEAN_OPERATORS:
                # Logical operators
                for arg in args:
                    self.analyze_logic(arg, "logical")

            elif op in self.NUMERIC_OPERATORS:
                # Arithmetic operators
                for arg in args:
                    self.analyze_logic(arg, "arithmetic")

            elif op == "if":
                # If: [condition, true_value, false_value]
                if len(args) >= 1:
                    self.analyze_logic(args[0], "if_condition")
                if len(args) >= 2:
                    self.analyze_logic(args[1], parent_context)
                if len(args) >= 3:
                    self.analyze_logic(args[2], parent_context)

            elif op == "in":
                # In: [element, list]
                if len(args) >= 2:
                    self.analyze_logic(args[0], "in_element")
                    # Extract enum options from list
                    if isinstance(args[1], list):
                        self._analyze_in_operator(args[0], args[1])

            else:
                # Generic: recurse into all args
                for arg in args:
                    self.analyze_logic(arg, parent_context)

    def _record_var_usage(self, var_path: str, context: Optional[str]):
        """Record variable usage in a context."""
        if var_path not in self.field_usage:
            self.field_usage[var_path] = FieldUsage(var_path)

        if context:
            self.field_usage[var_path].add_context(context)

    def _analyze_comparison(self, operator: str, args: List[Any], parent_context: Optional[str]):
        """Analyze comparison operator to extract variable and value.

        Supports both formats:
        - Normalized: {"op": "var", "args": ["path"]}
        - JsonLogic: {"var": ["path"]} or {"var": "path"}
        """
        if len(args) < 2:
            return

        # Determine which arg is the variable
        var_arg = None
        value_arg = None

        # Check if first arg is a var (normalized format)
        if isinstance(args[0], dict) and args[0].get("op") == "var":
            var_arg = args[0].get("args", [None])[0]
            value_arg = args[1]
        # Check if first arg is a var (JsonLogic format)
        elif isinstance(args[0], dict) and "var" in args[0]:
            var_value = args[0]["var"]
            var_arg = var_value[0] if isinstance(var_value, list) else var_value
            value_arg = args[1]
        # Check if second arg is a var (normalized format)
        elif isinstance(args[1], dict) and args[1].get("op") == "var":
            var_arg = args[1].get("args", [None])[0]
            value_arg = args[0]
        # Check if second arg is a var (JsonLogic format)
        elif isinstance(args[1], dict) and "var" in args[1]:
            var_value = args[1]["var"]
            var_arg = var_value[0] if isinstance(var_value, list) else var_value
            value_arg = args[0]

        if var_arg and isinstance(var_arg, str):
            if var_arg not in self.field_usage:
                self.field_usage[var_arg] = FieldUsage(var_arg)

            self.field_usage[var_arg].add_comparison(operator, value_arg)
            if parent_context:
                self.field_usage[var_arg].add_context(parent_context)

        # Recurse for nested logic
        for arg in args:
            if isinstance(arg, dict):
                # Skip var nodes (both formats)
                if arg.get("op") == "var" or "var" in arg:
                    continue
                self.analyze_logic(arg, parent_context)

    def _analyze_in_operator(self, element_node: Any, list_node: List[Any]):
        """Analyze 'in' operator to extract enum options.

        Supports both formats:
        - Normalized: {"op": "var", "args": ["path"]}
        - JsonLogic: {"var": ["path"]} or {"var": "path"}
        """
        var_path = None

        # Extract variable from element (normalized format)
        if isinstance(element_node, dict) and element_node.get("op") == "var":
            var_path = element_node.get("args", [None])[0]
        # Extract variable from element (JsonLogic format)
        elif isinstance(element_node, dict) and "var" in element_node:
            var_value = element_node["var"]
            var_path = var_value[0] if isinstance(var_value, list) else var_value

        if var_path and isinstance(var_path, str):
            if var_path not in self.field_usage:
                self.field_usage[var_path] = FieldUsage(var_path)

            # Record all list items as compared values
            for item in list_node:
                if item is not None:
                    self.field_usage[var_path].add_comparison("in", item)

    def infer_type(self, var_path: str) -> Dict[str, Any]:
        """Infer field type from usage patterns.

        Returns:
            Dict with keys: type, options (if enum), format (if date), confidence
        """
        usage = self.field_usage.get(var_path)
        if not usage:
            return {"type": "string", "confidence": "low"}

        # Rule 1: Boolean (HIGH CONFIDENCE)
        if self._is_boolean(usage):
            return {"type": "boolean", "confidence": "high"}

        # Rule 2: Date/DateTime (MEDIUM CONFIDENCE - pattern-based)
        if self._is_date(var_path, usage):
            return {"type": "string", "format": "date-time", "confidence": "medium"}

        # Rule 3: Number (HIGH CONFIDENCE)
        if self._is_number(usage):
            number_type = self._infer_number_type(usage)
            return {"type": number_type, "confidence": "high"}

        # Rule 4: Enum (MEDIUM-HIGH CONFIDENCE)
        enum_result = self._is_enum(usage)
        if enum_result:
            return enum_result

        # Default: String (LOW CONFIDENCE)
        return {"type": "string", "confidence": "low"}

    def _is_boolean(self, usage: FieldUsage) -> bool:
        """Check if variable is used as boolean.

        Rules:
        - Used directly in if_condition
        - Used in logical operators (and/or)
        - Compared only to true/false
        """
        # Check context
        if "if_condition" in usage.context_usage:
            # If used as direct condition, likely boolean
            if not usage.compared_values:
                return True

        # Check logical usage
        if "logical" in usage.context_usage and not usage.compared_values:
            return True

        # Check if only compared to true/false
        if usage.compared_values:
            # Filter out non-hashable values (nested logic)
            hashable_values = [v for v in usage.compared_values
                             if not isinstance(v, (dict, list))]
            if hashable_values:
                unique_values = set(hashable_values)
                if unique_values.issubset({True, False}):
                    return True

        return False

    def _is_date(self, var_path: str, usage: FieldUsage) -> bool:
        """Check if variable is a date/time field.

        Rules:
        - Field name matches common date patterns
        - Not used in arithmetic (would indicate timestamp)
        """
        # Check field name patterns
        for pattern in self.DATE_PATTERNS:
            if re.match(pattern, var_path.split(".")[-1]):
                # Exclude if used in arithmetic (likely timestamp)
                if usage.context_usage and "arithmetic" in usage.context_usage:
                    return False
                return True

        return False

    def _is_number(self, usage: FieldUsage) -> bool:
        """Check if variable is numeric.

        Rules:
        - Used in arithmetic operators
        - Compared with >, >=, <, <=
        - All compared values are numbers
        """
        # Check arithmetic usage
        if "arithmetic" in usage.context_usage:
            return True

        # Check numeric comparisons
        numeric_ops = {">", ">=", "<", "<="}
        if usage.operators_used & numeric_ops:
            return True

        # Check if all compared values are numbers
        if usage.compared_values:
            all_numeric = all(isinstance(v, (int, float)) for v in usage.compared_values)
            if all_numeric and len(usage.compared_values) >= 2:
                return True

        return False

    def _infer_number_type(self, usage: FieldUsage) -> str:
        """Infer if number is integer or float.

        Returns:
            "integer" or "number"
        """
        if not usage.compared_values:
            return "number"

        # Check if all values are integers
        all_int = all(isinstance(v, int) or (isinstance(v, float) and v.is_integer())
                     for v in usage.compared_values if isinstance(v, (int, float)))

        return "integer" if all_int else "number"

    def _is_enum(self, usage: FieldUsage) -> Optional[Dict[str, Any]]:
        """Check if variable is an enum.

        Rules:
        - Compared to 2+ distinct string values
        - Uses ==, !=, or in operators
        - Less than 20 unique values (arbitrary threshold)

        Returns:
            Dict with type, options, confidence if enum, else None
        """
        if not usage.compared_values:
            return None

        # Extract unique string values
        string_values = [v for v in usage.compared_values if isinstance(v, str)]
        unique_strings = list(set(string_values))

        # Require 2+ values and < 20 options
        if len(unique_strings) >= 2 and len(unique_strings) < 20:
            # Check if used with appropriate operators
            enum_ops = {"==", "!=", "in"}
            if usage.operators_used & enum_ops:
                return {
                    "type": "enum",
                    "options": sorted(unique_strings),
                    "confidence": "high" if len(unique_strings) >= 3 else "medium"
                }

        return None

    def get_all_inferred_types(self) -> Dict[str, Dict[str, Any]]:
        """Get inferred types for all analyzed variables.

        Returns:
            Dict mapping var_path -> type_info
        """
        result = {}
        for var_path in self.field_usage:
            result[var_path] = self.infer_type(var_path)
        return result
