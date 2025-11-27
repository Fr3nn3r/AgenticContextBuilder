"""Utility to render symbol table JSON into token-efficient Markdown format.

Converts the raw JSON symbol table into a clean, readable Markdown block
optimized for LLM context injection.
"""

from typing import Dict, Any


def render_symbol_context(symbol_table: Dict[str, Any]) -> str:
    """
    Converts the raw JSON symbol table into a token-efficient Markdown block.

    Args:
        symbol_table: Dictionary with 'defined_terms' and 'explicit_variables' keys

    Returns:
        Markdown-formatted string ready for prompt injection

    Example:
        >>> symbol_table = {
        ...     "defined_terms": [
        ...         {"term": "Insured", "definition_verbatim": "The person named..."}
        ...     ],
        ...     "explicit_variables": [
        ...         {"name": "Coverage Limit", "value": "100,000", "unit": "CHF"}
        ...     ]
        ... }
        >>> md = render_symbol_context(symbol_table)
        >>> print(md)
        ### GLOBAL DEFINITIONS
        - **Insured**: The person named...

        ### EXPLICIT VARIABLES
        - **Coverage Limit**: 100,000 CHF
    """
    md_output = ["### GLOBAL DEFINITIONS"]

    # 1. Terms
    for item in symbol_table.get("defined_terms", []):
        # Format: **Term**: Definition
        term = item['term']
        definition = item['definition_verbatim']
        md_output.append(f"- **{term}**: {definition}")

    # 2. Variables (Limits/Deductibles)
    md_output.append("\n### EXPLICIT VARIABLES")
    for var in symbol_table.get("explicit_variables", []):
        # Format: **Name**: Value Unit
        name = var['name']
        val = f"{var['value']} {var['unit']}"
        md_output.append(f"- **{name}**: {val}")

    return "\n".join(md_output)
