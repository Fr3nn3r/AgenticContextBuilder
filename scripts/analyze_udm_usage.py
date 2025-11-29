"""Analyze UDM variable usage in extracted logic files."""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Set, List, Any


# UDM Schema Variables (from udm_schema.md)
UDM_VARIABLES = {
    # Header
    "claim.header.line_of_business",
    "claim.header.claim_type",
    "claim.header.loss_at",
    "claim.header.discovered_at",
    "claim.header.reported_at",
    "claim.header.jurisdiction",
    # Incident
    "claim.incident.primary_cause_code",
    "claim.incident.secondary_cause_code",
    "claim.incident.location_country",
    "claim.incident.location_description",
    # Parties
    "claim.parties.claimants[].role",
    # Financials
    "claim.financials.currency",
    "claim.financials.amounts[].type",
    "claim.financials.amounts[].amount",
}

# Dynamic patterns (attributes, custom)
DYNAMIC_PATTERNS = {
    "claim.header.attributes.*": r"^claim\.header\.attributes\..+",
    "claim.incident.attributes.*": r"^claim\.incident\.attributes\..+",
    "claim.parties.claimants[].attributes.*": r"^claim\.parties\.claimants\[\]\.attributes\..+",
    "claim.financials.amounts[].attributes.*": r"^claim\.financials\.amounts\[\]\.attributes\..+",
    "claim.financials.attributes.*": r"^claim\.financials\.attributes\..+",
    "claim.custom.*": r"^claim\.custom\..+",
}


def normalize_array_indices(var_path: str) -> str:
    """Normalize numeric array indices to [] for matching.

    Examples:
        claim.amounts[0].total -> claim.amounts[].total
        claim.parties.claimants[1].role -> claim.parties.claimants[].role
    """
    # Skip JMESPath filters
    if "[?(" in var_path:
        return var_path

    # Replace [0], [1], etc. with []
    return re.sub(r'\[\d+\]', '[]', var_path)


def categorize_variable(var_path: str) -> str:
    """Categorize a variable path.

    Returns:
        - "udm" if it's a standard UDM variable
        - "attributes" if it matches an attributes pattern
        - "custom" if it's claim.custom.*
        - "unknown" otherwise
    """
    normalized = normalize_array_indices(var_path)

    # Check UDM variables
    if normalized in UDM_VARIABLES:
        return "udm"

    # Check dynamic patterns
    for pattern_name, pattern_regex in DYNAMIC_PATTERNS.items():
        if re.match(pattern_regex, normalized):
            if "custom" in pattern_name:
                return "custom"
            return "attributes"

    return "unknown"


def extract_variables_from_logic(logic_node: Any, variables: List[str]) -> None:
    """Recursively extract all variable references from logic tree.

    Handles both formats:
    - JsonLogic format: {"var": ["path"]} or {"var": "path"}
    - Normalized format: {"op": "var", "args": ["path"]}

    Args:
        logic_node: Current node in logic tree (dict, list, or scalar)
        variables: List to append found variables to
    """
    if isinstance(logic_node, dict):
        # Format 1: Normalized format {"op": "var", "args": [...]}
        if logic_node.get("op") == "var":
            args = logic_node.get("args", [])
            if args and isinstance(args[0], str):
                variables.append(args[0])

        # Format 2: JsonLogic format {"var": [...]} or {"var": "..."}
        if "var" in logic_node:
            var_value = logic_node["var"]
            if isinstance(var_value, str):
                variables.append(var_value)
            elif isinstance(var_value, list) and var_value and isinstance(var_value[0], str):
                variables.append(var_value[0])

        # Recurse into all values
        for value in logic_node.values():
            extract_variables_from_logic(value, variables)

    elif isinstance(logic_node, list):
        # Recurse into list items
        for item in logic_node:
            extract_variables_from_logic(item, variables)


def analyze_logic_file(file_path: Path) -> Dict[str, int]:
    """Analyze a single logic JSON file and return variable counts.

    Args:
        file_path: Path to logic JSON file

    Returns:
        Dict mapping variable paths to occurrence counts
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract rules - try different data structures
        rules = []
        if "transpiled_data" in data:
            # Format: {"transpiled_data": {"rules": [...]}}
            rules = data["transpiled_data"].get("rules", [])
        elif "extracted_data" in data:
            # Format: {"extracted_data": {"rules": [...]}}
            rules = data["extracted_data"].get("rules", [])
        elif "rules" in data:
            # Format: {"rules": [...]}
            rules = data.get("rules", [])

        if not rules:
            # print(f"[DEBUG] No rules found in {file_path.name}")
            return {}

        # Collect all variables
        all_variables = []
        for rule in rules:
            logic = rule.get("logic", {})
            extract_variables_from_logic(logic, all_variables)

        # Count occurrences
        return dict(Counter(all_variables))

    except Exception as e:
        print(f"[WARNING] Failed to parse {file_path.name}: {e}")
        return {}


def find_logic_files(base_dir: Path) -> List[Path]:
    """Find all non-normalized logic JSON files.

    Args:
        base_dir: Base directory to search (e.g., output/)

    Returns:
        List of Path objects
    """
    logic_files = []

    # Pattern 1: *_extracted_logic.json (original extraction)
    logic_files.extend(base_dir.glob("**/*_extracted_logic.json"))

    # Pattern 2: *_logic.json but NOT *_normalized_logic.json
    all_logic = base_dir.glob("**/*_logic.json")
    for f in all_logic:
        if "normalized" not in f.stem:
            logic_files.append(f)

    # Deduplicate
    return list(set(logic_files))


def main():
    """Main analysis function."""
    import sys

    print("=" * 80)
    print("UDM VARIABLE USAGE ANALYSIS")
    print("=" * 80)
    print()

    # Find output directory (use command line arg if provided)
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    else:
        output_dir = Path(__file__).parent.parent / "output"

    if not output_dir.exists():
        print(f"[ERROR] Output directory not found: {output_dir}")
        return

    print(f"Searching for logic files in: {output_dir}")
    logic_files = find_logic_files(output_dir)

    if not logic_files:
        print("[ERROR] No logic files found.")
        return

    print(f"Found {len(logic_files)} logic files to analyze")
    print()

    # Analyze all files
    total_var_counts = Counter()  # Total occurrences across all files
    file_var_counts = defaultdict(set)  # Track which files use which variables
    category_counts = Counter()  # Count by category

    for file_path in logic_files:
        print(f"  Analyzing: {file_path.relative_to(output_dir)}")
        var_counts = analyze_logic_file(file_path)

        for var, count in var_counts.items():
            total_var_counts[var] += count
            file_var_counts[var].add(str(file_path))
            category_counts[categorize_variable(var)] += count

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    # Summary statistics
    unique_vars = len(total_var_counts)
    total_refs = sum(total_var_counts.values())
    udm_vars_used = sum(1 for v in total_var_counts if categorize_variable(v) == "udm")
    udm_coverage = (udm_vars_used / len(UDM_VARIABLES)) * 100 if UDM_VARIABLES else 0

    print(f"Summary:")
    print(f"  Files analyzed: {len(logic_files)}")
    print(f"  Total variable references: {total_refs:,}")
    print(f"  Unique variables found: {unique_vars}")
    print(f"  UDM variables used: {udm_vars_used}/{len(UDM_VARIABLES)} ({udm_coverage:.1f}% coverage)")
    print()

    print(f"By Category:")
    for category in ["udm", "attributes", "custom", "unknown"]:
        count = category_counts[category]
        pct = (count / total_refs * 100) if total_refs > 0 else 0
        print(f"  {category.upper():12s}: {count:6,} ({pct:5.1f}%)")
    print()

    # Top 20 most used variables
    print("=" * 80)
    print("TOP 20 MOST USED VARIABLES")
    print("=" * 80)
    print()
    print(f"{'Variable':<60s} {'Total':>8s} {'Files':>6s} {'Category':>12s}")
    print("-" * 88)

    for var, count in total_var_counts.most_common(20):
        file_count = len(file_var_counts[var])
        category = categorize_variable(var)
        # Truncate long variable names
        var_display = var if len(var) <= 60 else var[:57] + "..."
        print(f"{var_display:<60s} {count:8,} {file_count:6} {category:>12s}")

    print()

    # UDM variables never used
    used_udm = {normalize_array_indices(v) for v in total_var_counts if categorize_variable(v) == "udm"}
    unused_udm = UDM_VARIABLES - used_udm

    if unused_udm:
        print("=" * 80)
        print(f"UDM VARIABLES NEVER USED ({len(unused_udm)})")
        print("=" * 80)
        print()
        for var in sorted(unused_udm):
            print(f"  - {var}")
        print()

    # All UDM variables with usage counts
    print("=" * 80)
    print("ALL UDM VARIABLES (BY USAGE)")
    print("=" * 80)
    print()
    print(f"{'Variable':<50s} {'Total':>8s} {'Files':>6s}")
    print("-" * 66)

    udm_usage = []
    for var in UDM_VARIABLES:
        # Find matching variables (handles array index normalization)
        matching_vars = [v for v in total_var_counts if normalize_array_indices(v) == var]
        total = sum(total_var_counts[v] for v in matching_vars)
        files = set()
        for v in matching_vars:
            files.update(file_var_counts[v])
        udm_usage.append((var, total, len(files)))

    # Sort by usage (descending)
    for var, total, file_count in sorted(udm_usage, key=lambda x: x[1], reverse=True):
        print(f"{var:<50s} {total:8,} {file_count:6}")

    print()

    # Top attributes patterns
    attributes_vars = [v for v in total_var_counts if categorize_variable(v) == "attributes"]
    if attributes_vars:
        print("=" * 80)
        print(f"TOP 15 ATTRIBUTES PATTERNS ({len(attributes_vars)} unique)")
        print("=" * 80)
        print()
        print(f"{'Variable':<60s} {'Total':>8s} {'Files':>6s}")
        print("-" * 76)

        attributes_sorted = sorted(
            [(v, total_var_counts[v], len(file_var_counts[v])) for v in attributes_vars],
            key=lambda x: x[1],
            reverse=True
        )[:15]

        for var, count, file_count in attributes_sorted:
            var_display = var if len(var) <= 60 else var[:57] + "..."
            print(f"{var_display:<60s} {count:8,} {file_count:6}")
        print()

    # Top custom variables
    custom_vars = [v for v in total_var_counts if categorize_variable(v) == "custom"]
    if custom_vars:
        print("=" * 80)
        print(f"TOP 15 CUSTOM VARIABLES ({len(custom_vars)} unique)")
        print("=" * 80)
        print()
        print(f"{'Variable':<60s} {'Total':>8s} {'Files':>6s}")
        print("-" * 76)

        custom_sorted = sorted(
            [(v, total_var_counts[v], len(file_var_counts[v])) for v in custom_vars],
            key=lambda x: x[1],
            reverse=True
        )[:15]

        for var, count, file_count in custom_sorted:
            var_display = var if len(var) <= 60 else var[:57] + "..."
            print(f"{var_display:<60s} {count:8,} {file_count:6}")
        print()

    # Top unknown variables (potential schema gaps)
    unknown_vars = [v for v in total_var_counts if categorize_variable(v) == "unknown"]
    if unknown_vars:
        print("=" * 80)
        print(f"TOP 20 UNKNOWN VARIABLES ({len(unknown_vars)} unique)")
        print("Potential schema gaps or extraction errors")
        print("=" * 80)
        print()
        print(f"{'Variable':<60s} {'Total':>8s} {'Files':>6s}")
        print("-" * 76)

        unknown_sorted = sorted(
            [(v, total_var_counts[v], len(file_var_counts[v])) for v in unknown_vars],
            key=lambda x: x[1],
            reverse=True
        )[:20]

        for var, count, file_count in unknown_sorted:
            var_display = var if len(var) <= 60 else var[:57] + "..."
            print(f"{var_display:<60s} {count:8,} {file_count:6}")
        print()

    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print("Key Findings:")
    print(f"  - {len([v for v in total_var_counts if categorize_variable(v) == 'udm'])}/{len(UDM_VARIABLES)} UDM variables are actively used")
    print(f"  - {len(attributes_vars)} unique attributes patterns found")
    print(f"  - {len(custom_vars)} custom variables defined (claim.custom.*)")
    print(f"  - {len(unknown_vars)} unknown variables detected (may indicate schema gaps)")
    print()


if __name__ == "__main__":
    main()
