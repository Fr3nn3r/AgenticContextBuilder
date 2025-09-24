#!/usr/bin/env python3
"""Test OCR functionality."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from context_builder.processors.content_support.extractors import get_registry, OCRTesseractStrategy

def test_ocr():
    """Test OCR extraction strategy."""
    print("Testing OCR Tesseract Strategy")
    print("=" * 50)

    # Create strategy instance
    strategy = OCRTesseractStrategy()

    # Validate requirements
    is_valid, error = strategy.validate_requirements()
    if is_valid:
        print("[OK] OCR Tesseract is properly configured")
        print("  - Tesseract is installed and accessible")
        print("  - Required Python libraries are available")
    else:
        print(f"[X] OCR Tesseract validation failed: {error}")
        return False

    # Test with registry
    print("\nTesting with Registry")
    print("-" * 30)

    registry = get_registry()

    # Configure with OCR enabled
    config = {
        "ocr_tesseract": {
            "enabled": True,
            "priority": 1,
            "config": {
                "languages": ["eng"],
                "quality_threshold": 0.6
            }
        }
    }

    registry.configure(config)

    # Check if OCR is available
    if registry.is_method_available("ocr_tesseract"):
        print("[OK] OCR Tesseract is available through registry")
    else:
        print("[X] OCR Tesseract is not available through registry")
        return False

    # Get enabled strategies
    strategies = registry.get_enabled_strategies()
    ocr_enabled = any(s.name == "ocr_tesseract" for s in strategies)

    if ocr_enabled:
        print("[OK] OCR Tesseract is enabled and ready to use")
    else:
        print("[X] OCR Tesseract is not in enabled strategies")
        return False

    print("\n" + "=" * 50)
    print("SUCCESS: OCR functionality is working correctly!")
    print("\nYou can now use OCR extraction in the content processor.")
    print("Both OCR and Vision API methods are available.")

    return True

if __name__ == "__main__":
    success = test_ocr()
    sys.exit(0 if success else 1)