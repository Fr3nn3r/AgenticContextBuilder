# intake/processors/content_support/interfaces/ai_provider.py
# Abstract interface for AI service providers
# Enables swapping between different AI providers (OpenAI, Anthropic, etc.)

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class AIProviderInterface(ABC):
    """Abstract interface for AI service providers."""

    @abstractmethod
    def analyze_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Analyze text content using AI.

        Args:
            prompt: The prompt to send to the AI
            model: Model identifier to use
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation

        Returns:
            AI response as string

        Raises:
            AIProviderError: If the request fails
        """
        pass

    @abstractmethod
    def analyze_image(
        self,
        prompt: str,
        image_base64: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Analyze image content using Vision API.

        Args:
            prompt: The prompt to send to the AI
            image_base64: Base64-encoded image data
            model: Model identifier to use
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation

        Returns:
            AI response as string

        Raises:
            AIProviderError: If the request fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the AI provider is available and configured."""
        pass

    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the AI provider configuration."""
        pass


class AIProviderError(Exception):
    """Base exception for AI provider errors."""

    def __init__(self, message: str, error_type: str = "general", original_error: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.original_error = original_error