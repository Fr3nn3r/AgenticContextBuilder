"""Test PolicyLinter on real extracted logic files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.extraction.policy_logic_linter import validate_rules
import json


def test_real_file(file_path: str):
    """Test PolicyLinter on a real extraction file."""
    print("=" * 80)
    print(f"Testing: {Path(file_path).name}")
    print("=" * 80)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validate rules
        report = validate_rules(data)

        # Print summary
        print(f"\nValidation Summary:")
        print(f"  Total Rules: {report.summary['total_rules']}")
        print(f"  Clean Rules: {report.summary['clean_rules']}")
        print(f"  Total Violations: {report.summary['violations']}")
        print(f"  Critical Violations: {report.summary['critical_violations']}")
        print(f"  Warnings: {report.summary['warnings']}")

        # Print violations (first 10 only)
        if report.violations:
            print(f"\nViolations (showing first 10):")
            for i, v in enumerate(report.violations[:10], 1):
                print(f"\n  {i}. [{v['type']}] {v['severity']}")
                print(f"     Rule: {v['rule_id']} - {v['rule_name']}")
                print(f"     Message: {v['message']}")
                if v.get('variable'):
                    print(f"     Variable: {v['variable']}")
                if v.get('invalid_value') is not None:
                    print(f"     Invalid Value: {v['invalid_value']}")

            if len(report.violations) > 10:
                print(f"\n  ... and {len(report.violations) - 10} more violations")
        else:
            print("\n[OK] No violations found!")

        return report

    except Exception as e:
        print(f"\n[FAIL] Error testing file: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test most recent extraction
    test_file = r"C:\Users\fbrun\Documents\GitHub\AgenticContextBuilder\output\ACB-20251128-102130\GoReady Choice Plan MN 4_extracted_normalized_logic.json"

    if not Path(test_file).exists():
        print(f"[FAIL] Test file not found: {test_file}")
        sys.exit(1)

    report = test_real_file(test_file)

    if report:
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        sys.exit(0)
    else:
        sys.exit(1)
