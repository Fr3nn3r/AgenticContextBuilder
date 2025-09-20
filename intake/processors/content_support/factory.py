# intake/processors/content_support/factory.py
# Factory for creating content handlers
# Centralizes handler instantiation and dependency injection

import logging
from pathlib import Path
from typing import Optional, List

from .handlers import (
    BaseContentHandler,
    TextContentHandler,
    ImageContentHandler,
    SpreadsheetContentHandler,
    DocumentContentHandler,
    PDFContentHandler
)
from .services import AIAnalysisService, ResponseParser
from .prompt_manager import PromptManager
from .config import ContentProcessorConfig


def create_content_handler(
    file_path: Path,
    ai_service: AIAnalysisService,
    prompt_manager: PromptManager,
    config: ContentProcessorConfig
) -> Optional[BaseContentHandler]:
    """
    Create appropriate content handler for a file.

    Args:
        file_path: Path to the file to process
        ai_service: AI analysis service
        prompt_manager: Prompt manager instance
        config: Content processor configuration

    Returns:
        Content handler instance or None if no handler available
    """
    logger = logging.getLogger(__name__)
    response_parser = ResponseParser()

    # Get file extension
    extension = file_path.suffix.lower()

    # Find handler based on configuration
    handler_name = config.get_handler_for_extension(extension)

    if not handler_name:
        logger.warning(f"No handler configured for extension: {extension}")
        return None

    # Create handler based on type
    handler_map = {
        'text': TextContentHandler,
        'image': ImageContentHandler,
        'pdf': PDFContentHandler,
        'spreadsheet': SpreadsheetContentHandler,
        'document': DocumentContentHandler
    }

    handler_class = handler_map.get(handler_name)

    if not handler_class:
        logger.error(f"Unknown handler type: {handler_name}")
        return None

    # Check if handler is enabled
    if not config.is_handler_enabled(handler_name):
        logger.info(f"Handler '{handler_name}' is disabled in configuration")
        return None

    # Create handler instance with dependencies
    try:
        handler = handler_class(
            ai_service=ai_service,
            prompt_manager=prompt_manager,
            response_parser=response_parser,
            config=config.model_dump()  # Pass full config as dict
        )

        # Verify handler can handle the file
        if not handler.can_handle(file_path):
            logger.warning(f"Handler {handler_class.__name__} cannot handle {file_path}")
            return None

        logger.debug(f"Created {handler_class.__name__} for {file_path}")
        return handler

    except Exception as e:
        logger.error(f"Failed to create handler {handler_class.__name__}: {str(e)}")
        return None


def get_all_handlers(
    ai_service: AIAnalysisService,
    prompt_manager: PromptManager,
    config: ContentProcessorConfig
) -> List[BaseContentHandler]:
    """
    Create all enabled handlers.

    Args:
        ai_service: AI analysis service
        prompt_manager: Prompt manager instance
        config: Content processor configuration

    Returns:
        List of enabled handler instances
    """
    logger = logging.getLogger(__name__)
    response_parser = ResponseParser()
    handlers = []

    handler_classes = [
        ('text', TextContentHandler),
        ('image', ImageContentHandler),
        ('pdf', PDFContentHandler),
        ('spreadsheet', SpreadsheetContentHandler),
        ('document', DocumentContentHandler)
    ]

    for handler_name, handler_class in handler_classes:
        if config.is_handler_enabled(handler_name):
            try:
                handler = handler_class(
                    ai_service=ai_service,
                    prompt_manager=prompt_manager,
                    response_parser=response_parser,
                    config=config.model_dump()
                )
                handlers.append(handler)
                logger.debug(f"Initialized {handler_name} handler")
            except Exception as e:
                logger.error(f"Failed to initialize {handler_name} handler: {str(e)}")

    return handlers