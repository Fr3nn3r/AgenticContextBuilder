#!/usr/bin/env python3
"""
Test script to demonstrate the new extraction methods architecture.
Shows how different extraction methods can be enabled/disabled and configured.
"""

import json
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from context_builder.processors.content_support.extractors import get_registry


def test_registry():
    """Test the extraction registry functionality."""
    print("Testing Extraction Registry")
    print("=" * 50)

    registry = get_registry()

    # List registered methods
    methods = registry.get_registered_methods()
    print(f"\nRegistered extraction methods: {methods}")

    # Test different configurations
    configs = [
        {
            "name": "OCR Only",
            "config": {
                "ocr_tesseract": {
                    "enabled": True,
                    "priority": 1,
                    "config": {"languages": ["eng"], "quality_threshold": 0.6}
                },
                "vision_openai": {
                    "enabled": False,
                    "priority": 2,
                    "config": {}
                }
            }
        },
        {
            "name": "Vision Only",
            "config": {
                "ocr_tesseract": {
                    "enabled": False,
                    "priority": 1,
                    "config": {}
                },
                "vision_openai": {
                    "enabled": True,
                    "priority": 2,
                    "config": {"model": "gpt-4o", "max_pages": 20}
                }
            }
        },
        {
            "name": "Both Methods",
            "config": {
                "ocr_tesseract": {
                    "enabled": True,
                    "priority": 1,
                    "config": {"languages": ["eng"], "quality_threshold": 0.6}
                },
                "vision_openai": {
                    "enabled": True,
                    "priority": 2,
                    "config": {"model": "gpt-4o", "max_pages": 20}
                }
            }
        }
    ]

    for test_config in configs:
        print(f"\n\nTesting: {test_config['name']}")
        print("-" * 30)

        # Configure registry
        registry.configure(test_config['config'])

        # Validate configuration
        errors = registry.validate_configuration(test_config['config'])
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("Configuration is valid")

        # Get enabled strategies
        enabled = registry.get_enabled_strategies()
        print(f"Enabled strategies: {[s.name for s in enabled]}")

        # Check availability of each method
        for method_name in registry.get_registered_methods():
            if registry.is_method_available(method_name):
                print(f"  {method_name}: Available")
            else:
                print(f"  {method_name}: Not available (missing requirements)")


def demonstrate_output_structure():
    """Show the new output structure with extraction_results."""
    print("\n\nNew Output Structure Example")
    print("=" * 50)

    example_output = {
        "file_path": "document.pdf",
        "processing_info": {
            "status": "partial_success",
            "processing_time": 5.2,
            "extracted_by": ["ocr_tesseract", "vision_openai"],
            "skipped_methods": [],
            "failed_methods": []
        },
        "content_metadata": {
            "content_type": "document",
            "file_category": "pdf",
            "total_pages": 2
        },
        "extraction_results": [
            {
                "method": "ocr_tesseract",
                "status": "success",
                "pages": [
                    {
                        "page_number": 1,
                        "status": "success",
                        "content": {
                            "text": "Extracted text from page 1...",
                            "confidence": 0.95,
                            "languages": ["eng"]
                        },
                        "quality_score": 0.95,
                        "processing_time": 1.2
                    },
                    {
                        "page_number": 2,
                        "status": "unreadable_content",
                        "content": None,
                        "quality_score": 0,
                        "error": "No readable text found"
                    }
                ]
            },
            {
                "method": "vision_openai",
                "status": "success",
                "pages": [
                    {
                        "page_number": 1,
                        "status": "success",
                        "content": {
                            "document_type": "invoice",
                            "text_content": "Invoice #12345...",
                            "key_information": {
                                "invoice_number": "12345",
                                "date": "2024-01-01",
                                "total": "$1,234.56"
                            }
                        },
                        "quality_score": None,
                        "processing_time": 2.5
                    },
                    {
                        "page_number": 2,
                        "status": "success",
                        "content": {
                            "document_type": "invoice",
                            "text_content": "Page 2 content...",
                            "summary": "Second page of invoice with line items"
                        },
                        "quality_score": None,
                        "processing_time": 2.3
                    }
                ]
            }
        ]
    }

    print("\nExample output with multiple extraction methods:")
    print(json.dumps(example_output, indent=2))

    print("\n\nKey Changes:")
    print("-" * 30)
    print("1. Removed 'content_data' field")
    print("2. Added 'extraction_results' array with results from each method")
    print("3. Each method has its own pages array with page-by-page results")
    print("4. Status can be 'success', 'partial_success', 'error', or 'skipped'")
    print("5. Page status can be 'success', 'unreadable_content', or 'error'")
    print("6. Quality scores included where available (OCR)")


if __name__ == "__main__":
    test_registry()
    demonstrate_output_structure()

    print("\n\nCLI Usage Examples:")
    print("=" * 50)
    print("\n# Use all enabled methods from config:")
    print("python -m intake /path/to/files output/ -c config/default_config.json")
    print("\n# Override to use only OCR:")
    print("python -m intake /path/to/files output/ -c config/default_config.json --extraction-methods ocr_tesseract")
    print("\n# Use both OCR and Vision:")
    print("python -m intake /path/to/files output/ -c config/default_config.json --extraction-methods ocr_tesseract,vision_openai")
    print("\n# Enable all available methods:")
    print("python -m intake /path/to/files output/ -c config/default_config.json --extraction-methods all")
    print("\n# Validate configuration:")
    print("python -m intake --validate-config -c config/default_config.json")