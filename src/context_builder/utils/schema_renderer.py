"""
Render JSON Schema as UDM (Unified Data Model) context for LLM prompts.

Converts JSON Schema into token-efficient markdown variable documentation that
ensures prompt-schema alignment and prevents hallucinated variables.
"""

import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def render_udm_context(schema_dict: Dict[str, Any]) -> str:
    """
    Convert JSON Schema into markdown-formatted UDM variable list for LLM context.

    Recursively parses schema to extract:
    - Variable paths (e.g., claim.loss.cause_primary)
    - Types (String, Number, Boolean, etc.)
    - Enum constraints (e.g., [fire, flood, windstorm])
    - Descriptions from schema
    - Dynamic maps via additionalProperties detection

    Args:
        schema_dict: Loaded JSON schema dictionary with $schema and properties

    Returns:
        Markdown-formatted bullet list of allowed variables

    Example output:
        * `claim.meta.jurisdiction` (String; ISO Country/Region code)
        * `claim.loss.cause_primary` (String; Enum: [fire, flood, earth_movement])
        * `claim.financials.amount_claimed` (Number)
        * `policy_snapshot.limits.{name}` (Number) - Dynamic keys derived from Symbol Table
    """
    lines = []

    def _recurse(properties: Dict[str, Any], parent_path: str = "") -> None:
        """
        Recursively traverse schema properties to build variable list.

        Args:
            properties: Properties dict from schema level
            parent_path: Dot-separated parent path (e.g., "claim.loss")
        """
        for key, value in properties.items():
            current_path = f"{parent_path}.{key}" if parent_path else key

            # CASE A: Dynamic Map (detected by additionalProperties)
            # Used for policy limits, deductibles, and other runtime-defined keys
            if "additionalProperties" in value:
                value_type = value['additionalProperties'].get('type', 'any').capitalize()

                # Format as path.{name} to indicate dynamic key
                desc = f"* `{current_path}.{{name}}` ({value_type})"

                # Append schema description if exists
                if "description" in value:
                    desc += f" - {value['description']}"

                lines.append(desc)

            # CASE B: Standard Nested Object (recurse into properties)
            elif "properties" in value:
                _recurse(value["properties"], current_path)

            # CASE C: Leaf Node (standard variable with type)
            elif "type" in value:
                meta_parts = [value['type'].capitalize()]

                # Add enum constraint if present (critical for valid logic)
                if "enum" in value:
                    enum_values = ", ".join(str(v) for v in value['enum'])
                    meta_parts.append(f"Enum: [{enum_values}]")

                # Add description if present
                if "description" in value:
                    meta_parts.append(value['description'])

                # Format: * `path` (Type; Enum: [...]; Description)
                desc = f"* `{current_path}` ({'; '.join(meta_parts)})"
                lines.append(desc)

    # Start recursion from root properties
    if "properties" in schema_dict:
        _recurse(schema_dict["properties"])
    else:
        logger.warning("Schema has no 'properties' key - empty UDM context generated")

    return "\n".join(lines)


def load_schema(schema_path: str) -> Dict[str, Any]:
    """
    Load JSON schema from file.

    Args:
        schema_path: Path to JSON schema file

    Returns:
        Parsed schema dictionary

    Raises:
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema is invalid JSON
    """
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)
