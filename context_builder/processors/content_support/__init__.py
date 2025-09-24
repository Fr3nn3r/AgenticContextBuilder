# intake/processors/content_support/__init__.py
# Content processing support modules
# Provides models, handlers, and utilities for content extraction

from .models import FileContentOutput
from .handlers import BaseContentHandler

__all__ = [
    'FileContentOutput',
    'BaseContentHandler'
]