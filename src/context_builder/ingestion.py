"""Abstract base classes and factory for data ingestion implementations."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Type, List, Optional

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


@dataclass(frozen=True)
class IngestionIssue:
    """Structured warning/error for ingestion results."""

    code: str
    message: str


@dataclass
class IngestionResult:
    """Standard ingestion result envelope."""

    data: Dict[str, Any]
    warnings: List[IngestionIssue] = field(default_factory=list)
    errors: List[IngestionIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "warnings": [issue.__dict__ for issue in self.warnings],
            "errors": [issue.__dict__ for issue in self.errors],
        }


def wrap_ingestion_result(
    data: Dict[str, Any],
    warnings: Optional[List[IngestionIssue]] = None,
    errors: Optional[List[IngestionIssue]] = None,
) -> Dict[str, Any]:
    """Create a standard ingestion result envelope."""
    result = IngestionResult(
        data=data,
        warnings=warnings or [],
        errors=errors or [],
    )
    return result.to_dict()


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

    def process(self, filepath: Path, envelope: bool = False) -> Dict[str, Any]:
        """
        Process a file and extract context.

        Args:
            filepath: Path to file to process

        Returns:
            Dictionary containing extracted context, optionally wrapped
            in a standard ingestion result envelope.

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
            if envelope:
                return wrap_ingestion_result(result)
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
                    print(f"[IngestionFactory] Attempting to import azure_di_ingestion...", flush=True)
                    from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                    print(f"[IngestionFactory] Successfully imported AzureDocumentIntelligenceIngestion", flush=True)
                    cls.register("azure-di", AzureDocumentIntelligenceIngestion)
                except ImportError as e:
                    print(f"[IngestionFactory] ImportError: {e}", flush=True)
                    raise ValueError(f"Failed to import Azure DI implementation: {e}")
                except Exception as e:
                    print(f"[IngestionFactory] Exception during import: {type(e).__name__}: {e}", flush=True)
                    raise

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
