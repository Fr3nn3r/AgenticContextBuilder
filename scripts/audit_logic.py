"""
Value Profiling Audit Script for Logic Extraction.

Scans extracted logic files to detect semantic hallucinations where the LLM
forces incompatible business concepts into existing UDM fields.

Detects:
- Null List bug: {"in": [var, [..., null]]}
- Orphan concepts: Values that don't belong to the variable's domain
- Cross-field contamination: Values from one enum appearing in another field
- Type mismatches: Strings where numbers expected

Usage:
    python scripts/audit_logic.py [--dir OUTPUT_DIR]
"""

import argparse
import json
import glob
import os
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple

# Configuration
DEFAULT_LOGIC_DIR = "./output"
OUTPUT_FILE = "semantic_audit_report.txt"
SCHEMA_FILE = "src/context_builder/schemas/standard_claim_schema.json"

# Trackers
variable_values = defaultdict(Counter)  # Map[Variable, Counter[Values]]
null_bug_files = set()  # Files containing Null List bug
orphan_map = defaultdict(lambda: defaultdict(set))  # Map[Variable, Map[OrphanValue, Set[Files]]]
file_orphan_counts = defaultdict(int)  # Map[File, OrphanCount]

# Schema validation cache
schema_enums = {}  # Map[Variable, Set[ValidValues]]
known_loss_causes = set()  # Cache of valid loss causes for cross-contamination detection


def load_schema_enums(schema_path: str) -> None:
    """Load enum values from standard claim schema for validation."""
    global schema_enums, known_loss_causes

    if not os.path.exists(schema_path):
        print(f"⚠️ Schema file not found: {schema_path}")
        print("   Continuing without enum validation...")
        return

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)

        # Extract enums from schema
        def extract_enums(obj, path=""):
            if isinstance(obj, dict):
                # Check if this property has an enum
                if "enum" in obj:
                    schema_enums[path] = set(obj["enum"])
                    # Cache loss causes for cross-contamination detection
                    if "cause_primary" in path:
                        known_loss_causes.update(obj["enum"])

                # Recurse into properties
                if "properties" in obj:
                    for key, value in obj["properties"].items():
                        new_path = f"{path}.{key}" if path else key
                        extract_enums(value, new_path)

        extract_enums(schema.get("properties", {}))
        print(f"✅ Loaded {len(schema_enums)} enum definitions from schema")

    except Exception as e:
        print(f"⚠️ Error loading schema: {e}")


def is_var_node(node: Any) -> bool:
    """Check if node is a variable reference."""
    if isinstance(node, dict):
        # Normalized format: {"op": "var", "args": ["claim.x"]}
        if node.get("op") == "var":
            return True
        # Transpiled format: {"var": "claim.x"}
        if "var" in node:
            return True
    return False


def get_var_name(node: Dict) -> str:
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


def is_orphan_concept(var_name: str, value: Any) -> Tuple[bool, str]:
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
    if var_name in schema_enums:
        if value not in schema_enums[var_name]:
            # Check if it's cross-contamination
            if value in known_loss_causes:
                return True, "CRITICAL - Appears to be loss cause"
            return True, "CRITICAL - Not in schema enum"
        return False, ""

    # Heuristic checks for common patterns

    # Jurisdiction should be short ISO codes (2-3 chars)
    if "jurisdiction" in var_name.lower():
        if len(value) > 3:
            # Check if it looks like a loss cause or peril
            if value in known_loss_causes:
                return True, "CRITICAL - Appears to be loss cause"
            if any(word in value.lower() for word in ["damage", "loss", "coverage", "policy"]):
                return True, "WARNING - Suspicious long value"
            return True, "WARNING - ISO codes are typically 2-3 chars"

    # Loss date should be a date string, not text
    if "date" in var_name.lower():
        if not any(char.isdigit() for char in value):
            return True, "WARNING - Date field contains non-date value"

    return False, ""


def record_value(var_name: str, value: Any, filename: str) -> None:
    """Record a value seen for a variable."""
    # Convert None to "NULL" string
    if value is None:
        value = "NULL"

    # Record the value
    variable_values[var_name][str(value)] += 1

    # Check if it's an orphan concept
    is_orphan, severity = is_orphan_concept(var_name, value)
    if is_orphan:
        orphan_map[var_name][str(value)].add(filename)
        file_orphan_counts[filename] += 1


def traverse_logic(node: Any, filename: str) -> None:
    """Recursively walk JSON logic tree to find comparisons."""
    if isinstance(node, list):
        for item in node:
            traverse_logic(item, filename)
        return

    if not isinstance(node, dict):
        return

    # NORMALIZED FORMAT: {"op": "operator", "args": [...]}
    if "op" in node:
        op = node["op"]
        args = node.get("args", [])

        # Detect Null List bug in normalized format
        if op == "in" and len(args) >= 2:
            if isinstance(args[1], list) and None in args[1]:
                null_bug_files.add(filename)
                if is_var_node(args[0]):
                    var_name = get_var_name(args[0])
                    orphan_map[f"{var_name} (NULL LIST BUG)"]["NULL"].add(filename)

        # Extract comparisons
        if op in ["==", "!=", "in"] and len(args) >= 2:
            var_name = None
            value = None

            if is_var_node(args[0]):
                var_name = get_var_name(args[0])
                value = args[1]
            elif is_var_node(args[1]):
                var_name = get_var_name(args[1])
                value = args[0]

            if var_name:
                if isinstance(value, list):
                    for v in value:
                        record_value(var_name, v, filename)
                else:
                    record_value(var_name, value, filename)

        # Recurse into args
        traverse_logic(args, filename)

    # TRANSPILED FORMAT: {"==": [...], "var": "...", etc}
    else:
        # Detect Null List bug in transpiled format
        if "in" in node:
            args = node["in"]
            if isinstance(args, list) and len(args) >= 2:
                if isinstance(args[1], list) and None in args[1]:
                    null_bug_files.add(filename)
                    if is_var_node(args[0]):
                        var_name = get_var_name(args[0])
                        orphan_map[f"{var_name} (NULL LIST BUG)"]["NULL"].add(filename)

        # Extract comparisons
        for op in ["==", "!=", "in"]:
            if op in node:
                args = node[op]
                if not isinstance(args, list) or len(args) < 2:
                    continue

                var_name = None
                value = None

                if is_var_node(args[0]):
                    var_name = get_var_name(args[0])
                    value = args[1]
                elif is_var_node(args[1]):
                    var_name = get_var_name(args[1])
                    value = args[0]

                if var_name:
                    if isinstance(value, list):
                        for v in value:
                            record_value(var_name, v, filename)
                    else:
                        record_value(var_name, value, filename)

        # Recurse into all dict values
        for value in node.values():
            traverse_logic(value, filename)


def scan_logic_files(directory: str) -> List[str]:
    """Scan directory for logic JSON files and process them."""
    print(f"🔍 Scanning for logic files in {directory}...")

    # Find both transpiled and normalized logic files
    patterns = [
        "*_logic.json",
        "*_normalized_logic.json",
        "*/output_chunks/*_normalized_logic.json"
    ]

    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(directory, "**", pattern), recursive=True))

    # Remove duplicates
    files = list(set(files))

    if not files:
        print(f"❌ No logic files found in {directory}")
        return []

    print(f"📄 Found {len(files)} logic files")

    for filepath in files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            filename = os.path.basename(filepath)

            # Handle different file structures
            rules = []

            # Normalized format: {"rules": [...]}
            if "rules" in data:
                rules = data["rules"]
            # Transpiled format: {"transpiled_data": {"rules": [...]}}
            elif "transpiled_data" in data and "rules" in data["transpiled_data"]:
                rules = data["transpiled_data"]["rules"]

            # Process each rule's logic tree
            for rule in rules:
                logic_tree = rule.get("logic", {})
                traverse_logic(logic_tree, filename)

        except Exception as e:
            print(f"⚠️ Error reading {filepath}: {e}")

    return files


def generate_report(output_file: str) -> None:
    """Generate comprehensive audit report."""
    print(f"✅ Scan complete. Generating {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("LOGIC HALLUCINATION AUDIT REPORT\n")
        f.write("=" * 80 + "\n\n")

        # Section 1: Critical Bugs
        f.write("1. CRITICAL BUG: 'NULL in List' Error\n")
        f.write("-" * 40 + "\n")
        if null_bug_files:
            f.write(f"Files affected: {len(null_bug_files)}\n\n")
            for bad_file in sorted(null_bug_files):
                f.write(f"   - {bad_file}\n")
        else:
            f.write("✅ No NULL list bugs detected\n")
        f.write("\n" + "=" * 80 + "\n\n")

        # Section 2: Variable Value Profiles
        f.write("2. VARIABLE VALUE PROFILE\n")
        f.write("-" * 40 + "\n")
        f.write("Inspect these lists for orphan concepts (hallucinations)\n\n")

        for var in sorted(variable_values.keys()):
            counts = variable_values[var]
            orphans = orphan_map.get(var, {})

            f.write(f"\nVARIABLE: {var}\n")
            f.write(f"Total Unique Values: {len(counts)}\n")

            if var in schema_enums:
                valid_count = sum(1 for v in counts if v in schema_enums[var])
                f.write(f"Valid Values (per schema): {valid_count}\n")
                orphan_count = len(counts) - valid_count
                if orphan_count > 0:
                    f.write(f"⚠️ Orphan Concepts: {orphan_count}\n")

            f.write("\n")

            # Separate valid and orphan values
            valid_values = []
            orphan_values = []

            for val, count in counts.most_common():
                is_orphan, severity = is_orphan_concept(var, val)
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
                f.write("\n  ⚠️ ORPHAN CONCEPTS (likely hallucinations):\n")
                for val, count, severity in orphan_values:
                    files_with_orphan = orphans.get(val, set())
                    file_list = ", ".join(sorted(list(files_with_orphan)[:3]))
                    if len(files_with_orphan) > 3:
                        file_list += f" ... (+{len(files_with_orphan) - 3} more)"
                    f.write(f"   [{count}x] {val} ⚠️ {severity}\n")
                    f.write(f"           Found in: {file_list}\n")

            f.write("-" * 40 + "\n")

        # Section 3: Files Requiring Review
        f.write("\n" + "=" * 80 + "\n\n")
        f.write("3. FILES REQUIRING REVIEW\n")
        f.write("-" * 40 + "\n")

        if file_orphan_counts:
            sorted_files = sorted(file_orphan_counts.items(), key=lambda x: x[1], reverse=True)
            f.write(f"Total files with orphan concepts: {len(sorted_files)}\n\n")

            for filename, orphan_count in sorted_files:
                f.write(f"   {filename} - {orphan_count} orphan concept(s)\n")
        else:
            f.write("✅ No files with orphan concepts detected\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("End of Report\n")
        f.write("=" * 80 + "\n")

    print(f"\n✅ Report written to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Audit logic files for semantic hallucinations")
    parser.add_argument(
        "--dir",
        default=DEFAULT_LOGIC_DIR,
        help=f"Directory containing logic files (default: {DEFAULT_LOGIC_DIR})"
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_FILE,
        help=f"Output report file (default: {OUTPUT_FILE})"
    )
    parser.add_argument(
        "--schema",
        default=SCHEMA_FILE,
        help=f"Path to standard claim schema (default: {SCHEMA_FILE})"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("LOGIC HALLUCINATION AUDIT")
    print("=" * 60)
    print()

    # Load schema for enum validation
    load_schema_enums(args.schema)
    print()

    # Scan files
    files = scan_logic_files(args.dir)

    if not files:
        print("\n❌ No logic files found. Nothing to audit.")
        return 1

    print()

    # Generate report
    generate_report(args.output)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files scanned: {len(files)}")
    print(f"Variables analyzed: {len(variable_values)}")
    print(f"Files with NULL bug: {len(null_bug_files)}")
    print(f"Files with orphan concepts: {len(file_orphan_counts)}")

    if file_orphan_counts:
        total_orphans = sum(file_orphan_counts.values())
        print(f"Total orphan concepts found: {total_orphans}")
        print(f"\n⚠️ Review {args.output} for details")
        return 1
    else:
        print("\n✅ No semantic hallucinations detected!")
        return 0


if __name__ == "__main__":
    exit(main())
