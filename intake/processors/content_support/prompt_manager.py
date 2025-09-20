# intake/processors/content_support/prompt_manager.py
# Prompt management system with versioning capabilities
# Handles prompt templates, versioning, and configuration management

import logging
from typing import Dict, Optional, Any
from .models import PromptConfig, PromptVersionConfig, ContentProcessorError


class PromptManager:
    """
    Manages versioned prompts for content processing.

    Provides methods to store, retrieve, and version prompts following
    semantic versioning principles for reproducible AI processing.
    """

    def __init__(self, config: Dict[str, PromptConfig] = None):
        """
        Initialize the prompt manager with optional configuration.

        Args:
            config: Dictionary of prompt configurations
        """
        self.prompts: Dict[str, PromptConfig] = config or {}
        self.logger = logging.getLogger(__name__)

    def add_prompt(self, name: str, prompt_config: PromptConfig) -> None:
        """
        Add or update a prompt configuration.

        Args:
            name: Unique name for the prompt
            prompt_config: Prompt configuration object

        Raises:
            ContentProcessorError: If prompt configuration is invalid
        """
        try:
            # Validate prompt configuration
            if prompt_config.active_version not in prompt_config.versions:
                raise ValueError(f"Active version '{prompt_config.active_version}' not found in versions")

            # Validate each version has a template
            for version, config in prompt_config.versions.items():
                if not config.template.strip():
                    raise ValueError(f"Prompt template for version {version} cannot be empty")

            self.prompts[name] = prompt_config
            self.logger.info(f"Added prompt '{name}' with active version {prompt_config.active_version}")

        except Exception as e:
            raise ContentProcessorError(
                f"Failed to add prompt '{name}': {str(e)}",
                error_type="prompt_configuration_error",
                original_error=e
            )

    def get_prompt(self, name: str, version: Optional[str] = None) -> Optional[PromptVersionConfig]:
        """
        Retrieve a prompt configuration by name and optionally version.

        Args:
            name: Name of the prompt to retrieve
            version: Specific version to retrieve (if None, uses active version)

        Returns:
            PromptVersionConfig object if found, None otherwise
        """
        prompt_config = self.prompts.get(name)
        if not prompt_config:
            return None

        # Use specified version or active version
        target_version = version or prompt_config.active_version
        return prompt_config.versions.get(target_version)

    def get_active_prompt(self, name: str) -> Optional[PromptVersionConfig]:
        """
        Get the active version of a prompt.

        Args:
            name: Name of the prompt

        Returns:
            Active PromptVersionConfig or None if not found
        """
        return self.get_prompt(name)

    def get_active_version(self, name: str) -> Optional[str]:
        """
        Get the active version string for a prompt.

        Args:
            name: Name of the prompt

        Returns:
            Active version string or None if not found
        """
        prompt_config = self.prompts.get(name)
        return prompt_config.active_version if prompt_config else None

    def get_prompt_template(self, name: str, version: Optional[str] = None, **kwargs) -> str:
        """
        Get a formatted prompt template with variable substitution.

        Args:
            name: Name of the prompt
            version: Specific version to use (if None, uses active version)
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted prompt string

        Raises:
            ContentProcessorError: If prompt not found or formatting fails
        """
        prompt_version = self.get_prompt(name, version)
        if not prompt_version:
            raise ContentProcessorError(
                f"Prompt '{name}' (version: {version or 'active'}) not found",
                error_type="prompt_not_found"
            )

        try:
            # Simple string formatting - can be enhanced with more sophisticated templating
            return prompt_version.template.format(**kwargs)
        except KeyError as e:
            raise ContentProcessorError(
                f"Missing template variable in prompt '{name}': {str(e)}",
                error_type="template_formatting_error",
                original_error=e
            )
        except Exception as e:
            raise ContentProcessorError(
                f"Failed to format prompt '{name}': {str(e)}",
                error_type="template_formatting_error",
                original_error=e
            )

    def list_prompts(self) -> Dict[str, str]:
        """
        List all available prompts with their active versions.

        Returns:
            Dictionary mapping prompt names to active versions
        """
        return {name: config.active_version for name, config in self.prompts.items()}

    def get_prompt_info(self, name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific prompt.

        Args:
            name: Name of the prompt
            version: Specific version (if None, uses active version)

        Returns:
            Dictionary with prompt information or None if not found
        """
        prompt_config = self.prompts.get(name)
        if not prompt_config:
            return None

        target_version = version or prompt_config.active_version
        prompt_version = prompt_config.versions.get(target_version)
        if not prompt_version:
            return None

        return {
            'name': name,
            'version': target_version,
            'active_version': prompt_config.active_version,
            'available_versions': list(prompt_config.versions.keys()),
            'model': prompt_version.model,
            'max_tokens': prompt_version.max_tokens,
            'temperature': prompt_version.temperature,
            'description': prompt_version.description,
            'output_format': prompt_version.output_format,
            'template_length': len(prompt_version.template),
            'has_parameters': bool(prompt_version.parameters)
        }

    def add_prompt_version(self, name: str, new_version: str, version_config: PromptVersionConfig) -> None:
        """
        Add a new version to an existing prompt.

        Args:
            name: Name of the prompt to update
            new_version: New version string (must follow semantic versioning)
            version_config: Configuration for the new version

        Raises:
            ContentProcessorError: If prompt not found or version invalid
        """
        prompt_config = self.prompts.get(name)
        if not prompt_config:
            raise ContentProcessorError(
                f"Cannot add version: prompt '{name}' not found",
                error_type="prompt_not_found"
            )

        try:
            # Add new version
            prompt_config.versions[new_version] = version_config
            self.logger.info(f"Added version {new_version} to prompt '{name}'")

        except Exception as e:
            raise ContentProcessorError(
                f"Failed to add version to prompt '{name}': {str(e)}",
                error_type="prompt_update_error",
                original_error=e
            )

    def set_active_version(self, name: str, version: str) -> None:
        """
        Set the active version for a prompt.

        Args:
            name: Name of the prompt
            version: Version to set as active

        Raises:
            ContentProcessorError: If prompt or version not found
        """
        prompt_config = self.prompts.get(name)
        if not prompt_config:
            raise ContentProcessorError(
                f"Prompt '{name}' not found",
                error_type="prompt_not_found"
            )

        if version not in prompt_config.versions:
            raise ContentProcessorError(
                f"Version {version} not found in prompt '{name}'",
                error_type="version_not_found"
            )

        old_version = prompt_config.active_version
        prompt_config.active_version = version
        self.logger.info(f"Changed active version of prompt '{name}' from {old_version} to {version}")

    def validate_all_prompts(self) -> Dict[str, bool]:
        """
        Validate all stored prompts.

        Returns:
            Dictionary mapping prompt names to validation results (True/False)
        """
        results = {}
        for name, prompt_config in self.prompts.items():
            try:
                # Check active version exists
                if prompt_config.active_version not in prompt_config.versions:
                    results[name] = False
                    self.logger.warning(f"Prompt '{name}' active version not found in versions")
                    continue

                # Validate all versions
                all_valid = True
                for version, version_config in prompt_config.versions.items():
                    is_valid = (
                        bool(version_config.template.strip()) and
                        version_config.max_tokens > 0 and
                        0 <= version_config.temperature <= 2.0
                    )
                    if not is_valid:
                        all_valid = False
                        self.logger.warning(f"Prompt '{name}' version {version} failed validation")

                results[name] = all_valid

            except Exception as e:
                results[name] = False
                self.logger.error(f"Error validating prompt '{name}': {str(e)}")

        return results

    def export_prompts(self) -> Dict[str, Dict[str, Any]]:
        """
        Export all prompts to a serializable format.

        Returns:
            Dictionary containing all prompt configurations
        """
        return {
            name: prompt_config.model_dump()
            for name, prompt_config in self.prompts.items()
        }

    def import_prompts(self, prompts_data: Dict[str, Dict[str, Any]]) -> None:
        """
        Import prompts from a serialized format.

        Args:
            prompts_data: Dictionary containing prompt configurations

        Raises:
            ContentProcessorError: If import fails
        """
        try:
            imported_count = 0
            for name, prompt_data in prompts_data.items():
                prompt_config = PromptConfig(**prompt_data)
                self.add_prompt(name, prompt_config)
                imported_count += 1

            self.logger.info(f"Successfully imported {imported_count} prompts")

        except Exception as e:
            raise ContentProcessorError(
                f"Failed to import prompts: {str(e)}",
                error_type="prompt_import_error",
                original_error=e
            )