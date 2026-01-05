"""
Quick test script to verify the schema-driven architecture works with auto policy.

This proves the CTO's success criteria: the system works with a different policy type
without any code changes.
"""

from pathlib import Path
from policy_compiler.runtime import (
    load_schema,
    load_logic,
    SchemaBasedClaimMapper,
    NeuroSymbolicEvaluator,
    ResultInterpreter
)


def main():
    print("=" * 80)
    print("Testing Schema-Driven Architecture with Auto Policy")
    print("=" * 80)
    print()

    # Load auto policy files
    schema_path = Path("output/output_schemas/auto_policy_sa_2890meep_1_19_form_schema.json")
    logic_path = Path("output/processing/20251129-121237-auto_policy/auto_policy_sa_2890meep_1_19_logic.json")

    if not schema_path.exists():
        print(f"[X] Schema file not found: {schema_path}")
        return

    if not logic_path.exists():
        print(f"[X] Logic file not found: {logic_path}")
        return

    print("[OK] Loading auto policy schema and logic...")
    schema = load_schema(schema_path)
    logic = load_logic(logic_path)

    # Display policy info
    policy_id = schema.get("policy_id", "Unknown")
    total_fields = schema.get("statistics", {}).get("total_fields", 0)
    total_rules = logic.get("transpiled_data", {}).get("_total_rules", 0)

    print(f"[OK] Policy: {policy_id}")
    print(f"[OK] Fields: {total_fields}")
    print(f"[OK] Rules: {total_rules}")
    print()

    # Create sample auto claim data
    print("[OK] Creating sample auto claim data...")
    flat_claim_data = {
        "claim.header.claim_type": "first_party",
        "claim.header.policy_number": "AUTO-001",
        "claim.incident.date": "2025-11-29",
        "claim.incident.location": "Highway 401, Toronto",
        "claim.incident.attributes.is_collision": True,
        "claim.incident.attributes.is_vehicle_damage": True,
        "claim.parties.claimants[0].role": "insured",
        "claim.financials.claim_amount": 15000
    }

    # Initialize components (SAME CODE as insurance policy)
    print("[OK] Initializing components...")
    mapper = SchemaBasedClaimMapper()
    evaluator = NeuroSymbolicEvaluator()
    interpreter = ResultInterpreter()

    # Step 1: Validate
    print("[OK] Validating claim data...")
    errors = mapper.validate(flat_claim_data, schema)
    if errors:
        print(f"[X] Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"    - {error}")
        return
    else:
        print("[OK] Validation passed!")

    # Step 2: Inflate
    print("[OK] Inflating flat data to nested structure...")
    nested_claim_data = mapper.inflate(flat_claim_data, schema)
    print(f"[OK] Inflated structure has {len(nested_claim_data)} top-level key(s)")

    # Step 3: Evaluate
    print("[OK] Executing policy rules...")
    raw_result = evaluator.evaluate(logic, nested_claim_data)

    limits = raw_result.get("limits", [])
    conditions = raw_result.get("conditions", [])
    exclusions = raw_result.get("exclusions", [])
    deductibles = raw_result.get("deductibles", [])

    print(f"[OK] Evaluated {len(limits)} limits, {len(conditions)} conditions, "
          f"{len(exclusions)} exclusions, {len(deductibles)} deductibles")

    # Step 4: Interpret
    print("[OK] Interpreting results...")
    rich_result = interpreter.interpret(raw_result, logic)

    summary = rich_result.get("summary", {})
    financials = rich_result.get("financials", {})
    reasoning_trace = rich_result.get("reasoning_trace", {})
    metadata = rich_result.get("metadata", {})

    # Display results
    print()
    print("=" * 80)
    print("EVALUATION RESULT")
    print("=" * 80)
    print()

    status = summary.get("status", "UNKNOWN")
    message = summary.get("primary_message", "No message")
    color_code = summary.get("color_code", "gray")

    color_symbols = {
        "green": "[OK]",
        "red": "[X]",
        "orange": "[!]",
        "gray": "[?]"
    }

    print(f"{color_symbols.get(color_code, '[?]')} Status: {status}")
    print(f"{color_symbols.get(color_code, '[?]')} Message: {message}")
    print()

    # Financials
    if financials.get("applicable_limit"):
        limit = financials["applicable_limit"]
        print(f"[OK] Coverage Limit: {limit.get('currency', 'CAD')} ${limit.get('amount', 0):,.2f}")
        print(f"    Category: {limit.get('category', 'Unknown')}")

    if financials.get("applicable_deductible"):
        deductible = financials["applicable_deductible"]
        print(f"[OK] Deductible: {deductible.get('currency', 'CAD')} ${deductible.get('amount', 0):,.2f}")

    print()

    # Reasoning trace
    triggers = reasoning_trace.get("triggers", [])
    red_flags = reasoning_trace.get("red_flags", [])

    if triggers:
        print(f"[OK] Conditions Met: {len(triggers)}")
        for trigger in triggers[:3]:  # Show first 3
            print(f"    - {trigger.get('rule_name', 'Unknown')}")

    if red_flags:
        print(f"[X] Exclusions Triggered: {len(red_flags)}")
        for flag in red_flags[:3]:  # Show first 3
            print(f"    - {flag.get('rule_name', 'Unknown')}")

    print()
    print(f"[OK] Execution time: {metadata.get('execution_time_ms', 0)} ms")
    print()

    print("=" * 80)
    print("SUCCESS: Auto policy processed without ANY code changes!")
    print("=" * 80)


if __name__ == "__main__":
    main()
