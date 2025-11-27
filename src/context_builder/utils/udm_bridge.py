"""
UDM Bridge: Transform explicit_variables into dynamic UDM injection strings.

Converts symbol table variables into UDM paths (e.g., policy.limit.bodily_injury)
for inclusion in LLM prompts alongside static schema UDM.
"""

import re
from typing import Dict, List, Set, Any


# Currency codes to strip from variable names
CURRENCY_CODES = {"CAD", "USD", "EUR", "GBP", "CHF", "AUD"}

# Words to remove during normalization
REDUNDANT_WORDS = {
    "limit", "deductible", "aggregate", "coverage", "premium",
    "amount", "value", "total", "sum"
}


def normalize_variable_key(name: str) -> str:
    """
    Convert variable name to snake_case UDM key.

    Rules:
    1. Remove redundant words (limit, deductible, aggregate, currency codes)
    2. Remove special characters
    3. Convert to snake_case

    Args:
        name: Raw variable name (e.g., "Bodily Injury & Property Damage Limit (CAD)")

    Returns:
        Normalized key (e.g., "bodily_injury_property_damage")

    Examples:
        >>> normalize_variable_key("Bodily Injury Limit")
        'bodily_injury'
        >>> normalize_variable_key("Property Damage Deductible (USD)")
        'property_damage'
        >>> normalize_variable_key("Tenants' Liability Coverage")
        'tenants_liability'
    """
    # Convert to lowercase
    normalized = name.lower()

    # Remove currency codes (with or without parentheses)
    for currency in CURRENCY_CODES:
        normalized = re.sub(rf"\b{currency.lower()}\b", "", normalized)

    # Remove parentheses and their contents
    normalized = re.sub(r"\([^)]*\)", "", normalized)

    # Remove redundant words
    words = normalized.split()
    words = [w for w in words if w not in REDUNDANT_WORDS]

    # Join remaining words
    normalized = " ".join(words)

    # Remove all non-alphanumeric characters except spaces
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)

    # Convert spaces to underscores
    normalized = re.sub(r"\s+", "_", normalized.strip())

    # Remove trailing/leading underscores
    normalized = normalized.strip("_")

    return normalized


def categorize_variable(name: str, context: str) -> str:
    """
    Detect if variable is a limit, deductible, or premium.

    Args:
        name: Variable name
        context: Variable context/description

    Returns:
        Category string: "limit", "deductible", or "premium"

    Examples:
        >>> categorize_variable("Bodily Injury Limit", "Coverage limit for...")
        'limit'
        >>> categorize_variable("Property Damage Deductible", "Deductible for...")
        'deductible'
        >>> categorize_variable("Annual Premium", "Premium amount")
        'premium'
    """
    name_lower = name.lower()
    context_lower = context.lower()

    # Check for deductible
    if "deductible" in name_lower or "deductible" in context_lower:
        return "deductible"

    # Check for premium
    if "premium" in name_lower or "premium" in context_lower:
        return "premium"

    # Check for limit/coverage (default)
    if "limit" in name_lower or "limit" in context_lower or "coverage" in name_lower:
        return "limit"

    # Default fallback
    return "limit"


def generate_udm_path(variable: Dict[str, Any]) -> str:
    """
    Generate UDM path for a variable.

    Format: policy.{category}.{normalized_key}

    Args:
        variable: Explicit variable dict with "name" and "context" keys

    Returns:
        UDM path string (e.g., "policy.limit.bodily_injury")

    Examples:
        >>> generate_udm_path({"name": "Bodily Injury Limit", "context": "Coverage limit"})
        'policy.limit.bodily_injury'
        >>> generate_udm_path({"name": "Property Damage Deductible (CAD)", "context": "Deductible"})
        'policy.deductible.property_damage'
    """
    name = variable.get("name", "")
    context = variable.get("context", "")

    # Categorize variable
    category = categorize_variable(name, context)

    # Normalize key
    key = normalize_variable_key(name)

    # Build path
    path = f"policy.{category}.{key}"

    return path


def render_dynamic_udm(variables: List[Dict[str, Any]]) -> str:
    """
    Render markdown for filtered subset of dynamic variables.

    Generates UDM section showing policy variables extracted from symbol table.

    Args:
        variables: List of explicit variable dicts

    Returns:
        Markdown-formatted UDM variable section

    Example Output:
        ## Dynamic Policy Variables

        These variables were extracted from the symbol table:

        - `policy.limit.bodily_injury` - Bodily Injury Limit (Coverage limit for bodily injury claims)
        - `policy.deductible.property_damage` - Property Damage Deductible (Deductible for property damage)
    """
    if not variables:
        return ""

    lines = [
        "## Dynamic Policy Variables",
        "",
        "These variables were extracted from the symbol table:",
        ""
    ]

    for var in variables:
        path = generate_udm_path(var)
        name = var.get("name", "")
        context = var.get("context", "")

        # Format: - `path` - Name (Context)
        if context:
            line = f"- `{path}` - {name} ({context})"
        else:
            line = f"- `{path}` - {name}"

        lines.append(line)

    return "\n".join(lines)


def extract_static_paths(schema_dict: Dict[str, Any]) -> Set[str]:
    """
    Extract all paths from standard claim schema for validation.

    Recursively walks schema to find all property paths (e.g., "claim.meta.id").

    Args:
        schema_dict: JSON schema dictionary

    Returns:
        Set of all valid static paths in schema

    Examples:
        >>> schema = {"properties": {"claim": {"properties": {"meta": {"properties": {"id": {}}}}}}}
        >>> extract_static_paths(schema)
        {'claim', 'claim.meta', 'claim.meta.id'}
    """
    paths = set()

    def walk_properties(obj: Any, path: str = ""):
        """Recursively walk schema properties."""
        nonlocal paths  # Access outer paths set

        if not isinstance(obj, dict):
            return

        # Add current path if not root
        if path:
            paths.add(path)

        # Recurse into properties
        if "properties" in obj:
            for key, value in obj["properties"].items():
                new_path = f"{path}.{key}" if path else key
                walk_properties(value, new_path)

    # Start walking from root schema
    walk_properties(schema_dict)

    return paths


def validate_no_conflicts(dynamic_paths: Set[str], static_paths: Set[str]) -> None:
    """
    Validate that dynamic UDM paths don't conflict with static schema paths.

    Raises ValueError if any dynamic path collides with static path.

    Args:
        dynamic_paths: Set of generated dynamic UDM paths
        static_paths: Set of static schema paths

    Raises:
        ValueError: If conflicts detected

    Examples:
        >>> validate_no_conflicts({"policy.limit.bodily_injury"}, {"claim.meta.id"})
        # No error

        >>> validate_no_conflicts({"claim.meta.id"}, {"claim.meta.id"})
        # ValueError: Conflicts detected...
    """
    conflicts = dynamic_paths.intersection(static_paths)

    if conflicts:
        conflict_list = "\n  - ".join(sorted(conflicts))
        raise ValueError(
            f"Dynamic UDM path conflicts detected with static schema:\n"
            f"  - {conflict_list}\n\n"
            f"Dynamic variables generated paths that already exist in the schema. "
            f"This indicates a problem with variable categorization or normalization."
        )


def build_dynamic_udm_map(explicit_variables: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Build map of all dynamic UDM variables from symbol table.

    Creates lookup map keyed by lowercase variable name for symbol-based filtering.

    Args:
        explicit_variables: List of explicit variable dicts from symbol table

    Returns:
        Dict mapping lowercase variable name to variable data with UDM path

    Example:
        >>> variables = [{"name": "Bodily Injury Limit", "context": "Coverage limit"}]
        >>> build_dynamic_udm_map(variables)
        {
            'bodily injury limit': {
                'name': 'Bodily Injury Limit',
                'context': 'Coverage limit',
                'udm_path': 'policy.limit.bodily_injury'
            }
        }
    """
    udm_map = {}

    for var in explicit_variables:
        # Generate UDM path
        udm_path = generate_udm_path(var)

        # Build entry with UDM path
        key = var.get("name", "").lower()
        udm_map[key] = {
            "name": var.get("name", ""),
            "context": var.get("context", ""),
            "udm_path": udm_path,
            "original_data": var
        }

    return udm_map
