# intake/services/__init__.py
# Shared services used across multiple processors

from .prompt_provider import PromptProvider

__all__ = [
    'PromptProvider',
]