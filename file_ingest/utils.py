# file_ingest/utils.py
# Shared utility functions for file ingestion system
# Contains common operations like hashing, formatting, and ID generation

import hashlib
import random
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_file_hash(file_path: Path, algorithm: str = 'sha256') -> Optional[str]:
    """
    Calculate file hash using specified algorithm.

    Args:
        file_path: Path to the file to hash
        algorithm: Hash algorithm to use (md5, sha1, sha256, etc.)

    Returns:
        Hexadecimal hash string, or None if file cannot be read

    Raises:
        ValueError: If algorithm is not supported
    """
    try:
        hash_obj = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    try:
        with open(file_path, 'rb') as f:
            # Read file in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except (OSError, IOError):
        return None


def format_bytes(bytes_value: int) -> str:
    """
    Convert bytes to human readable format.

    Args:
        bytes_value: Number of bytes to format

    Returns:
        Human-readable string representation (e.g., "1.23 MB")
    """
    if bytes_value == 0:
        return "0 B"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def generate_ingestion_id(input_folder: Path) -> str:
    """
    Generate unique ingestion ID with timestamp and input folder name.

    Format: ingest-YYYY-MM-DD-XXXXXXXXXX-folder_name

    Args:
        input_folder: Path to the input folder being processed

    Returns:
        Unique ingestion ID string
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(10)])
    input_folder_name = input_folder.name
    return f"ingest-{current_date}-{random_suffix}-{input_folder_name}"


def ensure_directory(path: Path) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)


def get_relative_path_safe(file_path: Path, base_path: Path) -> Path:
    """
    Get relative path safely, handling cases where file is not under base path.

    Args:
        file_path: The file path to make relative
        base_path: The base path to make it relative to

    Returns:
        Relative path if file is under base_path, otherwise the file name
    """
    try:
        return file_path.relative_to(base_path)
    except ValueError:
        # File is not under base_path, return just the filename
        return Path(file_path.name)


def validate_path_exists(path: Path, path_type: str = "path") -> None:
    """
    Validate that a path exists and raise descriptive error if not.

    Args:
        path: Path to validate
        path_type: Description of what the path represents (for error messages)

    Raises:
        FileNotFoundError: If path does not exist
        NotADirectoryError: If path exists but is not a directory when expected
    """
    if not path.exists():
        raise FileNotFoundError(f"{path_type.capitalize()} does not exist: {path}")

    if path_type == "directory" and not path.is_dir():
        raise NotADirectoryError(f"{path_type.capitalize()} is not a directory: {path}")


def safe_filename(filename: str, replacement: str = "_") -> str:
    """
    Create a safe filename by replacing invalid characters.

    Args:
        filename: Original filename
        replacement: Character to replace invalid characters with

    Returns:
        Sanitized filename safe for filesystem use
    """
    # Windows invalid characters: < > : " | ? * \ /
    # Also remove control characters
    invalid_chars = '<>:"|?*\\/'
    safe_name = filename
    for char in invalid_chars:
        safe_name = safe_name.replace(char, replacement)

    # Remove control characters (0-31)
    safe_name = ''.join(char for char in safe_name if ord(char) >= 32)

    # Ensure filename is not empty and not too long
    if not safe_name.strip():
        safe_name = "unnamed_file"

    # Limit filename length (255 is common filesystem limit)
    if len(safe_name) > 255:
        name_part, ext_part = safe_name.rsplit('.', 1) if '.' in safe_name else (safe_name, '')
        max_name_len = 255 - len(ext_part) - 1 if ext_part else 255
        safe_name = name_part[:max_name_len] + ('.' + ext_part if ext_part else '')

    return safe_name