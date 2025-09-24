"""Tests for AI analysis service."""

import os
import pytest
from unittest.mock import Mock, patch

from context_builder.processors.content_support.services import AIAnalysisService, OpenAIProvider
from context_builder.processors.content_support.interfaces.ai_provider import AIProviderError
from context_builder.processors.content_support.config import AIConfig


class TestAIAnalysisService:
    """Test suite for AIAnalysisService."""

    def test_initialization_with_provider(self, mock_ai_provider):
        """Test service initialization with mock provider."""
        service = AIAnalysisService(mock_ai_provider)

        assert service.provider == mock_ai_provider
        assert service.logger is not None

    def test_analyze_text_content(self, ai_service, mock_ai_provider):
        """Test analyzing text content."""
        result = ai_service.analyze_content(
            prompt="Analyze this text",
            model="gpt-4o",
            max_tokens=100
        )

        assert result is not None
        mock_ai_provider.analyze_text.assert_called_once_with(
            "Analyze this text", "gpt-4o", 100, None
        )

    def test_analyze_image_content(self, ai_service, mock_ai_provider):
        """Test analyzing image content."""
        result = ai_service.analyze_content(
            prompt="Describe this image",
            image_base64="base64_image_data",
            model="gpt-4o",
            max_tokens=200
        )

        assert result is not None
        mock_ai_provider.analyze_image.assert_called_once_with(
            "Describe this image", "base64_image_data", "gpt-4o", 200, None
        )

    def test_provider_not_available(self, mock_ai_provider):
        """Test error when provider is not available."""
        mock_ai_provider.is_available.return_value = False
        service = AIAnalysisService(mock_ai_provider)

        with pytest.raises(AIProviderError) as exc_info:
            service.analyze_content("Test prompt")

        assert exc_info.value.error_type == "provider_unavailable"

    def test_analysis_failure(self, ai_service, mock_ai_provider):
        """Test handling of analysis failure."""
        mock_ai_provider.analyze_text.side_effect = Exception("API error")

        with pytest.raises(AIProviderError) as exc_info:
            ai_service.analyze_content("Test prompt")

        assert exc_info.value.error_type == "analysis_failed"

    def test_with_all_parameters(self, ai_service, mock_ai_provider):
        """Test analysis with all parameters specified."""
        result = ai_service.analyze_content(
            prompt="Test prompt",
            model="gpt-3.5-turbo",
            max_tokens=500,
            temperature=0.5
        )

        mock_ai_provider.analyze_text.assert_called_with(
            "Test prompt", "gpt-3.5-turbo", 500, 0.5
        )


class TestOpenAIProvider:
    """Test suite for OpenAIProvider."""

    def test_initialization_without_api_key(self):
        """Test provider initialization without API key."""
        with patch.dict('os.environ', {}, clear=True):
            config = AIConfig(openai_api_key=None)
            provider = OpenAIProvider(config)

            assert provider._client is None
            assert not provider.is_available()

    @patch('openai.OpenAI')
    def test_initialization_with_api_key(self, mock_openai_class):
        """Test provider initialization with API key."""
        config = AIConfig(openai_api_key="test-key")
        provider = OpenAIProvider(config)

        mock_openai_class.assert_called_once_with(api_key="test-key")
        assert provider.is_available()

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'env-test-key'})
    @patch('openai.OpenAI')
    def test_initialization_with_env_key(self, mock_openai_class):
        """Test provider initialization with environment API key."""
        config = AIConfig()  # No key in config
        provider = OpenAIProvider(config)

        mock_openai_class.assert_called_once_with(api_key="env-test-key")

    @patch.dict('os.environ', {}, clear=True)  # Clear environment to ensure no API key
    def test_analyze_text_no_client(self):
        """Test text analysis when client is not initialized."""
        config = AIConfig(openai_api_key=None)
        provider = OpenAIProvider(config)

        # Verify client is not initialized
        assert provider._client is None

        with pytest.raises(AIProviderError) as exc_info:
            provider.analyze_text("Test prompt")

        assert exc_info.value.error_type == "client_not_initialized"

    @patch('openai.OpenAI')
    def test_analyze_text_success(self, mock_openai_class):
        """Test successful text analysis."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="AI response"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AIConfig(openai_api_key="test-key")
        provider = OpenAIProvider(config)

        result = provider.analyze_text("Test prompt")

        assert result == "AI response"
        mock_client.chat.completions.create.assert_called_once()

    def test_analyze_image_no_client(self):
        """Test image analysis when client is not initialized."""
        # Don't mock OpenAI here - we want the client to not be initialized
        with patch.dict('os.environ', {}, clear=True):
            config = AIConfig(
                openai_api_key=None  # No API key means no client
            )
            provider = OpenAIProvider(config)

            with pytest.raises(AIProviderError) as exc_info:
                provider.analyze_image("Test prompt", "base64_data")

            assert exc_info.value.error_type == "client_not_initialized"

    @patch('openai.OpenAI')
    def test_analyze_image_success(self, mock_openai_class):
        """Test successful image analysis."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Image description"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AIConfig(openai_api_key="test-key")
        provider = OpenAIProvider(config)

        result = provider.analyze_image("Describe image", "base64_data")

        assert result == "Image description"

        # Check the call was made with correct structure
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs['messages']
        assert len(messages) == 1
        assert messages[0]['role'] == 'user'
        assert len(messages[0]['content']) == 2  # Text and image

    @patch('openai.OpenAI')
    def test_api_error_handling(self, mock_openai_class):
        """Test API error handling."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client

        config = AIConfig(openai_api_key="test-key")
        provider = OpenAIProvider(config)

        with pytest.raises(AIProviderError) as exc_info:
            provider.analyze_text("Test prompt")

        assert exc_info.value.error_type == "api_request_failed"

    def test_get_provider_info(self):
        """Test getting provider information."""
        config = AIConfig(
            openai_api_key="test-key",
            default_model="gpt-4",
            max_retries=5
        )

        with patch('openai.OpenAI'):
            provider = OpenAIProvider(config)
            info = provider.get_provider_info()

            assert info['provider'] == 'OpenAI'
            assert info['default_model'] == 'gpt-4'
            assert info['max_retries'] == 5
            assert 'available' in info
            assert 'vision_enabled' in info


@pytest.mark.skipif(
    not os.environ.get('OPENAI_API_KEY'),
    reason="OpenAI API key not available"
)
class TestOpenAIProviderIntegration:
    """Integration tests for OpenAI provider with real API."""

    def test_real_text_analysis(self, real_ai_service):
        """Test text analysis with real OpenAI API."""
        result = real_ai_service.analyze_content(
            prompt="Say 'Hello, test successful' and nothing else",
            max_tokens=10
        )

        assert "test successful" in result.lower()

    def test_real_api_error(self, real_ai_service):
        """Test handling of real API errors."""
        with pytest.raises(AIProviderError):
            # Invalid model should cause error
            real_ai_service.analyze_content(
                prompt="Test",
                model="invalid-model-xyz"
            )


# TODO: Add retry mechanism tests
# - Test retry on transient failures
# - Test max retry limit
# - Test exponential backoff

# TODO: Add timeout handling tests
# - Test request timeout
# - Test long-running requests
# - Test timeout configuration