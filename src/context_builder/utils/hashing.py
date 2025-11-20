"""Hashing utility functions for file operations."""

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def calculate_file_md5(file_path: Path) -> str:
    """
    Calculate MD5 hash of a file.

    Args:
        file_path: Path to file to hash

    Returns:
        MD5 hash as hexadecimal string, or empty string on error
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to calculate MD5: {e}")
        return ""