"""Generate claim input form schemas from compiled policy logic.

This script performs static analysis on policy logic JSON files and generates
dynamic input schemas optimized for claims adjusters.

Outputs:
- Custom JSON format (UI-optimized)
- JSON Schema draft-07 (standards-compliant)

Usage:
    python scripts/generate_form_schema.py [input_path] [output_dir]

    input_path: File or directory containing logic JSON files (default: output/processing)
    output_dir: Directory to save schemas (default: output/output_schemas)
"""

import sys
from pathlib import Path
from typing import List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.execution.form_generator import FormGenerator


def find_logic_files(input_path: Path) -> List[Path]:
    """Find all policy logic JSON files.

    Args:
        input_path: File or directory path

    Returns:
        List of logic file paths
    """
    if input_path.is_file():
        return [input_path]

    # Search for logic files
    logic_files = []

    # Pattern: *_logic.json (but not *_normalized_logic.json)
    for f in input_path.glob("**/*_logic.json"):
        if "normalized" not in f.stem:
            logic_files.append(f)

    return sorted(logic_files)


def main():
    """Main script entry point."""
    print("=" * 80)
    print("FORM SCHEMA GENERATOR")
    print("=" * 80)
    print()

    # Parse arguments
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_path = Path(__file__).parent.parent / "output" / "processing"

    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])
    else:
        output_dir = Path(__file__).parent.parent / "output" / "output_schemas"

    # Validate input
    if not input_path.exists():
        print(f"[ERROR] Input path not found: {input_path}")
        return 1

    print(f"Input: {input_path}")
    print(f"Output: {output_dir}")
    print()

    # Find logic files
    logic_files = find_logic_files(input_path)

    if not logic_files:
        print("[ERROR] No logic files found.")
        print("Looking for: *_logic.json (excluding *_normalized_logic.json)")
        return 1

    print(f"Found {len(logic_files)} logic files")
    print()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate schemas
    success_count = 0
    error_count = 0
    total_fields = 0

    print("Generating schemas...")
    print("-" * 80)

    for logic_file in logic_files:
        try:
            # Create fresh FormGenerator instance per file to avoid state accumulation
            generator = FormGenerator()
            print(f"\nProcessing: {logic_file.name}")

            # Generate schemas
            output_files = generator.generate_from_file(
                logic_file=logic_file,
                output_dir=output_dir,
                generate_json_schema=True,
                generate_custom=True,
            )

            # Count fields
            custom_file = output_files.get("custom")
            if custom_file and custom_file.exists():
                import json
                with open(custom_file, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                    field_count = schema.get("statistics", {}).get("total_fields", 0)
                    total_fields += field_count
                    print(f"  Fields: {field_count}")

            success_count += 1

        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to process {logic_file.name}: {e}")
            print(f"[DEBUG] Traceback:")
            traceback.print_exc()
            error_count += 1

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Total files processed: {len(logic_files)}")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"Total fields extracted: {total_fields:,}")
    print()
    print(f"Output directory: {output_dir}")
    print()

    if success_count > 0:
        print("[OK] Schema generation complete!")
        return 0
    else:
        print("[ERROR] No schemas generated")
        return 1


if __name__ == "__main__":
    sys.exit(main())
