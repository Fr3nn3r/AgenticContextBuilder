#!/usr/bin/env python3
"""Manual test for Ctrl-C interruption - creates a long-running task that can be interrupted."""

import time
import sys
from pathlib import Path

# Add parent directory to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder.cli import signal_handler, setup_signal_handlers

def simulate_long_running_task():
    """Simulate a long-running task that can be interrupted."""

    print("Starting long-running task simulation...")
    print("Press Ctrl-C to interrupt at any time")
    print("-" * 60)

    # Set up signal handlers
    setup_signal_handlers()

    try:
        for i in range(20):
            print(f"Processing item {i+1}/20...")
            time.sleep(1)  # Simulate processing time

        print("\n[OK] Task completed successfully!")

    except KeyboardInterrupt:
        print("\n[!] Caught KeyboardInterrupt - exiting gracefully")
        sys.exit(0)

if __name__ == "__main__":
    print("Manual Interrupt Test")
    print("=" * 60)
    print("This script simulates a long-running process.")
    print("Try pressing Ctrl-C during execution to test graceful exit.")
    print("=" * 60)
    print()

    simulate_long_running_task()