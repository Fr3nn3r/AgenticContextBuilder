# intake/processors/enrichment.py
# Example enrichment processor for demonstrating extensibility
# Can be used as a template for creating custom processors

import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel

from .base import BaseProcessor


class EnrichmentProcessor(BaseProcessor):
    """
    Example processor that enriches file metadata with additional information.

    This processor demonstrates how to create custom processors that build
    on existing metadata. It can add content analysis, file categorization,
    and other enhanced metadata.
    """

    VERSION = "1.0.0"
    DESCRIPTION = "Enriches file metadata with additional analysis and categorization"
    SUPPORTED_EXTENSIONS = ["*"]  # Supports all file types

    def __init__(self, config: Optional[Union[Dict[str, Any], BaseModel]] = None):
        super().__init__(config)
        # Default configuration
        self.config.setdefault('enable_content_analysis', False)
        self.config.setdefault('categorize_files', True)
        self.config.setdefault('analyze_images', False)
        self.config.setdefault('extract_text_preview', False)

    def process_file(self, file_path: Path, existing_metadata: Optional[Union[Dict[str, Any], BaseModel]] = None) -> Dict[str, Any]:
        """
        Enrich existing file metadata with additional information.

        Args:
            file_path: Path to the file to process
            existing_metadata: Metadata from previous processors

        Returns:
            Dictionary containing enriched metadata
        """
        enriched_metadata = {}

        # File categorization
        if self.config.get('categorize_files', True):
            enriched_metadata['file_category'] = self._categorize_file(file_path)

        # Content analysis (placeholder for future implementation)
        if self.config.get('enable_content_analysis', False):
            enriched_metadata['content_analysis'] = self._analyze_content(file_path)

        # Image analysis (placeholder for future implementation)
        if (self.config.get('analyze_images', False) and
            self._is_image_file(file_path)):
            enriched_metadata['image_analysis'] = self._analyze_image(file_path)

        # Text preview (placeholder for future implementation)
        if (self.config.get('extract_text_preview', False) and
            self._is_text_file(file_path)):
            enriched_metadata['text_preview'] = self._extract_text_preview(file_path)

        # Add processing metadata
        enriched_metadata['enrichment_info'] = {
            'processor_version': self.VERSION,
            'enrichment_features_enabled': [
                key for key, value in self.config.items()
                if key.startswith(('enable_', 'categorize_', 'analyze_', 'extract_')) and value
            ]
        }

        return {'enriched_metadata': enriched_metadata}

    def _categorize_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Categorize the file based on extension and MIME type.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary containing file category information
        """
        extension = file_path.suffix.lower()
        mime_type, _ = mimetypes.guess_type(file_path)

        # Define category mappings
        categories = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg', '.webp'],
            'video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
            'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'],
            'document': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
            'spreadsheet': ['.xls', '.xlsx', '.csv', '.ods'],
            'presentation': ['.ppt', '.pptx', '.odp'],
            'archive': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'],
            'code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.go', '.rs'],
            'data': ['.json', '.xml', '.yaml', '.yml', '.sql', '.db', '.sqlite'],
        }

        # Find category based on extension
        file_category = 'other'
        for category, extensions in categories.items():
            if extension in extensions:
                file_category = category
                break

        # Additional MIME type analysis
        mime_category = None
        if mime_type:
            if mime_type.startswith('image/'):
                mime_category = 'image'
            elif mime_type.startswith('video/'):
                mime_category = 'video'
            elif mime_type.startswith('audio/'):
                mime_category = 'audio'
            elif mime_type.startswith('text/'):
                mime_category = 'text'
            elif 'application/' in mime_type:
                if 'pdf' in mime_type:
                    mime_category = 'document'
                elif any(x in mime_type for x in ['zip', 'archive', 'compressed']):
                    mime_category = 'archive'

        return {
            'primary_category': file_category,
            'mime_category': mime_category,
            'extension': extension,
            'mime_type': mime_type,
            'is_binary': not self._is_text_file(file_path),
        }

    def _analyze_content(self, file_path: Path) -> Dict[str, Any]:
        """
        Placeholder for content analysis functionality.

        This could be extended to include:
        - Text sentiment analysis
        - Language detection
        - Content summarization
        - Keyword extraction

        Args:
            file_path: Path to the file

        Returns:
            Dictionary containing content analysis results
        """
        return {
            'status': 'not_implemented',
            'note': 'Content analysis feature is not yet implemented',
            'future_features': [
                'text_sentiment_analysis',
                'language_detection',
                'content_summarization',
                'keyword_extraction'
            ]
        }

    def _analyze_image(self, file_path: Path) -> Dict[str, Any]:
        """
        Placeholder for image analysis functionality.

        This could be extended to include:
        - Image dimensions and properties
        - Color analysis
        - Object detection
        - Duplicate image detection

        Args:
            file_path: Path to the image file

        Returns:
            Dictionary containing image analysis results
        """
        return {
            'status': 'not_implemented',
            'note': 'Image analysis feature is not yet implemented',
            'future_features': [
                'image_dimensions',
                'color_analysis',
                'object_detection',
                'duplicate_detection'
            ]
        }

    def _extract_text_preview(self, file_path: Path) -> Dict[str, Any]:
        """
        Placeholder for text preview extraction.

        This could be extended to include:
        - First N characters/lines of text files
        - Text encoding detection
        - Line count and statistics

        Args:
            file_path: Path to the text file

        Returns:
            Dictionary containing text preview
        """
        return {
            'status': 'not_implemented',
            'note': 'Text preview feature is not yet implemented',
            'future_features': [
                'text_preview',
                'encoding_detection',
                'line_count_statistics'
            ]
        }

    def _is_image_file(self, file_path: Path) -> bool:
        """Check if file is an image based on extension."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg', '.webp'}
        return file_path.suffix.lower() in image_extensions

    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is likely a text file based on extension."""
        text_extensions = {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml'}
        return file_path.suffix.lower() in text_extensions

    def validate_config(self) -> bool:
        """
        Validate the processor configuration.

        Returns:
            True if configuration is valid
        """
        # All boolean configuration options
        boolean_options = [
            'enable_content_analysis',
            'categorize_files',
            'analyze_images',
            'extract_text_preview'
        ]

        for option in boolean_options:
            if option in self.config and not isinstance(self.config[option], bool):
                return False

        return True