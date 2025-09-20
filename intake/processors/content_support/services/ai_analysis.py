# intake/processors/content_support/services/ai_analysis.py
# AI analysis service for content processing
# Implements AIProviderInterface for OpenAI and manages AI interactions

import os
import logging
from typing import Optional, Dict, Any

from ..interfaces.ai_provider import AIProviderInterface, AIProviderError
from ..config import AIConfig


class AIAnalysisService:
    """Manages AI analysis operations with different providers."""

    def __init__(self, provider: AIProviderInterface):
        """
        Initialize the AI analysis service.

        Args:
            provider: AI provider implementation
        """
        self.provider = provider
        self.logger = logging.getLogger(__name__)

    def analyze_content(
        self,
        prompt: str,
        image_base64: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Analyze content using the configured AI provider.

        Args:
            prompt: Text prompt for analysis
            image_base64: Optional base64-encoded image
            model: Model to use (provider-specific)
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation

        Returns:
            AI response as string

        Raises:
            AIProviderError: If analysis fails
        """
        if not self.provider.is_available():
            raise AIProviderError(
                "AI provider is not available",
                error_type="provider_unavailable"
            )

        try:
            if image_base64:
                return self.provider.analyze_image(
                    prompt, image_base64, model, max_tokens, temperature
                )
            else:
                return self.provider.analyze_text(
                    prompt, model, max_tokens, temperature
                )
        except Exception as e:
            self.logger.error(f"AI analysis failed: {str(e)}")
            raise AIProviderError(
                f"AI analysis failed: {str(e)}",
                error_type="analysis_failed",
                original_error=e
            )


class OpenAIProvider(AIProviderInterface):
    """OpenAI implementation of the AI provider interface."""

    def __init__(self, config: AIConfig):
        """
        Initialize OpenAI provider with configuration.

        Args:
            config: AI configuration settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize OpenAI client with lazy loading."""
        api_key = (
            self.config.openai_api_key or
            os.getenv('OPENAI_API_KEY') or
            os.getenv('OPENAI_KEY')
        )

        if not api_key:
            self.logger.warning("OpenAI API key not found")
            return

        try:
            # Lazy import of OpenAI client
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key)
            self.logger.info("OpenAI client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            self._client = None

    def analyze_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Analyze text using OpenAI API."""
        if not self._client:
            raise AIProviderError(
                "OpenAI client not initialized",
                error_type="client_not_initialized"
            )

        try:
            response = self._client.chat.completions.create(
                model=model or self.config.default_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            raise AIProviderError(
                f"OpenAI text analysis failed: {str(e)}",
                error_type="api_request_failed",
                original_error=e
            )

    def analyze_image(
        self,
        prompt: str,
        image_base64: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Analyze image using OpenAI Vision API."""
        if not self._client:
            raise AIProviderError(
                "OpenAI client not initialized",
                error_type="client_not_initialized"
            )

        if not self.config.enable_vision_api:
            raise AIProviderError(
                "Vision API is not enabled",
                error_type="vision_api_disabled"
            )

        try:
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                }
            ]

            response = self._client.chat.completions.create(
                model=model or self.config.default_model,
                messages=[{"role": "user", "content": content}],
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            raise AIProviderError(
                f"OpenAI Vision API failed: {str(e)}",
                error_type="vision_api_failed",
                original_error=e
            )

    def is_available(self) -> bool:
        """Check if OpenAI client is available."""
        return self._client is not None

    def get_provider_info(self) -> Dict[str, Any]:
        """Get OpenAI provider information."""
        return {
            "provider": "OpenAI",
            "available": self.is_available(),
            "default_model": self.config.default_model,
            "vision_enabled": self.config.enable_vision_api,
            "max_retries": self.config.max_retries,
            "timeout_seconds": self.config.timeout_seconds
        }