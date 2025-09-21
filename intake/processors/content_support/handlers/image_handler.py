# intake/processors/content_support/handlers/image_handler.py
# Handler for image files using OpenAI Vision API
# Processes images to extract visual content and descriptions

import base64
from pathlib import Path
from typing import Dict, Any, Optional

from .base import BaseContentHandler
from ..models import FileContentOutput, ContentProcessorError
from ..services import track_processing_time


class ImageContentHandler(BaseContentHandler):
    """Handler for image files using Vision API."""

    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif',
        '.bmp', '.tiff', '.webp'
    }

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported image type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(
        self,
        file_path: Path,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> FileContentOutput:
        """Process image file using Vision API."""
        with track_processing_time("image_processing") as metrics:
            try:
                # Convert image to base64
                image_base64 = self._encode_image(file_path)

                # Get prompt configuration
                prompt_name = "universal-document"
                prompt_config = self.prompt_provider.get_prompt(prompt_name)
                prompt_version = self.prompt_provider.get_active_version(prompt_name) or "1.0.0"

                if not prompt_config:
                    # Fallback to default configuration
                    prompt_config = self.prompt_provider.get_prompt(prompt_name)
                    prompt_version = "1.0.0"

                # Get AI analysis
                prompt_template = self.prompt_provider.get_prompt_template(prompt_name)

                ai_response = self.ai_service.analyze_content(
                    prompt_template,
                    image_base64=image_base64,
                    model=prompt_config.model,
                    max_tokens=prompt_config.max_tokens,
                    temperature=prompt_config.temperature
                )

                # Parse response
                parsed_data, summary = self.response_parser.parse_ai_response(
                    ai_response,
                    expected_format=prompt_config.output_format or "text"
                )

                # Create output
                content_metadata = self.create_content_metadata(
                    content_type="image",
                    file_category="image",
                    summary=summary if summary else "AI-analyzed image content"
                )

                processing_info = self.create_processing_info(
                    status="success",
                    ai_model=prompt_config.model,
                    prompt_version=prompt_version,
                    processing_time=metrics.duration_seconds,
                    extraction_method="Vision API"
                )

                # Structure the content data
                content_data = parsed_data if parsed_data else {"description": ai_response}

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata,
                    content_data=content_data,
                    data_image_content=image_base64
                )

            except Exception as e:
                self.logger.error(f"Image processing failed for {file_path}: {str(e)}")

                processing_info = self.create_processing_info(
                    status="error",
                    error_message=str(e),
                    processing_time=metrics.duration_seconds
                )

                content_metadata = self.create_content_metadata(
                    content_type="image",
                    file_category="image"
                )

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata
                )

    def _encode_image(self, file_path: Path) -> str:
        """Encode image file to base64."""
        try:
            with open(file_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            raise ContentProcessorError(
                f"Failed to encode image: {str(e)}",
                error_type="image_encoding_error"
            )