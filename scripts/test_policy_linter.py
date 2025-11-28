"""Test script for PolicyLinter validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.extraction.policy_logic_linter import validate_rules
import json


def test_valid_rules():
    """Test with valid rules (should pass)."""
    print("=" * 80)
    print("TEST 1: Valid Rules")
    print("=" * 80)

    rules_data = {
        "rules": [
            {
                "id": "rule_flood_coverage",
                "name": "Flood Coverage Check",
                "type": "COVERAGE",
                "logic": {
                    "op": "==",
                    "args": [
                        {"op": "var", "args": ["claim.incident.primary_cause_code"]},
                        "flood"
                    ]
                }
            }
        ]
    }

    report = validate_rules(rules_data)
    print(f"\nSummary: {report.summary}")
    print(f"Violations: {len(report.violations)}")

    if report.violations:
        print("\nViolations found:")
        for v in report.violations:
            print(f"  - [{v['type']}] {v['message']}")

    return report.summary["violations"] == 0


def test_null_bug():
    """Test NULL bug detection."""
    print("\n" + "=" * 80)
    print("TEST 2: NULL Bug Detection")
    print("=" * 80)

    rules_data = {
        "rules": [
            {
                "id": "rule_null_bug",
                "name": "NULL Bug Test",
                "type": "COVERAGE",
                "logic": {
                    "op": "in",
                    "args": [
                        {"op": "var", "args": ["claim.incident.primary_cause_code"]},
                        ["flood", "fire", None]  # NULL in list
                    ]
                }
            }
        ]
    }

    report = validate_rules(rules_data)
    print(f"\nSummary: {report.summary}")
    print(f"Violations: {len(report.violations)}")

    if report.violations:
        print("\nViolations found:")
        for v in report.violations:
            print(f"  - [{v['type']}] {v['severity']}: {v['message']}")

    # Should detect NULL bug
    has_null_bug = any(v["type"] == "NULL_BUG" for v in report.violations)
    print(f"\n[{'OK' if has_null_bug else 'FAIL'}] NULL bug detection")
    return has_null_bug


def test_invalid_vocab():
    """Test invalid vocabulary detection."""
    print("\n" + "=" * 80)
    print("TEST 3: Invalid Vocabulary Detection")
    print("=" * 80)

    rules_data = {
        "rules": [
            {
                "id": "rule_invalid_vocab",
                "name": "Invalid Vocab Test",
                "type": "COVERAGE",
                "logic": {
                    "op": "==",
                    "args": [
                        {"op": "var", "args": ["claim.custom.my_field"]},  # custom.* not allowed
                        "some_value"
                    ]
                }
            }
        ]
    }

    report = validate_rules(rules_data)
    print(f"\nSummary: {report.summary}")
    print(f"Violations: {len(report.violations)}")

    if report.violations:
        print("\nViolations found:")
        for v in report.violations:
            print(f"  - [{v['type']}] {v['severity']}: {v['message']}")

    # Should detect vocab error
    has_vocab_error = any(v["type"] == "VOCAB_ERROR" for v in report.violations)
    print(f"\n[{'OK' if has_vocab_error else 'FAIL'}] Vocab error detection")
    return has_vocab_error


def test_valid_attributes():
    """Test that attributes.* pattern is allowed."""
    print("\n" + "=" * 80)
    print("TEST 4: Valid Attributes Pattern")
    print("=" * 80)

    rules_data = {
        "rules": [
            {
                "id": "rule_attributes",
                "name": "Attributes Test",
                "type": "COVERAGE",
                "logic": {
                    "op": "==",
                    "args": [
                        {"op": "var", "args": ["claim.header.attributes.trip_type"]},
                        "business"
                    ]
                }
            }
        ]
    }

    report = validate_rules(rules_data)
    print(f"\nSummary: {report.summary}")
    print(f"Violations: {len(report.violations)}")

    if report.violations:
        print("\nViolations found:")
        for v in report.violations:
            print(f"  - [{v['type']}] {v['severity']}: {v['message']}")

    # Should pass (no vocab errors)
    has_vocab_error = any(v["type"] == "VOCAB_ERROR" for v in report.violations)
    print(f"\n[{'OK' if not has_vocab_error else 'FAIL'}] Attributes pattern allowed")
    return not has_vocab_error


def test_syntax_errors():
    """Test syntax error detection (wrong arg count)."""
    print("\n" + "=" * 80)
    print("TEST 5: Syntax Error Detection (Argument Count)")
    print("=" * 80)

    rules_data = {
        "rules": [
            {
                "id": "rule_syntax_error",
                "name": "Syntax Error Test",
                "type": "COVERAGE",
                "logic": {
                    "op": "==",
                    "args": [
                        {"op": "var", "args": ["claim.incident.primary_cause_code"]}
                        # Missing second argument
                    ]
                }
            }
        ]
    }

    report = validate_rules(rules_data)
    print(f"\nSummary: {report.summary}")
    print(f"Violations: {len(report.violations)}")

    if report.violations:
        print("\nViolations found:")
        for v in report.violations:
            print(f"  - [{v['type']}] {v['severity']}: {v['message']}")

    # Should detect syntax error
    has_syntax_error = any(v["type"] == "SYNTAX_ERROR" for v in report.violations)
    print(f"\n[{'OK' if has_syntax_error else 'FAIL'}] Syntax error detection")
    return has_syntax_error


def test_tautology():
    """Test tautology detection."""
    print("\n" + "=" * 80)
    print("TEST 6: Tautology Detection")
    print("=" * 80)

    rules_data = {
        "rules": [
            {
                "id": "rule_tautology",
                "name": "Tautology Test",
                "type": "COVERAGE",
                "logic": {
                    "op": "==",
                    "args": [5, 5]  # Always true
                }
            }
        ]
    }

    report = validate_rules(rules_data)
    print(f"\nSummary: {report.summary}")
    print(f"Violations: {len(report.violations)}")

    if report.violations:
        print("\nViolations found:")
        for v in report.violations:
            print(f"  - [{v['type']}] {v['severity']}: {v['message']}")

    # Should detect tautology
    has_tautology = any(
        v["type"] == "SYNTAX_ERROR" and "tautolog" in v["message"].lower()
        for v in report.violations
    )
    print(f"\n[{'OK' if has_tautology else 'FAIL'}] Tautology detection")
    return has_tautology


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("POLICY LINTER TEST SUITE")
    print("=" * 80)

    results = []

    try:
        results.append(("Valid Rules", test_valid_rules()))
        results.append(("NULL Bug Detection", test_null_bug()))
        results.append(("Invalid Vocab Detection", test_invalid_vocab()))
        results.append(("Valid Attributes Pattern", test_valid_attributes()))
        results.append(("Syntax Error Detection", test_syntax_errors()))
        results.append(("Tautology Detection", test_tautology()))

    except Exception as e:
        print(f"\n[FAIL] Test suite crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print summary
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n[OK] All tests passed!")
        sys.exit(0)
    else:
        print(f"\n[FAIL] {total - passed} test(s) failed")
        sys.exit(1)
