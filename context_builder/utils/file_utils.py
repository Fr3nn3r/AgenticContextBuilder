"""File utility functions for metadata extraction."""

import mimetypes
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