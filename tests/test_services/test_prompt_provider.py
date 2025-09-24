#!/usr/bin/env python3
"""
Tests for the PromptProvider service.
Tests prompt loading, versioning, and error handling.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import json

from intake.services import PromptProvider
from intake.services.models import PromptError


class TestPromptProvider:
    """Test suite for the PromptProvider class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.test_prompts_dir = Path("test_prompts")

    def test_prompt_file_missing_error(self, tmp_path):
        """Test that missing prompt file raises PromptError with correct error_type."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Create config that references a prompt that will exist in config but not on disk
        config = {
            "prompts": {
                "missing-prompt": {
                    "active_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "model": "gpt-4o",
                            "max_tokens": 1500
                        }
                    }
                }
            }
        }

        provider = PromptProvider(prompts_dir=prompts_dir, config=config)

        # The get_prompt method will try to load the file and raise prompt_file_missing
        with pytest.raises(PromptError) as exc_info:
            provider.get_prompt_template("missing-prompt")

        assert exc_info.value.error_type == "prompt_file_missing"
        assert "Required prompt file not found" in str(exc_info.value)

    def test_prompt_not_found_error(self, tmp_path):
        """Test that non-existent prompt name raises PromptError with correct error_type."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        provider = PromptProvider(prompts_dir=prompts_dir, config={})

        # Should raise PromptError with error_type="prompt_not_found"
        with pytest.raises(PromptError) as exc_info:
            provider.get_prompt_template("non-existent-prompt")

        assert exc_info.value.error_type == "prompt_not_found"
        assert "not found" in str(exc_info.value)

    def test_template_formatting_error(self, tmp_path):
        """Test that missing template variables raise PromptError with correct error_type."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Create a prompt file with template variables
        prompt_file = prompts_dir / "test-prompt-1.0.0.md"
        prompt_file.write_text("Hello {user_name}, your age is {age}")

        config = {
            "prompts": {
                "test-prompt": {
                    "active_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "model": "gpt-4o"
                        }
                    }
                }
            }
        }

        provider = PromptProvider(prompts_dir=prompts_dir, config=config)

        # Should raise PromptError with error_type="template_formatting_error"
        with pytest.raises(PromptError) as exc_info:
            provider.get_prompt_template("test-prompt", user_name="John")  # Missing 'age'

        assert exc_info.value.error_type == "template_formatting_error"
        assert "Missing template variable" in str(exc_info.value)

    def test_prompt_file_load_error(self, tmp_path):
        """Test that file loading errors raise PromptError with correct error_type."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Create prompt file path
        prompt_file = prompts_dir / "test-prompt-1.0.0.md"
        prompt_file.write_text("test")

        config = {
            "prompts": {
                "test-prompt": {
                    "active_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "model": "gpt-4o"
                        }
                    }
                }
            }
        }

        provider = PromptProvider(prompts_dir=prompts_dir, config=config)

        # Mock file open to raise an exception
        with patch("builtins.open", side_effect=Exception("Permission denied")):
            with pytest.raises(PromptError) as exc_info:
                provider.get_prompt_template("test-prompt")

        assert exc_info.value.error_type == "prompt_file_error"
        assert "Error loading prompt file" in str(exc_info.value)

    def test_successful_prompt_retrieval(self, tmp_path):
        """Test successful prompt retrieval with template formatting."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Create a prompt file (avoid using 'name' as template variable to prevent conflict)
        prompt_file = prompts_dir / "greeting-1.0.0.md"
        prompt_file.write_text("Hello {user}, welcome to {place}!")

        config = {
            "prompts": {
                "greeting": {
                    "active_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "model": "gpt-4o",
                            "description": "Greeting prompt"
                        }
                    }
                }
            }
        }

        provider = PromptProvider(prompts_dir=prompts_dir, config=config)

        # Should successfully format and return the prompt
        result = provider.get_prompt_template("greeting", user="Alice", place="Wonderland")
        assert result == "Hello Alice, welcome to Wonderland!"

    def test_role_based_prompt(self, tmp_path):
        """Test role-based prompt file naming."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Create a role-based prompt file
        prompt_file = prompts_dir / "analysis-summary-1.0.0.md"
        prompt_file.write_text("Summarize: {content}")

        config = {
            "prompts": {
                "analysis-summary": {
                    "active_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "model": "gpt-4o"
                        }
                    }
                }
            }
        }

        provider = PromptProvider(prompts_dir=prompts_dir, config=config)

        # Should successfully retrieve role-based prompt
        result = provider.get_prompt_template("analysis", role="summary", content="Test data")
        assert result == "Summarize: Test data"

    def test_prompt_version_selection(self, tmp_path):
        """Test explicit version selection."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Create versioned prompt files
        prompt_v1 = prompts_dir / "test-1.0.0.md"
        prompt_v1.write_text("Version 1: {text}")

        prompt_v2 = prompts_dir / "test-2.0.0.md"
        prompt_v2.write_text("Version 2: {text}")

        config = {
            "prompts": {
                "test": {
                    "active_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "model": "gpt-4o"
                        },
                        "2.0.0": {
                            "model": "gpt-4o"
                        }
                    }
                }
            }
        }

        provider = PromptProvider(prompts_dir=prompts_dir, config=config)

        # Test default (active) version
        result_v1 = provider.get_prompt_template("test", text="hello")
        assert result_v1 == "Version 1: hello"

        # Test explicit version selection
        result_v2 = provider.get_prompt_template("test", version="2.0.0", text="hello")
        assert result_v2 == "Version 2: hello"