# intake/services/prompt_provider.py
# Shared service for loading and managing file-based prompt templates

import logging
from pathlib import Path
from typing import Dict, Optional, Any, Union
import json
from .models import PromptVersionConfig, PromptError


class PromptProvider:
    """
    Provides prompts from file-based templates with versioning support.

    Prompts are stored as markdown files in nested directories:
    - prompts/content/{name}-{version}.md
    - prompts/enrichment/{name}-{role}-{version}.md
    """

    def __init__(self, prompts_dir: Path = None, config: Dict[str, Any] = None, processor_name: str = None):
        """
        Initialize the prompt provider.

        Args:
            prompts_dir: Root directory containing prompt files (defaults to ./prompts)
            config: Configuration containing prompt references and metadata
            processor_name: Name of processor (used for subdirectory, e.g., 'content', 'enrichment')
        """
        self.prompts_dir = prompts_dir or Path("prompts")
        self.processor_name = processor_name
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self._prompt_cache: Dict[str, str] = {}

    def get_prompt_from_config(self, prompt_config: Dict[str, Any], processor_type: str = None) -> str:
        """
        Load a prompt based on configuration with name and version.

        Args:
            prompt_config: Dict with 'name' and 'version' keys
            processor_type: Type of processor ('content', 'enrichment', etc.)

        Returns:
            The prompt template string

        Raises:
            PromptError: If prompt file not found or cannot be loaded
        """
        if not prompt_config:
            raise PromptError("No prompt configuration provided", error_type="config_missing")

        name = prompt_config.get("name")
        version = prompt_config.get("version")

        if not name or not version:
            raise PromptError(
                f"Prompt config must include both 'name' and 'version'. Got: {prompt_config}",
                error_type="config_invalid"
            )

        # Build the filename: {name}-{version}.md
        filename = f"{name}-{version}.md"

        # Determine the path based on processor type or self.processor_name
        if processor_type:
            prompt_file = self.prompts_dir / processor_type / filename
        elif self.processor_name:
            prompt_file = self.prompts_dir / self.processor_name / filename
        else:
            prompt_file = self.prompts_dir / filename

        # Load and return the prompt (will raise PromptError if not found)
        return self._load_prompt_file(prompt_file)

    def get_prompt(self, name: str, role: str = None, version: str = None) -> Optional[PromptVersionConfig]:
        """
        Retrieve a prompt configuration by name, role, and version.

        Args:
            name: Name of the prompt (e.g., "document-enrichment")
            role: Optional role qualifier (e.g., "analysis", "summary")
            version: Specific version to retrieve (defaults to active version from config)

        Returns:
            PromptVersionConfig object if found, None otherwise
        """
        # Build the prompt key from config
        prompt_key = f"{name}-{role}" if role else name
        prompt_config = self.config.get("prompts", {}).get(prompt_key, {})

        if not prompt_config:
            self.logger.warning(f"No configuration found for prompt: {prompt_key}")
            return None

        # Determine version to use
        target_version = version or prompt_config.get("active_version", "1.0.0")
        version_config = prompt_config.get("versions", {}).get(target_version, {})

        if not version_config:
            self.logger.warning(f"No version {target_version} found for prompt: {prompt_key}")
            return None

        # Build filename and path
        filename_parts = [name]
        if role:
            filename_parts.append(role)
        filename_parts.append(target_version)
        filename = f"{'-'.join(filename_parts)}.md"

        # Determine subdirectory based on processor name
        if self.processor_name:
            prompt_file = self.prompts_dir / self.processor_name / filename
        else:
            # Fallback to root prompts directory
            prompt_file = self.prompts_dir / filename
        template = self._load_prompt_file(prompt_file)

        if template is None:
            self.logger.error(f"Failed to load prompt file: {prompt_file}")
            return None

        # Create PromptVersionConfig with template from file and metadata from config
        return PromptVersionConfig(
            template=template,
            model=version_config.get("model", "gpt-4o"),
            max_tokens=version_config.get("max_tokens", 1500),
            temperature=version_config.get("temperature", 0.3),
            description=version_config.get("description", ""),
            output_format=version_config.get("output_format", "text"),
            parameters=version_config.get("parameters", {})
        )

    def _load_prompt_file(self, filepath: Path) -> str:
        """
        Load a prompt template from a file.

        Args:
            filepath: Path to the prompt file

        Returns:
            Prompt template string

        Raises:
            PromptError: If file not found or cannot be read
        """
        cache_key = str(filepath)

        # Check cache first
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        # Fail fast - no fallback defaults
        if not filepath.exists():
            raise PromptError(
                f"Required prompt file not found: {filepath}",
                error_type="prompt_file_missing"
            )

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Cache the loaded prompt
            self._prompt_cache[cache_key] = content
            return content

        except Exception as e:
            raise PromptError(
                f"Error loading prompt file {filepath}: {str(e)}",
                error_type="prompt_file_error",
                original_error=e
            )

    def get_prompt_template(self, name: str, role: str = None, version: str = None, **kwargs) -> str:
        """
        Get a formatted prompt template with variable substitution.

        Args:
            name: Name of the prompt
            role: Optional role qualifier
            version: Specific version to use
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted prompt string

        Raises:
            PromptError: If prompt not found or formatting fails
        """
        prompt_version = self.get_prompt(name, role, version)
        if not prompt_version:
            prompt_key = f"{name}-{role}" if role else name
            raise PromptError(
                f"Prompt '{prompt_key}' (version: {version or 'active'}) not found",
                error_type="prompt_not_found"
            )

        try:
            return prompt_version.template.format(**kwargs)
        except KeyError as e:
            raise PromptError(
                f"Missing template variable in prompt '{name}': {str(e)}",
                error_type="template_formatting_error",
                original_error=e
            )
        except Exception as e:
            raise PromptError(
                f"Failed to format prompt '{name}': {str(e)}",
                error_type="template_formatting_error",
                original_error=e
            )

    def get_active_version(self, name: str, role: str = None) -> Optional[str]:
        """
        Get the active version for a prompt.

        Args:
            name: Name of the prompt
            role: Optional role qualifier

        Returns:
            Active version string or None if not found
        """
        prompt_key = f"{name}-{role}" if role else name
        prompt_config = self.config.get("prompts", {}).get(prompt_key, {})
        return prompt_config.get("active_version") if prompt_config else None

    def list_prompts(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available prompts from configuration.

        Returns:
            Dictionary of prompt configurations
        """
        return self.config.get("prompts", {})

    def refresh_cache(self):
        """Clear the prompt cache to force reloading from files."""
        self._prompt_cache.clear()
        self.logger.info("Prompt cache cleared")

    def validate_prompts(self) -> Dict[str, bool]:
        """
        Validate that all configured prompts have corresponding files.

        Returns:
            Dictionary mapping prompt keys to validation status
        """
        results = {}
        prompts = self.config.get("prompts", {})

        for prompt_key, prompt_config in prompts.items():
            # Parse the prompt key
            parts = prompt_key.split("-")
            if len(parts) >= 2 and parts[-1] in ["analysis", "summary", "extraction"]:
                name = "-".join(parts[:-1])
                role = parts[-1]
            else:
                name = prompt_key
                role = None

            # Check each version
            versions = prompt_config.get("versions", {})
            all_valid = True

            for version in versions.keys():
                prompt = self.get_prompt(name, role, version)
                if prompt is None:
                    all_valid = False
                    self.logger.warning(f"Missing file for {prompt_key} version {version}")

            results[prompt_key] = all_valid

        return results

    @classmethod
    def from_config_file(cls, config_path: Path, prompts_dir: Path = None, processor_name: str = None) -> "PromptProvider":
        """
        Create a PromptProvider from a configuration file.

        Args:
            config_path: Path to configuration JSON file
            prompts_dir: Directory containing prompt files
            processor_name: Name of processor for subdirectory

        Returns:
            Configured PromptProvider instance
        """
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Extract processor name from config if not provided
        if not processor_name and "processor" in config:
            processor_name = config["processor"]["name"].lower().replace("processor", "")

        return cls(prompts_dir=prompts_dir, config=config, processor_name=processor_name)