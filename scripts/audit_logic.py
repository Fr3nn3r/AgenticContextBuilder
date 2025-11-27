"""
Value Profiling Audit Script for Logic Extraction.

Standalone CLI wrapper for LogicAuditor to audit extracted logic files
for semantic hallucinations where the LLM forces incompatible business
concepts into existing UDM fields.

Usage:
    python scripts/audit_logic.py [--dir OUTPUT_DIR]
    python scripts/audit_logic.py --files FILE1 FILE2 ...
"""

import argparse
import glob
import os
import sys
from pathlib import Path
from typing import List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.extraction.logic_auditor import LogicAuditor

# Configuration
DEFAULT_LOGIC_DIR = "./output"
OUTPUT_FILE = "semantic_audit_report.txt"
SCHEMA_FILE = "src/context_builder/schemas/standard_claim_schema.json"


def scan_logic_files(directory: str = None, file_list: List[str] = None) -> List[str]:
    """Scan directory for logic JSON files or process specific files."""

    if file_list:
        # Process specific files provided by user
        print(f"[*] Processing {len(file_list)} specified files...")
        files = []
        for filepath in file_list:
            if os.path.exists(filepath):
                files.append(filepath)
            else:
                print(f"[!] File not found: {filepath}")

        if not files:
            print("[X] None of the specified files were found")
            return []

        print(f"[OK] Found {len(files)} valid files")
    else:
        # Original directory scanning logic
        print(f"[*] Scanning for logic files in {directory}...")

        # Find both transpiled and normalized logic files
        patterns = [
            "*_logic.json",
            "*_normalized_logic.json",
            "*/output_chunks/*_normalized_logic.json"
        ]

        files = []
        for pattern in patterns:
            files.extend(glob.glob(os.path.join(directory, "**", pattern), recursive=True))

        # Remove duplicates
        files = list(set(files))

        if not files:
            print(f"[X] No logic files found in {directory}")
            return []

        print(f"[OK] Found {len(files)} logic files")

    return files


def main():
    parser = argparse.ArgumentParser(description="Audit logic files for semantic hallucinations")
    parser.add_argument(
        "--dir",
        default=DEFAULT_LOGIC_DIR,
        help=f"Directory containing logic files (default: {DEFAULT_LOGIC_DIR})"
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Specific logic files to audit (space-separated paths)"
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_FILE,
        help=f"Output report file (default: {OUTPUT_FILE})"
    )
    parser.add_argument(
        "--schema",
        default=SCHEMA_FILE,
        help=f"Path to standard claim schema (default: {SCHEMA_FILE})"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("LOGIC HALLUCINATION AUDIT")
    print("=" * 60)
    print()

    # Scan files
    if args.files:
        files = scan_logic_files(file_list=args.files)
    else:
        files = scan_logic_files(directory=args.dir)

    if not files:
        print("\n[X] No logic files found. Nothing to audit.")
        return 1

    print()

    # Create auditor and run audit
    try:
        auditor = LogicAuditor(schema_path=args.schema)
        auditor.audit_files(files)
        auditor.generate_report(args.output)
    except Exception as e:
        print(f"\n[X] Audit failed: {e}")
        return 1

    # Summary
    summary = auditor.get_summary()
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files scanned: {len(files)}")
    print(f"Variables analyzed: {summary['variables_analyzed']}")
    print(f"Files with NULL bug: {summary['null_bugs']}")
    print(f"Orphan concepts found: {summary['orphan_concepts']}")

    if summary["has_issues"]:
        print(f"\n[!] Review {args.output} for details")
        return 1
    else:
        print(f"\n[OK] No semantic hallucinations detected!")
        return 0


if __name__ == "__main__":
    exit(main())
