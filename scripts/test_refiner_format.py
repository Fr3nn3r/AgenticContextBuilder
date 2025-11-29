"""Test script to verify linter error report formatting for refiner."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.extraction.policy_logic_linter import (
    validate_rules,
    format_linter_report_for_refiner,
)
import json


def test_error_report_formatting():
    """Test formatting of error report for refiner prompt."""
    print("=" * 80)
    print("TEST: Error Report Formatting for Refiner")
    print("=" * 80)

    # Create test data with violations
    rules_data = {
        "rules": [
            {
                "id": "rule_null_bug_test",
                "name": "NULL Bug Test Rule",
                "type": "COVERAGE",
                "reasoning": "This rule tests NULL bug detection in the 'in' operator.",
                "source_ref": "Coverage applies when the cause is in the covered perils list.",
                "logic": {
                    "op": "in",
                    "args": [
                        {"op": "var", "args": ["claim.incident.primary_cause_code"]},
                        ["flood", "fire", None]  # NULL in list
                    ]
                }
            },
            {
                "id": "rule_vocab_error_test",
                "name": "Vocabulary Error Test",
                "type": "EXCLUSION",
                "reasoning": "This rule tests unknown variable detection.",
                "source_ref": "Excludes claims where the incident occurred during war.",
                "logic": {
                    "op": "==",
                    "args": [
                        {"op": "var", "args": ["incident.primary_cause_code"]},  # Wrong path
                        "war"
                    ]
                }
            },
            {
                "id": "rule_syntax_error_test",
                "name": "Syntax Error Test",
                "type": "LIMIT",
                "reasoning": "This rule tests syntax error detection (wrong arg count).",
                "source_ref": "Limit is $10,000 if flood, otherwise $5,000.",
                "logic": {
                    "op": "if",
                    "args": [
                        {"op": "==", "args": [{"op": "var", "args": ["claim.incident.primary_cause_code"]}, "flood"]}
                        # Missing true_value and false_value
                    ]
                }
            },
            {
                "id": "rule_clean",
                "name": "Clean Rule (No Violations)",
                "type": "COVERAGE",
                "reasoning": "This rule has no violations.",
                "source_ref": "Coverage applies to property damage.",
                "logic": {
                    "op": "==",
                    "args": [
                        {"op": "var", "args": ["claim.incident.primary_cause_code"]},
                        "property_damage"
                    ]
                }
            }
        ]
    }

    # Validate to get violations
    print("\nRunning PolicyLinter validation...\n")
    validation_report = validate_rules(rules_data)

    print(f"Validation Summary:")
    print(f"  Total Rules: {validation_report.summary['total_rules']}")
    print(f"  Violations: {validation_report.summary['violations']}")
    print(f"  Clean Rules: {validation_report.summary['clean_rules']}")
    print()

    # Format error report for refiner
    print("Formatting error report for refiner...\n")
    formatted_report, error_count = format_linter_report_for_refiner(
        validation_report, rules_data["rules"], max_rules=20
    )

    # Display formatted report
    print("=" * 80)
    print(f"FORMATTED ERROR REPORT (error_count={error_count})")
    print("=" * 80)
    print()
    print(formatted_report)
    print()
    print("=" * 80)

    # Verify format
    checks = []

    # Check 1: Error count matches unique rules with violations
    expected_error_count = len(set(v["rule_id"] for v in validation_report.violations))
    checks.append(("Error count", error_count == expected_error_count))

    # Check 2: Report contains numbered rules
    checks.append(("Contains '1. Rule ID:'", "1. Rule ID:" in formatted_report))
    checks.append(("Contains '2. Rule ID:'", "2. Rule ID:" in formatted_report))

    # Check 3: Report contains separators
    checks.append(("Contains '---'", "---" in formatted_report))

    # Check 4: Report contains violation types
    checks.append(("Contains '[NULL_BUG]'", "[NULL_BUG]" in formatted_report))
    checks.append(("Contains '[VOCAB_ERROR]'", "[VOCAB_ERROR]" in formatted_report))
    checks.append(("Contains '[SYNTAX_ERROR]'", "[SYNTAX_ERROR]" in formatted_report))

    # Check 5: Report contains current logic
    checks.append(("Contains 'Current Logic:'", "Current Logic:" in formatted_report))

    # Check 6: Report contains source references
    checks.append(("Contains 'Source Reference:'", "Source Reference:" in formatted_report))

    # Check 7: Clean rule should NOT appear
    checks.append(("Clean rule excluded", "rule_clean" not in formatted_report))

    # Print check results
    print("\nValidation Checks:")
    all_passed = True
    for check_name, passed in checks:
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("[OK] All formatting checks passed!")
        return True
    else:
        print("[FAIL] Some formatting checks failed")
        return False


if __name__ == "__main__":
    success = test_error_report_formatting()
    sys.exit(0 if success else 1)
