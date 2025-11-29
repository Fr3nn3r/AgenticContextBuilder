"""
Utility module for loading and validating schema and logic JSON files.

This module provides simple file loading with basic structure validation
to ensure the files contain expected keys for the runtime system.
"""

import json
from pathlib import Path
from typing import Dict, Any


class SchemaLoadError(Exception):
    """Raised when schema or logic file cannot be loaded or is invalid."""
    pass


def load_schema(file_path: str | Path) -> Dict[str, Any]:
    """
    Load and validate a form schema JSON file.

    Args:
        file_path: Path to the schema JSON file

    Returns:
        Dictionary containing the schema structure

    Raises:
        SchemaLoadError: If file cannot be loaded or doesn't have required structure

    Expected structure:
        {
            "policy_id": str,
            "sections": {...},
            "statistics": {...}
        }
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except FileNotFoundError:
        raise SchemaLoadError(f"Schema file not found: {file_path}")
    except json.JSONDecodeError as e:
        raise SchemaLoadError(f"Invalid JSON in schema file: {e}")

    # Validate required keys
    if "sections" not in schema:
        raise SchemaLoadError("Schema must contain 'sections' key")

    if not isinstance(schema["sections"], dict):
        raise SchemaLoadError("Schema 'sections' must be a dictionary")

    return schema


def load_logic(file_path: str | Path) -> Dict[str, Any]:
    """
    Load and validate a logic rules JSON file.

    Args:
        file_path: Path to the logic JSON file

    Returns:
        Dictionary containing the logic rules

    Raises:
        SchemaLoadError: If file cannot be loaded or doesn't have required structure

    Expected structure:
        {
            "transpiled_data": {
                "rules": [...]
            }
        }
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            logic = json.load(f)
    except FileNotFoundError:
        raise SchemaLoadError(f"Logic file not found: {file_path}")
    except json.JSONDecodeError as e:
        raise SchemaLoadError(f"Invalid JSON in logic file: {e}")

    # Validate required keys
    if "transpiled_data" not in logic:
        raise SchemaLoadError("Logic file must contain 'transpiled_data' key")

    transpiled = logic["transpiled_data"]
    if "rules" not in transpiled:
        raise SchemaLoadError("Logic 'transpiled_data' must contain 'rules' key")

    if not isinstance(transpiled["rules"], list):
        raise SchemaLoadError("Logic 'rules' must be a list")

    return logic


def get_all_fields(schema: Dict[str, Any]) -> list[Dict[str, Any]]:
    """
    Extract all field definitions from a schema.

    Args:
        schema: Schema dictionary loaded from load_schema()

    Returns:
        List of field definitions with their metadata
        Each field has: key, label, type, options (for enums), required, etc.
    """
    fields = []
    sections = schema.get("sections", {})

    for section_name, section_data in sections.items():
        section_fields = section_data.get("fields", [])
        for field in section_fields:
            fields.append(field)

    return fields


def get_rules_by_type(logic: Dict[str, Any], rule_type: str | None = None) -> list[Dict[str, Any]]:
    """
    Extract rules from logic file, optionally filtered by type.

    Args:
        logic: Logic dictionary loaded from load_logic()
        rule_type: Optional filter (e.g., "limit", "condition", "exclusion", "deductible")

    Returns:
        List of rule definitions
    """
    rules = logic.get("transpiled_data", {}).get("rules", [])

    if rule_type is None:
        return rules

    return [rule for rule in rules if rule.get("type") == rule_type]
