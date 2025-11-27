"""File utility functions for metadata extraction."""

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from context_builder.utils.hashing import calculate_file_md5


def get_file_metadata(filepath: Path) -> Dict[str, Any]:
    """
    Extract metadata from a file.

    Args:
        filepath: Path to file

    Returns:
        Dictionary containing file metadata including name, path, size, mime type, and MD5 hash
    """
    absolute_path = filepath.resolve()
    mime_type, _ = mimetypes.guess_type(str(filepath))

    return {
        "file_name": filepath.name,
        "file_path": str(absolute_path),
        "file_extension": filepath.suffix.lower(),
        "file_size_bytes": filepath.stat().st_size,
        "mime_type": mime_type or "application/octet-stream",
        "md5": calculate_file_md5(filepath),
    }


def create_timestamped_output_folder(base_dir: Path, prefix: str = "ACB") -> Path:
    """
    Create unique timestamped output folder.

    Args:
        base_dir: Base directory where timestamped folder will be created
        prefix: Folder name prefix (default: "ACB")

    Returns:
        Path to created timestamped folder

    Raises:
        FileExistsError: If timestamped folder already exists (collision)

    Example:
        Given base_dir=/output and timestamp 2025-11-27 14:30:00
        Creates: /output/ACB-20251127-143000/
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder_name = f"{prefix}-{timestamp}"
    folder_path = base_dir / folder_name

    if folder_path.exists():
        raise FileExistsError(
            f"Output folder collision detected: {folder_path}\n"
            f"This should be extremely rare. Please try again in 1 second."
        )

    folder_path.mkdir(parents=True, exist_ok=False)
    return folder_path