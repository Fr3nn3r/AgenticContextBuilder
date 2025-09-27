#!/usr/bin/env python
"""Test script for the new context-processor CLI (cli2.py)"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder.cli2 import main

if __name__ == "__main__":
    # Test with command line arguments
    print("Testing context-processor CLI...")
    print("=" * 50)

    # You can modify sys.argv to test different scenarios
    # Example: process a single file
    # sys.argv = ['test_cli2.py', 'input.pdf', 'output/', '-c', 'config/metadata_only_config.json']

    # Example: process a folder
    # sys.argv = ['test_cli2.py', 'datasets/sample/', 'output/', '-c', 'config/metadata_only_config.json', '-v']

    exit_code = main()
    print(f"\nExit code: {exit_code}")
    sys.exit(exit_code)