"""Quick script to render UDM context from extended schema."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.utils.schema_renderer import load_schema
import json

def render_udm_safe(schema_dict):
    """Render UDM with better handling of additionalProperties: false."""
    lines = []

    def _recurse(properties, parent_path=""):
        for key, value in properties.items():
            current_path = f"{parent_path}.{key}" if parent_path else key

            # CASE A: Dynamic Map (only if additionalProperties is an object)
            if "additionalProperties" in value and isinstance(value["additionalProperties"], dict):
                type_value = value['additionalProperties'].get('type', 'any')
                # Handle type as list (e.g., ["string", "number", "boolean", "null"])
                if isinstance(type_value, list):
                    value_type = "/".join(t.capitalize() for t in type_value)
                else:
                    value_type = type_value.capitalize()

                desc = f"* `{current_path}.{{name}}` ({value_type})"

                if "description" in value:
                    desc += f" - {value['description']}"

                lines.append(desc)

            # CASE B: Standard Nested Object (recurse into properties)
            elif "properties" in value:
                _recurse(value["properties"], current_path)

            # CASE C: Array of Objects
            elif value.get("type") == "array" and "items" in value:
                items = value["items"]
                if isinstance(items, dict) and "properties" in items:
                    # Array of objects - show as path[n].field
                    desc = f"* `{current_path}[]` (Array)"
                    if "description" in value:
                        desc += f" - {value['description']}"
                    lines.append(desc)

                    # Show item properties
                    for item_key, item_value in items["properties"].items():
                        item_path = f"{current_path}[].{item_key}"

                        # Check if this is a dynamic map (attributes)
                        if "additionalProperties" in item_value and isinstance(item_value["additionalProperties"], dict):
                            type_value = item_value['additionalProperties'].get('type', 'any')
                            if isinstance(type_value, list):
                                value_type = "/".join(t.capitalize() for t in type_value)
                            else:
                                value_type = type_value.capitalize()

                            desc = f"  * `{item_path}.{{name}}` ({value_type})"
                            if "description" in item_value:
                                desc += f" - {item_value['description']}"
                            lines.append(desc)

                        elif "type" in item_value:
                            meta_parts = [item_value['type'].capitalize()]
                            if "description" in item_value:
                                meta_parts.append(item_value['description'])
                            desc = f"  * `{item_path}` ({'; '.join(meta_parts)})"
                            lines.append(desc)

            # CASE D: Leaf Node (standard variable with type)
            elif "type" in value:
                meta_parts = [value['type'].capitalize()]

                # Add enum constraint if present
                if "enum" in value:
                    enum_values = ", ".join(str(v) for v in value['enum'])
                    meta_parts.append(f"Enum: [{enum_values}]")

                # Add format if present
                if "format" in value:
                    meta_parts.append(f"Format: {value['format']}")

                # Add description if present
                if "description" in value:
                    meta_parts.append(value['description'])

                desc = f"* `{current_path}` ({'; '.join(meta_parts)})"
                lines.append(desc)

    # Start recursion from root properties
    if "properties" in schema_dict:
        _recurse(schema_dict["properties"])
    else:
        print("Warning: Schema has no 'properties' key")

    return "\n".join(lines)


if __name__ == "__main__":
    schema_path = Path(__file__).parent.parent / "src" / "context_builder" / "schemas" / "extended_standard_claim_schema.json"

    print(f"Loading schema: {schema_path.name}\n")
    schema = load_schema(str(schema_path))

    print("=" * 80)
    print("UDM CONTEXT - Extended Standard Claim Schema")
    print("=" * 80)
    print()

    udm = render_udm_safe(schema)
    print(udm)

    print()
    print("=" * 80)
    print(f"Total Variables: {len(udm.splitlines())}")
    print("=" * 80)
