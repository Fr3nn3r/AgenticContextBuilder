"""Abstract base classes and factory for data acquisition implementations."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Type

logger = logging.getLogger(__name__)


class AcquisitionError(Exception):
    """Base exception for acquisition-related errors."""
    pass


class FileNotSupportedError(AcquisitionError):
    """Exception raised when file type is not supported."""
    pass


class APIError(AcquisitionError):
    """Exception raised when API call fails."""
    pass


class ConfigurationError(AcquisitionError):
    """Exception raised when configuration is missing or invalid."""
    pass


class DataAcquisition(ABC):
    """Abstract base class for data acquisition implementations."""

    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.tiff'}

    def __init__(self):
        """Initialize the acquisition handler."""
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def _process_implementation(self, filepath: Path) -> Dict[str, Any]:
        """
        Implementation-specific processing logic.

        Args:
            filepath: Path to file to process

        Returns:
            Dictionary containing extracted context

        Raises:
            AcquisitionError: If processing fails
        """
        pass

    def validate_file(self, filepath: Path) -> None:
        """
        Validate that file exists and has supported extension.

        Args:
            filepath: Path to validate

        Raises:
            FileNotSupportedError: If file type not supported
            FileNotFoundError: If file doesn't exist
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        if not filepath.is_file():
            raise FileNotSupportedError(f"Path is not a file: {filepath}")

        extension = filepath.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise FileNotSupportedError(
                f"File type '{extension}' not supported. "
                f"Supported types: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        self.logger.debug(f"File validation passed: {filepath}")

    def process(self, filepath: Path) -> Dict[str, Any]:
        """
        Process a file and extract context.

        Args:
            filepath: Path to file to process

        Returns:
            Dictionary containing extracted context

        Raises:
            AcquisitionError: If processing fails
        """
        # Convert to Path object if string
        if isinstance(filepath, str):
            filepath = Path(filepath)

        # Validate file
        self.validate_file(filepath)

        self.logger.info(f"Processing file: {filepath}")

        try:
            # Call implementation-specific processing
            result = self._process_implementation(filepath)

            # Note: Metadata is now included in the result by implementations
            # at the top level (file_name, file_path, file_size_bytes, etc.)

            self.logger.info(f"Successfully processed: {filepath}")
            return result

        except AcquisitionError:
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error processing {filepath}")
            raise AcquisitionError(f"Processing failed: {str(e)}") from e


class AcquisitionFactory:
    """Factory for creating data acquisition instances."""

    _registry: Dict[str, Type[DataAcquisition]] = {}

    @classmethod
    def register(cls, name: str, acquisition_class: Type[DataAcquisition]) -> None:
        """
        Register an acquisition implementation.

        Args:
            name: Name identifier for the implementation
            acquisition_class: Class implementing DataAcquisition
        """
        if not issubclass(acquisition_class, DataAcquisition):
            raise ValueError(f"{acquisition_class} must inherit from DataAcquisition")

        cls._registry[name.lower()] = acquisition_class
        logger.debug(f"Registered acquisition provider: {name}")

    @classmethod
    def create(cls, name: str) -> DataAcquisition:
        """
        Create an acquisition instance by name.

        Args:
            name: Name of the registered implementation

        Returns:
            Instance of the requested acquisition implementation

        Raises:
            ValueError: If implementation not found
        """
        name_lower = name.lower()

        if name_lower not in cls._registry:
            # Try to import the implementation
            if name_lower == "openai":
                try:
                    from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition
                    cls.register("openai", OpenAIVisionAcquisition)
                except ImportError as e:
                    raise ValueError(f"Failed to import OpenAI implementation: {e}")

        if name_lower not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unknown acquisition provider: {name}. "
                f"Available: {available if available else 'none registered'}"
            )

        acquisition_class = cls._registry[name_lower]
        logger.debug(f"Creating acquisition instance: {acquisition_class.__name__}")
        return acquisition_class()

    @classmethod
    def list_providers(cls) -> list:
        """Get list of registered provider names."""
        return list(cls._registry.keys())