# intake/processors/content_support/extractors/__init__.py
# Extraction strategies module initialization

from .base import ExtractionStrategy, ExtractionResult, PageExtractionResult
from .registry import ExtractionRegistry, get_registry, register_strategy
from .ocr_tesseract import OCRTesseractStrategy
from .vision_openai import VisionOpenAIStrategy

# Register available strategies
register_strategy(OCRTesseractStrategy)
register_strategy(VisionOpenAIStrategy)

__all__ = [
    'ExtractionStrategy',
    'ExtractionResult',
    'PageExtractionResult',
    'ExtractionRegistry',
    'get_registry',
    'register_strategy',
    'OCRTesseractStrategy',
    'VisionOpenAIStrategy'
]