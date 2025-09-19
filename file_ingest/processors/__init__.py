# file_ingest/processors/__init__.py
# Processor plugin registry and auto-discovery system
# Automatically loads and manages all available processors

import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Type, Any, Union
from pydantic import BaseModel
from .base import BaseProcessor, ProcessingError


class ProcessorRegistry:
    """
    Registry for managing and discovering file processors.

    Automatically discovers processor classes in the processors directory
    and provides methods to instantiate and manage them.
    """

    def __init__(self):
        self._processors: Dict[str, Type[BaseProcessor]] = {}
        self._discover_processors()

    def _discover_processors(self) -> None:
        """
        Automatically discover and register all processor classes.

        Scans the processors directory for Python files and imports
        any classes that inherit from BaseProcessor.
        """
        processors_dir = Path(__file__).parent

        for py_file in processors_dir.glob("*.py"):
            if py_file.name.startswith("_") or py_file.name == "base.py":
                continue

            module_name = py_file.stem
            try:
                # Import the module
                module = importlib.import_module(f".{module_name}", package=__package__)

                # Find processor classes
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        issubclass(obj, BaseProcessor) and
                        obj != BaseProcessor):
                        self._processors[name] = obj

            except ImportError as e:
                print(f"Warning: Could not import processor module {module_name}: {e}")

    def get_processor(self, name: str, config: Union[Dict[str, Any], BaseModel] = None) -> BaseProcessor:
        """
        Get an instance of a processor by name.

        Args:
            name: The processor class name
            config: Configuration dictionary for the processor

        Returns:
            Configured processor instance

        Raises:
            ValueError: If processor is not found
        """
        if name not in self._processors:
            raise ValueError(f"Processor '{name}' not found. Available: {list(self._processors.keys())}")

        processor_class = self._processors[name]
        return processor_class(config)

    def list_processors(self) -> List[str]:
        """
        Get a list of all available processor names.

        Returns:
            List of processor class names
        """
        return list(self._processors.keys())

    def get_processor_info(self, name: str) -> Dict[str, Any]:
        """
        Get information about a specific processor.

        Args:
            name: The processor class name

        Returns:
            Dictionary with processor information

        Raises:
            ValueError: If processor is not found
        """
        if name not in self._processors:
            raise ValueError(f"Processor '{name}' not found")

        # Create a temporary instance to get info
        temp_instance = self._processors[name]()
        return temp_instance.get_processor_info()

    def get_all_processor_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all available processors.

        Returns:
            Dictionary mapping processor names to their info
        """
        return {name: self.get_processor_info(name) for name in self._processors.keys()}


class ProcessingPipeline:
    """
    Manages a pipeline of processors for file ingestion.

    Coordinates the execution of multiple processors in sequence,
    passing metadata between processors and handling errors.
    """

    def __init__(self, registry: ProcessorRegistry):
        self.registry = registry
        self.processors: List[BaseProcessor] = []

    def add_processor(self, processor_name: str, config: Union[Dict[str, Any], BaseModel] = None) -> None:
        """
        Add a processor to the pipeline.

        Args:
            processor_name: Name of the processor to add
            config: Configuration for the processor
        """
        processor = self.registry.get_processor(processor_name, config)
        self.processors.append(processor)

    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a file through the entire pipeline.

        Args:
            file_path: Path to the file to process

        Returns:
            Dictionary containing all metadata from all processors

        Raises:
            ProcessingError: If any processor fails
        """
        metadata = {}

        for processor in self.processors:
            try:
                result = processor.process_file(file_path, metadata)
                # Merge results into existing metadata
                if result:
                    metadata.update(result)
            except Exception as e:
                raise ProcessingError(
                    f"Processing failed: {str(e)}",
                    file_path=file_path,
                    processor_name=processor.name
                )

        # Convert any Pydantic models to dictionaries for external API compatibility
        return _serialize_for_json(metadata)


    def get_pipeline_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all processors in the pipeline.

        Returns:
            List of processor information dictionaries
        """
        return [processor.get_processor_info() for processor in self.processors]


def _serialize_for_json(obj):
    """Convert Pydantic models and other objects to JSON-serializable format."""
    if hasattr(obj, 'model_dump'):
        # It's a Pydantic model
        return obj.model_dump()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    else:
        return obj


# Global registry instance
registry = ProcessorRegistry()

# Export main classes and instance
__all__ = ['BaseProcessor', 'ProcessorRegistry', 'ProcessingPipeline', 'ProcessingError', 'registry']