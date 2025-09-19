# file_ingest/__init__.py
# File ingestion package for extracting metadata from datasets
# Provides extensible processing pipeline with pluggable processors

from .ingest import FileIngestor
from .processors import BaseProcessor, ProcessorRegistry, ProcessingPipeline, ProcessingError, registry
from .utils import get_file_hash, format_bytes, generate_ingestion_id

__version__ = "1.0.0"
__author__ = "Context Manager Project"
__description__ = "Extensible file ingestion system with pluggable processors"

# Main exports
__all__ = [
    'FileIngestor',
    'BaseProcessor',
    'ProcessorRegistry',
    'ProcessingPipeline',
    'ProcessingError',
    'registry',
    'get_file_hash',
    'format_bytes',
    'generate_ingestion_id',
]