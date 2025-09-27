# intake/processors/content_support/extractors/vision_openai.py
# OpenAI Vision API extraction strategy

import logging
import base64
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import json

from .base import ExtractionStrategy, PageExtractionResult
from ....services.prompt_provider import PromptProvider
from ....services.models import PromptError

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
    def max_file_size_mb(self) -> float:
        return float(self.config.get('max_file_size_mb', 20.0))

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
        self.prompt_provider = None

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

            # Setup prompt provider and load prompt
            self._setup_prompt_provider()

            return True, None

        except ImportError as e:
            return False, f"Required libraries not installed: {str(e)}"

    def _setup_prompt_provider(self) -> None:
        """Setup the prompt provider and load prompt template."""
        # Get prompt configuration from config
        prompt_config = self.config.get('prompt')

        if not prompt_config:
            raise PromptError(
                "No prompt configuration found in vision_openai config. "
                "Expected 'prompt' with 'name' and 'version' keys.",
                error_type="config_missing"
            )

        # Initialize prompt provider
        from pathlib import Path
        prompts_dir = Path("prompts")
        self.prompt_provider = PromptProvider(prompts_dir=prompts_dir)

        # Load the prompt template
        try:
            self.prompt_template = self.prompt_provider.get_prompt_from_config(
                prompt_config,
                processor_type="content"
            )
            logger.info(f"Loaded prompt: {prompt_config.get('name')}-{prompt_config.get('version')}")
        except PromptError as e:
            logger.error(f"Failed to load prompt: {e}")
            raise

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
            logger.info(f"Preparing page {page_num}/{total_pages} for Vision API processing...")
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

            # Log image size for debugging
            image_size_kb = len(image_base64) / 1024
            logger.info(f"Image prepared (size: {image_size_kb:.1f}KB). Calling OpenAI Vision API...")

            # Call Vision API
            response = self._call_vision_api(image_base64)

            logger.info(f"OpenAI Vision API response received for page {page_num}/{total_pages}")

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
            import time
            start_time = time.time()

            logger.info(f"Sending request to OpenAI Vision API (model: {self.model})...")
            logger.info(f"Waiting for OpenAI Vision API response... (this may take 10-30 seconds)")

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

            elapsed_time = time.time() - start_time
            logger.info(f"OpenAI Vision API responded in {elapsed_time:.1f} seconds")

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