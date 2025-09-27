"""Shared fixtures for content processor tests."""

import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from context_builder.processors.content_support.interfaces import AIProviderInterface
from context_builder.processors.content_support.services import AIAnalysisService, ResponseParser
from context_builder.services import PromptProvider
from context_builder.processors.content_support.config import ContentProcessorConfig


# Path to fixtures directory
FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures" / "content"


@pytest.fixture
def fixtures_path():
    """Return path to fixtures directory."""
    return FIXTURES_PATH


@pytest.fixture
def sample_files_path():
    """Return path to sample files directory."""
    return FIXTURES_PATH / "sample_files"


@pytest.fixture
def mock_responses_path():
    """Return path to mock responses directory."""
    return FIXTURES_PATH / "mock_responses"


@pytest.fixture
def mock_ai_provider():
    """Create a mock AI provider for testing without API calls."""
    provider = Mock(spec=AIProviderInterface)
    provider.is_available.return_value = True

    # Load mock responses
    responses_path = FIXTURES_PATH / "mock_responses"

    # Default text analysis response
    with open(responses_path / "text_analysis_success.json") as f:
        text_response = json.load(f)
    provider.analyze_text.return_value = text_response["raw_response"]

    # Default vision API response
    with open(responses_path / "vision_api_success.json") as f:
        vision_response = json.load(f)
    provider.analyze_image.return_value = vision_response["raw_response"]

    provider.get_provider_info.return_value = {
        "provider": "Mock",
        "available": True,
        "default_model": "gpt-4o",
        "vision_enabled": True
    }

    return provider


@pytest.fixture
def ai_service(mock_ai_provider):
    """Create AI analysis service with mock provider."""
    return AIAnalysisService(mock_ai_provider)


@pytest.fixture
def response_parser():
    """Create response parser instance."""
    return ResponseParser()


@pytest.fixture
def test_config():
    """Create test configuration."""
    config = ContentProcessorConfig()
    # Adjust for testing
    config.processing.max_file_size_mb = 10
    config.processing.text_truncation_chars = 1000
    config.processing.json_truncation_chars = 500
    return config


@pytest.fixture
def prompt_provider(tmp_path):
    """Create prompt provider with test prompts."""
    # Create temporary prompt files for testing
    prompts_dir = tmp_path / "prompts" / "content"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    # Create test prompts that match what handlers expect
    text_prompt = prompts_dir / "text-analysis-2.0.0.md"
    text_prompt.write_text("Test prompt: {content}")

    spreadsheet_prompt = prompts_dir / "spreadsheet-analysis-2.0.0.md"
    spreadsheet_prompt.write_text("Test spreadsheet prompt: {content}")

    # Mock the get_prompt_from_config method to return the prompt template
    provider = PromptProvider(
        prompts_dir=tmp_path / "prompts",
        config={},  # Empty config since we're using direct prompt loading
        processor_name="content"
    )

    # Add the method that our handlers use
    original_get = provider.get_prompt_from_config
    def mock_get_prompt_from_config(prompt_config, processor_type=None):
        # For tests, just return a simple template
        if prompt_config.get('name') == 'text-analysis':
            return "Test prompt: {content}"
        elif prompt_config.get('name') == 'spreadsheet-analysis':
            return "Test spreadsheet prompt: {content}"
        else:
            return original_get(prompt_config, processor_type)

    provider.get_prompt_from_config = mock_get_prompt_from_config

    return provider


@pytest.fixture
def prompt_manager(prompt_provider):
    """Backwards compatibility fixture - maps to prompt_provider."""
    return prompt_provider


@pytest.fixture
def sample_text_file(tmp_path):
    """Create a temporary text file for testing."""
    test_file = tmp_path / "test.txt"
    test_file.write_text(
        "This is a test file.\n"
        "It contains sample text for testing.\n"
        "Date: 2024-01-15\n"
        "Author: Test System"
    )
    return test_file


@pytest.fixture
def sample_csv_file(tmp_path):
    """Create a temporary CSV file for testing."""
    test_file = tmp_path / "test.csv"
    test_file.write_text(
        "Name,Value,Category\n"
        "Item1,100,A\n"
        "Item2,200,B\n"
        "Item3,150,A\n"
    )
    return test_file


@pytest.fixture
def empty_file(tmp_path):
    """Create an empty file for testing."""
    test_file = tmp_path / "empty.txt"
    test_file.touch()
    return test_file


@pytest.fixture
def large_text_file(tmp_path):
    """Create a large text file for truncation testing."""
    test_file = tmp_path / "large.txt"
    # Create text larger than truncation limit
    content = "This is a test sentence. " * 500  # ~12500 chars
    test_file.write_text(content)
    return test_file


# Real AI service fixture for integration tests (optional)
@pytest.fixture
def real_ai_service():
    """
    Create real AI service if API key is available.
    Skip test if no API key is configured.
    """
    from context_builder.processors.content_support.services import OpenAIProvider
    from context_builder.processors.content_support.config import AIConfig

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        pytest.skip("OpenAI API key not available")

    config = AIConfig(openai_api_key=api_key)
    provider = OpenAIProvider(config)

    if not provider.is_available():
        pytest.skip("OpenAI provider not available")

    return AIAnalysisService(provider)