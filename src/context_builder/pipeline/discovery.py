"""Discovery module: find claims and documents in input folders."""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

# File extensions by type
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif"}
TEXT_EXTENSIONS = {".txt"}  # Pre-extracted text

SourceType = Literal["pdf", "image", "text"]


@dataclass
class DiscoveredDocument:
    """A discovered document source file."""

    source_path: Path
    original_filename: str
    source_type: SourceType  # "pdf", "image", or "text"
    file_md5: str  # Hash of file bytes
    doc_id: str  # file_md5[:12]
    content: Optional[str] = None  # Only populated for text files
    needs_ingestion: bool = True  # False if already has extracted text


@dataclass
class DiscoveredClaim:
    """A discovered claim folder with its documents."""

    claim_id: str
    source_path: Path
    documents: List[DiscoveredDocument]


def doc_id_from_bytes(file_bytes: bytes) -> str:
    """Compute document ID from file bytes hash (md5[:12])."""
    full_hash = hashlib.md5(file_bytes).hexdigest()
    return full_hash[:12]


def doc_id_from_content(content: str) -> str:
    """Compute document ID from text content hash (md5[:12])."""
    return doc_id_from_bytes(content.encode("utf-8"))


def _get_source_type(file_path: Path) -> Optional[SourceType]:
    """Determine source type from file extension."""
    ext = file_path.suffix.lower()
    if ext in PDF_EXTENSIONS:
        return "pdf"
    elif ext in IMAGE_EXTENSIONS:
        return "image"
    elif ext in TEXT_EXTENSIONS:
        return "text"
    return None


def _sanitize_claim_id(folder_name: str) -> str:
    """
    Sanitize folder name for use as claim_id.

    Replaces spaces with underscores, removes problematic chars.
    """
    # Replace multiple spaces with single underscore
    sanitized = re.sub(r"\s+", "_", folder_name.strip())
    # Remove any chars that could cause filesystem issues
    sanitized = re.sub(r'[<>:"/\\|?*]', "", sanitized)
    return sanitized


def _load_document(file_path: Path) -> Optional[DiscoveredDocument]:
    """
    Load a document file and create DiscoveredDocument.

    Handles PDFs, images, and pre-extracted text files.
    Returns None if file cannot be read or is empty.
    """
    source_type = _get_source_type(file_path)
    if source_type is None:
        return None

    try:
        # Read file bytes for hashing
        file_bytes = file_path.read_bytes()
        if not file_bytes:
            logger.warning(f"Empty file skipped: {file_path}")
            return None

        file_md5 = hashlib.md5(file_bytes).hexdigest()
        doc_id = file_md5[:12]

        # Determine original filename
        original_filename = file_path.name
        if original_filename.endswith(".pdf.txt"):
            original_filename = original_filename[:-4]  # Keep .pdf

        # For text files, also load content
        content = None
        needs_ingestion = True
        if source_type == "text":
            content = file_bytes.decode("utf-8")
            needs_ingestion = False  # Already has text

        return DiscoveredDocument(
            source_path=file_path,
            original_filename=original_filename,
            source_type=source_type,
            file_md5=file_md5,
            doc_id=doc_id,
            content=content,
            needs_ingestion=needs_ingestion,
        )
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return None


def discover_documents(claim_folder: Path) -> List[DiscoveredDocument]:
    """
    Discover all documents in a claim folder.

    Finds PDFs, images, and pre-extracted text files.
    Prefers .pdf.txt over .pdf if both exist (already ingested).

    Args:
        claim_folder: Path to claim folder

    Returns:
        List of DiscoveredDocument
    """
    documents = []
    seen_basenames = set()  # Track by base name to avoid duplicates

    # Build set of already-ingested files (have .pdf.txt companion)
    txt_files = {f.stem for f in claim_folder.glob("*.pdf.txt")}

    # Find all supported files
    all_extensions = PDF_EXTENSIONS | IMAGE_EXTENSIONS | TEXT_EXTENSIONS
    all_files = sorted(
        f for f in claim_folder.iterdir()
        if f.is_file() and f.suffix.lower() in all_extensions
    )

    for file_path in all_files:
        # Skip .pdf if .pdf.txt exists (prefer pre-extracted)
        if file_path.suffix.lower() == ".pdf":
            if file_path.stem in txt_files:
                logger.debug(f"Skipping {file_path.name} (has .pdf.txt)")
                continue

        # Skip if we've already seen this base document
        base_name = file_path.stem
        if base_name.endswith(".pdf"):
            base_name = base_name[:-4]  # Remove .pdf from .pdf.txt
        if base_name in seen_basenames:
            continue

        doc = _load_document(file_path)
        if doc:
            documents.append(doc)
            seen_basenames.add(base_name)

    logger.debug(f"Found {len(documents)} documents in {claim_folder.name}")
    return documents


def discover_claims(input_path: Path) -> List[DiscoveredClaim]:
    """
    Discover claims from input path.

    Handles:
    - Single claim folder (if contains document files directly)
    - Multi-claim folder (if contains subdirectories with documents)

    Args:
        input_path: Path to claims root or single claim folder

    Returns:
        List of DiscoveredClaim objects sorted by claim_id
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    if not input_path.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_path}")

    # Check if this folder contains documents directly (single claim mode)
    docs_in_root = discover_documents(input_path)
    if docs_in_root:
        claim_id = _sanitize_claim_id(input_path.name)
        logger.info(f"Single claim mode: {claim_id} with {len(docs_in_root)} documents")
        return [DiscoveredClaim(claim_id, input_path, docs_in_root)]

    # Multi-claim mode: scan subdirectories
    claims = []
    for subdir in sorted(input_path.iterdir()):
        if not subdir.is_dir():
            continue

        docs = discover_documents(subdir)
        if docs:
            claim_id = _sanitize_claim_id(subdir.name)
            claims.append(DiscoveredClaim(claim_id, subdir, docs))
            logger.debug(f"Discovered claim: {claim_id} ({len(docs)} docs)")

    logger.info(f"Multi-claim mode: found {len(claims)} claims")
    return claims


def discover_single_file(file_path: Path) -> DiscoveredClaim:
    """
    Discover a single document file and create a claim for it.

    The claim_id is inferred from the parent folder name.

    Args:
        file_path: Path to a single document file (PDF, image, or text)

    Returns:
        DiscoveredClaim with a single document

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is not a supported type or cannot be loaded
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    # Check if file type is supported
    source_type = _get_source_type(file_path)
    if source_type is None:
        supported = PDF_EXTENSIONS | IMAGE_EXTENSIONS | TEXT_EXTENSIONS
        raise ValueError(
            f"Unsupported file type: {file_path.suffix}. "
            f"Supported: {', '.join(sorted(supported))}"
        )

    # Load the document
    doc = _load_document(file_path)
    if doc is None:
        raise ValueError(f"Failed to load document: {file_path}")

    # Infer claim_id from parent folder name
    claim_id = _sanitize_claim_id(file_path.parent.name)
    if not claim_id:
        claim_id = "single_doc"  # Fallback if parent has no name

    logger.info(f"Single file mode: {file_path.name} -> claim {claim_id}")
    return DiscoveredClaim(
        claim_id=claim_id,
        source_path=file_path.parent,
        documents=[doc],
    )


def check_existing_ingestion(
    output_base: Path,
    claim_id: str,
    doc_id: str,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if document has existing ingestion and classification outputs.

    Args:
        output_base: Base output directory
        claim_id: Claim identifier
        doc_id: Document identifier

    Returns:
        Tuple of (has_pages_json, doc_meta_dict or None)
    """
    from context_builder.pipeline.paths import get_claim_paths, get_doc_paths

    claim_paths = get_claim_paths(output_base, claim_id)
    doc_paths = get_doc_paths(claim_paths, doc_id)

    has_pages = doc_paths.pages_json.exists()
    doc_meta = None

    if doc_paths.doc_json.exists():
        try:
            with open(doc_paths.doc_json, "r", encoding="utf-8") as f:
                doc_meta = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read doc.json for {doc_id}: {e}")

    return has_pages, doc_meta
