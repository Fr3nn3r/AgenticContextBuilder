# This script is designed to process a directory of files and generate a structured
# JSON file that serves as a "context" for further analysis. It recursively scans
# a specified base folder, identifies different file types (PDF, images, text, sheets),
# and extracts their content using various methods like OCR, AI-based image analysis,
# and standard file reading.
#
# The script can handle:
# - Text-based files (e.g., .txt, .json, .csv) by reading their content directly.
# - PDF files by performing OCR with Tesseract. If the OCR output appears to be
#   gibberish, it falls back to using the OpenAI Vision API for a more robust analysis.
# - Image files by generating descriptions using the OpenAI Vision API.
# - Sheet files (CSV, Excel) by converting their content to JSON.
#
# It supports two modes of operation:
# 1. Processing a single base folder to generate one context file.
# 2. Processing each immediate subfolder within a base folder to generate a separate
#    context file for each, which is useful for partitioned datasets.
#
# The final output is a single JSON file (or multiple, if processing subfolders)
# containing a list of entries, where each entry represents a file and includes its
# relative path, detected file type, and the extracted content.
#
# Usage:
# - For a single folder: python generate_context.py /path/to/folder --output_folder /path/to/output
# - For subfolders: python generate_context.py /path/to/root_folder --process-subfolders

import os
import sys
import json
import logging
import argparse
import base64
import mimetypes
import io
import re
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import pandas as pd
import pypdfium2 as pdfium

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# --- Import from existing scripts ---
# It's better to refactor these scripts into importable functions,
# but for now, we'll try to import them directly.
try:
    from simple_ocr import process_pdf_ocr_only, pytesseract
    from image_to_text_analyzer import OPENAI_API_KEY
    from PIL import Image
    from openai import OpenAI
    import fitz  # PyMuPDF for PDF scan detection
    from docx2pdf import convert as docx_to_pdf
    import antiword
except (ImportError, ModuleNotFoundError) as e:
    logging.error(f"Failed to import necessary modules: {e}")
    logging.error(
        "Please ensure that the required packages are installed and that the script is run from the project root."
    )
    sys.exit(1)

# --- Constants ---
SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".json",
    ".md",
    ".xml",
    ".html",
    ".csv",
    ".py",
    ".js",
}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
SUPPORTED_SHEET_EXTENSIONS = {".csv", ".xls", ".xlsx"}

# --- File Processing Functions ---


def get_file_type(file_path: Path) -> str:
    """Detects the file type based on extension."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "doc_image"  # Treat as image for Vision API processing
    if ext == ".doc":
        return "doc_image"  # Treat as image for Vision API processing
    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    if ext in SUPPORTED_SHEET_EXTENSIONS:
        return "sheet"
    if (
        ext in SUPPORTED_TEXT_EXTENSIONS or file_path.stat().st_size < 1000000
    ):  # Guess for text files
        # Check mime type for text
        mimetype, _ = mimetypes.guess_type(file_path)
        if mimetype and mimetype.startswith("text/"):
            return "text"
    return "unsupported"


def read_text_file(file_path: Path) -> Optional[str]:
    """Reads content from a text-based file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Could not read text file {file_path}: {e}")
        return None


def test_document_conversion_capabilities():
    """
    Test function to check if document conversion dependencies are working.
    """
    try:
        # Test docx2pdf import
        from docx2pdf import convert as docx_to_pdf

        logging.info("✓ docx2pdf import successful")

        # Test OpenAI client
        if OPENAI_API_KEY:
            client = OpenAI(api_key=OPENAI_API_KEY)
            logging.info("✓ OpenAI client initialized")
        else:
            logging.warning("⚠ OPENAI_API_KEY not configured")

        # Test PyMuPDF
        import fitz

        logging.info("✓ PyMuPDF (fitz) available")

        return True

    except Exception as e:
        logging.error(f"✗ Document conversion capability test failed: {e}")
        return False


def convert_doc_to_images(client: OpenAI, file_path: Path) -> List[Dict[str, Any]]:
    """
    Converts a .doc or .docx file to images and processes them with Vision API.
    """
    import tempfile
    import os
    import subprocess

    results = []
    temp_pdf = None

    try:
        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_pdf = temp_file.name

        file_ext = file_path.suffix.lower()

        if file_ext == ".docx":
            # Use docx2pdf for .docx files
            logging.info(f"Converting {file_path.name} to PDF using docx2pdf...")
            try:
                # Ensure the file exists and is readable
                if not file_path.exists() or file_path.stat().st_size == 0:
                    raise Exception(f"File {file_path.name} is empty or doesn't exist")

                docx_to_pdf(str(file_path), temp_pdf)

                # Verify PDF was created
                if not os.path.exists(temp_pdf) or os.path.getsize(temp_pdf) == 0:
                    raise Exception("docx2pdf created an empty or invalid PDF file")

                logging.info(
                    f"Successfully converted {file_path.name} to PDF ({os.path.getsize(temp_pdf)} bytes)"
                )

            except Exception as docx_error:
                # Enhanced error reporting for docx conversion
                logging.error(
                    f"Failed to convert {file_path.name} to PDF: {docx_error}"
                )
                # Provide file information as fallback
                file_stats = file_path.stat()
                results = [
                    {
                        "detected_type": "docx_conversion_failed",
                        "fields": {
                            "filename": file_path.name,
                            "file_size_bytes": file_stats.st_size,
                            "modified_date": str(file_stats.st_mtime),
                            "error": str(docx_error),
                            "note": "DOCX file detected but conversion to PDF failed. This may be due to file corruption or unsupported format.",
                        },
                        "raw_text": f"File: {file_path.name} (DOCX document, conversion failed: {docx_error})",
                        "image_description": f"This is a Microsoft Word document (.docx format) named '{file_path.name}' that could not be converted to PDF for Vision API processing. Error: {docx_error}",
                    }
                ]
                return results
        elif file_ext == ".doc":
            # For .doc files, provide file information since full conversion is complex
            logging.info(
                f"Processing .doc file {file_path.name} - providing file information..."
            )
            file_stats = file_path.stat()
            results = [
                {
                    "detected_type": "legacy_doc_file",
                    "fields": {
                        "filename": file_path.name,
                        "file_size_bytes": file_stats.st_size,
                        "modified_date": str(file_stats.st_mtime),
                        "note": "Legacy .doc file format detected. Content extraction requires specialized tools.",
                    },
                    "raw_text": f"File: {file_path.name} (Legacy Microsoft Word document, {file_stats.st_size} bytes)",
                    "image_description": f"This is a legacy Microsoft Word document (.doc format) named '{file_path.name}'. The file is {file_stats.st_size} bytes in size. Content extraction would require specialized conversion tools like LibreOffice or Microsoft Word.",
                }
            ]
            return results

        # For non-.doc files, check if PDF was created and process it
        if file_ext != ".doc":
            # Check if PDF was created successfully
            if not os.path.exists(temp_pdf) or os.path.getsize(temp_pdf) == 0:
                raise Exception("No valid PDF was created from document")

            # Now process the PDF as images using existing function
            logging.info(f"Processing converted PDF with Vision API...")
            results = process_pdf_with_vision(client, Path(temp_pdf))

    except Exception as e:
        logging.error(f"Failed to convert {file_path} to images: {e}")
        results = [{"error": "Document to image conversion failed", "details": str(e)}]

    finally:
        # Clean up temporary PDF file with retry mechanism
        if temp_pdf and os.path.exists(temp_pdf):
            import time

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    os.unlink(temp_pdf)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logging.warning(
                            f"Temporary file cleanup attempt {attempt + 1} failed, retrying: {e}"
                        )
                        time.sleep(0.5)  # Wait before retry
                    else:
                        logging.warning(
                            f"Could not delete temporary file {temp_pdf} after {max_retries} attempts: {e}"
                        )

    return results


def read_sheet_file(file_path: Path) -> Optional[str]:
    """Reads content from a CSV or Excel file and converts to JSON."""
    try:
        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        return df.to_json(orient="records")
    except Exception as e:
        logging.error(f"Could not read sheet file {file_path}: {e}")
        return None


def get_image_ocr_text(file_path: Path) -> str:
    """Extracts text from an image using Tesseract OCR."""
    try:
        return pytesseract.image_to_string(Image.open(file_path))
    except Exception as e:
        logging.error(f"OCR failed for image {file_path}: {e}")
        return ""


def get_image_ai_description(client: OpenAI, file_path: Path) -> str:
    """Generates a description for an image using OpenAI."""
    try:
        with open(file_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

        # Using a more generic prompt than the one in image_to_text_analyzer.py
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe the contents of this image.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI analysis failed for {file_path}: {e}")
        return ""


def is_ocr_gibberish(text: str) -> bool:
    """
    Detects if the OCR output is sparse or gibberish based on simple rules.
    """
    clean_text = text.strip()

    if not clean_text or len(clean_text) < 50:  # If the text is empty or very short
        return True

    # Check the ratio of alphanumeric characters to total characters
    alphanum_chars = sum(c.isalnum() for c in clean_text)
    total_chars = len(clean_text)

    if total_chars > 0 and (alphanum_chars / total_chars) < 0.6:
        return True  # Less than 60% alphanumeric characters suggests gibberish

    return False


def is_pdf_scanned(pdf_path: Path) -> bool:
    """
    Detects if a PDF contains scanned pages by checking if pages have no text but have images.
    """
    try:
        doc = fitz.open(pdf_path)
        scanned_pages = 0
        total_pages = len(doc)

        for page in doc:
            text = page.get_text()
            images = page.get_images(full=True)

            # If a page has no text but has images, it's likely scanned
            if not text.strip() and images:
                scanned_pages += 1

        doc.close()

        # If more than half the pages are scanned, consider it a scanned PDF
        return scanned_pages > total_pages / 2
    except Exception as e:
        logging.error(f"Error checking if PDF {pdf_path} is scanned: {e}")
        return False


def extract_json_from_output(raw_output: str) -> Dict[str, Any]:
    """
    Extracts and parses JSON from a raw string, cleaning up markdown code blocks.
    """
    # Remove Markdown code block if present
    match = re.search(r"```json(.*?)```", raw_output, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1).strip()
    else:
        # fallback: try to find the first '{' and last '}'
        start = raw_output.find("{")
        end = raw_output.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = raw_output[start : end + 1]
        else:
            raise ValueError("No JSON found in output")
    # Parse JSON
    return json.loads(json_str)


def encode_image_to_base64(file_path: Path) -> str:
    """Encodes an image file to a base64 string."""
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_with_vision(client: OpenAI, image_base64: str) -> str:
    """
    Generates a description or extracts structured data from an image using the
    OpenAI Vision API with the new universal prompt.
    """
    new_prompt = """
You are an AI assistant for universal document and image processing.
For the image provided:

If the image is a document (receipt, ticket, invoice, form, etc.), extract all visible information in structured JSON format (include key fields, tables, totals, dates, etc.).

If the image is a photo (e.g., a vehicle, damaged property, or objects), describe the content and any visible details as clearly as possible.

In all cases, identify the type of image or document, and include this as a field in your output.
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": new_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ],
            }
        ],
        max_tokens=2048,
    )
    return response.choices[0].message.content


def process_pdf_with_vision(client: OpenAI, file_path: Path) -> List[Dict[str, Any]]:
    """
    Processes a PDF page-by-page using the Vision API.
    Used as a fallback when Tesseract OCR fails.
    """
    results = []
    logging.info(f"Processing PDF {file_path.name} with Vision API fallback...")
    try:
        pdf_doc = pdfium.PdfDocument(file_path)
        for i, page in enumerate(pdf_doc):
            logging.info(f"  - Analyzing page {i + 1}/{len(pdf_doc)}...")
            # Render page to a PIL image
            bitmap = page.render(scale=2)  # Scale can be adjusted
            pil_image = bitmap.to_pil()

            # Convert PIL image to base64
            buffered = io.BytesIO()
            pil_image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Analyze the image of the page
            vision_output_str = ""
            try:
                vision_output_str = analyze_with_vision(client, img_base64)
                vision_output_json = extract_json_from_output(vision_output_str)
                results.append(vision_output_json)
            except (ValueError, json.JSONDecodeError) as e:
                logging.warning(
                    f"    - Could not parse JSON from Vision API for page {i + 1}: {e}. Storing raw output."
                )
                results.append(
                    {"error": "Invalid JSON from API", "raw_output": vision_output_str}
                )
            except Exception as e:
                logging.error(f"    - Vision API analysis failed for page {i + 1}: {e}")
                results.append({"error": "Vision API call failed", "details": str(e)})
        return results
    except Exception as e:
        logging.error(f"Failed to process PDF {file_path} with Vision API: {e}")
        return [{"error": "PDF processing with Vision failed", "details": str(e)}]


# --- Main Orchestration Function ---


def generate_context(
    basefolder: str,
    output_folder: Optional[str] = None,
    vision_only_pdf: bool = False,
) -> None:
    """
    Recursively scans a base folder, extracts content from files, and
    generates a JSON context file.
    """
    logging.info("Starting generate_context function")
    basefolder = basefolder.strip("'\"")  # Clean up path from shell quoting issues
    base_path = Path(basefolder)
    if not base_path.is_dir():
        logging.error(
            f"Error: The base folder '{basefolder}' does not exist or is not a directory."
        )
        return

    output_path = Path(output_folder) if output_folder else Path.cwd()
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / f"{base_path.name}-context.json"
    logging.info(f"Output will be saved to: {output_file}")

    # Initialize OpenAI client if the key is available
    client = None
    if OPENAI_API_KEY:
        logging.info("OpenAI API key found, initializing client.")
        client = OpenAI(api_key=OPENAI_API_KEY)
    else:
        logging.warning(
            "OPENAI_API_KEY not found. AI descriptions for images will be skipped."
        )

    all_files_context: List[Dict[str, Any]] = []

    # Use rglob for recursive scanning
    logging.info(f"Scanning for files in {base_path}.")
    files_to_process = list(base_path.rglob("*"))
    logging.info(f"Found {len(files_to_process)} files to process in {base_path}.")

    for i, file_path in enumerate(files_to_process):
        logging.info(f"Processing file {i+1}/{len(files_to_process)}: {file_path}")
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(base_path).as_posix()
        logging.info(f"Processing: {relative_path}")

        file_type = get_file_type(file_path)
        content: Union[str, Dict[str, str], None] = None

        entry = {
            "relative_path": relative_path,
            "file_type": file_type,
            "content": None,
        }

        try:
            if file_type == "pdf":
                if vision_only_pdf:
                    logging.info(f"Vision-only mode is active for PDF: {relative_path}")
                    if client:
                        content = process_pdf_with_vision(client, file_path)
                    else:
                        logging.error(
                            "Cannot use Vision API for PDF as OPENAI_API_KEY is not configured."
                        )
                        content = {
                            "error": "Vision-only PDF mode requires Vision API but key not available."
                        }
                # Check if PDF contains scans first
                elif is_pdf_scanned(file_path):
                    logging.info(
                        f"Detected scanned PDF {relative_path}. Using Vision API."
                    )
                    if client:
                        content = process_pdf_with_vision(client, file_path)
                    else:
                        logging.error(
                            "Cannot use Vision API fallback for PDF as OPENAI_API_KEY is not configured."
                        )
                        content = {"error": "OCR failed and Vision API not available."}
                else:
                    # Regular PDF with text - try OCR first
                    ocr_text = process_pdf_ocr_only(str(file_path))
                    if is_ocr_gibberish(ocr_text):
                        logging.warning(
                            f"Sparse OCR for {relative_path}. Falling back to Vision API."
                        )
                        if client:
                            content = process_pdf_with_vision(client, file_path)
                        else:
                            logging.error(
                                "Cannot use Vision API fallback for PDF as OPENAI_API_KEY is not configured."
                            )
                            content = {
                                "error": "OCR failed and Vision API not available."
                            }
                    else:
                        content = ocr_text
            elif file_type == "image":
                if client:
                    vision_output_str = ""
                    try:
                        image_base64 = encode_image_to_base64(file_path)
                        vision_output_str = analyze_with_vision(client, image_base64)
                        content = extract_json_from_output(vision_output_str)
                    except (ValueError, json.JSONDecodeError) as e:
                        logging.warning(
                            f"Could not parse JSON from Vision API for image {relative_path}: {e}. Storing raw output."
                        )
                        content = {
                            "error": "Invalid JSON from API",
                            "raw_output": vision_output_str,
                        }
                    except Exception as e:
                        logging.error(
                            f"Vision API analysis failed for image {relative_path}: {e}"
                        )
                        content = {"error": "Vision API call failed", "details": str(e)}
                else:
                    logging.warning(
                        f"Skipping AI description for {relative_path} due to missing API key."
                    )
                    # Fallback to just OCR if vision is not available
                    content = {
                        "ai_description": "",
                        "ocr_text": get_image_ocr_text(file_path),
                    }

            elif file_type == "doc_image":
                if client:
                    content = convert_doc_to_images(client, file_path)
                else:
                    logging.error(
                        f"Cannot process document {relative_path} as OPENAI_API_KEY is not configured."
                    )
                    content = {
                        "error": "Document processing requires Vision API but API key not available."
                    }
            elif file_type == "text":
                content = read_text_file(file_path)
            elif file_type == "sheet":
                content = read_sheet_file(file_path)
            else:
                logging.warning(f"Unsupported file type for {relative_path}. Skipping.")
                continue

            if content is not None:
                entry["content"] = content
                all_files_context.append(entry)
            else:
                logging.warning(
                    f"Skipping {relative_path} due to content extraction failure."
                )

        except Exception as e:
            logging.error(f"An unexpected error occurred processing {relative_path}:")
            logging.error(traceback.format_exc())
            # Add entry with no content if processing fails
            all_files_context.append(entry)

    # Write the final JSON output
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_files_context, f, indent=2, ensure_ascii=False)
        logging.info(f"Successfully generated context file at {output_file}")
    except Exception as e:
        logging.error(f"Failed to write JSON output to {output_file}: {e}")
    logging.info("generate_context function finished.")


# --- CLI Interface ---

if __name__ == "__main__":
    logging.info("Script started.")
    parser = argparse.ArgumentParser(
        description="Generate a context JSON file from a directory of files."
    )
    parser.add_argument(
        "basefolder",
        type=str,
        nargs="?",
        help="The base folder to recursively scan for files.",
    )
    parser.add_argument(
        "--output_folder",
        type=str,
        default="output",
        help="The folder to save the output JSON file. Defaults to 'output'.",
    )
    parser.add_argument(
        "--process-subfolders",
        action="store_true",
        help="Process each immediate subfolder of the basefolder individually.",
    )
    parser.add_argument(
        "--vision-only-pdf",
        action="store_true",
        help="Force PDF processing using only OpenAI Vision for every page, skipping OCR.",
    )
    parser.add_argument(
        "--test-conversion",
        action="store_true",
        help="Test document conversion capabilities and exit.",
    )

    args = parser.parse_args()

    # Handle test conversion flag
    if args.test_conversion:
        logging.info("Running document conversion capability test...")
        test_result = test_document_conversion_capabilities()
        if test_result:
            logging.info(
                "✅ All document conversion capabilities are working correctly!"
            )
        else:
            logging.error(
                "❌ Some document conversion capabilities are missing or broken."
            )
        sys.exit(0 if test_result else 1)

    # Check that basefolder is provided when not testing
    if not args.basefolder:
        parser.error("basefolder is required when not using --test-conversion")

    # Tesseract path configuration check
    # The original script has a hardcoded path. We should check if it's set.
    if not pytesseract.pytesseract.tesseract_cmd:
        logging.warning("Tesseract command path is not set in pytesseract.")
        logging.warning(
            "Please ensure Tesseract is in your system's PATH or set the path in the script."
        )
    else:
        # Check if the configured path exists
        tesseract_path = pytesseract.pytesseract.tesseract_cmd.strip('"')
        if not os.path.exists(tesseract_path):
            logging.error(f"Tesseract executable not found at: {tesseract_path}")
            logging.error(
                "Please install Tesseract OCR and/or configure the correct path."
            )
            sys.exit(1)

    if args.process_subfolders:
        root_folder = Path(args.basefolder.strip("'\""))
        output_folder = Path(args.output_folder)
        if not root_folder.is_dir():
            logging.error(
                f"Error: The root folder '{root_folder}' does not exist or is not a directory."
            )
            sys.exit(1)

        logging.info(f"Processing subfolders in '{root_folder}'...")
        for subfolder in root_folder.iterdir():
            if subfolder.is_dir():
                logging.info(f"--- Generating context for: {subfolder.name} ---")
                try:
                    generate_context(
                        str(subfolder), str(output_folder), args.vision_only_pdf
                    )
                except Exception as e:
                    logging.error(f"Failed to process subfolder {subfolder.name}: {e}")
                    logging.error(traceback.format_exc())
        logging.info("--- All subfolders processed. ---")
    else:
        generate_context(args.basefolder, args.output_folder, args.vision_only_pdf)
    logging.info("Script finished.")
