# intake/processors/content_support/extractors/registry.py
# Registry for managing and coordinating extraction strategies

import logging
from typing import Dict, List, Optional, Type
from pathlib import Path

from .base import ExtractionStrategy, ExtractionResult

logger = logging.getLogger(__name__)


class ExtractionRegistry:
    """Manages all available extraction strategies."""

    def __init__(self):
        """Initialize the extraction registry."""
        self._strategies: Dict[str, Type[ExtractionStrategy]] = {}
        self._instances: Dict[str, ExtractionStrategy] = {}
        self._config: Dict[str, Dict] = {}

    def register(self, strategy_class: Type[ExtractionStrategy]) -> None:
        """
        Register a new extraction strategy class.

        Args:
            strategy_class: The extraction strategy class to register
        """
        # Create a temporary instance to get the name
        temp_instance = strategy_class()
        name = temp_instance.name

        if name in self._strategies:
            logger.warning(f"Strategy '{name}' already registered, overwriting")

        self._strategies[name] = strategy_class
        logger.info(f"Registered extraction strategy: {name}")

    def configure(self, config: Dict[str, Dict]) -> None:
        """
        Configure extraction methods with their settings.

        Args:
            config: Configuration dictionary with method configs
        """
        self._config = config

        # Clear existing instances to force reconfiguration
        self._instances.clear()

    def get_enabled_strategies(self, file_type: Optional[str] = None) -> List[ExtractionStrategy]:
        """
        Get all enabled extraction strategies, optionally filtered by file type.

        Args:
            file_type: Optional file type to filter strategies ('pdf', 'image', etc.)

        Returns:
            List of enabled extraction strategy instances, sorted by priority
        """
        enabled = []

        for method_name, method_config in self._config.items():
            # Check if method is enabled
            if not method_config.get('enabled', False):
                continue

            # Check if strategy is registered
            if method_name not in self._strategies:
                logger.warning(f"Strategy '{method_name}' enabled but not registered")
                continue

            # Get or create instance
            if method_name not in self._instances:
                strategy_class = self._strategies[method_name]
                config = method_config.get('config', {})
                self._instances[method_name] = strategy_class(config)

            strategy = self._instances[method_name]

            # Filter by file type if specified
            if file_type and file_type not in strategy.supports_file_types:
                continue

            # Add with priority for sorting
            priority = method_config.get('priority', 999)
            enabled.append((priority, strategy))

        # Sort by priority and return strategies only
        enabled.sort(key=lambda x: x[0])
        return [strategy for _, strategy in enabled]

    def get_strategies_for_file(self, file_path: Path) -> List[ExtractionStrategy]:
        """
        Get all enabled strategies that can handle a specific file.

        Args:
            file_path: Path to the file

        Returns:
            List of applicable extraction strategies, sorted by priority
        """
        strategies = []

        for strategy in self.get_enabled_strategies():
            if strategy.can_handle(file_path):
                strategies.append(strategy)

        return strategies

    def validate_configuration(self, config: Dict[str, Dict]) -> List[str]:
        """
        Validate extraction methods configuration.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check if at least one method is enabled
        enabled_count = sum(1 for cfg in config.values() if cfg.get('enabled', False))
        if enabled_count == 0:
            errors.append("At least one extraction method must be enabled")

        # Check each enabled method
        for method_name, method_config in config.items():
            if not method_config.get('enabled', False):
                continue

            # Check if strategy is registered
            if method_name not in self._strategies:
                errors.append(f"Unknown extraction method: {method_name}")
                continue

            # Create instance and validate requirements
            try:
                strategy_class = self._strategies[method_name]
                strategy = strategy_class(method_config.get('config', {}))
                is_valid, error_msg = strategy.validate_requirements()
                if not is_valid:
                    errors.append(f"{method_name}: {error_msg}")
            except Exception as e:
                errors.append(f"Failed to validate {method_name}: {str(e)}")

        # Check for priority conflicts
        priorities = {}
        for method_name, method_config in config.items():
            if not method_config.get('enabled', False):
                continue

            priority = method_config.get('priority', 999)
            if priority in priorities:
                errors.append(
                    f"Priority conflict: {method_name} and {priorities[priority]} "
                    f"both have priority {priority}"
                )
            priorities[priority] = method_name

        return errors

    def extract_from_file(
        self,
        file_path: Path,
        method_names: Optional[List[str]] = None
    ) -> List[ExtractionResult]:
        """
        Extract content from a file using enabled strategies.

        Args:
            file_path: Path to the file
            method_names: Optional list of specific methods to use

        Returns:
            List of extraction results from each method
        """
        results = []

        # Get strategies to use
        if method_names:
            # Use specific methods requested
            strategies = []
            for name in method_names:
                if name not in self._strategies:
                    results.append(ExtractionResult(
                        method=name,
                        status="skipped",
                        pages=[],
                        error=f"Method '{name}' not registered"
                    ))
                    continue

                # Create instance if needed
                if name not in self._instances:
                    strategy_class = self._strategies[name]
                    config = self._config.get(name, {}).get('config', {})
                    self._instances[name] = strategy_class(config)

                strategies.append(self._instances[name])
        else:
            # Use all enabled strategies for this file
            strategies = self.get_strategies_for_file(file_path)

        # Extract with each strategy
        for strategy in strategies:
            logger.info(f"Extracting with {strategy.name} from {file_path.name}")
            try:
                result = strategy.extract(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Strategy {strategy.name} failed: {str(e)}")
                results.append(ExtractionResult(
                    method=strategy.name,
                    status="error",
                    pages=[],
                    error=str(e)
                ))

        return results

    def get_registered_methods(self) -> List[str]:
        """Get list of all registered extraction method names."""
        return list(self._strategies.keys())

    def is_method_available(self, method_name: str) -> bool:
        """Check if a method is registered and its requirements are met."""
        if method_name not in self._strategies:
            return False

        try:
            strategy_class = self._strategies[method_name]
            strategy = strategy_class()
            is_valid, _ = strategy.validate_requirements()
            return is_valid
        except:
            return False


# Global registry instance
_registry = ExtractionRegistry()


def get_registry() -> ExtractionRegistry:
    """Get the global extraction registry instance."""
    return _registry


def register_strategy(strategy_class: Type[ExtractionStrategy]) -> None:
    """
    Register an extraction strategy with the global registry.

    Args:
        strategy_class: The extraction strategy class to register
    """
    _registry.register(strategy_class)