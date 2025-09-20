# intake/processors/metadata.py
# Core metadata processor for extracting file system and basic file information
# Migrated from original extract_datasets_metadata.py with ingestion terminology

import os
import stat
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .base import BaseProcessor, ProcessingError
from ..utils import get_file_hash, format_bytes
from ..models import (
    FileMetadata, FilePermissions, FileHashes, WindowsAttributes,
    MetadataProcessorConfig
)


class MetadataProcessor(BaseProcessor):
    """
    Processor that extracts comprehensive file system metadata.

    Extracts basic file information, timestamps, permissions, MIME types,
    and file hashes. This is typically the first processor in the pipeline.
    """

    VERSION = "1.0.0"
    DESCRIPTION = "Extracts comprehensive file system metadata including hashes, permissions, and timestamps"
    SUPPORTED_EXTENSIONS = ["*"]  # Supports all file types

    def __init__(self, config: Optional[Union[Dict[str, Any], MetadataProcessorConfig]] = None):
        # Convert to MetadataProcessorConfig if needed
        if isinstance(config, dict):
            self.typed_config = MetadataProcessorConfig(**config)
        elif isinstance(config, MetadataProcessorConfig):
            self.typed_config = config
        else:
            self.typed_config = MetadataProcessorConfig()

        # Initialize base class with dict version for backward compatibility
        super().__init__(self.typed_config.model_dump())

    def process_file(self, file_path: Path, existing_metadata: Optional[Union[Dict[str, Any], FileMetadata]] = None) -> Dict[str, FileMetadata]:
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

            # MIME type
            mime_type, encoding = mimetypes.guess_type(file_path)

            # Build FileMetadata model
            metadata_dict = {
                'file_name': file_path_obj.name,
                'file_path': str(file_path_obj.absolute()),
                'file_extension': file_path_obj.suffix,
                'file_size_bytes': file_stat.st_size,
                'file_size_human': format_bytes(file_stat.st_size),
                'created_time': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                'modified_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                'accessed_time': datetime.fromtimestamp(file_stat.st_atime).isoformat(),
                'is_directory': file_path_obj.is_dir(),
                'is_file': file_path_obj.is_file(),
                'is_symlink': file_path_obj.is_symlink(),
                'mime_type': mime_type,
                'encoding': encoding,
            }

            # File permissions and attributes (if enabled)
            if self.typed_config.include_permissions:
                metadata_dict['permissions'] = self._extract_permissions(file_path, file_stat)

            # File hashes (only for regular files, not directories)
            if (file_path_obj.is_file() and self.typed_config.include_hashes):
                metadata_dict['hashes'] = self._extract_hashes(file_path)

            # Windows-specific attributes (if enabled and on Windows)
            if (os.name == 'nt' and self.typed_config.include_windows_attributes):
                metadata_dict['windows_attributes'] = self._extract_windows_attributes(file_stat)

            # Create FileMetadata model
            file_metadata = FileMetadata(**metadata_dict)
            return {'file_metadata': file_metadata}

        except (OSError, IOError) as e:
            # Return partial metadata with error information
            error_metadata = FileMetadata(
                file_name=Path(file_path).name,
                file_path=str(Path(file_path).absolute()),
                file_extension='',
                file_size_bytes=0,
                file_size_human='0 B',
                created_time=datetime.now().isoformat(),
                modified_time=datetime.now().isoformat(),
                accessed_time=datetime.now().isoformat(),
                is_directory=False,
                is_file=False,
                is_symlink=False,
                error=str(e),
                metadata_ingestion_failed=True
            )
            return {'file_metadata': error_metadata}
        except Exception as e:
            raise ProcessingError(
                f"Failed to extract metadata: {str(e)}",
                file_path=file_path,
                processor_name=self.name
            )

    def _extract_permissions(self, file_path: Path, file_stat) -> FilePermissions:
        """
        Extract file permissions and access information.

        Args:
            file_path: Path to the file
            file_stat: Result of os.stat() call

        Returns:
            FilePermissions model containing permission information
        """
        return FilePermissions(
            octal=oct(stat.S_IMODE(file_stat.st_mode)),
            readable=os.access(file_path, os.R_OK),
            writable=os.access(file_path, os.W_OK),
            executable=os.access(file_path, os.X_OK),
        )

    def _extract_hashes(self, file_path: Path) -> FileHashes:
        """
        Extract file hashes using configured algorithms.

        Args:
            file_path: Path to the file to hash

        Returns:
            FileHashes model with hash values
        """
        # Start with all None values
        hashes_data = {
            'md5': None,
            'sha1': None,
            'sha256': None,
            'sha384': None,
            'sha512': None,
        }

        # Only compute hashes for requested algorithms
        for algorithm in self.typed_config.hash_algorithms:
            try:
                hashes_data[algorithm] = get_file_hash(file_path, algorithm)
            except ValueError:
                # Unsupported algorithm, keep as None
                hashes_data[algorithm] = None

        return FileHashes(**hashes_data)

    def _extract_windows_attributes(self, file_stat) -> WindowsAttributes:
        """
        Extract Windows-specific file attributes.

        Args:
            file_stat: Result of os.stat() call

        Returns:
            WindowsAttributes model containing Windows attributes
        """
        if hasattr(file_stat, 'st_file_attributes'):
            return WindowsAttributes(
                hidden=bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN),
                system=bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_SYSTEM),
                archive=bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE),
            )
        else:
            return WindowsAttributes(
                hidden=None,
                system=None,
                archive=None,
            )

    def validate_config(self) -> bool:
        """
        Validate the processor configuration.

        Returns:
            True if configuration is valid
        """
        try:
            # Try to create a valid config from current settings
            MetadataProcessorConfig(**self.config)
            return True
        except Exception:
            return False