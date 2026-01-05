"""UDM Schema Enrichment for Form Generator.

Loads UDM schema and enriches field information with descriptions and metadata.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional


class UDMSchemaEnricher:
    """Enriches field information with UDM schema descriptions.

    Uses singleton pattern to cache schema loading.
    """

    _instance: Optional['UDMSchemaEnricher'] = None
    _schema: Optional[Dict[str, Any]] = None

    def __new__(cls):
        """Singleton pattern: return same instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize and load UDM schema if not already loaded."""
        if self._schema is None:
            self._load_schema()

    def _load_schema(self) -> None:
        """Load UDM schema from udm_schema.md."""
        # Find schema file
        schema_path = (
            Path(__file__).parent.parent
            / "schemas"
            / "udm_schema.md"
        )

        if not schema_path.exists():
            print(f"[WARNING] UDM schema not found at {schema_path}")
            self._schema = {}
            return

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse markdown to extract field definitions
            self._schema = self._parse_markdown_schema(content)
            print(f"[OK] Loaded UDM schema from {schema_path.name}")
        except Exception as e:
            print(f"[WARNING] Failed to load UDM schema: {e}")
            self._schema = {}

    def _parse_markdown_schema(self, content: str) -> Dict[str, Dict[str, str]]:
        """Parse markdown UDM schema into field definitions.

        Example markdown format:
        * `claim.header.line_of_business` (String; e.g. 'Property', 'Liability')
        * `claim.header.attributes.{name}` (Dynamic; Policy-specific header tags)

        Returns:
            Dict mapping field path -> {"description": "...", "type": "..."}
        """
        schema = {}

        # Match pattern: * `field.path` (Type; description)
        pattern = r'\*\s+`([^`]+)`\s+\(([^)]+)\)'

        for match in re.finditer(pattern, content):
            field_path = match.group(1)
            desc_full = match.group(2)

            # Parse type and description
            # Format: "String; e.g. 'Property', 'Liability'"
            # Format: "Dynamic; Policy-specific header tags"
            # Format: "Date-Time"
            parts = desc_full.split(';', 1)
            field_type = parts[0].strip()
            description = desc_full if len(parts) == 1 else parts[1].strip()

            # Normalize dynamic field patterns
            # {name} means this is a template for dynamic fields
            normalized_path = field_path.replace('{name}', '')

            schema[normalized_path] = {
                "description": description,
                "type": field_type
            }

        return schema

    def get_field_info(self, var_path: str) -> Dict[str, Any]:
        """Get enriched field information from UDM schema.

        Args:
            var_path: Variable path (e.g., "claim.header.line_of_business")

        Returns:
            Dict with:
                - description: Human-readable description
                - schema_type: Type from JSON Schema (if available)
                - schema_format: Format from JSON Schema (if available)
                - is_udm: Whether this is a standard UDM field
        """
        # Normalize array indices
        normalized_path = self._normalize_path(var_path)

        # Try to look up in schema
        schema_info = self._lookup_in_schema(normalized_path)

        if schema_info:
            return {
                "description": schema_info.get("description", self._generate_label(var_path)),
                "schema_type": schema_info.get("type"),
                "schema_format": schema_info.get("format"),
                "is_udm": True,
            }

        # Fallback: generate from field name
        return {
            "description": self._generate_label(var_path),
            "schema_type": None,
            "schema_format": None,
            "is_udm": False,
        }

    def _normalize_path(self, var_path: str) -> str:
        """Normalize variable path for schema lookup.

        Examples:
            claim.parties.claimants[0].role -> claim.parties.claimants.role
            claim.amounts[].type -> claim.amounts.type
        """
        # Remove array indices
        normalized = re.sub(r'\[\d*\]\.', '.', var_path)
        # Remove trailing []
        normalized = re.sub(r'\[\d*\]$', '', normalized)
        return normalized

    def _lookup_in_schema(self, var_path: str) -> Optional[Dict[str, Any]]:
        """Look up variable path in UDM schema.

        Args:
            var_path: Normalized variable path

        Returns:
            Schema definition dict if found, else None
        """
        if not self._schema:
            return None

        # Direct lookup first
        if var_path in self._schema:
            return self._schema[var_path]

        # Check for dynamic attributes patterns
        # e.g., claim.header.attributes.trip_type matches claim.header.attributes.
        for schema_path, schema_info in self._schema.items():
            # Check if var_path starts with a dynamic field pattern
            if schema_path.endswith('.') and var_path.startswith(schema_path):
                return schema_info

        return None

    def _generate_label(self, var_path: str) -> str:
        """Generate human-readable label from variable path.

        Examples:
            claim.header.line_of_business -> Line of Business
            claim.incident.primary_cause_code -> Primary Cause Code
            claim.custom.trip_type -> Trip Type
        """
        # Get last part of path
        parts = var_path.split(".")
        field_name = parts[-1]

        # Handle array notation
        field_name = re.sub(r'\[\d*\]', '', field_name)

        # Convert snake_case to Title Case
        words = field_name.split("_")
        label = " ".join(word.capitalize() for word in words)

        return label

    def categorize_field(self, var_path: str) -> str:
        """Categorize field by UDM section.

        Args:
            var_path: Variable path

        Returns:
            Category: header, incident, parties, financials, policy_specific
        """
        if "header" in var_path:
            return "header"
        elif "incident" in var_path:
            return "incident"
        elif "parties" in var_path or "claimants" in var_path:
            return "parties"
        elif "financials" in var_path or "amounts" in var_path:
            return "financials"
        else:
            return "policy_specific"

    def is_array_field(self, var_path: str) -> bool:
        """Check if field is an array element.

        Args:
            var_path: Variable path

        Returns:
            True if path contains array notation
        """
        return "[]" in var_path or re.search(r'\[\d+\]', var_path) is not None

    def flatten_array_field(self, var_path: str) -> Dict[str, Any]:
        """Flatten array field for form UI.

        Examples:
            claim.parties.claimants[].role ->
                ui_key: claimant_role
                original_path: claim.parties.claimants[].role
                is_repeatable: True

        Args:
            var_path: Variable path with array notation

        Returns:
            Dict with ui_key, original_path, is_repeatable
        """
        # Remove array notation
        flattened = re.sub(r'\[\d*\]', '', var_path)

        # Generate UI key from last two parts
        parts = flattened.split(".")
        if len(parts) >= 2:
            # e.g., claimants.role -> claimant_role
            container = parts[-2].rstrip("s")  # Remove plural
            field = parts[-1]
            ui_key = f"{container}_{field}"
        else:
            ui_key = parts[-1]

        return {
            "ui_key": ui_key,
            "original_path": var_path,
            "is_repeatable": True,
        }
