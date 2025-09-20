# intake/processors/content_support/interfaces/__init__.py
# Export all interfaces for easy access

from .ai_provider import AIProviderInterface
from .content_extractor import ContentExtractorInterface
from .image_processor import ImageProcessorInterface

__all__ = [
    'AIProviderInterface',
    'ContentExtractorInterface',
    'ImageProcessorInterface'
]