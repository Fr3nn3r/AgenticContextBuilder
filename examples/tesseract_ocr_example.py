"""
Example usage of Tesseract OCR ingestion module.

This example demonstrates:
- Basic OCR text extraction from images
- PDF processing with page-by-page extraction
- Language configuration for multilingual documents
- Image preprocessing options for better accuracy
- Confidence score interpretation
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder.ingestion import IngestionFactory


def example_basic_usage():
    """Basic usage example with a single image."""
    print("[Example 1: Basic Image OCR]")
    print("=" * 50)

    # Create Tesseract ingestion instance
    tesseract = IngestionFactory.create("tesseract")

    # Example with an image file
    image_path = Path("sample_image.png")  # Replace with your image

    if image_path.exists():
        try:
            # Process the image
            result = tesseract.process(image_path)

            # Display results
            print(f"File: {result['file_name']}")
            print(f"Size: {result['file_size_bytes']} bytes")
            print(f"Confidence: {result['average_confidence']:.2%}")

            # Extract text from first (only) page
            if result['pages']:
                page = result['pages'][0]
                print(f"\nExtracted Text ({page['word_count']} words):")
                print("-" * 40)
                print(page['text'][:500])  # Show first 500 characters
                if len(page['text']) > 500:
                    print("...")

        except Exception as e:
            print(f"Error: {e}")
    else:
        print(f"Sample file not found: {image_path}")
        print("Please provide an image file to test")

    print("\n")


def example_pdf_processing():
    """Example of processing multi-page PDFs."""
    print("[Example 2: PDF Document Processing]")
    print("=" * 50)

    # Create and configure Tesseract
    tesseract = AcquisitionFactory.create("tesseract")
    tesseract.max_pages = 5  # Limit to first 5 pages for demo

    pdf_path = Path("sample_document.pdf")  # Replace with your PDF

    if pdf_path.exists():
        try:
            # Process PDF
            result = tesseract.process(pdf_path)

            print(f"PDF: {result['file_name']}")
            print(f"Total pages processed: {result['total_pages']}")
            print(f"Overall confidence: {result['average_confidence']:.2%}")

            # Show text from each page
            for page in result['pages']:
                print(f"\n--- Page {page['page_number']} ---")
                print(f"Confidence: {page['confidence']:.2%}")
                print(f"Words: {page['word_count']}")

                # Show preview of text
                text = page['text'].strip()
                if text:
                    preview = text[:200] + "..." if len(text) > 200 else text
                    print(f"Text preview: {preview}")
                else:
                    print("No text extracted from this page")

        except Exception as e:
            print(f"Error: {e}")
    else:
        print(f"Sample PDF not found: {pdf_path}")
        print("Please provide a PDF file to test")

    print("\n")


def example_multilingual():
    """Example with multiple language support."""
    print("[Example 3: Multilingual Document OCR]")
    print("=" * 50)

    # Create Tesseract with multiple languages
    tesseract = AcquisitionFactory.create("tesseract")

    # Configure for English and French
    # Note: Language packs must be installed for Tesseract
    tesseract.languages = ['eng', 'fra']

    print(f"Configured languages: {tesseract.languages}")
    print("Note: Tesseract language packs must be installed")
    print("  Windows: Download from Tesseract installer")
    print("  Linux: apt-get install tesseract-ocr-fra")
    print("  Mac: brew install tesseract-lang")

    multilingual_doc = Path("multilingual_document.png")

    if multilingual_doc.exists():
        try:
            result = tesseract.process(multilingual_doc)

            if result['pages']:
                page = result['pages'][0]
                print(f"\nExtracted multilingual text:")
                print("-" * 40)
                print(page['text'][:500])

        except Exception as e:
            print(f"Error: {e}")
    else:
        print(f"\nNo sample multilingual document found")

    print("\n")


def example_preprocessing_options():
    """Example with different preprocessing configurations."""
    print("[Example 4: Image Preprocessing Options]")
    print("=" * 50)

    image_path = Path("low_quality_scan.png")  # Replace with your image

    # Test without preprocessing
    print("1. WITHOUT preprocessing:")
    tesseract_basic = AcquisitionFactory.create("tesseract")
    tesseract_basic.enable_preprocessing = False

    if image_path.exists():
        try:
            result_basic = tesseract_basic.process(image_path)
            confidence_basic = result_basic['average_confidence']
            print(f"   Confidence: {confidence_basic:.2%}")

            # Test with preprocessing
            print("\n2. WITH preprocessing (deskew + contrast):")
            tesseract_enhanced = AcquisitionFactory.create("tesseract")
            tesseract_enhanced.enable_preprocessing = True
            tesseract_enhanced.deskew = True
            tesseract_enhanced.enhance_contrast = True
            tesseract_enhanced.remove_noise = False  # Can enable if very noisy

            result_enhanced = tesseract_enhanced.process(image_path)
            confidence_enhanced = result_enhanced['average_confidence']
            print(f"   Confidence: {confidence_enhanced:.2%}")

            # Compare results
            improvement = confidence_enhanced - confidence_basic
            if improvement > 0:
                print(f"\n   Improvement: +{improvement:.2%}")
            else:
                print(f"\n   Change: {improvement:.2%}")

        except Exception as e:
            print(f"Error: {e}")
    else:
        print("No sample image found for preprocessing test")

    print("\n")


def example_confidence_analysis():
    """Example of analyzing OCR confidence scores."""
    print("[Example 5: Confidence Score Analysis]")
    print("=" * 50)

    tesseract = AcquisitionFactory.create("tesseract")

    # Process any available test file
    test_files = [
        Path("test.png"),
        Path("test.jpg"),
        Path("test.pdf"),
        Path("screenshot.png"),
    ]

    test_file = None
    for file in test_files:
        if file.exists():
            test_file = file
            break

    if test_file:
        try:
            result = tesseract.process(test_file)

            print(f"File: {result['file_name']}")
            print(f"Overall confidence: {result['average_confidence']:.2%}")

            # Interpret confidence scores
            confidence = result['average_confidence']

            print("\nConfidence interpretation:")
            if confidence >= 0.9:
                print("  [Excellent] Very high quality OCR result")
            elif confidence >= 0.75:
                print("  [Good] Reliable OCR result, minor errors possible")
            elif confidence >= 0.6:
                print("  [Fair] Usable result, review recommended")
            elif confidence >= 0.4:
                print("  [Poor] Low quality, significant errors likely")
            else:
                print("  [Very Poor] Unreliable result, manual review required")

            # Suggest improvements for low confidence
            if confidence < 0.75:
                print("\nSuggestions to improve OCR quality:")
                print("  - Ensure image has good resolution (300+ DPI)")
                print("  - Check image is not blurry or skewed")
                print("  - Enable preprocessing options")
                print("  - Try different language settings if applicable")
                print("  - Consider using a higher quality scan")

        except Exception as e:
            print(f"Error: {e}")
    else:
        print("No test files found in current directory")

    print("\n")


def example_batch_processing():
    """Example of processing multiple files."""
    print("[Example 6: Batch Processing]")
    print("=" * 50)

    tesseract = AcquisitionFactory.create("tesseract")

    # Find all image and PDF files in current directory
    from pathlib import Path

    current_dir = Path(".")
    files_to_process = []

    for pattern in ["*.png", "*.jpg", "*.jpeg", "*.pdf", "*.tiff"]:
        files_to_process.extend(current_dir.glob(pattern))

    if files_to_process:
        print(f"Found {len(files_to_process)} files to process:")

        results_summary = []

        for file_path in files_to_process[:5]:  # Limit to 5 for demo
            print(f"\nProcessing: {file_path.name}")

            try:
                result = tesseract.process(file_path)

                # Collect summary
                total_words = sum(
                    page.get('word_count', 0)
                    for page in result['pages']
                )

                summary = {
                    'file': file_path.name,
                    'pages': result['total_pages'],
                    'words': total_words,
                    'confidence': result['average_confidence']
                }
                results_summary.append(summary)

                print(f"  Pages: {summary['pages']}")
                print(f"  Words: {summary['words']}")
                print(f"  Confidence: {summary['confidence']:.2%}")

            except Exception as e:
                print(f"  Error: {e}")

        # Show summary
        if results_summary:
            print("\n" + "=" * 50)
            print("Batch Processing Summary:")
            print("-" * 50)

            total_pages = sum(r['pages'] for r in results_summary)
            total_words = sum(r['words'] for r in results_summary)
            avg_confidence = sum(r['confidence'] for r in results_summary) / len(results_summary)

            print(f"Files processed: {len(results_summary)}")
            print(f"Total pages: {total_pages}")
            print(f"Total words: {total_words}")
            print(f"Average confidence: {avg_confidence:.2%}")

    else:
        print("No image or PDF files found in current directory")

    print("\n")


def save_results_to_json(result, output_file="ocr_output.json"):
    """Save OCR results to JSON file for further processing."""
    print(f"Saving results to {output_file}...")

    # Convert Path objects to strings for JSON serialization
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


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print(" TESSERACT OCR ACQUISITION MODULE EXAMPLES")
    print("=" * 60 + "\n")

    # Check if Tesseract is available
    try:
        tesseract = AcquisitionFactory.create("tesseract")
        print("[OK] Tesseract is available and configured")
    except Exception as e:
        print(f"[ERROR] Tesseract setup failed: {e}")
        print("\nPlease install Tesseract OCR:")
        print("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  Mac: brew install tesseract")
        print("  Linux: apt-get install tesseract-ocr")
        return

    print("\nNote: Examples will work with any image/PDF files")
    print("Place test files in current directory to see results\n")

    # Run examples
    example_basic_usage()
    example_pdf_processing()
    example_multilingual()
    example_preprocessing_options()
    example_confidence_analysis()
    example_batch_processing()

    print("=" * 60)
    print("Examples completed!")
    print("\nFor production usage:")
    print("  1. Install language packs for multilingual support")
    print("  2. Use high-resolution scans (300+ DPI) for best results")
    print("  3. Enable preprocessing for low-quality images")
    print("  4. Monitor confidence scores to identify issues")
    print("=" * 60)


if __name__ == "__main__":
    main()