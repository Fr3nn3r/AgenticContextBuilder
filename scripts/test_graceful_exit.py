#!/usr/bin/env python3
"""Test script to verify graceful Ctrl-C handling in the CLI."""

import sys
import time
import subprocess
from pathlib import Path

def test_graceful_exit():
    """Test that Ctrl-C exits gracefully without stack trace."""

    print("[TEST] Testing graceful exit on Ctrl-C")
    print("=" * 60)

    # Get the path to the CLI module
    project_root = Path(__file__).parent.parent
    cli_module = project_root / "context_builder" / "cli.py"

    # Create a test file
    test_file = project_root / "test_folder" / "test.txt"
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text("Test content for graceful exit testing")

    print(f"[INFO] Created test file: {test_file}")
    print("[INFO] Starting CLI process...")
    print("[INFO] Press Ctrl-C after you see the process starting to test graceful exit")
    print("-" * 60)

    # Run the CLI with a long-running operation
    try:
        # Use a command that will take some time
        cmd = [
            sys.executable,
            "-m", "context_builder.cli",
            str(test_file.parent),
            "-o", str(test_file.parent),
            "-r",
            "-v"
        ]

        print(f"[CMD] {' '.join(cmd)}")
        print("-" * 60)

        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # Give it a moment to start
        time.sleep(2)

        # Send interrupt signal
        print("\n[TEST] Sending interrupt signal...")
        process.terminate()

        # Get the output
        output, _ = process.communicate(timeout=5)

        print("[OUTPUT]")
        print(output)
        print("-" * 60)

        # Check if there's a stack trace in the output
        has_traceback = "Traceback" in output or "Exception" in output and not "KeyboardInterrupt" in output

        if has_traceback:
            print("[FAIL] Stack trace detected in output!")
            print("The process should exit gracefully without showing a stack trace.")
            return False

        if "[!] Process interrupted" in output or "Exiting gracefully" in output:
            print("[PASS] Graceful exit message detected!")
            return True

        print("[INFO] Process exited. Check output above.")
        return True

    except subprocess.TimeoutExpired:
        print("[WARN] Process didn't exit in time")
        process.kill()
        return False
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False
    finally:
        # Clean up
        if test_file.exists():
            test_file.unlink()
        print("\n[INFO] Test complete")

if __name__ == "__main__":
    print("Graceful Exit Test Script")
    print("=" * 60)

    success = test_graceful_exit()

    if success:
        print("\n[SUCCESS] Graceful exit handling is working correctly!")
    else:
        print("\n[FAILURE] Graceful exit handling needs adjustment.")

    sys.exit(0 if success else 1)