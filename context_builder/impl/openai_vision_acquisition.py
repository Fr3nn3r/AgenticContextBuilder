"""OpenAI Vision API implementation for data acquisition."""

import base64
import hashlib
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from io import BytesIO

from context_builder.acquisition import (
    DataAcquisition,
    APIError,
    ConfigurationError,
    AcquisitionFactory,
)

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

            self.client = OpenAI(api_key=self.api_key)
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

    def _calculate_md5(self, file_path: Path) -> str:
        """
        Calculate MD5 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            MD5 hash as hexadecimal string
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to calculate MD5: {e}")
            return ""

    def _get_file_metadata(self, filepath: Path) -> Dict[str, Any]:
        """
        Get file metadata.

        Args:
            filepath: Path to file

        Returns:
            Dictionary with file metadata
        """
        absolute_path = filepath.resolve()
        mime_type, _ = mimetypes.guess_type(str(filepath))

        return {
            "file_name": filepath.name,
            "file_path": str(absolute_path),
            "file_extension": filepath.suffix.lower(),
            "file_size_bytes": filepath.stat().st_size,
            "mime_type": mime_type or "application/octet-stream",
            "md5": self._calculate_md5(filepath),
        }

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

    def _convert_pdf_to_images(self, pdf_path: Path) -> List:
        """
        Convert PDF pages to images using pypdfium2 for high quality rendering.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of PIL Image objects

        Raises:
            IOError: If PDF cannot be converted
        """
        try:
            import pypdfium2 as pdfium
            from PIL import Image

            logger.info(f"Converting PDF to images with pypdfium2: {pdf_path}")

            # Open PDF document
            pdf_doc = pdfium.PdfDocument(pdf_path)
            images = []

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
                    page = pdf_doc[page_index]

                    # Render at high quality (configurable scale factor for better extraction)
                    mat = page.render(scale=self.render_scale)

                    # Convert to PIL Image
                    img = mat.to_pil()
                    images.append(img)

                    logger.debug(
                        f"Converted page {page_index + 1}/{pages_to_process} to image (scale={self.render_scale})"
                    )

                logger.info(f"Successfully converted {len(images)} pages from PDF")
                return images

            finally:
                # Always close the PDF document
                pdf_doc.close()

        except ImportError:
            raise ConfigurationError(
                "pypdfium2 package not installed. "
                "Please install it with: pip install pypdfium2"
            )
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            raise IOError(f"Cannot convert PDF file: {e}")

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
        result = self._get_file_metadata(filepath)

        try:
            # For non-PDF files, process directly
            if filepath.suffix.lower() != ".pdf":
                # Prepare messages
                messages = self._prepare_messages(filepath)

                # Call OpenAI API
                logger.debug(f"Calling OpenAI API with model: {self.model}")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )

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

            # For PDFs, convert to images and process page by page
            else:
                logger.info(
                    "Converting PDF to images using pypdfium2 for processing..."
                )
                # Convert PDF to images and process page by page
                images = self._convert_pdf_to_images(filepath)

                all_results = []
                total_usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }

                for i, image in enumerate(images, 1):
                    logger.info(f"Processing page {i}/{len(images)}...")

                    # Encode the image
                    base64_image = self._encode_image_from_pil(image)

                    # Prepare messages with the image
                    page_messages = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Page {i} of {len(images)}\n\n{self.DEFAULT_PROMPT}",
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

                    # Call OpenAI API for this page
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=page_messages,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        response_format={"type": "json_object"},
                    )

                    # Parse and store result
                    page_result = self._parse_response(
                        response.choices[0].message.content
                    )
                    page_result["page_number"] = i
                    all_results.append(page_result)

                    # Accumulate usage
                    if hasattr(response, "usage"):
                        total_usage["prompt_tokens"] += response.usage.prompt_tokens
                        total_usage[
                            "completion_tokens"
                        ] += response.usage.completion_tokens
                        total_usage["total_tokens"] += response.usage.total_tokens

                # Add pages to result
                result["total_pages"] = len(images)
                result["pages"] = all_results

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
