# intake/models.py
# Pydantic data models for file ingestion system
# Defines structured data models for metadata, processing info, and summaries

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class FilePermissions(BaseModel):
    """File permissions and access information."""
    octal: str = Field(..., description="Octal representation of file permissions")
    readable: bool = Field(..., description="Whether file is readable")
    writable: bool = Field(..., description="Whether file is writable")
    executable: bool = Field(..., description="Whether file is executable")


class FileHashes(BaseModel):
    """File hash values for different algorithms."""
    md5: Optional[str] = Field(None, description="MD5 hash of the file")
    sha1: Optional[str] = Field(None, description="SHA1 hash of the file")
    sha256: Optional[str] = Field(None, description="SHA256 hash of the file")
    sha384: Optional[str] = Field(None, description="SHA384 hash of the file")
    sha512: Optional[str] = Field(None, description="SHA512 hash of the file")


class WindowsAttributes(BaseModel):
    """Windows-specific file attributes."""
    hidden: Optional[bool] = Field(None, description="Whether file is hidden")
    system: Optional[bool] = Field(None, description="Whether file is a system file")
    archive: Optional[bool] = Field(None, description="Whether file has archive attribute")


class FileMetadata(BaseModel):
    """Core file metadata extracted from filesystem."""
    model_config = ConfigDict(extra="forbid")

    # Basic file information
    file_name: str = Field(..., description="Name of the file")
    file_path: str = Field(..., description="Absolute path to the file")
    file_extension: str = Field(..., description="File extension including dot")
    file_size_bytes: int = Field(..., description="File size in bytes")
    file_size_human: str = Field(..., description="Human-readable file size")

    # Timestamps
    created_time: str = Field(..., description="File creation time in ISO format")
    modified_time: str = Field(..., description="File modification time in ISO format")
    accessed_time: str = Field(..., description="File access time in ISO format")

    # File type information
    is_directory: bool = Field(..., description="Whether this is a directory")
    is_file: bool = Field(..., description="Whether this is a regular file")
    is_symlink: bool = Field(..., description="Whether this is a symbolic link")

    # MIME type information
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    encoding: Optional[str] = Field(None, description="Character encoding of the file")

    # Detailed metadata (optional)
    permissions: Optional[FilePermissions] = Field(None, description="File permissions")
    hashes: Optional[FileHashes] = Field(None, description="File hash values")
    windows_attributes: Optional[WindowsAttributes] = Field(None, description="Windows-specific attributes")

    # Error handling
    error: Optional[str] = Field(None, description="Error message if metadata extraction failed")
    metadata_ingestion_failed: Optional[bool] = Field(None, description="Whether metadata extraction failed")

    def model_dump(self, **kwargs):
        """Override model_dump to exclude None values for optional fields."""
        data = super().model_dump(**kwargs)

        # Remove None values for truly optional fields
        optional_fields = ['permissions', 'hashes', 'windows_attributes', 'error', 'metadata_ingestion_failed', 'mime_type', 'encoding']
        return {k: v for k, v in data.items() if not (k in optional_fields and v is None)}


class ProcessorInfo(BaseModel):
    """Information about a processor in the pipeline."""
    name: str = Field(..., description="Name of the processor")
    version: str = Field(..., description="Version of the processor")
    description: str = Field(..., description="Description of what the processor does")
    supported_extensions: List[str] = Field(..., description="File extensions supported by this processor")


class ProcessingInfo(BaseModel):
    """Information about the processing/ingestion run."""
    ingestion_time: str = Field(..., description="Timestamp when ingestion was performed")
    ingestion_id: str = Field(..., description="Unique identifier for this ingestion run")
    source_dataset: str = Field(..., description="Name of the source dataset")
    dataset_folder_name: str = Field(..., description="Name of the dataset output folder")
    output_path: str = Field(..., description="Path where output files are stored")


class ProcessedFileInfo(BaseModel):
    """Information about a processed file."""
    original_file: str = Field(..., description="Path to the original file")
    relative_path: str = Field(..., description="Relative path within the dataset")
    file_name: str = Field(..., description="Name of the original file")
    metadata_file: Optional[str] = Field(None, description="Path to the generated metadata file")
    metadata_filename: Optional[str] = Field(None, description="Name of the metadata file")
    content_file: Optional[str] = Field(None, description="Path to the generated content file")
    content_filename: Optional[str] = Field(None, description="Name of the content file")
    error: Optional[str] = Field(None, description="Error message if processing failed")
    processing_failed: Optional[bool] = Field(None, description="Whether processing failed")


class DatasetInfo(BaseModel):
    """Information about a processed dataset."""
    ingestion_id: str = Field(..., description="Unique identifier for this ingestion run")
    dataset_name: str = Field(..., description="Name of the dataset")
    dataset_folder_name: str = Field(..., description="Name of the dataset output folder")
    source_path: str = Field(..., description="Path to the source dataset folder")
    output_path: str = Field(..., description="Path to the output folder")
    processing_time: str = Field(..., description="Timestamp when processing completed")
    total_files_processed: int = Field(..., description="Number of files successfully processed")
    total_files_failed: int = Field(..., description="Number of files that failed processing")


class DatasetSummary(BaseModel):
    """Complete summary of dataset processing."""
    dataset_info: DatasetInfo = Field(..., description="Dataset processing information")
    processed_files: List[ProcessedFileInfo] = Field(..., description="List of all processed files")


class IngestionSummary(BaseModel):
    """Overall summary of the ingestion process."""
    ingestion_id: str = Field(..., description="Unique identifier for this ingestion run")
    input_folder: str = Field(..., description="Path to the input folder")
    output_folder: str = Field(..., description="Path to the output folder")
    processing_time: str = Field(..., description="Timestamp when processing completed")
    datasets_requested: Optional[int] = Field(None, description="Number of datasets requested (if applicable)")
    specific_datasets_requested: Optional[List[str]] = Field(None, description="Specific datasets requested")
    specific_subfolders_requested: Optional[List[str]] = Field(None, description="Specific subfolders requested")
    datasets_processed: int = Field(..., description="Number of datasets actually processed")
    total_files_processed: int = Field(..., description="Total number of files successfully processed")
    total_files_failed: int = Field(..., description="Total number of files that failed processing")
    processed_datasets: List[str] = Field(..., description="Names of datasets that were processed")


class OverallSummary(BaseModel):
    """Top-level summary containing all ingestion information."""
    ingestion_summary: IngestionSummary = Field(..., description="Overall ingestion summary")
    dataset_summaries: List[DatasetSummary] = Field(..., description="Individual dataset summaries")


# Configuration Models

class MetadataProcessorConfig(BaseModel):
    """Configuration for the MetadataProcessor."""
    model_config = ConfigDict(extra="allow")  # Allow additional config options

    include_hashes: bool = Field(True, description="Whether to compute file hashes")
    hash_algorithms: List[Literal['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']] = Field(
        ['md5', 'sha1', 'sha256'],
        description="Hash algorithms to use"
    )
    include_permissions: bool = Field(True, description="Whether to include file permissions")
    include_windows_attributes: bool = Field(True, description="Whether to include Windows-specific attributes")

    @field_validator('hash_algorithms')
    @classmethod
    def validate_hash_algorithms(cls, v):
        """Ensure hash algorithms are valid."""
        if not v:  # Empty list is valid
            return v

        supported = {'md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512'}
        invalid = set(v) - supported
        if invalid:
            raise ValueError(f"Unsupported hash algorithms: {invalid}")
        return v


class ProcessorConfig(BaseModel):
    """Generic processor configuration."""
    model_config = ConfigDict(extra="allow")  # Allow processor-specific options

    name: str = Field(..., description="Name of the processor")
    config: Dict[str, Any] = Field(default_factory=dict, description="Processor-specific configuration")


class FileIngestorConfig(BaseModel):
    """Configuration for the FileIngestor."""
    model_config = ConfigDict(extra="allow")

    processors: List[ProcessorConfig] = Field(
        default_factory=lambda: [ProcessorConfig(name='MetadataProcessor', config={})],
        description="List of processors to use in the pipeline"
    )


# Complete file processing result
class FileProcessingResult(BaseModel):
    """Complete result of processing a single file through the pipeline."""
    processing_info: ProcessingInfo = Field(..., description="Processing metadata")
    file_metadata: FileMetadata = Field(..., description="Core file metadata")

    # Allow additional fields from other processors
    model_config = ConfigDict(extra="allow")