"""AI Provider Adapter - Abstraction layer for AI provider interactions.

This module provides a thin adapter layer around AI provider clients (like OpenAI)
to isolate API surface changes and make it easier to swap providers or update
SDK versions without changing the rest of the codebase.
"""

import logging
from typing import Optional, Dict, Any, Protocol
from abc import ABC, abstractmethod


class AIClientAdapter(ABC):
    """Abstract base class for AI client adapters.

    Provides a stable interface for AI operations regardless of the underlying
    provider or SDK version changes.
    """

    @abstractmethod
    def analyze_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Analyze text using the AI provider.

        Args:
            prompt: Text prompt for analysis
            model: Model to use (provider-specific)
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation

        Returns:
            AI response as string

        Raises:
            Exception: If analysis fails
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
        """Analyze image using the AI provider.

        Args:
            prompt: Text prompt for analysis
            image_base64: Base64-encoded image
            model: Model to use (provider-specific)
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation

        Returns:
            AI response as string

        Raises:
            Exception: If analysis fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the AI provider is available.

        Returns:
            True if provider is configured and ready
        """
        pass


class OpenAIAdapter(AIClientAdapter):
    """Adapter for OpenAI client library.

    Isolates OpenAI SDK specifics from the rest of the application.
    """

    def __init__(self, api_key: str, timeout: int = 30, default_model: str = "gpt-4o"):
        """Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key
            timeout: Request timeout in seconds
            default_model: Default model to use
        """
        self.api_key = api_key
        self.timeout = timeout
        self.default_model = default_model
        self.logger = logging.getLogger(__name__)
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the OpenAI client."""
        if not self.api_key:
            self.logger.warning("OpenAI API key not provided")
            return

        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                timeout=self.timeout
            )
            self.logger.info("OpenAI client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            self._client = None

    def is_available(self) -> bool:
        """Check if OpenAI client is available."""
        return self._client is not None

    def analyze_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Analyze text using OpenAI.

        Args:
            prompt: Text prompt for analysis
            model: Model to use (defaults to configured model)
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation

        Returns:
            AI response as string

        Raises:
            Exception: If analysis fails
        """
        if not self._client:
            raise RuntimeError("OpenAI client not initialized")

        response = self._client.chat.completions.create(
            model=model or self.default_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens or 2048,
            temperature=temperature or 0.1
        )

        return response.choices[0].message.content

    def analyze_image(
        self,
        prompt: str,
        image_base64: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Analyze image using OpenAI Vision.

        Args:
            prompt: Text prompt for analysis
            image_base64: Base64-encoded image
            model: Model to use (defaults to configured model)
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation

        Returns:
            AI response as string

        Raises:
            Exception: If analysis fails
        """
        if not self._client:
            raise RuntimeError("OpenAI client not initialized")

        response = self._client.chat.completions.create(
            model=model or self.default_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=max_tokens or 2048,
            temperature=temperature or 0.1
        )

        return response.choices[0].message.content


def create_ai_adapter(provider: str, config: Dict[str, Any]) -> AIClientAdapter:
    """Factory function to create appropriate AI adapter.

    Args:
        provider: Name of the AI provider ("openai", etc.)
        config: Configuration dictionary for the provider

    Returns:
        Configured AI adapter instance

    Raises:
        ValueError: If provider is not supported
    """
    if provider.lower() == "openai":
        return OpenAIAdapter(
            api_key=config.get("api_key"),
            timeout=config.get("timeout", 30),
            default_model=config.get("default_model", "gpt-4o")
        )
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")