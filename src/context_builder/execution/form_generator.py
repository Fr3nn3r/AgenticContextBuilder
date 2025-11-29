"""Form Generator: Auto-generate claim input schemas from policy logic.

Performs static analysis on compiled policy logic to generate dynamic
input schemas for claims adjusters.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Set
from datetime import datetime, timezone
from collections import defaultdict, Counter

from .type_inference import TypeInferenceEngine, FieldUsage
from .schema_enrichment import UDMSchemaEnricher


class FormGenerator:
    """Generates claim input schemas from policy logic JSON files."""

    VERSION = "1.0.0"

    def __init__(self):
        self.type_engine = TypeInferenceEngine()
        self.enricher = UDMSchemaEnricher()

    def generate_from_file(
        self,
        logic_file: Path,
        output_dir: Path,
        generate_json_schema: bool = True,
        generate_custom: bool = True,
    ) -> Dict[str, Path]:
        """Generate form schemas from a policy logic JSON file.

        Args:
            logic_file: Path to policy logic JSON file
            output_dir: Directory to save generated schemas
            generate_json_schema: Generate JSON Schema format
            generate_custom: Generate custom JSON format

        Returns:
            Dict mapping format name -> output file path
        """
        # Load logic file
        with open(logic_file, "r", encoding="utf-8") as f:
            logic_data = json.load(f)

        # Extract policy ID from filename
        policy_id = logic_file.stem.replace("_logic", "")

        # Analyze logic
        variables = self._extract_all_variables(logic_data)

        # Generate schemas
        output_files = {}

        if generate_custom:
            custom_schema = self._generate_custom_schema(
                policy_id, logic_file, variables
            )
            custom_path = output_dir / f"{policy_id}_form_schema.json"
            self._save_json(custom_schema, custom_path)
            output_files["custom"] = custom_path

        if generate_json_schema:
            json_schema = self._generate_json_schema(policy_id, variables)
            schema_path = output_dir / f"{policy_id}_form_schema.jsonschema"
            self._save_json(json_schema, schema_path)
            output_files["jsonschema"] = schema_path

        return output_files

    def _extract_all_variables(self, logic_data: Dict[str, Any]) -> List[str]:
        """Extract all variable references from policy logic.

        Args:
            logic_data: Loaded logic JSON (with 'rules' key)

        Returns:
            List of unique variable paths
        """
        # Find rules
        rules = self._find_rules(logic_data)

        if not rules:
            return []

        # Analyze each rule
        for rule in rules:
            logic = rule.get("logic", {})
            self.type_engine.analyze_logic(logic)

        # Return unique variables
        return list(self.type_engine.field_usage.keys())

    def _find_rules(self, logic_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find rules in logic data structure.

        Supports multiple formats:
        - {"rules": [...]}
        - {"transpiled_data": {"rules": [...]}}
        - {"extracted_data": {"rules": [...]}}
        """
        if "rules" in logic_data:
            return logic_data["rules"]
        elif "transpiled_data" in logic_data:
            return logic_data["transpiled_data"].get("rules", [])
        elif "extracted_data" in logic_data:
            return logic_data["extracted_data"].get("rules", [])
        return []

    def _generate_custom_schema(
        self, policy_id: str, source_file: Path, variables: List[str]
    ) -> Dict[str, Any]:
        """Generate custom JSON format optimized for form UI.

        Args:
            policy_id: Policy identifier
            source_file: Source logic file
            variables: List of variable paths

        Returns:
            Custom schema dict
        """
        # Group variables by section
        sections = self._organize_by_section(variables)

        # Build field definitions
        field_stats = {"by_type": Counter(), "by_category": Counter()}

        for section_name, section_data in sections.items():
            var_paths = section_data["fields"]  # Extract variable paths list
            field_list = []
            for var_path in sorted(var_paths):
                field_def = self._build_field_definition(var_path)
                field_list.append(field_def)

                # Update statistics
                field_type = field_def.get("type", "string")
                field_stats["by_type"][field_type] += 1
                field_stats["by_category"][field_def["category"]] += 1

            sections[section_name]["fields"] = field_list

        # Build final schema
        return {
            "policy_id": policy_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_file": source_file.name,
            "generator_version": self.VERSION,
            "sections": {
                "header": {
                    "title": "Claim Header Information",
                    "order": 1,
                    "fields": sections.get("header", {}).get("fields", []),
                },
                "incident": {
                    "title": "Incident Details",
                    "order": 2,
                    "fields": sections.get("incident", {}).get("fields", []),
                },
                "parties": {
                    "title": "Parties Involved",
                    "order": 3,
                    "fields": sections.get("parties", {}).get("fields", []),
                },
                "financials": {
                    "title": "Financial Information",
                    "order": 4,
                    "fields": sections.get("financials", {}).get("fields", []),
                },
                "policy_specific": {
                    "title": "Policy-Specific Fields",
                    "order": 5,
                    "fields": sections.get("policy_specific", {}).get("fields", []),
                },
            },
            "statistics": {
                "total_fields": len(variables),
                "by_type": dict(field_stats["by_type"]),
                "by_category": dict(field_stats["by_category"]),
            },
        }

    def _organize_by_section(
        self, variables: List[str]
    ) -> Dict[str, Dict[str, List[str]]]:
        """Organize variables by UDM section.

        Args:
            variables: List of variable paths

        Returns:
            Dict mapping section name -> {"fields": [var_paths]}
        """
        sections = defaultdict(lambda: {"fields": []})

        for var in variables:
            section = self.enricher.categorize_field(var)
            sections[section]["fields"].append(var)

        return dict(sections)

    def _build_field_definition(self, var_path: str) -> Dict[str, Any]:
        """Build complete field definition with type, description, etc.

        Args:
            var_path: Variable path

        Returns:
            Field definition dict
        """
        # Get type inference
        type_info = self.type_engine.infer_type(var_path)

        # Get UDM enrichment
        udm_info = self.enricher.get_field_info(var_path)

        # Handle array fields
        if self.enricher.is_array_field(var_path):
            array_info = self.enricher.flatten_array_field(var_path)
            ui_key = array_info["ui_key"]
            is_repeatable = True
        else:
            # Generate UI key from last part
            ui_key = var_path.split(".")[-1]
            is_repeatable = False

        # Get usage count
        usage = self.type_engine.field_usage.get(var_path)
        usage_count = len(usage.compared_values) if usage else 0

        # Determine category
        category = "udm_core" if udm_info["is_udm"] else "policy_specific"

        # Build base definition
        field_def = {
            "key": var_path,
            "ui_key": ui_key,
            "label": udm_info["description"],
            "type": type_info.get("type", "string"),
            "description": udm_info["description"],
            "category": category,
            "required": False,  # Conservative: assume optional
            "repeatable": is_repeatable,
        }

        # Add type-specific properties
        if type_info.get("type") == "enum" and "options" in type_info:
            field_def["options"] = type_info["options"]

        if "format" in type_info:
            field_def["format"] = type_info["format"]

        # Add usage metadata
        field_def["usage_count"] = usage_count

        return field_def

    def _generate_json_schema(
        self, policy_id: str, variables: List[str]
    ) -> Dict[str, Any]:
        """Generate JSON Schema (draft-07) format.

        Args:
            policy_id: Policy identifier
            variables: List of variable paths

        Returns:
            JSON Schema dict
        """
        properties = {}
        required_fields = []

        for var_path in variables:
            # Get type inference
            type_info = self.type_engine.infer_type(var_path)

            # Get UDM enrichment
            udm_info = self.enricher.get_field_info(var_path)

            # Build property schema
            prop_schema = {
                "description": udm_info["description"],
            }

            # Map type
            field_type = type_info.get("type", "string")
            if field_type == "enum":
                prop_schema["type"] = "string"
                if "options" in type_info:
                    prop_schema["enum"] = type_info["options"]
            elif field_type in ["integer", "number", "boolean"]:
                prop_schema["type"] = field_type
            else:
                prop_schema["type"] = "string"
                if "format" in type_info:
                    prop_schema["format"] = type_info["format"]

            # Use normalized key (replace dots with underscores)
            schema_key = var_path.replace(".", "_").replace("[]", "")
            properties[schema_key] = prop_schema

        # Build root schema
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": f"https://example.com/schemas/{policy_id}_claim_input.schema.json",
            "title": f"{policy_id} Claim Input Schema",
            "description": f"Auto-generated claim input schema for policy {policy_id}",
            "type": "object",
            "properties": properties,
            "required": required_fields,  # Conservative: no required fields
        }

    def _save_json(self, data: Dict[str, Any], output_path: Path) -> None:
        """Save JSON data to file with pretty formatting.

        Args:
            data: Data to save
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[OK] Saved schema to {output_path}")
