"""
Batch claims document processing pipeline.

Processes insurance claim folders to inventory, extract, and classify documents.

For each claim folder:
1. Scan files and build inventory
2. Extract text (use companion .txt if available, else Azure DI/OpenAI Vision)
3. Classify each document
4. Write outputs: inventory.json, process-summary.json, {filename}-context.json

Usage:
    python scripts/batch_claims_processing.py --input-dir data/04-Claims-Motor-Ecuador
    python scripts/batch_claims_processing.py --input-dir data/claims --output-dir output/claims-processed
    python scripts/batch_claims_processing.py --input-dir data/claims --no-resume

Requirements:
    - OPENAI_API_KEY environment variable
    - AZURE_DI_ENDPOINT and AZURE_DI_API_KEY (for PDF extraction without companion .txt)
"""

import sys
import json
import logging
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from context_builder.utils.file_utils import get_file_metadata
from context_builder.classification import ClassifierFactory, ClassificationError
from context_builder.acquisition import AcquisitionFactory, AcquisitionError

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Note: Install tqdm for progress bars: pip install tqdm")

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# File type constants
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif'}
PDF_EXTENSIONS = {'.pdf'}
TEXT_EXTENSIONS = {'.txt'}
SKIP_FILES = {'.DS_Store', 'Thumbs.db', '.gitkeep', 'desktop.ini'}


@dataclass
class FileInventoryItem:
    """Single file in a claim folder."""
    filename: str
    file_path: str
    file_type: str  # "pdf", "txt", "image", "unknown"
    file_size_bytes: int
    md5: str
    # Classification results (populated after processing)
    document_type: Optional[str] = None
    language: Optional[str] = None
    summary: Optional[str] = None
    # Pre-existing text extraction (e.g., foo.pdf has foo.pdf.txt already)
    preextracted_txt_path: Optional[str] = None


@dataclass
class FileProcessingResult:
    """Result of processing a single file."""
    filename: str
    status: str  # "success", "error", "skipped"
    source: Optional[str] = None  # "companion_txt", "azure_di", "openai_vision"
    classification: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time_ms: int = 0


@dataclass
class ClaimProcessingResult:
    """Result of processing an entire claim folder."""
    folder_name: str
    status: str  # "success", "partial", "failed"
    files_total: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    document_types_found: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    processing_time_seconds: float = 0.0


def get_file_type(filepath: Path) -> str:
    """Determine file type from extension."""
    ext = filepath.suffix.lower()
    if ext in PDF_EXTENSIONS:
        return "pdf"
    elif ext in IMAGE_EXTENSIONS:
        return "image"
    elif ext in TEXT_EXTENSIONS:
        return "txt"
    return "unknown"


def should_skip_file(filename: str) -> bool:
    """Check if file should be skipped (hidden/system files)."""
    return filename in SKIP_FILES or filename.startswith('.')


def find_companion_txt(file_path: Path) -> Optional[Path]:
    """
    Find companion .txt file for a given file.
    e.g., POLIZA.pdf -> POLIZA.pdf.txt
    """
    txt_path = file_path.parent / f"{file_path.name}.txt"
    return txt_path if txt_path.exists() else None


def discover_claim_folders(base_dir: Path) -> List[Path]:
    """Find all claim folders (immediate subdirectories)."""
    if not base_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {base_dir}")

    folders = [d for d in base_dir.iterdir() if d.is_dir()]
    folders.sort()
    return folders


def scan_folder_files(folder: Path) -> List[FileInventoryItem]:
    """Scan folder and build file inventory."""
    inventory = []

    for filepath in folder.iterdir():
        if not filepath.is_file():
            continue
        if should_skip_file(filepath.name):
            continue

        file_type = get_file_type(filepath)

        # Skip .txt files that are companions (they'll be used with their source)
        if file_type == "txt":
            # Check if this is a companion to another file (e.g., foo.pdf.txt)
            # Pattern: original.pdf.txt is companion to original.pdf
            if filepath.suffix == ".txt" and len(filepath.suffixes) > 1:
                # e.g., "file.pdf.txt" -> check if "file.pdf" exists
                base_name = filepath.stem  # "file.pdf" (removes last .txt)
                potential_source = folder / base_name
                if potential_source.exists():
                    continue  # Skip companion .txt files

        # Get metadata
        metadata = get_file_metadata(filepath)

        # Check for pre-existing .txt extraction
        preextracted = find_companion_txt(filepath)

        item = FileInventoryItem(
            filename=filepath.name,
            file_path=metadata["file_path"],
            file_type=file_type,
            file_size_bytes=metadata["file_size_bytes"],
            md5=metadata["md5"],
            preextracted_txt_path=str(preextracted) if preextracted else None,
        )
        inventory.append(item)

    return inventory


def read_text_file(filepath: Path) -> str:
    """Read text content from file with encoding detection."""
    encodings = ['utf-8', 'latin-1', 'cp1252']
    for encoding in encodings:
        try:
            return filepath.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    # Fallback: read as bytes and decode ignoring errors
    return filepath.read_bytes().decode('utf-8', errors='ignore')


def get_text_content(
    file_item: FileInventoryItem,
    azure_di: Optional[Any] = None,
    openai_vision: Optional[Any] = None,
) -> tuple[str, str]:
    """
    Get text content for a file.

    Returns:
        Tuple of (text_content, source) where source is one of:
        "companion_txt", "azure_di", "openai_vision"
    """
    filepath = Path(file_item.file_path)

    # Priority 1: Use pre-existing .txt extraction if available
    if file_item.preextracted_txt_path:
        text = read_text_file(Path(file_item.preextracted_txt_path))
        return text, "preextracted_txt"

    # Priority 2: Read .txt files directly
    if file_item.file_type == "txt":
        text = read_text_file(filepath)
        return text, "text_file"

    # Priority 3: For PDFs, use Azure DI
    if file_item.file_type == "pdf" and azure_di:
        result = azure_di.process(filepath)
        # Azure DI returns markdown in a separate file
        markdown_path = result.get("markdown_file")
        if markdown_path:
            md_path = filepath.parent / markdown_path
            if md_path.exists():
                return read_text_file(md_path), "azure_di"
        # Fallback to any text content in result
        return result.get("text_content", ""), "azure_di"

    # Priority 3: For images, use OpenAI Vision
    if file_item.file_type == "image" and openai_vision:
        result = openai_vision.process(filepath)
        # Extract text from pages
        pages = result.get("pages", [])
        text_parts = [p.get("text_content", "") for p in pages]
        return "\n\n".join(text_parts), "openai_vision"

    raise ValueError(f"Cannot extract text from {file_item.filename}: no suitable method")


def process_file(
    file_item: FileInventoryItem,
    classifier: Any,
    azure_di: Optional[Any] = None,
    openai_vision: Optional[Any] = None,
) -> FileProcessingResult:
    """Process a single file: extract text and classify."""
    start_time = time.time()

    try:
        # Skip unknown file types
        if file_item.file_type == "unknown":
            return FileProcessingResult(
                filename=file_item.filename,
                status="skipped",
                error_message="Unknown file type",
            )

        # Get text content
        text_content, source = get_text_content(
            file_item, azure_di, openai_vision
        )

        if not text_content.strip():
            return FileProcessingResult(
                filename=file_item.filename,
                status="error",
                source=source,
                error_message="Empty text content",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        # Classify document
        classification = classifier.classify(text_content, file_item.filename)

        return FileProcessingResult(
            filename=file_item.filename,
            status="success",
            source=source,
            classification=classification,
            processing_time_ms=int((time.time() - start_time) * 1000),
        )

    except (ClassificationError, AcquisitionError) as e:
        return FileProcessingResult(
            filename=file_item.filename,
            status="error",
            error_message=str(e),
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
    except Exception as e:
        logger.exception(f"Unexpected error processing {file_item.filename}")
        return FileProcessingResult(
            filename=file_item.filename,
            status="error",
            error_message=f"Unexpected error: {str(e)}",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )


def process_claim_folder(
    folder: Path,
    classifier: Any,
    azure_di: Optional[Any] = None,
    openai_vision: Optional[Any] = None,
    progress_bar: Optional[Any] = None,
) -> tuple[ClaimProcessingResult, List[FileInventoryItem], List[FileProcessingResult]]:
    """
    Process all files in a claim folder.

    Returns:
        Tuple of (summary_result, inventory, file_results)
    """
    start_time = time.time()

    # Scan folder
    inventory = scan_folder_files(folder)

    result = ClaimProcessingResult(
        folder_name=folder.name,
        status="success",
        files_total=len(inventory),
    )

    file_results = []
    document_types = set()

    # Process each file
    for file_item in inventory:
        if progress_bar:
            progress_bar.set_postfix_str(file_item.filename[:30])

        file_result = process_file(file_item, classifier, azure_di, openai_vision)
        file_results.append(file_result)

        if file_result.status == "success":
            result.files_processed += 1
            if file_result.classification:
                # Populate classification back into inventory item
                file_item.document_type = file_result.classification.get("document_type")
                file_item.language = file_result.classification.get("language")
                file_item.summary = file_result.classification.get("summary")
                doc_type = file_item.document_type or "unknown"
                document_types.add(doc_type)
        elif file_result.status == "skipped":
            result.files_skipped += 1
        else:
            result.files_failed += 1
            result.errors.append({
                "file": file_result.filename,
                "error": file_result.error_message or "Unknown error",
            })

        if progress_bar:
            progress_bar.update(1)

    result.document_types_found = sorted(document_types)
    result.processing_time_seconds = time.time() - start_time

    # Determine overall status
    if result.files_failed == 0 and result.files_processed > 0:
        result.status = "success"
    elif result.files_processed > 0:
        result.status = "partial"
    else:
        result.status = "failed"

    return result, inventory, file_results


def write_outputs(
    output_dir: Path,
    claim_result: ClaimProcessingResult,
    inventory: List[FileInventoryItem],
    file_results: List[FileProcessingResult],
):
    """Write all output files for a claim folder."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write inventory.json
    inventory_data = {
        "folder_name": claim_result.folder_name,
        "scan_timestamp": datetime.now().isoformat(),
        "total_files": len(inventory),
        "file_types": {},
        "files": [asdict(item) for item in inventory],
    }
    # Count file types
    for item in inventory:
        inventory_data["file_types"][item.file_type] = \
            inventory_data["file_types"].get(item.file_type, 0) + 1

    with open(output_dir / "inventory.json", "w", encoding="utf-8") as f:
        json.dump(inventory_data, f, indent=2, ensure_ascii=False)

    # Write process-summary.json
    summary_data = {
        "folder_name": claim_result.folder_name,
        "status": claim_result.status,
        "processed_at": datetime.now().isoformat(),
        "processing_time_seconds": claim_result.processing_time_seconds,
        "statistics": {
            "total_files": claim_result.files_total,
            "files_processed": claim_result.files_processed,
            "files_skipped": claim_result.files_skipped,
            "files_failed": claim_result.files_failed,
        },
        "document_types_found": claim_result.document_types_found,
        "errors": claim_result.errors,
    }

    with open(output_dir / "process-summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    # Write per-file context JSONs
    for file_result in file_results:
        if file_result.status == "skipped":
            continue

        # Find corresponding inventory item
        inv_item = next(
            (i for i in inventory if i.filename == file_result.filename), None
        )

        context_data = {
            "source_file": asdict(inv_item) if inv_item else {"filename": file_result.filename},
            "extraction": {
                "source": file_result.source,
                "processed_at": datetime.now().isoformat(),
                "processing_time_ms": file_result.processing_time_ms,
            },
            "classification": file_result.classification,
            "status": file_result.status,
            "error": file_result.error_message,
        }

        # Create safe filename for context file
        safe_name = file_result.filename.replace(" ", "_")
        context_filename = f"{safe_name}-context.json"

        with open(output_dir / context_filename, "w", encoding="utf-8") as f:
            json.dump(context_data, f, indent=2, ensure_ascii=False)


def is_folder_processed(output_dir: Path) -> bool:
    """Check if folder has already been successfully processed."""
    summary_file = output_dir / "process-summary.json"
    if not summary_file.exists():
        return False
    try:
        with open(summary_file, "r") as f:
            summary = json.load(f)
            return summary.get("status") in ("success", "partial")
    except (json.JSONDecodeError, IOError):
        return False


def create_run_folder(base_dir: Path) -> Path:
    """Create timestamped run folder for non-destructive processing."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_folder = base_dir / f"run-{timestamp}"
    run_folder.mkdir(parents=True, exist_ok=True)
    return run_folder


def main():
    parser = argparse.ArgumentParser(
        description="Process insurance claim folders: inventory, extract, classify"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Input directory containing claim folders",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/claims-processed"),
        help="Base output directory (default: output/claims-processed)",
    )
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="Write directly to output-dir without creating timestamped subfolder",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Process all folders, even if already completed",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of folders to process",
    )

    args = parser.parse_args()

    # Determine output directory (timestamped by default)
    if args.no_timestamp:
        output_dir = args.output_dir
    else:
        output_dir = create_run_folder(args.output_dir)

    print(f"[OK] Input directory: {args.input_dir}")
    print(f"[OK] Output directory: {output_dir}")

    # Discover claim folders
    folders = discover_claim_folders(args.input_dir)
    print(f"[OK] Found {len(folders)} claim folders")

    if args.limit:
        folders = folders[:args.limit]
        print(f"[OK] Limited to {len(folders)} folders")

    # Filter already processed (unless --no-resume)
    if not args.no_resume:
        original_count = len(folders)
        folders = [
            f for f in folders
            if not is_folder_processed(output_dir / f.name)
        ]
        skipped = original_count - len(folders)
        if skipped > 0:
            print(f"[OK] Skipping {skipped} already processed folders")

    if not folders:
        print("[OK] No folders to process")
        return 0

    # Initialize components
    print("[..] Initializing classifier...")
    try:
        classifier = ClassifierFactory.create(
            "openai",
            prompt_name="claims_document_classification"
        )
        print("[OK] Classifier initialized")
    except Exception as e:
        print(f"[X] Failed to initialize classifier: {e}")
        return 1

    # Try to initialize acquisition providers (optional)
    azure_di = None
    openai_vision = None

    try:
        from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition
        azure_di = AcquisitionFactory.create("azure-di")
        print("[OK] Azure DI initialized")
    except Exception as e:
        print(f"[!] Azure DI not available: {e}")

    try:
        openai_vision = AcquisitionFactory.create("openai")
        print("[OK] OpenAI Vision initialized")
    except Exception as e:
        print(f"[!] OpenAI Vision not available: {e}")

    # Process folders
    print(f"\n[..] Processing {len(folders)} claim folders...")

    total_files = 0
    total_processed = 0
    total_errors = 0

    if HAS_TQDM:
        folder_pbar = tqdm(folders, desc="Claim folders", unit="folder")
    else:
        folder_pbar = folders

    for folder in folder_pbar:
        if HAS_TQDM:
            folder_pbar.set_postfix_str(folder.name[:30])

        # Count files for nested progress
        inventory = scan_folder_files(folder)
        file_count = len(inventory)

        if HAS_TQDM:
            file_pbar = tqdm(
                total=file_count,
                desc=f"  {folder.name[:25]}",
                leave=False,
                unit="file",
            )
        else:
            file_pbar = None
            print(f"  Processing: {folder.name} ({file_count} files)")

        # Process folder
        result, inventory, file_results = process_claim_folder(
            folder,
            classifier,
            azure_di,
            openai_vision,
            file_pbar,
        )

        if file_pbar:
            file_pbar.close()

        # Write outputs
        output_folder = output_dir / folder.name
        write_outputs(output_folder, result, inventory, file_results)

        # Update totals
        total_files += result.files_total
        total_processed += result.files_processed
        total_errors += result.files_failed

    # Print summary
    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"  Folders processed: {len(folders)}")
    print(f"  Total files: {total_files}")
    print(f"  Successfully classified: {total_processed}")
    print(f"  Errors: {total_errors}")
    print(f"  Output: {output_dir}")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
