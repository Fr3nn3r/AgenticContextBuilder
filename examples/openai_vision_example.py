"""
Example usage of OpenAI Vision API acquisition module.

This example demonstrates:
- Basic document analysis with structured output
- PDF processing with intelligent content extraction
- Invoice/form data extraction
- Multi-page document processing
- API configuration and error handling
- Cost estimation and token usage tracking
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder.acquisition import AcquisitionFactory


def example_basic_usage():
    """Basic usage example with a single image."""
    print("[Example 1: Basic Document Analysis]")
    print("=" * 50)

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set in environment")
        print("Please set: export OPENAI_API_KEY='your-key-here'")
        return

    try:
        # Create OpenAI Vision acquisition instance
        openai_vision = AcquisitionFactory.create("openai")

        # Example with an image file
        image_path = Path("sample_document.png")  # Replace with your image

        if image_path.exists():
            # Process the image
            result = openai_vision.process(image_path)

            # Display results
            print(f"File: {result['file_name']}")
            print(f"Size: {result['file_size_bytes']} bytes")

            # Extract structured content from first page
            if result['pages']:
                page = result['pages'][0]
                print(f"\nDocument Type: {page.get('document_type', 'Unknown')}")
                print(f"Language: {page.get('language', 'Unknown')}")
                print(f"\nSummary:")
                print("-" * 40)
                print(page.get('summary', 'No summary available'))

                # Show key information
                key_info = page.get('key_information', {})
                if key_info:
                    print("\nKey Information:")
                    print("-" * 40)
                    for key, value in key_info.items():
                        print(f"  {key}: {value}")

                # Show visual elements
                visual_elements = page.get('visual_elements', [])
                if visual_elements:
                    print("\nVisual Elements Detected:")
                    print("-" * 40)
                    for element in visual_elements:
                        print(f"  - {element}")

            # Show token usage
            if '_usage' in result:
                usage = result['_usage']
                print(f"\nAPI Usage:")
                print(f"  Prompt tokens: {usage['prompt_tokens']}")
                print(f"  Completion tokens: {usage['completion_tokens']}")
                print(f"  Total tokens: {usage['total_tokens']}")
                estimate_cost(usage)

        else:
            print(f"Sample file not found: {image_path}")
            print("Please provide an image file to test")

    except Exception as e:
        print(f"Error: {e}")

    print("\n")


def example_invoice_processing():
    """Example of processing invoices or forms."""
    print("[Example 2: Invoice/Form Processing]")
    print("=" * 50)

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    try:
        openai_vision = AcquisitionFactory.create("openai")

        # Process invoice image
        invoice_path = Path("invoice.png")  # Replace with your invoice

        if invoice_path.exists():
            result = openai_vision.process(invoice_path)

            if result['pages']:
                page = result['pages'][0]

                print(f"Document Type: {page.get('document_type', 'Unknown')}")

                # Extract structured invoice data
                key_info = page.get('key_information', {})

                print("\nExtracted Invoice Data:")
                print("-" * 40)

                # Common invoice fields to look for
                invoice_fields = [
                    'invoice_number', 'invoice_date', 'due_date',
                    'vendor_name', 'vendor_address', 'customer_name',
                    'customer_address', 'subtotal', 'tax', 'total',
                    'payment_terms', 'po_number'
                ]

                for field in invoice_fields:
                    if field in key_info:
                        field_name = field.replace('_', ' ').title()
                        print(f"  {field_name}: {key_info[field]}")

                # Show all extracted text
                if page.get('text_content'):
                    print("\nFull Text Content:")
                    print("-" * 40)
                    text = page['text_content']
                    preview = text[:500] + "..." if len(text) > 500 else text
                    print(preview)

        else:
            print(f"Invoice file not found: {invoice_path}")
            print("Tip: This works best with invoice/receipt images")

    except Exception as e:
        print(f"Error: {e}")

    print("\n")


def example_pdf_processing():
    """Example of processing multi-page PDFs."""
    print("[Example 3: Multi-Page PDF Processing]")
    print("=" * 50)

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    try:
        openai_vision = AcquisitionFactory.create("openai")

        # Configure for PDF processing
        openai_vision.max_pages = 5  # Limit pages to control costs
        openai_vision.render_scale = 2.0  # Higher quality rendering

        pdf_path = Path("report.pdf")  # Replace with your PDF

        if pdf_path.exists():
            print(f"Processing PDF: {pdf_path.name}")
            print(f"Max pages: {openai_vision.max_pages}")
            print("Note: Each page requires a separate API call")
            print()

            result = openai_vision.process(pdf_path)

            print(f"Total pages processed: {result['total_pages']}")

            # Analyze each page
            for page_data in result['pages']:
                page_num = page_data.get('page_number', 'Unknown')
                print(f"\n--- Page {page_num} ---")
                print(f"Type: {page_data.get('document_type', 'Unknown')}")
                print(f"Summary: {page_data.get('summary', 'No summary')[:200]}")

                # Show key information if available
                key_info = page_data.get('key_information', {})
                if key_info:
                    print("Key Points:")
                    for key, value in list(key_info.items())[:3]:  # Show first 3
                        print(f"  - {key}: {value}")

            # Show total API usage for all pages
            if '_usage' in result:
                usage = result['_usage']
                print(f"\nTotal API Usage for {result['total_pages']} pages:")
                print(f"  Total tokens: {usage['total_tokens']}")
                estimate_cost(usage)

        else:
            print(f"PDF file not found: {pdf_path}")
            print("Note: PDF processing requires pypdfium2 package")

    except Exception as e:
        print(f"Error: {e}")

    print("\n")


def example_model_configuration():
    """Example of different model configurations."""
    print("[Example 4: Model Configuration]")
    print("=" * 50)

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    try:
        # Create with default settings
        openai_default = AcquisitionFactory.create("openai")
        print("Default Configuration:")
        print(f"  Model: {openai_default.model}")
        print(f"  Max tokens: {openai_default.max_tokens}")
        print(f"  Temperature: {openai_default.temperature}")
        print(f"  Max pages: {openai_default.max_pages}")

        # Create with custom settings
        openai_custom = AcquisitionFactory.create("openai")

        # Customize settings for different use cases
        print("\nCustom Configuration (for detailed analysis):")

        # For detailed analysis
        openai_custom.model = "gpt-4o"  # Latest vision model
        openai_custom.max_tokens = 4096  # More detailed responses
        openai_custom.temperature = 0.2  # More consistent output
        openai_custom.max_pages = 10  # Process more pages

        print(f"  Model: {openai_custom.model}")
        print(f"  Max tokens: {openai_custom.max_tokens}")
        print(f"  Temperature: {openai_custom.temperature}")
        print(f"  Max pages: {openai_custom.max_pages}")

        # Test with a sample file if available
        test_file = Path("test.png")
        if test_file.exists():
            print(f"\nTesting with {test_file.name}...")

            result = openai_custom.process(test_file)
            if '_usage' in result:
                print(f"Tokens used: {result['_usage']['total_tokens']}")

    except Exception as e:
        print(f"Error: {e}")

    print("\n")


def example_error_handling():
    """Example of handling various error scenarios."""
    print("[Example 5: Error Handling]")
    print("=" * 50)

    # Test various error scenarios
    scenarios = [
        ("No API key", None),
        ("Invalid file", Path("nonexistent.png")),
        ("Unsupported format", Path("test.txt")),
    ]

    for scenario_name, test_path in scenarios:
        print(f"\nTesting: {scenario_name}")
        print("-" * 30)

        try:
            if scenario_name == "No API key":
                # Temporarily clear API key
                original_key = os.environ.get("OPENAI_API_KEY", "")
                if original_key:
                    del os.environ["OPENAI_API_KEY"]

                try:
                    openai_vision = AcquisitionFactory.create("openai")
                except Exception as e:
                    print(f"  Expected error caught: {type(e).__name__}")
                    print(f"  Message: {str(e)[:100]}")
                finally:
                    # Restore API key
                    if original_key:
                        os.environ["OPENAI_API_KEY"] = original_key

            elif test_path:
                openai_vision = AcquisitionFactory.create("openai")
                result = openai_vision.process(test_path)

        except Exception as e:
            print(f"  Error type: {type(e).__name__}")
            print(f"  Message: {str(e)[:100]}")

    print("\n")


def example_batch_processing():
    """Example of processing multiple files with progress tracking."""
    print("[Example 6: Batch Processing with Cost Tracking]")
    print("=" * 50)

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    try:
        openai_vision = AcquisitionFactory.create("openai")

        # Find test files
        test_files = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.pdf']:
            test_files.extend(Path(".").glob(ext))

        if test_files:
            print(f"Found {len(test_files)} files to process")
            print("Processing first 3 files to control costs...\n")

            total_tokens = 0
            results_summary = []

            for file_path in test_files[:3]:  # Limit to 3 files
                print(f"Processing: {file_path.name}")

                try:
                    result = openai_vision.process(file_path)

                    # Collect summary
                    doc_types = []
                    for page in result['pages']:
                        doc_type = page.get('document_type', 'unknown')
                        if doc_type not in doc_types:
                            doc_types.append(doc_type)

                    summary = {
                        'file': file_path.name,
                        'pages': result['total_pages'],
                        'types': ', '.join(doc_types),
                        'tokens': result.get('_usage', {}).get('total_tokens', 0)
                    }
                    results_summary.append(summary)
                    total_tokens += summary['tokens']

                    print(f"  Document types: {summary['types']}")
                    print(f"  Pages: {summary['pages']}")
                    print(f"  Tokens: {summary['tokens']}")

                except Exception as e:
                    print(f"  Error: {e}")

                print()

            # Show batch summary
            if results_summary:
                print("=" * 50)
                print("Batch Processing Summary:")
                print("-" * 50)
                print(f"Files processed: {len(results_summary)}")
                print(f"Total tokens used: {total_tokens}")

                # Estimate total cost
                estimate_cost({'total_tokens': total_tokens})

        else:
            print("No image or PDF files found in current directory")

    except Exception as e:
        print(f"Error: {e}")

    print("\n")


def estimate_cost(usage: Dict[str, int]):
    """Estimate API costs based on token usage."""
    # Approximate costs (check OpenAI pricing for current rates)
    # GPT-4 Vision pricing as of 2024
    input_cost_per_1k = 0.01  # $0.01 per 1K input tokens
    output_cost_per_1k = 0.03  # $0.03 per 1K output tokens

    input_cost = (usage.get('prompt_tokens', 0) / 1000) * input_cost_per_1k
    output_cost = (usage.get('completion_tokens', 0) / 1000) * output_cost_per_1k
    total_cost = input_cost + output_cost

    print(f"\nEstimated Cost:")
    print(f"  Input: ${input_cost:.4f}")
    print(f"  Output: ${output_cost:.4f}")
    print(f"  Total: ${total_cost:.4f}")
    print("  (Note: Actual pricing may vary)")


def save_structured_output(result: Dict[str, Any], output_file: str = "vision_output.json"):
    """Save structured extraction results to JSON."""
    print(f"\nSaving results to {output_file}...")

    # Make Path objects JSON serializable
    def make_serializable(obj):
        if isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(item) for item in obj]
        return obj

    serializable_result = make_serializable(result)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_result, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {output_file}")


def compare_with_tesseract():
    """Compare OpenAI Vision with Tesseract OCR."""
    print("[Example 7: OpenAI Vision vs Tesseract Comparison]")
    print("=" * 50)

    test_file = Path("comparison_test.png")  # Replace with your file

    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        print("Create a test image to compare both methods")
        return

    print(f"Comparing extraction methods for: {test_file.name}\n")

    # Test with Tesseract
    print("1. Tesseract OCR:")
    print("-" * 30)
    try:
        tesseract = AcquisitionFactory.create("tesseract")
        tesseract_result = tesseract.process(test_file)

        if tesseract_result['pages']:
            page = tesseract_result['pages'][0]
            print(f"  Confidence: {page.get('confidence', 0):.2%}")
            print(f"  Word count: {page.get('word_count', 0)}")
            print(f"  Text preview: {page.get('text', '')[:100]}...")

    except Exception as e:
        print(f"  Tesseract not available: {e}")

    # Test with OpenAI Vision
    print("\n2. OpenAI Vision:")
    print("-" * 30)
    if not os.getenv("OPENAI_API_KEY"):
        print("  OpenAI API key not set")
        return

    try:
        openai_vision = AcquisitionFactory.create("openai")
        openai_result = openai_vision.process(test_file)

        if openai_result['pages']:
            page = openai_result['pages'][0]
            print(f"  Document type: {page.get('document_type', 'Unknown')}")
            print(f"  Summary: {page.get('summary', 'No summary')[:100]}...")

            # Show token usage
            if '_usage' in openai_result:
                print(f"  Tokens used: {openai_result['_usage']['total_tokens']}")
                estimate_cost(openai_result['_usage'])

    except Exception as e:
        print(f"  Error: {e}")

    print("\n" + "=" * 50)
    print("Comparison Summary:")
    print("  Tesseract: Fast, free, good for simple text extraction")
    print("  OpenAI Vision: Intelligent analysis, structured data, costs per use")
    print("=" * 50)


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print(" OPENAI VISION ACQUISITION MODULE EXAMPLES")
    print("=" * 60 + "\n")

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("[WARNING] OPENAI_API_KEY not set in environment")
        print("\nTo use OpenAI Vision, set your API key:")
        print("  Windows: set OPENAI_API_KEY=your-key-here")
        print("  Linux/Mac: export OPENAI_API_KEY='your-key-here'")
        print("\nOr add to .env file:")
        print("  OPENAI_API_KEY=your-key-here")
        print("\n" + "=" * 60 + "\n")
    else:
        print("[OK] OpenAI API key found")

    print("\nNote: OpenAI Vision API charges per token used")
    print("Monitor usage to control costs\n")

    # Run examples
    example_basic_usage()
    example_invoice_processing()
    example_pdf_processing()
    example_model_configuration()
    example_error_handling()
    example_batch_processing()
    compare_with_tesseract()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("\nKey Differences from Tesseract:")
    print("  1. Returns structured JSON with semantic understanding")
    print("  2. Identifies document types and key information")
    print("  3. Provides summaries and visual element detection")
    print("  4. Costs money per API call (monitor usage!)")
    print("  5. Requires internet connection and API key")
    print("\nBest Practices:")
    print("  - Use Tesseract for high-volume simple text extraction")
    print("  - Use OpenAI Vision for complex document understanding")
    print("  - Set page limits for PDFs to control costs")
    print("  - Cache results to avoid redundant API calls")
    print("=" * 60)


if __name__ == "__main__":
    main()