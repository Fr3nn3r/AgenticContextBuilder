# intake/processors/base.py
# Base processor interface for the file ingestion system
# Defines the contract that all processors must implement

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel


class BaseProcessor(ABC):
    """
    Abstract base class for file processors in the ingestion pipeline.

    All processors must implement the process_file method and can optionally
    implement configure and validate methods for setup and validation.
    """

    def __init__(self, config: Optional[Union[Dict[str, Any], BaseModel]] = None):
        """
        Initialize the processor with optional configuration.

        Args:
            config: Dictionary or Pydantic model containing processor-specific configuration
        """
        if isinstance(config, BaseModel):
            self.config = config.model_dump()
        else:
            self.config = config or {}
        self.name = self.__class__.__name__

    @abstractmethod
    def process_file(self, file_path: Path, existing_metadata: Optional[Union[Dict[str, Any], BaseModel]] = None) -> Union[Dict[str, Any], BaseModel]:
        """
        Process a single file and return metadata.

        Args:
            file_path: Path to the file to process
            existing_metadata: Any metadata from previous processors in the pipeline (dict or Pydantic model)

        Returns:
            Dictionary or Pydantic model containing the processed metadata

        Raises:
            ProcessingError: When file processing fails
        """
        pass

    def configure(self, config: Union[Dict[str, Any], BaseModel]) -> None:
        """
        Configure the processor with new settings.

        Args:
            config: Configuration dictionary or Pydantic model
        """
        if isinstance(config, BaseModel):
            self.config.update(config.model_dump())
        else:
            self.config.update(config)

    def validate_config(self) -> bool:
        """
        Validate the processor configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        return True

    def get_processor_info(self) -> Dict[str, Any]:
        """
        Get information about this processor.

        Returns:
            Dictionary with processor name, version, and capabilities
        """
        return {
            'name': self.name,
            'version': getattr(self, 'VERSION', '1.0.0'),
            'description': getattr(self, 'DESCRIPTION', 'No description available'),
            'supported_extensions': getattr(self, 'SUPPORTED_EXTENSIONS', []),
        }


class ProcessingError(Exception):
    """Exception raised when file processing fails."""

    def __init__(self, message: str, file_path: Optional[Path] = None, processor_name: Optional[str] = None):
        self.message = message
        self.file_path = file_path
        self.processor_name = processor_name
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format the error message with context."""
        parts = [self.message]
        if self.processor_name:
            parts.append(f"Processor: {self.processor_name}")
        if self.file_path:
            parts.append(f"File: {self.file_path}")
        return " | ".join(parts)