"""Abstract base classes and factory for document classification implementations."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Type

logger = logging.getLogger(__name__)


class ClassificationError(Exception):
    """Base exception for classification-related errors."""
    pass


class APIError(ClassificationError):
    """Exception raised when API call fails."""
    pass


class ConfigurationError(ClassificationError):
    """Exception raised when configuration is missing or invalid."""
    pass


class DocumentClassifier(ABC):
    """Abstract base class for document classification implementations."""

    def __init__(self):
        """Initialize the classifier."""
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def _classify_implementation(
        self, text_content: str, filename: str = ""
    ) -> Dict[str, Any]:
        """
        Implementation-specific classification logic.

        Args:
            text_content: Extracted text from document
            filename: Original filename (hint for classification)

        Returns:
            Dict with document_type, language, summary, key_information

        Raises:
            ClassificationError: If classification fails
        """
        pass

    def classify(self, text_content: str, filename: str = "") -> Dict[str, Any]:
        """
        Classify document and extract key information.

        Args:
            text_content: Extracted text from document
            filename: Original filename (hint for classification)

        Returns:
            Dict with document_type, language, summary, key_information

        Raises:
            ClassificationError: If classification fails
        """
        if not text_content or not text_content.strip():
            raise ClassificationError("Empty text content provided")

        self.logger.info(f"Classifying document: {filename or '(unnamed)'}")

        try:
            result = self._classify_implementation(text_content, filename)
            self.logger.info(
                f"Classification complete: {result.get('document_type', 'unknown')}"
            )
            return result

        except ClassificationError:
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error classifying {filename}")
            raise ClassificationError(f"Classification failed: {str(e)}") from e


class ClassifierFactory:
    """Factory for creating document classifier instances."""

    _registry: Dict[str, Type[DocumentClassifier]] = {}

    @classmethod
    def register(cls, name: str, classifier_class: Type[DocumentClassifier]) -> None:
        """
        Register a classifier implementation.

        Args:
            name: Name identifier for the implementation
            classifier_class: Class implementing DocumentClassifier
        """
        if not issubclass(classifier_class, DocumentClassifier):
            raise ValueError(f"{classifier_class} must inherit from DocumentClassifier")

        cls._registry[name.lower()] = classifier_class
        logger.debug(f"Registered classifier: {name}")

    @classmethod
    def create(cls, name: str, **kwargs) -> DocumentClassifier:
        """
        Create a classifier instance by name.

        Args:
            name: Name of the registered implementation
            **kwargs: Additional arguments passed to classifier constructor

        Returns:
            Instance of the requested classifier implementation

        Raises:
            ValueError: If implementation not found
        """
        name_lower = name.lower()

        if name_lower not in cls._registry:
            # Try to import the implementation
            if name_lower == "openai":
                try:
                    from context_builder.classification.openai_classifier import (
                        OpenAIDocumentClassifier,
                    )
                    cls.register("openai", OpenAIDocumentClassifier)
                except ImportError as e:
                    raise ValueError(f"Failed to import OpenAI classifier: {e}")

        if name_lower not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unknown classifier: {name}. "
                f"Available: {available if available else 'none registered'}"
            )

        classifier_class = cls._registry[name_lower]
        logger.debug(f"Creating classifier instance: {classifier_class.__name__}")
        return classifier_class(**kwargs)

    @classmethod
    def list_classifiers(cls) -> list:
        """Get list of registered classifier names."""
        return list(cls._registry.keys())
