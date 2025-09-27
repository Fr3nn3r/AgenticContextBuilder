#!/usr/bin/env python3
"""Test script for the vision CLI."""

import json
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def create_test_image():
    """Create a simple test image with text."""
    # Create a white image
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)

    # Add some text
    text = """TEST DOCUMENT

    Document Type: Test Invoice
    Invoice Number: INV-2024-001
    Date: 2024-01-15

    Customer: Test Company
    Amount: $1,234.56

    This is a test document for vision API testing."""

    # Use default font
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    # Draw text
    draw.text((50, 50), text, fill='black', font=font)

    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(temp_file.name)
    return temp_file.name


def main():
    """Main test function."""
    print("[OK] Creating test image...")
    test_image_path = create_test_image()
    print(f"[OK] Test image created: {test_image_path}")

    # Test the CLI
    import subprocess
    import sys

    cmd = [sys.executable, "-m", "context_builder.cli", test_image_path]

    print(f"[OK] Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("[OK] CLI executed successfully")
            print("Output:", result.stdout)

            # Check if output file was created
            output_file = Path(f"{Path(test_image_path).stem}-context.json")
            if output_file.exists():
                print(f"[OK] Output file created: {output_file}")

                # Read and display the content
                with open(output_file, 'r') as f:
                    content = json.load(f)
                print("[OK] JSON content:")
                print(json.dumps(content, indent=2))

                # Clean up
                output_file.unlink()
            else:
                print("[X] Output file not found")
        else:
            print(f"[X] CLI failed with return code: {result.returncode}")
            print("Error:", result.stderr)

    except subprocess.TimeoutExpired:
        print("[X] Command timed out")
    except Exception as e:
        print(f"[X] Error: {e}")

    finally:
        # Clean up test image
        Path(test_image_path).unlink(missing_ok=True)
        print("[OK] Test completed")


if __name__ == "__main__":
    main()