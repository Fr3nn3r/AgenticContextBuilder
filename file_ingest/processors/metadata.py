# file_ingest/processors/metadata.py
# Core metadata processor for extracting file system and basic file information
# Migrated from original extract_datasets_metadata.py with ingestion terminology

import os
import stat
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .base import BaseProcessor, ProcessingError
from ..utils import get_file_hash, format_bytes


class MetadataProcessor(BaseProcessor):
    """
    Processor that extracts comprehensive file system metadata.

    Extracts basic file information, timestamps, permissions, MIME types,
    and file hashes. This is typically the first processor in the pipeline.
    """

    VERSION = "1.0.0"
    DESCRIPTION = "Extracts comprehensive file system metadata including hashes, permissions, and timestamps"
    SUPPORTED_EXTENSIONS = ["*"]  # Supports all file types

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        # Default configuration
        self.config.setdefault('include_hashes', True)
        self.config.setdefault('hash_algorithms', ['md5', 'sha1', 'sha256'])
        self.config.setdefault('include_permissions', True)
        self.config.setdefault('include_windows_attributes', True)

    def process_file(self, file_path: Path, existing_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from a file.

        Args:
            file_path: Path to the file to process
            existing_metadata: Ignored for this processor (it's typically first)

        Returns:
            Dictionary containing file metadata

        Raises:
            ProcessingError: If metadata extraction fails
        """
        try:
            file_stat = os.stat(file_path)
            file_path_obj = Path(file_path)

            # Basic file information
            metadata = {
                'file_name': file_path_obj.name,
                'file_path': str(file_path_obj.absolute()),
                'file_extension': file_path_obj.suffix,
                'file_size_bytes': file_stat.st_size,
                'file_size_human': format_bytes(file_stat.st_size),
            }

            # Timestamps
            metadata.update({
                'created_time': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                'modified_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                'accessed_time': datetime.fromtimestamp(file_stat.st_atime).isoformat(),
            })

            # File type information
            metadata.update({
                'is_directory': file_path_obj.is_dir(),
                'is_file': file_path_obj.is_file(),
                'is_symlink': file_path_obj.is_symlink(),
            })

            # MIME type
            mime_type, encoding = mimetypes.guess_type(file_path)
            metadata.update({
                'mime_type': mime_type,
                'encoding': encoding,
            })

            # File permissions and attributes (if enabled)
            if self.config.get('include_permissions', True):
                metadata['permissions'] = self._extract_permissions(file_path, file_stat)

            # File hashes (only for regular files, not directories)
            if (file_path_obj.is_file() and
                self.config.get('include_hashes', True)):
                metadata['hashes'] = self._extract_hashes(file_path)

            # Windows-specific attributes (if enabled and on Windows)
            if (os.name == 'nt' and
                self.config.get('include_windows_attributes', True)):
                metadata['windows_attributes'] = self._extract_windows_attributes(file_stat)

            return {'file_metadata': metadata}

        except (OSError, IOError) as e:
            # Return partial metadata with error information
            return {
                'file_metadata': {
                    'file_name': Path(file_path).name,
                    'file_path': str(Path(file_path).absolute()),
                    'error': str(e),
                    'metadata_ingestion_failed': True
                }
            }
        except Exception as e:
            raise ProcessingError(
                f"Failed to extract metadata: {str(e)}",
                file_path=file_path,
                processor_name=self.name
            )

    def _extract_permissions(self, file_path: Path, file_stat) -> Dict[str, Any]:
        """
        Extract file permissions and access information.

        Args:
            file_path: Path to the file
            file_stat: Result of os.stat() call

        Returns:
            Dictionary containing permission information
        """
        return {
            'octal': oct(stat.S_IMODE(file_stat.st_mode)),
            'readable': os.access(file_path, os.R_OK),
            'writable': os.access(file_path, os.W_OK),
            'executable': os.access(file_path, os.X_OK),
        }

    def _extract_hashes(self, file_path: Path) -> Dict[str, Optional[str]]:
        """
        Extract file hashes using configured algorithms.

        Args:
            file_path: Path to the file to hash

        Returns:
            Dictionary mapping algorithm names to hash values
        """
        hashes = {}
        algorithms = self.config.get('hash_algorithms', ['md5', 'sha1', 'sha256'])

        for algorithm in algorithms:
            try:
                hashes[algorithm] = get_file_hash(file_path, algorithm)
            except ValueError:
                # Unsupported algorithm, skip it
                hashes[algorithm] = None

        return hashes

    def _extract_windows_attributes(self, file_stat) -> Dict[str, Optional[bool]]:
        """
        Extract Windows-specific file attributes.

        Args:
            file_stat: Result of os.stat() call

        Returns:
            Dictionary containing Windows attributes
        """
        if hasattr(file_stat, 'st_file_attributes'):
            return {
                'hidden': bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN),
                'system': bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_SYSTEM),
                'archive': bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE),
            }
        else:
            return {
                'hidden': None,
                'system': None,
                'archive': None,
            }

    def validate_config(self) -> bool:
        """
        Validate the processor configuration.

        Returns:
            True if configuration is valid
        """
        # Validate hash algorithms
        if 'hash_algorithms' in self.config:
            algorithms = self.config['hash_algorithms']
            if not isinstance(algorithms, list):
                return False

            # Check if algorithms are supported
            supported_algorithms = ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']
            for algo in algorithms:
                if algo not in supported_algorithms:
                    return False

        return True