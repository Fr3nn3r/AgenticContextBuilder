# intake/processors/content_support/handlers/text_handler.py
# Handler for text-based files (txt, json, csv, py, js, etc.)
# Processes text content using AI analysis

from pathlib import Path
from typing import Dict, Any, Optional

from .base import BaseContentHandler
from ..models import FileContentOutput, ContentProcessorError
from ..services import track_processing_time


class TextContentHandler(BaseContentHandler):
    """Handler for text-based files."""

    SUPPORTED_EXTENSIONS = {
        '.txt', '.json', '.md', '.xml', '.html',
        '.py', '.js', '.css', '.yaml', '.yml'
    }

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported text type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(
        self,
        file_path: Path,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> FileContentOutput:
        """Process text file and extract content."""
        with track_processing_time("text_processing") as metrics:
            try:
                # Read file content
                content = self._read_text_file(file_path)

                # Truncate if necessary
                truncated_content = self._truncate_content(content)

                # Get prompt configuration
                prompt_name = "text-analysis"
                prompt_config = self.prompt_provider.get_prompt(prompt_name)

                if not prompt_config:
                    raise ContentProcessorError(
                        f"Prompt '{prompt_name}' not found",
                        error_type="prompt_not_found"
                    )

                # Get AI analysis
                prompt_template = self.prompt_provider.get_prompt_template(
                    prompt_name,
                    content=truncated_content
                )

                ai_response = self.ai_service.analyze_content(
                    prompt_template,
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
                    content_type="text",
                    file_category="text_document",
                    summary=summary if parsed_data else f"Text file with {len(content)} characters",
                    detected_language=parsed_data.get('language') if isinstance(parsed_data, dict) else None
                )

                processing_info = self.create_processing_info(
                    status="success",
                    ai_model=prompt_config.model,
                    prompt_version="2.0.0",  # TODO: get from prompt_config
                    processing_time=metrics.duration_seconds,
                    extraction_method="direct_read"
                )

                # Create extraction results in standardized format
                extraction_results = [
                    {
                        "method": "direct_read",
                        "status": "success",
                        "priority": 1,
                        "content": content,
                        "metadata": {
                            "encoding": "utf-8",
                            "line_count": len(content.splitlines()),
                            "character_count": len(content),
                            "truncated": len(content) > self.config.get('text_truncation_chars', 8000)
                        },
                        "error": None
                    }
                ]

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata,
                    content_data=parsed_data,
                    extraction_results=extraction_results
                )

            except Exception as e:
                self.logger.error(f"Text processing failed for {file_path}: {str(e)}")

                processing_info = self.create_processing_info(
                    status="error",
                    error_message=str(e),
                    processing_time=metrics.duration_seconds
                )

                content_metadata = self.create_content_metadata(
                    content_type="text",
                    file_category="text_document"
                )

                # Create extraction results with error status
                extraction_results = [
                    {
                        "method": "direct_read",
                        "status": "error",
                        "priority": 1,
                        "content": "",
                        "metadata": {},
                        "error": str(e)
                    }
                ]

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata,
                    extraction_results=extraction_results
                )

    def _read_text_file(self, file_path: Path) -> str:
        """Read text file with error handling."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            raise ContentProcessorError(
                f"Failed to read text file: {str(e)}",
                error_type="file_read_error"
            )

    def _truncate_content(self, content: str) -> str:
        """Truncate content if too long."""
        max_chars = self.config.get('text_truncation_chars', 8000)
        if len(content) > max_chars:
            return content[:max_chars] + "\n[... content truncated ...]"
        return content