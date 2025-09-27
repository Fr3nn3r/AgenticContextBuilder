"""Test script for Tesseract acquisition module."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder.acquisition import AcquisitionFactory
from context_builder.impl.tesseract_acquisition import TesseractAcquisition


def test_tesseract_acquisition():
    """Test Tesseract acquisition functionality."""
    print("[Testing Tesseract Acquisition Module]")
    print("-" * 40)

    # Create Tesseract acquisition instance
    try:
        tesseract = AcquisitionFactory.create("tesseract")
        print("[OK] Tesseract acquisition created successfully")
    except Exception as e:
        print(f"[X] Failed to create Tesseract acquisition: {e}")
        return

    # Configure languages (optional)
    tesseract.languages = ['eng']  # You can add more: ['eng', 'fra', 'deu']
    print(f"[OK] Languages configured: {tesseract.languages}")

    # Test with a sample file (you'll need to provide a test image/PDF)
    test_files = [
        Path("test_image.png"),
        Path("test_document.pdf"),
        Path("screenshot.jpg"),
    ]

    for test_file in test_files:
        if test_file.exists():
            print(f"\n[Testing {test_file}]")
            try:
                result = tesseract.process(test_file)

                print(f"  File: {result['file_name']}")
                print(f"  Total pages: {result['total_pages']}")
                print(f"  Average confidence: {result.get('average_confidence', 0):.2%}")

                # Show first page text (truncated)
                if result.get('pages'):
                    first_page = result['pages'][0]
                    text = first_page.get('text', '')
                    if text:
                        preview = text[:200] + "..." if len(text) > 200 else text
                        print(f"  Text preview: {preview}")
                        print(f"  Word count: {first_page.get('word_count', 0)}")
                    else:
                        print("  No text extracted")

                print(f"[OK] Successfully processed {test_file}")

            except Exception as e:
                print(f"[X] Error processing {test_file}: {e}")

    # Show available providers
    print(f"\n[Available providers: {AcquisitionFactory.list_providers()}]")


def test_configuration():
    """Test different configuration options."""
    print("\n[Testing Configuration Options]")
    print("-" * 40)

    tesseract = TesseractAcquisition()

    # Test preprocessing options
    tesseract.enable_preprocessing = True
    tesseract.deskew = True
    tesseract.enhance_contrast = True
    print(f"[OK] Preprocessing enabled: deskew={tesseract.deskew}, contrast={tesseract.enhance_contrast}")

    # Test language configuration
    tesseract.languages = ['eng', 'fra']  # English and French
    print(f"[OK] Multi-language support: {tesseract.languages}")

    # Test page limits
    tesseract.max_pages = 10
    print(f"[OK] Max pages set to: {tesseract.max_pages}")


if __name__ == "__main__":
    test_tesseract_acquisition()
    test_configuration()
    print("\n[Test complete]")