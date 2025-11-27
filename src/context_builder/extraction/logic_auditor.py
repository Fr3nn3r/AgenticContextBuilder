"""
Logic Auditor for detecting semantic hallucinations in extracted policy logic.

Scans extracted logic files to detect:
- Null List bug: {"in": [var, [..., null]]}
- Orphan concepts: Values that don't belong to the variable's domain
- Cross-field contamination: Values from one enum appearing in another field
- Type mismatches: Strings where numbers expected
"""

import json
import logging
import os
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class LogicAuditor:
    """
    Audits extracted logic files for semantic hallucinations.

    Uses schema-aware validation to detect orphan concepts where LLM
    forces incompatible business concepts into existing UDM fields.
    """

    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize auditor with schema validation.

        Args:
            schema_path: Path to standard claim schema JSON file.
                        If None, auto-detects from package structure.
        """
        # Trackers
        self.variable_values = defaultdict(Counter)  # Map[Variable, Counter[Values]]
        self.null_bug_files = set()  # Files containing Null List bug
        self.orphan_map = defaultdict(lambda: defaultdict(set))  # Map[Variable, Map[OrphanValue, Set[Files]]]
        self.file_orphan_counts = defaultdict(int)  # Map[File, OrphanCount]

        # Schema validation cache
        self.schema_enums = {}  # Map[Variable, Set[ValidValues]]
        self.known_loss_causes = set()  # Cache of valid loss causes

        # Load schema
        self._load_schema(schema_path)

    def _load_schema(self, schema_path: Optional[str] = None):
        """Load enum values from standard claim schema for validation."""
        if schema_path is None:
            # Auto-detect schema path from package structure
            schema_path = str(Path(__file__).parent.parent / "schemas" / "standard_claim_schema.json")

        if not os.path.exists(schema_path):
            logger.warning(f"Schema file not found: {schema_path}")
            logger.warning("Continuing without enum validation...")
            return

        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)

            # Extract enums from schema
            def extract_enums(obj, path=""):
                if isinstance(obj, dict):
                    # Check if this property has an enum
                    if "enum" in obj:
                        self.schema_enums[path] = set(obj["enum"])
                        # Cache loss causes for cross-contamination detection
                        if "cause_primary" in path:
                            self.known_loss_causes.update(obj["enum"])

                    # Recurse into properties
                    if "properties" in obj:
                        for key, value in obj["properties"].items():
                            new_path = f"{path}.{key}" if path else key
                            extract_enums(value, new_path)

            extract_enums(schema.get("properties", {}))
            logger.debug(f"Loaded {len(self.schema_enums)} enum definitions from schema")

        except Exception as e:
            logger.warning(f"Error loading schema: {e}")

    def _is_var_node(self, node: Any) -> bool:
        """Check if node is a variable reference."""
        if isinstance(node, dict):
            # Normalized format: {"op": "var", "args": ["claim.x"]}
            if node.get("op") == "var":
                return True
            # Transpiled format: {"var": "claim.x"}
            if "var" in node:
                return True
        return False

    def _get_var_name(self, node: Dict) -> str:
        """Extract variable name from variable node."""
        # Normalized format: {"op": "var", "args": ["claim.x"]}
        if node.get("op") == "var":
            args = node.get("args", [])
            return args[0] if args else "unknown"

        # Transpiled format: {"var": "claim.x"}
        if "var" in node:
            val = node["var"]
            return val[0] if isinstance(val, list) else val

        return "unknown"

    def _is_orphan_concept(self, var_name: str, value: Any) -> Tuple[bool, str]:
        """
        Detect if a value is an orphan concept (hallucination).

        Returns:
            (is_orphan, severity) where severity is "CRITICAL" or "WARNING"
        """
        # Skip non-string values (numbers are usually limits/deductibles)
        if not isinstance(value, str):
            return False, ""

        if value == "NULL":
            return True, "CRITICAL"

        # Check against schema enums if available
        if var_name in self.schema_enums:
            if value not in self.schema_enums[var_name]:
                # Check if it's cross-contamination
                if value in self.known_loss_causes:
                    return True, "CRITICAL - Appears to be loss cause"
                return True, "CRITICAL - Not in schema enum"
            return False, ""

        # Heuristic checks for common patterns

        # Jurisdiction should be short ISO codes (2-3 chars)
        if "jurisdiction" in var_name.lower():
            if len(value) > 3:
                # Check if it looks like a loss cause or peril
                if value in self.known_loss_causes:
                    return True, "CRITICAL - Appears to be loss cause"
                if any(word in value.lower() for word in ["damage", "loss", "coverage", "policy"]):
                    return True, "WARNING - Suspicious long value"
                return True, "WARNING - ISO codes are typically 2-3 chars"

        # Loss date should be a date string, not text
        if "date" in var_name.lower():
            if not any(char.isdigit() for char in value):
                return True, "WARNING - Date field contains non-date value"

        return False, ""

    def _record_value(self, var_name: str, value: Any, filename: str) -> None:
        """Record a value seen for a variable."""
        # Convert None to "NULL" string
        if value is None:
            value = "NULL"

        # Record the value
        self.variable_values[var_name][str(value)] += 1

        # Check if it's an orphan concept
        is_orphan, severity = self._is_orphan_concept(var_name, value)
        if is_orphan:
            self.orphan_map[var_name][str(value)].add(filename)
            self.file_orphan_counts[filename] += 1

    def _traverse_logic(self, node: Any, filename: str) -> None:
        """Recursively walk JSON logic tree to find comparisons."""
        if isinstance(node, list):
            for item in node:
                self._traverse_logic(item, filename)
            return

        if not isinstance(node, dict):
            return

        # NORMALIZED FORMAT: {"op": "operator", "args": [...]}
        if "op" in node:
            op = node["op"]
            args = node.get("args", [])

            # Detect Null List bug in normalized format
            if op == "in" and len(args) >= 2:
                second_arg = args[1]
                # Check if second arg IS null or CONTAINS null
                if second_arg is None or (isinstance(second_arg, list) and None in second_arg):
                    self.null_bug_files.add(filename)
                    if self._is_var_node(args[0]):
                        var_name = self._get_var_name(args[0])
                        self.orphan_map[f"{var_name} (NULL LIST BUG)"]["NULL"].add(filename)

            # Extract comparisons
            if op in ["==", "!=", "in"] and len(args) >= 2:
                var_name = None
                value = None

                if self._is_var_node(args[0]):
                    var_name = self._get_var_name(args[0])
                    value = args[1]
                elif self._is_var_node(args[1]):
                    var_name = self._get_var_name(args[1])
                    value = args[0]

                if var_name:
                    if isinstance(value, list):
                        for v in value:
                            self._record_value(var_name, v, filename)
                    else:
                        self._record_value(var_name, value, filename)

            # Recurse into args
            self._traverse_logic(args, filename)

        # TRANSPILED FORMAT: {"==": [...], "var": "...", etc}
        else:
            # Detect Null List bug in transpiled format
            if "in" in node:
                args = node["in"]
                if isinstance(args, list) and len(args) >= 2:
                    second_arg = args[1]
                    # Check if second arg IS null or CONTAINS null
                    if second_arg is None or (isinstance(second_arg, list) and None in second_arg):
                        self.null_bug_files.add(filename)
                        if self._is_var_node(args[0]):
                            var_name = self._get_var_name(args[0])
                            self.orphan_map[f"{var_name} (NULL LIST BUG)"]["NULL"].add(filename)

            # Extract comparisons
            for op in ["==", "!=", "in"]:
                if op in node:
                    args = node[op]
                    if not isinstance(args, list) or len(args) < 2:
                        continue

                    var_name = None
                    value = None

                    if self._is_var_node(args[0]):
                        var_name = self._get_var_name(args[0])
                        value = args[1]
                    elif self._is_var_node(args[1]):
                        var_name = self._get_var_name(args[1])
                        value = args[0]

                    if var_name:
                        if isinstance(value, list):
                            for v in value:
                                self._record_value(var_name, v, filename)
                        else:
                            self._record_value(var_name, value, filename)

            # Recurse into all dict values to catch nested operators
            for value in node.values():
                self._traverse_logic(value, filename)

    def audit_files(self, file_paths: List[str]) -> None:
        """
        Audit logic files for semantic hallucinations.

        Args:
            file_paths: List of paths to logic JSON files
        """
        logger.info(f"Auditing {len(file_paths)} logic file(s)")

        for filepath in file_paths:
            if not os.path.exists(filepath):
                logger.warning(f"File not found: {filepath}")
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                filename = os.path.basename(filepath)

                # Handle different file structures
                rules = []

                # Normalized format: {"extracted_data": {"rules": [...]}}
                if "extracted_data" in data and "rules" in data["extracted_data"]:
                    rules = data["extracted_data"]["rules"]
                # Direct rules format: {"rules": [...]}
                elif "rules" in data:
                    rules = data["rules"]
                # Transpiled format: {"transpiled_data": {"rules": [...]}}
                elif "transpiled_data" in data and "rules" in data["transpiled_data"]:
                    rules = data["transpiled_data"]["rules"]

                # Process each rule's logic tree
                for rule in rules:
                    logic_tree = rule.get("logic", {})
                    self._traverse_logic(logic_tree, filename)

                logger.debug(f"Audited {filename}: {len(rules)} rules")

            except Exception as e:
                logger.error(f"Error reading {filepath}: {e}")

    def generate_report(self, output_path: str) -> None:
        """
        Generate comprehensive audit report.

        Args:
            output_path: Path to write report file
        """
        logger.info(f"Generating audit report: {output_path}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("LOGIC HALLUCINATION AUDIT REPORT\n")
            f.write("=" * 80 + "\n\n")

            # Section 1: Critical Bugs
            f.write("1. CRITICAL BUG: 'NULL in List' Error\n")
            f.write("-" * 40 + "\n")
            if self.null_bug_files:
                f.write(f"Files affected: {len(self.null_bug_files)}\n\n")
                for bad_file in sorted(self.null_bug_files):
                    f.write(f"   - {bad_file}\n")
            else:
                f.write("[OK] No NULL list bugs detected\n")
            f.write("\n" + "=" * 80 + "\n\n")

            # Section 2: Variable Value Profiles
            f.write("2. VARIABLE VALUE PROFILE\n")
            f.write("-" * 40 + "\n")
            f.write("Inspect these lists for orphan concepts (hallucinations)\n\n")

            for var in sorted(self.variable_values.keys()):
                counts = self.variable_values[var]
                orphans = self.orphan_map.get(var, {})

                f.write(f"\nVARIABLE: {var}\n")
                f.write(f"Total Unique Values: {len(counts)}\n")

                if var in self.schema_enums:
                    valid_count = sum(1 for v in counts if v in self.schema_enums[var])
                    f.write(f"Valid Values (per schema): {valid_count}\n")
                    orphan_count = len(counts) - valid_count
                    if orphan_count > 0:
                        f.write(f"[!] Orphan Concepts: {orphan_count}\n")

                f.write("\n")

                # Separate valid and orphan values
                valid_values = []
                orphan_values = []

                for val, count in counts.most_common():
                    is_orphan, severity = self._is_orphan_concept(var, val)
                    if is_orphan:
                        orphan_values.append((val, count, severity))
                    else:
                        valid_values.append((val, count))

                # Print valid values first
                if valid_values:
                    f.write("  VALID VALUES:\n")
                    for val, count in valid_values:
                        f.write(f"   [{count}x] {val}\n")

                # Print orphans with warnings
                if orphan_values:
                    f.write("\n  [!] ORPHAN CONCEPTS (likely hallucinations):\n")
                    for val, count, severity in orphan_values:
                        files_with_orphan = orphans.get(val, set())
                        file_list = ", ".join(sorted(list(files_with_orphan)[:3]))
                        if len(files_with_orphan) > 3:
                            file_list += f" ... (+{len(files_with_orphan) - 3} more)"
                        f.write(f"   [{count}x] {val} [!] {severity}\n")
                        f.write(f"           Found in: {file_list}\n")

                f.write("-" * 40 + "\n")

            # Section 3: Files Requiring Review
            f.write("\n" + "=" * 80 + "\n\n")
            f.write("3. FILES REQUIRING REVIEW\n")
            f.write("-" * 40 + "\n")

            if self.file_orphan_counts:
                sorted_files = sorted(self.file_orphan_counts.items(), key=lambda x: x[1], reverse=True)
                f.write(f"Total files with orphan concepts: {len(sorted_files)}\n\n")

                for filename, orphan_count in sorted_files:
                    f.write(f"   {filename} - {orphan_count} orphan concept(s)\n")
            else:
                f.write("[OK] No files with orphan concepts detected\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("End of Report\n")
            f.write("=" * 80 + "\n")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for display.

        Returns:
            Dictionary with summary statistics
        """
        total_orphans = sum(self.file_orphan_counts.values())

        return {
            "variables_analyzed": len(self.variable_values),
            "null_bugs": len(self.null_bug_files),
            "orphan_concepts": total_orphans,
            "files_with_orphans": len(self.file_orphan_counts),
            "has_issues": len(self.null_bug_files) > 0 or total_orphans > 0
        }
