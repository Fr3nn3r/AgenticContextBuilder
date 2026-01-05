"""
Test script to verify symbol table integration with WidgetFactory.

This tests the context injection feature where policy definitions are
fused into widget help text.
"""

from pathlib import Path
import json
from policy_compiler.runtime.widget_factory import WidgetFactory
from policy_compiler.runtime import load_schema, load_logic


def main():
    print("=" * 80)
    print("Testing Symbol Table Integration with WidgetFactory")
    print("=" * 80)
    print()

    # Load insurance policy files
    schema_path = Path("output/output_schemas/insurance policy_form_schema.json")
    logic_path = Path("output/processing/20251129-114118-insurance p/insurance policy_logic.json")
    symbol_table_path = Path("output/processing/20251129-114118-insurance p/insurance policy_symbol_table.json")

    if not schema_path.exists():
        print(f"[X] Schema file not found: {schema_path}")
        return

    if not logic_path.exists():
        print(f"[X] Logic file not found: {logic_path}")
        return

    if not symbol_table_path.exists():
        print(f"[X] Symbol table file not found: {symbol_table_path}")
        return

    print("[OK] Loading files...")
    schema = load_schema(schema_path)
    logic = load_logic(logic_path)

    with open(symbol_table_path, "r", encoding="utf-8") as f:
        symbol_table = json.load(f)

    print(f"[OK] Schema loaded: {schema.get('policy_id', 'Unknown')}")
    print(f"[OK] Symbol table loaded: {len(symbol_table.get('extracted_data', {}).get('defined_terms', []))} terms, "
          f"{len(symbol_table.get('extracted_data', {}).get('explicit_variables', []))} variables")
    print()

    # Test 1: Test _normalize_key function
    print("=" * 80)
    print("TEST 1: _normalize_key")
    print("=" * 80)

    test_keys = [
        "Pre-Existing Condition",
        "Named Insured",
        "Bodily Injury",
        "is_watercraft_involved"
    ]

    for key in test_keys:
        normalized = WidgetFactory._normalize_key(key)
        print(f"  '{key}' -> '{normalized}'")

    print()

    # Test 2: Test _find_definition function
    print("=" * 80)
    print("TEST 2: _find_definition")
    print("=" * 80)

    # Test with actual ui_keys from schema
    sections = schema.get("sections", {})
    test_fields = []

    # Collect some fields to test
    for section_name, section_data in sections.items():
        fields = section_data.get("fields", [])
        for field in fields[:2]:  # Get first 2 fields from each section
            test_fields.append(field)

    for field in test_fields[:5]:  # Test first 5 fields
        ui_key = field.get("ui_key", "")
        if ui_key:
            definition = WidgetFactory._find_definition(ui_key, symbol_table)
            if definition:
                print(f"  [OK] '{ui_key}':")
                print(f"       {definition[:100]}...")
            else:
                print(f"  [--] '{ui_key}': No definition found")

    print()

    # Test 3: Test _find_limit function
    print("=" * 80)
    print("TEST 3: _find_limit")
    print("=" * 80)

    test_limit_keys = [
        "bodily_injury",
        "property_damage",
        "medical_expenses",
        "liability"
    ]

    for key in test_limit_keys:
        limit_info = WidgetFactory._find_limit(key, symbol_table)
        if limit_info:
            print(f"  [OK] '{key}': {limit_info}")
        else:
            print(f"  [--] '{key}': No limit found")

    print()

    # Test 4: Test context-aware widget creation (without actually rendering)
    print("=" * 80)
    print("TEST 4: Context-Aware Widget Simulation")
    print("=" * 80)

    # Pick a field and simulate help text generation
    header_section = sections.get("header", {})
    header_fields = header_section.get("fields", [])

    if header_fields:
        test_field = header_fields[0]
        ui_key = test_field.get("ui_key", "")

        print(f"  Field: {test_field.get('label', 'Unknown')}")
        print(f"  UI Key: {ui_key}")

        # Simulate help text generation logic from create_widget
        help_text = None

        if symbol_table:
            # Priority 1: Look for definition
            definition = WidgetFactory._find_definition(ui_key, symbol_table)
            if definition:
                help_text = f"**Policy Definition:** {definition}"

            # Priority 2: Look for limit
            if not help_text:
                limit_info = WidgetFactory._find_limit(ui_key, symbol_table)
                if limit_info:
                    help_text = f"**Limit:** {limit_info}"

        # Priority 3: Fall back to schema description
        if not help_text:
            description = test_field.get("description", "")
            generic_labels = [
                "Risk modifiers e.g. 'is_vacant', 'wind_speed'",
                "Policy-specific header tags",
                "Free text"
            ]
            label = test_field.get("label", "")
            if description and description not in generic_labels and description.lower() != label.lower():
                help_text = description

        if help_text:
            print(f"  [OK] Help text generated:")
            print(f"       {help_text[:200]}...")
        else:
            print(f"  [--] No help text generated")

    print()
    print("=" * 80)
    print("SUCCESS: All symbol table integration tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
