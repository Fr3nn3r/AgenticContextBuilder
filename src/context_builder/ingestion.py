"""Abstract base classes and factory for data ingestion implementations."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Type

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Base exception for ingestion-related errors."""
    pass


class FileNotSupportedError(IngestionError):
    """Exception raised when file type is not supported."""
    pass


class APIError(IngestionError):
    """Exception raised when API call fails."""
    pass


class ConfigurationError(IngestionError):
    """Exception raised when configuration is missing or invalid."""
    pass


class DataIngestion(ABC):
    """Abstract base class for data ingestion implementations."""

    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.tiff', '.tif'}

    def __init__(self):
        """Initialize the ingestion handler."""
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
            IngestionError: If processing fails
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
            IngestionError: If processing fails
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

        except IngestionError:
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error processing {filepath}")
            raise IngestionError(f"Processing failed: {str(e)}") from e


class IngestionFactory:
    """Factory for creating data ingestion instances."""

    _registry: Dict[str, Type[DataIngestion]] = {}

    @classmethod
    def register(cls, name: str, ingestion_class: Type[DataIngestion]) -> None:
        """
        Register an ingestion implementation.

        Args:
            name: Name identifier for the implementation
            ingestion_class: Class implementing DataIngestion
        """
        if not issubclass(ingestion_class, DataIngestion):
            raise ValueError(f"{ingestion_class} must inherit from DataIngestion")

        cls._registry[name.lower()] = ingestion_class
        logger.debug(f"Registered ingestion provider: {name}")

    @classmethod
    def create(cls, name: str) -> DataIngestion:
        """
        Create an ingestion instance by name.

        Args:
            name: Name of the registered implementation

        Returns:
            Instance of the requested ingestion implementation

        Raises:
            ValueError: If implementation not found
        """
        name_lower = name.lower()

        if name_lower not in cls._registry:
            # Try to import the implementation
            if name_lower == "openai":
                try:
                    from context_builder.impl.openai_vision_ingestion import OpenAIVisionIngestion
                    cls.register("openai", OpenAIVisionIngestion)
                except ImportError as e:
                    raise ValueError(f"Failed to import OpenAI implementation: {e}")
            elif name_lower == "tesseract":
                try:
                    from context_builder.impl.tesseract_ingestion import TesseractIngestion
                    cls.register("tesseract", TesseractIngestion)
                except ImportError as e:
                    raise ValueError(f"Failed to import Tesseract implementation: {e}")
            elif name_lower == "azure-di":
                try:
                    from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                    cls.register("azure-di", AzureDocumentIntelligenceIngestion)
                except ImportError as e:
                    raise ValueError(f"Failed to import Azure DI implementation: {e}")

        if name_lower not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unknown ingestion provider: {name}. "
                f"Available: {available if available else 'none registered'}"
            )

        ingestion_class = cls._registry[name_lower]
        logger.debug(f"Creating ingestion instance: {ingestion_class.__name__}")
        return ingestion_class()

    @classmethod
    def list_providers(cls) -> list:
        """Get list of registered provider names."""
        return list(cls._registry.keys())