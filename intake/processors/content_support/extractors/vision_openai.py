# intake/processors/content_support/extractors/vision_openai.py
# OpenAI Vision API extraction strategy

import logging
import base64
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import json

from .base import ExtractionStrategy, PageExtractionResult

logger = logging.getLogger(__name__)


class VisionOpenAIStrategy(ExtractionStrategy):
    """Content extraction using OpenAI Vision API."""

    @property
    def name(self) -> str:
        return "vision_openai"

    @property
    def supports_file_types(self) -> list:
        return ["pdf", "image", "document"]

    @property
    def supports_batch_processing(self) -> bool:
        return False

    @property
    def requires_api_key(self) -> bool:
        return True

    @property
    def max_file_size_mb(self) -> int:
        return self.config.get('max_file_size_mb', 20)

    def _setup(self) -> None:
        """Setup OpenAI Vision configuration."""
        self.model = self.config.get('model', 'gpt-4o')
        self.max_pages = self.config.get('max_pages', 20)
        self.api_key_env = self.config.get('api_key_env', 'OPENAI_API_KEY')
        self.temperature = self.config.get('temperature', 0.1)
        self.max_tokens = self.config.get('max_tokens', 2048)
        self.pdf_renderer = None
        self.openai_client = None
        self.prompt_template = None

    def validate_requirements(self) -> Tuple[bool, Optional[str]]:
        """Check if OpenAI API key and required libraries are available."""
        # Check for API key
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            return False, f"API key not found in environment variable {self.api_key_env}"

        try:
            # Check OpenAI library
            from openai import OpenAI
            self.openai_client = OpenAI(api_key=api_key)

            # For PDF support, check pypdfium2
            if "pdf" in self.supports_file_types:
                try:
                    import pypdfium2 as pdfium
                    self.pdf_renderer = pdfium
                except ImportError:
                    logger.warning("pypdfium2 not available, PDF Vision support disabled")

            # Set default prompt template
            self._setup_prompt_template()

            return True, None

        except ImportError as e:
            return False, f"Required libraries not installed: {str(e)}"

    def _setup_prompt_template(self) -> None:
        """Setup the prompt template for Vision API."""
        self.prompt_template = """Analyze this document/image and extract structured information.

Your task is to:
1. Extract all visible text content
2. Identify the document type (invoice, report, form, letter, etc.)
3. Extract key information and metadata
4. Note any important visual elements

Respond with a JSON structure containing:
{
  "document_type": "type of document",
  "title": "document title if identifiable",
  "text_content": "all extracted text",
  "key_information": {
    // Relevant key-value pairs based on document type
  },
  "visual_elements": [
    // List of notable visual elements
  ],
  "language": "primary language of the document",
  "summary": "brief summary of the document"
}"""

    def get_total_pages(self, file_path: Path) -> int:
        """Get total number of pages in the file."""
        if file_path.suffix.lower() == '.pdf':
            if not self.pdf_renderer:
                raise Exception("PDF support not available (pypdfium2 not installed)")

            pdf_doc = self.pdf_renderer.PdfDocument(file_path)
            page_count = min(len(pdf_doc), self.max_pages)  # Limit to max_pages
            pdf_doc.close()
            return page_count
        else:
            # Images and documents have single page
            return 1

    def extract_page(self, file_path: Path, page_num: int, total_pages: int) -> PageExtractionResult:
        """Extract content from a single page using Vision API."""
        try:
            # Get image data
            if file_path.suffix.lower() == '.pdf':
                image_base64 = self._pdf_page_to_base64(file_path, page_num - 1)
            else:
                # For images and documents
                if page_num != 1:
                    return PageExtractionResult(
                        page_number=page_num,
                        status="error",
                        error="Invalid page number for image/document file"
                    )
                image_base64 = self._file_to_base64(file_path)

            # Call Vision API
            response = self._call_vision_api(image_base64)

            # Parse response
            try:
                content = self._parse_vision_response(response)

                return PageExtractionResult(
                    page_number=page_num,
                    status="success",
                    content=content,
                    quality_score=None  # Vision API doesn't provide quality scores
                )

            except (json.JSONDecodeError, ValueError) as e:
                # If JSON parsing fails, return raw response
                logger.warning(f"Failed to parse Vision API response as JSON: {e}")
                return PageExtractionResult(
                    page_number=page_num,
                    status="success",
                    content={
                        "raw_response": response,
                        "parse_error": str(e)
                    },
                    quality_score=None
                )

        except Exception as e:
            logger.error(f"Vision API extraction failed for page {page_num}: {str(e)}")
            return PageExtractionResult(
                page_number=page_num,
                status="error",
                error=str(e)
            )

    def _pdf_page_to_base64(self, file_path: Path, page_index: int) -> str:
        """Convert a PDF page to base64-encoded image."""
        if not self.pdf_renderer:
            raise Exception("PDF support not available")

        pdf_doc = self.pdf_renderer.PdfDocument(file_path)
        try:
            page = pdf_doc[page_index]

            # Render at high quality for better extraction
            scale = 2.0
            mat = page.render(scale=scale)

            # Convert to PIL Image
            img = mat.to_pil()

            # Convert to base64
            import io
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
            return base64.b64encode(image_bytes).decode('utf-8')

        finally:
            pdf_doc.close()

    def _file_to_base64(self, file_path: Path) -> str:
        """Convert an image file to base64."""
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _call_vision_api(self, image_base64: str) -> str:
        """Call OpenAI Vision API with the image."""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.prompt_template},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "text"}
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI Vision API call failed: {str(e)}")
            raise

    def _parse_vision_response(self, response: str) -> Dict[str, Any]:
        """Parse the Vision API response to extract structured data."""
        # Try to extract JSON from the response
        response = response.strip()

        # Look for JSON block
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                response = response[start:end].strip()

        # Try to parse as JSON
        try:
            # First, try direct JSON parsing
            return json.loads(response)
        except json.JSONDecodeError:
            # If that fails, try to find JSON structure
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(response[start:end])
                except json.JSONDecodeError:
                    pass

        # If all parsing fails, return structured response with raw text
        return {
            "document_type": "unknown",
            "text_content": response,
            "summary": "Could not parse structured response",
            "_raw_response": response
        }