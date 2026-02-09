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


def discover_files(
    file_paths: List[Path],
    claim_id: Optional[str] = None,
) -> List[DiscoveredClaim]:
    """
    Discover multiple document files and group them into claims.

    Files are grouped by parent folder — each unique parent becomes one claim.
    If claim_id is provided, all files are forced into a single claim.

    Args:
        file_paths: List of paths to document files
        claim_id: If provided, forces all files into one claim with this ID

    Returns:
        List of DiscoveredClaim objects

    Raises:
        FileNotFoundError: If any file does not exist
        ValueError: If any file is not a supported type or cannot be loaded
    """
    if not file_paths:
        raise ValueError("No file paths provided")

    # Deduplicate by resolved path
    seen_resolved: Dict[Path, Path] = {}  # resolved -> original
    unique_paths: List[Path] = []
    for fp in file_paths:
        fp = Path(fp)
        resolved = fp.resolve()
        if resolved in seen_resolved:
            logger.warning(
                f"Duplicate path skipped: {fp} (same as {seen_resolved[resolved]})"
            )
            continue
        seen_resolved[resolved] = fp
        unique_paths.append(fp)

    # Validate all files exist and are supported types
    supported = PDF_EXTENSIONS | IMAGE_EXTENSIONS | TEXT_EXTENSIONS
    for fp in unique_paths:
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {fp}")
        if not fp.is_file():
            raise ValueError(f"Path is not a file: {fp}")
        source_type = _get_source_type(fp)
        if source_type is None:
            raise ValueError(
                f"Unsupported file type: {fp.suffix}. "
                f"Supported: {', '.join(sorted(supported))}"
            )

    # Load all documents
    docs_by_file: Dict[Path, DiscoveredDocument] = {}
    for fp in unique_paths:
        doc = _load_document(fp)
        if doc is None:
            raise ValueError(f"Failed to load document: {fp}")
        docs_by_file[fp] = doc

    # Group by parent folder (or single claim if claim_id forced)
    if claim_id:
        # All files into one claim
        all_docs = [docs_by_file[fp] for fp in unique_paths]
        source_path = unique_paths[0].parent
        logger.info(
            f"Multi-file mode (forced claim_id={claim_id}): "
            f"{len(all_docs)} documents"
        )
        return [DiscoveredClaim(claim_id=claim_id, source_path=source_path, documents=all_docs)]

    # Group by parent folder
    groups: Dict[Path, List[DiscoveredDocument]] = {}
    for fp in unique_paths:
        parent = fp.parent.resolve()
        if parent not in groups:
            groups[parent] = []
        groups[parent].append(docs_by_file[fp])

    claims = []
    for parent, docs in sorted(groups.items()):
        cid = _sanitize_claim_id(parent.name)
        if not cid:
            cid = "unknown_claim"
        claims.append(DiscoveredClaim(claim_id=cid, source_path=parent, documents=docs))
        logger.debug(f"Grouped {len(docs)} files under claim {cid}")

    logger.info(f"Multi-file mode: {len(claims)} claim(s) from {len(unique_paths)} files")
    return claims


def discover_claim_folders(folder_paths: List[Path]) -> List[DiscoveredClaim]:
    """
    Discover claims from explicit list of claim folders.

    Each folder is treated as a single claim (unlike discover_claims which
    scans a root directory for subdirectories).

    Args:
        folder_paths: List of paths to claim folders

    Returns:
        List of DiscoveredClaim objects

    Raises:
        FileNotFoundError: If any folder does not exist
        NotADirectoryError: If any path is not a directory
        ValueError: If duplicate claim IDs are detected
    """
    if not folder_paths:
        raise ValueError("No folder paths provided")

    # Validate all paths exist and are directories
    for fp in folder_paths:
        fp = Path(fp)
        if not fp.exists():
            raise FileNotFoundError(f"Folder not found: {fp}")
        if not fp.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {fp}")

    # Discover documents in each folder
    claims = []
    seen_ids: Dict[str, Path] = {}  # claim_id -> first folder path

    for fp in folder_paths:
        fp = Path(fp)
        claim_id = _sanitize_claim_id(fp.name)
        if not claim_id:
            claim_id = "unknown_claim"

        # Check for duplicate claim IDs from different paths
        if claim_id in seen_ids:
            raise ValueError(
                f"Duplicate claim ID '{claim_id}' from folders: "
                f"{seen_ids[claim_id]} and {fp}"
            )

        docs = discover_documents(fp)
        if not docs:
            logger.warning(f"Skipping empty folder: {fp}")
            continue

        seen_ids[claim_id] = fp
        claims.append(DiscoveredClaim(claim_id=claim_id, source_path=fp, documents=docs))
        logger.debug(f"Discovered claim: {claim_id} ({len(docs)} docs)")

    logger.info(f"Multi-claim mode: {len(claims)} claim(s) from {len(folder_paths)} folders")
    return claims


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


def discover_from_workspace(
    workspace_dir: Path,
    doc_type_filter: Optional[List[str]] = None,
    claim_id_filter: Optional[List[str]] = None,
) -> List[DiscoveredClaim]:
    """Discover documents from the workspace registry (doc_index.jsonl).

    Reads existing document index instead of scanning input folders.
    This enables re-extraction of specific doc types without re-ingesting.

    Args:
        workspace_dir: Path to workspace root (e.g. workspaces/nsa)
        doc_type_filter: Only include documents with these doc_types
        claim_id_filter: Only include documents from these claim_ids

    Returns:
        List of DiscoveredClaim objects sorted by claim_id

    Raises:
        FileNotFoundError: If doc_index.jsonl does not exist
    """
    index_path = workspace_dir / "registry" / "doc_index.jsonl"
    if not index_path.exists():
        raise FileNotFoundError(
            f"Registry index not found: {index_path}\n"
            f"Run 'python -m context_builder.cli index' first."
        )

    # Read and filter index records
    claims_map: Dict[str, List[DiscoveredDocument]] = {}
    claim_source_paths: Dict[str, Path] = {}
    skipped = 0

    with open(index_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON on line {line_num} in {index_path}: {e}")
                continue

            claim_id = record.get("claim_id", "")
            doc_type = record.get("doc_type", "")
            doc_id = record.get("doc_id", "")
            doc_root = record.get("doc_root", "").replace("\\", "/")

            # Apply filters
            if doc_type_filter and doc_type not in doc_type_filter:
                continue
            if claim_id_filter and claim_id not in claim_id_filter:
                continue

            # Load doc.json to get file_md5
            doc_json_path = workspace_dir / doc_root / "meta" / "doc.json"
            file_md5 = doc_id  # fallback: use doc_id as partial hash
            if doc_json_path.exists():
                try:
                    with open(doc_json_path, "r", encoding="utf-8") as dj:
                        doc_meta = json.load(dj)
                    file_md5 = doc_meta.get("file_md5", doc_id)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to read {doc_json_path}: {e}, skipping doc {doc_id}")
                    skipped += 1
                    continue
            else:
                logger.warning(f"Missing doc.json for {doc_id} at {doc_json_path}, skipping")
                skipped += 1
                continue

            # Build source path to the original file
            source_path = workspace_dir / doc_root / "source" / "original.pdf"
            if not source_path.exists():
                # Try common alternatives
                source_dir = workspace_dir / doc_root / "source"
                if source_dir.exists():
                    candidates = list(source_dir.iterdir())
                    source_path = candidates[0] if candidates else source_path
                else:
                    logger.warning(f"No source file for {doc_id} at {source_path}, skipping")
                    skipped += 1
                    continue

            doc = DiscoveredDocument(
                source_path=source_path,
                original_filename=record.get("filename", ""),
                source_type=record.get("source_type", "pdf"),
                file_md5=file_md5,
                doc_id=doc_id,
                needs_ingestion=False,
            )

            if claim_id not in claims_map:
                claims_map[claim_id] = []
                claim_source_paths[claim_id] = workspace_dir / "claims" / record.get("claim_folder", claim_id)
            claims_map[claim_id].append(doc)

    if skipped:
        logger.warning(f"Skipped {skipped} document(s) due to missing metadata")

    # Build sorted DiscoveredClaim list
    claims = [
        DiscoveredClaim(
            claim_id=cid,
            source_path=claim_source_paths[cid],
            documents=docs,
        )
        for cid, docs in sorted(claims_map.items())
    ]

    logger.info(
        f"Workspace discovery: {sum(len(c.documents) for c in claims)} doc(s) "
        f"in {len(claims)} claim(s)"
    )
    return claims
