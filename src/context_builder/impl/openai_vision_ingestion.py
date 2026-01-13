"""OpenAI Vision API implementation for data ingestion."""

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List
from io import BytesIO

from pydantic import ValidationError

from context_builder.ingestion import (
    DataIngestion,
    APIError,
    ConfigurationError,
    IngestionFactory,
)
from context_builder.utils.file_utils import get_file_metadata
from context_builder.utils.prompt_loader import load_prompt
from context_builder.schemas.document_analysis import DocumentAnalysis

logger = logging.getLogger(__name__)


class OpenAIVisionIngestion(DataIngestion):
    """
    OpenAI Vision API implementation for document context extraction.

    This implementation follows the "Schemas in Python, Prompts in Markdown" pattern:
    - Schema: DocumentAnalysis Pydantic model defines output structure
    - Prompt: document_analysis.md defines instructions and configuration
    - Runner: This class orchestrates the API calls

    NOTE: We use json_object mode (not .parse() API) to allow dynamic
    key_information structures based on document type.
    """

    def __init__(self):
        """Initialize OpenAI Vision ingestion."""
        super().__init__()

        # Get API key from environment
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY not found in environment variables. "
                "Please set it in your .env file."
            )

        # Initialize OpenAI client
        try:
            from openai import OpenAI

            # Default timeout and retry configuration
            self.timeout = 120  # seconds
            self.retries = 3  # number of retries

            # Initialize client with timeout
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0  # We handle retries ourselves for better control
            )
            logger.debug("OpenAI client initialized successfully")
        except ImportError:
            raise ConfigurationError(
                "OpenAI package not installed. "
                "Please install it with: pip install openai"
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize OpenAI client: {e}")

        # Load prompt configuration
        # This demonstrates separation of concerns: config lives in .md file
        try:
            prompt_data = load_prompt("document_analysis")
            self.prompt_config = prompt_data["config"]
            logger.debug(f"Loaded prompt: {self.prompt_config.get('name', 'unnamed')}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load prompt configuration: {e}")

        # Extract configuration from prompt file
        self.model = self.prompt_config.get("model", "gpt-4o")
        self.max_tokens = self.prompt_config.get("max_tokens", 4096)
        self.temperature = self.prompt_config.get("temperature", 0.2)

        # Additional configuration
        self.max_pages = 20  # Limit pages to prevent excessive API calls
        self.render_scale = 2.0  # Higher quality rendering for PDFs

        logger.debug(
            f"Using model: {self.model}, max_tokens: {self.max_tokens}, max_pages: {self.max_pages}"
        )

    def _encode_image(self, image_path: Path) -> str:
        """
        Encode image file to base64 string.

        Args:
            image_path: Path to image file

        Returns:
            Base64 encoded string

        Raises:
            IOError: If file cannot be read
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            raise IOError(f"Cannot read image file: {e}")

    def _encode_image_from_pil(self, pil_image) -> str:
        """
        Encode PIL image to base64 string.

        Args:
            pil_image: PIL Image object

        Returns:
            Base64 encoded string
        """
        try:
            buffer = BytesIO()
            pil_image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode PIL image: {e}")
            raise IOError(f"Cannot encode image: {e}")

    def _build_vision_messages(
        self,
        base64_image: str,
        mime_type: str,
        page_number: int = None,
        total_pages: int = None
    ) -> List[Dict[str, Any]]:
        """
        Build OpenAI API messages with image and prompt.

        Args:
            base64_image: Base64 encoded image
            mime_type: MIME type of image
            page_number: Optional page number for multi-page documents
            total_pages: Optional total pages for multi-page documents

        Returns:
            List of message dictionaries for OpenAI API
        """
        # Load prompt with optional page context
        prompt_kwargs = {}
        if page_number is not None and total_pages is not None:
            prompt_kwargs["page_number"] = page_number
            prompt_kwargs["total_pages"] = total_pages

        prompt_data = load_prompt("document_analysis", **prompt_kwargs)
        text_messages = prompt_data["messages"]

        # Build vision messages by adding image to user message
        vision_messages = []
        for msg in text_messages:
            if msg["role"] == "user":
                # Add image to user message
                vision_messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": msg["content"]},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                    ],
                })
            else:
                # Pass through system message as-is
                vision_messages.append(msg)

        return vision_messages

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse API response to extract JSON.

        Handles markdown code blocks and extracts valid JSON.

        Args:
            response_text: Raw response text from API

        Returns:
            Parsed JSON dictionary

        Raises:
            APIError: If response cannot be parsed
        """
        # Try to parse as JSON
        try:
            # Defensive check for None response
            if not response_text:
                return {
                    "document_type": "unknown",
                    "language": "unknown",
                    "summary": "Empty response from vision API",
                    "key_information": {},
                    "visual_elements": [],
                    "text_content": "",
                    "_parse_error": "response_text was None or empty",
                }

            # Handle potential markdown code blocks
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()

            return json.loads(response_text)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response_text}")

            # Return fallback structure with text content
            return {
                "document_type": "unknown",
                "language": "unknown",
                "summary": "Failed to parse structured response",
                "key_information": {},
                "visual_elements": [],
                "text_content": response_text,
                "_parse_error": str(e),
            }

    def _validate_with_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parsed JSON with Pydantic schema.

        Args:
            data: Parsed JSON data

        Returns:
            Validated data as dictionary

        Raises:
            APIError: If validation fails critically
        """
        try:
            # Validate with Pydantic model
            validated = DocumentAnalysis(**data)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning(f"Pydantic validation failed: {e}")
            logger.warning("Returning data with validation errors marked")

            # Return data with validation error marker
            data["_validation_errors"] = str(e)
            return data

    def _process_pdf_pages(self, pdf_path: Path) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Process PDF pages one by one to minimize memory usage.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (list of page results, total usage statistics)

        Raises:
            IOError: If PDF cannot be processed
        """
        try:
            import pypdfium2 as pdfium

            logger.info(f"Processing PDF pages with pypdfium2: {pdf_path}")

            # Open PDF document
            pdf_doc = pdfium.PdfDocument(pdf_path)
            all_results = []
            total_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

            try:
                total_pages = len(pdf_doc)
                pages_to_process = min(total_pages, self.max_pages)

                if total_pages > self.max_pages:
                    logger.warning(
                        f"PDF has {total_pages} pages, processing only first {self.max_pages} pages"
                    )
                else:
                    logger.info(f"PDF has {total_pages} pages")

                for page_index in range(pages_to_process):
                    logger.info(f"Processing page {page_index + 1}/{pages_to_process}...")

                    # Render single page
                    page = pdf_doc[page_index]
                    mat = page.render(scale=self.render_scale)
                    img = mat.to_pil()

                    # Encode and prepare messages
                    base64_image = self._encode_image_from_pil(img)

                    # Free the image memory immediately
                    del img
                    del mat

                    # Build messages with page context
                    page_messages = self._build_vision_messages(
                        base64_image=base64_image,
                        mime_type="image/png",
                        page_number=page_index + 1,
                        total_pages=pages_to_process
                    )

                    # Call API with retry logic
                    response = self._call_api_with_retry(page_messages)

                    # Parse and validate response
                    parsed_data = self._parse_response(response.choices[0].message.content)
                    page_result = self._validate_with_schema(parsed_data)
                    page_result["page_number"] = page_index + 1
                    all_results.append(page_result)

                    # Accumulate usage
                    if hasattr(response, "usage"):
                        total_usage["prompt_tokens"] += response.usage.prompt_tokens
                        total_usage["completion_tokens"] += response.usage.completion_tokens
                        total_usage["total_tokens"] += response.usage.total_tokens

                    logger.debug(f"Completed processing page {page_index + 1}")

                return all_results, total_usage

            finally:
                # Always close the PDF document
                pdf_doc.close()

        except ImportError:
            raise ConfigurationError(
                "pypdfium2 package not installed. "
                "Please install it with: pip install pypdfium2"
            )
        except Exception as e:
            logger.error(f"Failed to process PDF pages: {e}")
            raise IOError(f"Cannot process PDF file: {e}")

    def _prepare_image_messages(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Prepare messages for OpenAI API call for image files.

        Args:
            file_path: Path to image file

        Returns:
            List of message dictionaries
        """
        extension = file_path.suffix.lower()

        # Encode image
        base64_image = self._encode_image(file_path)

        # Determine MIME type
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(extension, "image/jpeg")

        # Build messages with image
        return self._build_vision_messages(
            base64_image=base64_image,
            mime_type=mime_type
        )

    def _call_api_with_retry(self, messages: List[Dict[str, Any]], attempt: int = 0) -> Any:
        """
        Call OpenAI API with retry logic, exponential backoff, and JSON object mode.

        Uses json_object mode (not .parse() API) to allow flexible key_information
        structures that adapt to different document types.

        Args:
            messages: Messages to send to API
            attempt: Current retry attempt number

        Returns:
            API response object with content

        Raises:
            APIError: If all retries exhausted
        """
        try:
            # Use json_object mode for flexibility
            # We validate with Pydantic afterward
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},
                timeout=self.timeout
            )
            return response

        except Exception as e:
            error_str = str(e).lower()
            is_retryable = any(
                keyword in error_str
                for keyword in ["rate", "429", "500", "502", "503", "504", "timeout"]
            )

            if is_retryable and attempt < self.retries - 1:
                # Exponential backoff: 2^attempt * base_delay
                wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{self.retries}): {e}. "
                    f"Retrying in {wait_time} seconds..."
                )
                time.sleep(wait_time)
                return self._call_api_with_retry(messages, attempt + 1)
            else:
                # Map to appropriate error type
                if "api_key" in error_str or "authentication" in error_str:
                    raise ConfigurationError(f"Invalid API key: {e}")
                elif "rate" in error_str or "429" in error_str:
                    raise APIError(f"Rate limit exceeded after {self.retries} retries: {e}")
                elif "timeout" in error_str:
                    raise APIError(f"Request timed out after {self.retries} retries: {e}")
                else:
                    raise APIError(f"API call failed after {self.retries} retries: {e}")

    def _process_implementation(self, filepath: Path) -> Dict[str, Any]:
        """
        Process file using OpenAI Vision API with JSON object mode.

        Args:
            filepath: Path to file to process

        Returns:
            Dictionary containing extracted context with file metadata

        Raises:
            APIError: If API call fails
        """
        logger.info(f"Processing with OpenAI Vision API: {filepath}")

        # Get file metadata first
        result = get_file_metadata(filepath)

        try:
            # For non-PDF files, process directly
            if filepath.suffix.lower() != ".pdf":
                # Prepare messages
                messages = self._prepare_image_messages(filepath)

                # Call OpenAI API with retry logic
                logger.debug(f"Calling OpenAI API with model: {self.model}")
                response = self._call_api_with_retry(messages)

                # Parse and validate response
                parsed_data = self._parse_response(response.choices[0].message.content)
                page_content = self._validate_with_schema(parsed_data)

                # Structure result
                result["total_pages"] = 1
                result["pages"] = [page_content]

                # Add usage information if available
                if hasattr(response, "usage"):
                    result["_usage"] = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }

                return result

            # For PDFs, process pages one by one to minimize memory
            else:
                logger.info("Processing PDF using memory-efficient streaming...")

                # Process PDF pages (streaming approach)
                pages, total_usage = self._process_pdf_pages(filepath)

                # Add pages to result
                result["total_pages"] = len(pages)
                result["pages"] = pages

                # Add total usage information
                if total_usage["total_tokens"] > 0:
                    result["_usage"] = total_usage

                return result

        except Exception as e:
            error_msg = f"Failed to process file: {str(e)}"
            logger.error(error_msg)

            # Check for specific error types
            if "api_key" in str(e).lower():
                raise ConfigurationError("Invalid API key")
            elif "rate" in str(e).lower():
                raise APIError("Rate limit exceeded. Please try again later.")
            elif "timeout" in str(e).lower():
                raise APIError("Request timed out. Please try again.")
            else:
                raise APIError(error_msg)


# Auto-register with factory
IngestionFactory.register("openai", OpenAIVisionIngestion)
