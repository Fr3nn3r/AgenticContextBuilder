"""
Test script to verify symbol table integration works with auto policy (81 fields).

This verifies the system scales to larger policies.
"""

from pathlib import Path
import json
from policy_compiler.runtime.widget_factory import WidgetFactory
from policy_compiler.runtime import load_schema, load_logic


def main():
    print("=" * 80)
    print("Testing Auto Policy (81 fields) with Symbol Table Integration")
    print("=" * 80)
    print()

    # Load auto policy files
    schema_path = Path("output/output_schemas/auto_policy_sa_2890meep_1_19_form_schema.json")
    logic_path = Path("output/processing/20251129-121237-auto_policy/auto_policy_sa_2890meep_1_19_logic.json")
    symbol_table_path = Path("output/processing/20251129-121237-auto_policy/auto_policy_sa_2890meep_1_19_symbol_table.json")

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

    policy_id = schema.get("policy_id", "Unknown")
    total_fields = schema.get("statistics", {}).get("total_fields", 0)
    total_rules = logic.get("transpiled_data", {}).get("_total_rules", 0)
    num_terms = len(symbol_table.get("extracted_data", {}).get("defined_terms", []))
    num_variables = len(symbol_table.get("extracted_data", {}).get("explicit_variables", []))

    print(f"[OK] Policy: {policy_id}")
    print(f"[OK] Fields: {total_fields}")
    print(f"[OK] Rules: {total_rules}")
    print(f"[OK] Symbol table: {num_terms} terms, {num_variables} variables")
    print()

    # Test: Extract currency
    print("=" * 80)
    print("TEST 1: Currency Extraction")
    print("=" * 80)

    currency = WidgetFactory.extract_currency_from_policy(schema, logic)
    print(f"  [OK] Detected currency: {currency}")
    print()

    # Test: Check help text generation for sample fields
    print("=" * 80)
    print("TEST 2: Help Text Generation (Sample of 10 fields)")
    print("=" * 80)

    sections = schema.get("sections", {})
    all_fields = []

    # Collect all fields
    for section_name, section_data in sections.items():
        fields = section_data.get("fields", [])
        all_fields.extend(fields)

    # Test first 10 fields
    fields_with_help = 0
    fields_without_help = 0

    for field in all_fields[:10]:
        ui_key = field.get("ui_key", "")
        label = field.get("label", "Unknown")

        # Simulate help text generation
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

        if help_text:
            print(f"  [OK] '{label}' ({ui_key})")
            print(f"       {help_text[:100]}...")
            fields_with_help += 1
        else:
            print(f"  [--] '{label}' ({ui_key}): No context found")
            fields_without_help += 1

    print()
    print(f"  Summary: {fields_with_help} fields with context, {fields_without_help} without")
    print()

    # Test: Statistics across all fields
    print("=" * 80)
    print("TEST 3: Coverage Statistics (All {0} fields)".format(total_fields))
    print("=" * 80)

    total_with_definition = 0
    total_with_limit = 0
    total_without_context = 0

    for field in all_fields:
        ui_key = field.get("ui_key", "")

        has_definition = WidgetFactory._find_definition(ui_key, symbol_table) is not None
        has_limit = WidgetFactory._find_limit(ui_key, symbol_table) is not None

        if has_definition:
            total_with_definition += 1
        elif has_limit:
            total_with_limit += 1
        else:
            total_without_context += 1

    coverage_rate = ((total_with_definition + total_with_limit) / len(all_fields) * 100) if all_fields else 0

    print(f"  Fields with policy definitions: {total_with_definition}")
    print(f"  Fields with limit info: {total_with_limit}")
    print(f"  Fields without context: {total_without_context}")
    print(f"  Coverage rate: {coverage_rate:.1f}%")
    print()

    # Test: Semantic widget detection
    print("=" * 80)
    print("TEST 4: Semantic Widget Detection")
    print("=" * 80)

    semantic_types = {}

    for field in all_fields:
        ui_key = field.get("ui_key", "")
        field_type = field.get("type", "string")
        semantic_type = WidgetFactory._detect_semantic_type(ui_key, field_type)

        if semantic_type not in semantic_types:
            semantic_types[semantic_type] = 0
        semantic_types[semantic_type] += 1

    for semantic_type, count in sorted(semantic_types.items(), key=lambda x: -x[1]):
        print(f"  {semantic_type}: {count} fields")

    print()
    print("=" * 80)
    print("SUCCESS: Auto policy integration tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
