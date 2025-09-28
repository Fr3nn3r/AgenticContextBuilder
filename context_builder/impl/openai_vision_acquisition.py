"""OpenAI Vision API implementation for data acquisition."""

import base64
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List
from io import BytesIO

from context_builder.acquisition import (
    DataAcquisition,
    APIError,
    ConfigurationError,
    AcquisitionFactory,
)
from context_builder.utils.file_utils import get_file_metadata

logger = logging.getLogger(__name__)


class OpenAIVisionAcquisition(DataAcquisition):
    """OpenAI Vision API implementation for document context extraction."""

    DEFAULT_PROMPT = """Analyze this document/page and extract structured information.

Your task is to:
1. Extract all visible text content
2. Identify the document/page type (invoice, report, form, letter, etc.)
3. Extract key information and metadata
4. Note any important visual elements

Respond with a JSON structure containing:
{
  "document_type": "type of page/document",
  "language": "primary language of the document",
  "summary": "brief summary of the page content",
  "key_information": {
    // Relevant key-value pairs based on document type
  },
  "visual_elements": [
    // List of notable visual elements (logos, charts, signatures, etc.)
  ],
  "text_content": "all extracted text from the page"
}"""

    def __init__(self):
        """Initialize OpenAI Vision acquisition."""
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

        # Configuration with default values (can be modified after instantiation)
        self.model = "gpt-4o"
        self.max_tokens = 4096
        self.temperature = 0.2
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

    def _process_pdf_pages(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Process PDF pages one by one to minimize memory usage.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of extracted content dictionaries for each page

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

                    page_messages = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Page {page_index + 1} of {pages_to_process}\n\n{self.DEFAULT_PROMPT}",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}"
                                    },
                                },
                            ],
                        }
                    ]

                    # Call API with retry logic
                    response = self._call_api_with_retry(page_messages)

                    # Parse and store result
                    page_result = self._parse_response(response.choices[0].message.content)
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

    def _prepare_messages(self, file_path: Path) -> list:
        """
        Prepare messages for OpenAI API call (for image files only).

        Args:
            file_path: Path to image file

        Returns:
            List of message dictionaries
        """
        extension = file_path.suffix.lower()

        # For image files, encode and prepare message
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

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": self.DEFAULT_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        },
                    },
                ],
            }
        ]

        return messages

    def _call_api_with_retry(self, messages: list, attempt: int = 0) -> Any:
        """
        Call OpenAI API with retry logic and exponential backoff.

        Args:
            messages: Messages to send to API
            attempt: Current retry attempt number

        Returns:
            API response object

        Raises:
            APIError: If all retries exhausted
        """
        try:
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

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse API response to extract JSON.

        Args:
            response_text: Raw response text from API

        Returns:
            Parsed JSON dictionary

        Raises:
            APIError: If response cannot be parsed
        """
        import json

        # Try to parse as JSON
        try:
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

            # Return as text content if JSON parsing fails
            return {
                "document_type": "unknown",
                "language": "unknown",
                "summary": "Failed to parse structured response",
                "key_information": {},
                "visual_elements": [],
                "text_content": response_text,
                "_parse_error": str(e),
            }

    def _process_implementation(self, filepath: Path) -> Dict[str, Any]:
        """
        Process file using OpenAI Vision API.

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
                messages = self._prepare_messages(filepath)

                # Call OpenAI API with retry logic
                logger.debug(f"Calling OpenAI API with model: {self.model}")
                response = self._call_api_with_retry(messages)

                # Parse response
                page_content = self._parse_response(response.choices[0].message.content)

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
AcquisitionFactory.register("openai", OpenAIVisionAcquisition)
