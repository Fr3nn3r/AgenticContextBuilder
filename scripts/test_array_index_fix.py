"""Test script to verify numeric array index normalization in PolicyLinter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.extraction.policy_logic_linter import validate_rules


def test_numeric_array_indices():
    """Test that numeric array indices are accepted."""
    print("=" * 80)
    print("TEST: Numeric Array Index Validation")
    print("=" * 80)

    # Test data with numeric array indices
    rules_data = {
        "rules": [
            {
                "id": "rule_test_numeric_index",
                "name": "Test Numeric Array Index",
                "type": "COVERAGE",
                "logic": {
                    "op": ">=",
                    "args": [
                        # Using numeric index: claim.financials.amounts[0].amount
                        {"op": "var", "args": ["claim.financials.amounts[0].amount"]},
                        1000
                    ]
                }
            },
            {
                "id": "rule_test_multiple_indices",
                "name": "Test Multiple Numeric Indices",
                "type": "COVERAGE",
                "logic": {
                    "op": "==",
                    "args": [
                        # Using multiple numeric indices
                        {"op": "var", "args": ["claim.parties.claimants[0].role"]},
                        "insured"
                    ]
                }
            },
            {
                "id": "rule_test_empty_bracket",
                "name": "Test Empty Bracket (should still work)",
                "type": "COVERAGE",
                "logic": {
                    "op": "==",
                    "args": [
                        # Using empty bracket notation (original behavior)
                        {"op": "var", "args": ["claim.parties.claimants[].role"]},
                        "insured"
                    ]
                }
            }
        ]
    }

    # Validate rules
    report = validate_rules(rules_data)

    # Print results
    print(f"\nValidation Summary:")
    print(f"  Total Rules: {report.summary['total_rules']}")
    print(f"  Clean Rules: {report.summary['clean_rules']}")
    print(f"  Total Violations: {report.summary['violations']}")
    print(f"  Critical Violations: {report.summary['critical_violations']}")
    print(f"  Warnings: {report.summary['warnings']}")

    # Check for VOCAB_ERROR violations
    vocab_errors = [v for v in report.violations if v['type'] == 'VOCAB_ERROR']

    if vocab_errors:
        print(f"\n[FAIL] Found {len(vocab_errors)} vocabulary errors:")
        for v in vocab_errors:
            print(f"  - Variable: {v['variable']}")
            print(f"    Message: {v['message']}")
        return False
    else:
        print("\n[OK] All numeric array indices validated successfully!")
        print("\nVariables tested:")
        print("  - claim.financials.amounts[0].amount")
        print("  - claim.parties.claimants[0].role")
        print("  - claim.parties.claimants[].role")
        return True


if __name__ == "__main__":
    success = test_numeric_array_indices()
    sys.exit(0 if success else 1)
