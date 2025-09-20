# intake/processors/content_support/handlers.py
# File type handlers for content processing
# Implements strategy pattern for different file type processing

import os
import json
import base64
import logging
import mimetypes
import io
import time
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

import pandas as pd
import pypdfium2 as pdfium
from PIL import Image
from openai import OpenAI

from .models import FileContentOutput, ProcessingInfo, ContentAnalysis, ContentProcessorError
from .prompt_manager import PromptManager


def process_pdf_with_unstructured(pdf_path: str, languages: Optional[List[str]] = None) -> str:
    """
    Extract text from PDF using unstructured library.

    Args:
        pdf_path: Path to the PDF file
        languages: List of languages to use for OCR (e.g., ['eng', 'spa'])

    Returns:
        Extracted text content

    Raises:
        Exception: If PDF processing fails
    """
    try:
        from unstructured.partition.pdf import partition_pdf

        # Default to English and Spanish for Ecuador documents
        if languages is None:
            languages = ['eng', 'spa']  # English and Spanish

        # Partition the PDF into elements with specified languages
        elements = partition_pdf(pdf_path, languages=languages)

        # Extract text from all elements
        text_content = []
        for element in elements:
            if hasattr(element, 'text') and element.text:
                text_content.append(element.text)

        return '\n'.join(text_content)

    except Exception as e:
        raise Exception(f"PDF text extraction failed: {str(e)}")


class BaseContentHandler(ABC):
    """
    Abstract base class for file type handlers.

    Each handler implements specific logic for processing a particular
    file type using AI models and returning structured context.
    """

    def __init__(self, openai_client: Optional[OpenAI], prompt_manager: PromptManager, config: Dict[str, Any]):
        """
        Initialize the handler with dependencies.

        Args:
            openai_client: OpenAI client for API calls
            prompt_manager: Prompt management instance
            config: Handler-specific configuration
        """
        self.openai_client = openai_client
        self.prompt_manager = prompt_manager
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """
        Determine if this handler can process the given file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if this handler can process the file, False otherwise
        """
        pass

    @abstractmethod
    def process(self, file_path: Path, existing_metadata: Optional[Dict[str, Any]] = None) -> FileContentOutput:
        """
        Process the file and extract AI-powered context.

        Args:
            file_path: Path to the file to process
            existing_metadata: Any existing metadata from previous processors

        Returns:
            FileContentOutput containing the processing results

        Raises:
            ContentProcessorError: If processing fails
        """
        pass

    def _clean_json_response(self, response: str) -> str:
        """
        Clean JSON response by removing markdown code blocks.

        Args:
            response: Raw response that might contain markdown code blocks

        Returns:
            Cleaned JSON string
        """
        cleaned = response.strip()

        # Remove markdown code blocks
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]  # Remove ```json
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]  # Remove ```

        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]  # Remove trailing ```

        return cleaned.strip()

    def _create_processing_info(self, status: str, ai_model: Optional[str] = None,
                              prompt_version: Optional[str] = None, error_message: Optional[str] = None,
                              processing_time: Optional[float] = None) -> ProcessingInfo:
        """
        Create standardized processing information.

        Args:
            status: Processing status (success, partial_success, error)
            ai_model: AI model used for processing
            prompt_version: Version of prompt used
            error_message: Error message if processing failed
            processing_time: Time taken for processing in seconds

        Returns:
            ProcessingInfo object
        """
        return ProcessingInfo(
            processor_version="1.0.0",
            ai_model_used=ai_model,
            processing_status=status,
            prompt_version=prompt_version,
            error_message=error_message,
            processing_time_seconds=processing_time
        )

    def _make_openai_request(self, prompt: str, image_base64: Optional[str] = None,
                           model: str = "gpt-4o", max_tokens: int = 2048,
                           temperature: float = 0.1) -> str:
        """
        Make a request to OpenAI API with error handling.

        Args:
            prompt: Text prompt for the AI
            image_base64: Optional base64-encoded image
            model: AI model to use
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation

        Returns:
            AI response text

        Raises:
            ContentProcessorError: If API call fails
        """
        if not self.openai_client:
            raise ContentProcessorError(
                "OpenAI client not available - check API key configuration",
                error_type="client_not_available"
            )

        try:
            messages = []

            if image_base64:
                # Vision API request
                content = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    }
                ]
                messages.append({"role": "user", "content": content})
            else:
                # Text-only request
                messages.append({"role": "user", "content": prompt})

            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            return response.choices[0].message.content

        except Exception as e:
            raise ContentProcessorError(
                f"OpenAI API request failed: {str(e)}",
                error_type="api_request_failed",
                original_error=e
            )


class TextContentHandler(BaseContentHandler):
    """Handler for text-based files (txt, json, csv, py, js, etc.)."""

    SUPPORTED_EXTENSIONS = {'.txt', '.json', '.md', '.xml', '.html', '.py', '.js', '.css', '.yaml', '.yml'}

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported text type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(self, file_path: Path, existing_metadata: Optional[Dict[str, Any]] = None) -> FileContentOutput:
        """Process text file and extract content."""
        import time
        start_time = time.time()

        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Truncate if too long (to avoid token limits)
            max_chars = 8000  # Rough estimate for token limits
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[... content truncated ...]"

            # Get the active prompt (which will use the active version)
            prompt_name = "text_analysis"
            prompt_config = self.prompt_manager.get_active_prompt(prompt_name)
            prompt_version = self.prompt_manager.get_active_version(prompt_name)

            if not prompt_config or not prompt_version:
                raise ContentProcessorError(
                    f"Prompt '{prompt_name}' not found",
                    error_type="prompt_not_found"
                )

            # Check if we should expect JSON output
            use_json = prompt_config.output_format == "json"

            # Get AI analysis using prompt
            prompt_template = self.prompt_manager.get_prompt_template(
                prompt_name,
                content=content
            )

            ai_response = self._make_openai_request(
                prompt_template,
                model=prompt_config.model,
                max_tokens=prompt_config.max_tokens,
                temperature=prompt_config.temperature
            )

            processing_time = time.time() - start_time

            # Parse JSON response if using JSON prompt
            extracted_data = None
            text_summary = ai_response
            if use_json:
                try:
                    import json
                    # Clean the response to remove markdown code blocks
                    cleaned_response = self._clean_json_response(ai_response)
                    extracted_data = json.loads(cleaned_response)
                    # Create a text summary from the JSON data
                    if isinstance(extracted_data, dict):
                        text_summary = extracted_data.get('summary', ai_response)
                except json.JSONDecodeError as e:
                    # If JSON parsing fails, treat as regular text
                    self.logger.warning(f"Failed to parse JSON response for {file_path}: {str(e)}")
                    # Print response for debugging
                    print(f"\n[JSON PARSE WARNING] Failed to parse response for text file {file_path.name}")
                    print(f"Error: {str(e)}")
                    print(f"Response that failed to parse:")
                    print("-" * 80)
                    print(ai_response[:1000] if len(ai_response) > 1000 else ai_response)
                    if len(ai_response) > 1000:
                        print(f"... (truncated, total length: {len(ai_response)} characters)")
                    print("-" * 80)
                    extracted_data = None

            # Create content metadata (renamed from content_analysis)
            content_metadata = ContentAnalysis(
                content_type="text",
                file_category="text_document",
                summary=text_summary if use_json and extracted_data else f"Text file with {len(content)} characters",
                detected_language=extracted_data.get('language') if extracted_data else None
            )

            # Create processing info
            processing_info = self._create_processing_info(
                status="success",
                ai_model=prompt_config.model,
                prompt_version=prompt_version,
                processing_time=processing_time
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata,  # Renamed from content_analysis
                data_content=extracted_data,  # Renamed from extracted_data
                data_summary=text_summary,  # Renamed from text_summary
                data_text_content=content  # Renamed from raw_content, type-specific field
            )

        except Exception as e:
            processing_time = time.time() - start_time
            processing_info = self._create_processing_info(
                status="error",
                error_message=str(e),
                processing_time=processing_time
            )

            content_metadata = ContentAnalysis(
                content_type="text",
                file_category="text_document"
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata  # Renamed from content_analysis
            )


class ImageContentHandler(BaseContentHandler):
    """Handler for image files using OpenAI Vision API."""

    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported image type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(self, file_path: Path, existing_metadata: Optional[Dict[str, Any]] = None) -> FileContentOutput:
        """Process image file using Vision API."""
        import time
        start_time = time.time()

        try:
            # Convert image to base64
            with open(file_path, 'rb') as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

            # Get AI analysis using vision prompt
            prompt_template = self.prompt_manager.get_prompt_template("universal_document")
            prompt_config = self.prompt_manager.get_prompt("universal_document")
            prompt_version = self.prompt_manager.get_active_version("universal_document") or "1.0.0"

            ai_response = self._make_openai_request(
                prompt_template,
                image_base64=image_base64,
                model=prompt_config.model,
                max_tokens=prompt_config.max_tokens,
                temperature=prompt_config.temperature
            )

            processing_time = time.time() - start_time

            # Create content metadata (renamed from content_analysis)
            content_metadata = ContentAnalysis(
                content_type="image",
                file_category="image",
                summary="AI-analyzed image content"
            )

            # Create processing info
            processing_info = self._create_processing_info(
                status="success",
                ai_model=prompt_config.model,
                prompt_version=prompt_version,
                processing_time=processing_time
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata,  # Renamed from content_analysis
                data_content={"description": ai_response},  # Store AI analysis as structured data
                data_summary=ai_response,  # Also store as summary
                data_image_content=image_base64  # Store base64 image in type-specific field
            )

        except Exception as e:
            processing_time = time.time() - start_time
            processing_info = self._create_processing_info(
                status="error",
                error_message=str(e),
                processing_time=processing_time
            )

            content_metadata = ContentAnalysis(
                content_type="image",
                file_category="image"
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata  # Renamed from content_analysis
            )


class PDFContentHandler(BaseContentHandler):
    """Handler for PDF files with OCR and Vision API fallback."""

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a PDF."""
        return file_path.suffix.lower() == '.pdf'

    def process(self, file_path: Path, existing_metadata: Optional[Dict[str, Any]] = None) -> FileContentOutput:
        """Process PDF using OCR with Vision API fallback."""
        import time
        start_time = time.time()

        try:
            # Try OCR first, then fallback to Vision API if needed
            if self.config.get('enable_ocr_fallback', True):
                try:
                    # Get OCR languages from config
                    ocr_languages = self.config.get('ocr_languages', ['eng', 'spa'])

                    # Use unstructured library for PDF text extraction with configured languages
                    ocr_text = process_pdf_with_unstructured(str(file_path), languages=ocr_languages)

                    # Check if OCR text is meaningful
                    if self._is_ocr_meaningful(ocr_text):
                        # Use text analysis on OCR result
                        return self._process_pdf_text(file_path, ocr_text, start_time)
                except Exception as e:
                    self.logger.warning(f"OCR failed for {file_path}: {e}, falling back to Vision API")

            # Fallback to Vision API processing
            return self._process_pdf_with_vision(file_path, start_time)

        except Exception as e:
            processing_time = time.time() - start_time
            processing_info = self._create_processing_info(
                status="error",
                error_message=str(e),
                processing_time=processing_time
            )

            content_metadata = ContentAnalysis(
                content_type="document",
                file_category="pdf"
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata  # Renamed from content_analysis
            )

    def _is_ocr_meaningful(self, text: str) -> bool:
        """Check if OCR text contains meaningful content."""
        clean_text = text.strip()
        if not clean_text or len(clean_text) < 50:
            return False

        # Check ratio of alphanumeric characters
        alphanum_chars = sum(c.isalnum() for c in clean_text)
        total_chars = len(clean_text)

        return total_chars > 0 and (alphanum_chars / total_chars) >= 0.6

    def _process_pdf_text(self, file_path: Path, text_content: str, start_time: float) -> FileContentOutput:
        """Process PDF using extracted text content."""
        # Truncate if too long
        max_chars = 8000
        original_text = text_content
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n[... content truncated ...]"

        # Get AI analysis
        prompt_template = self.prompt_manager.get_prompt_template(
            "text_analysis",
            content=text_content
        )

        prompt_config = self.prompt_manager.get_prompt("text_analysis")
        prompt_version = self.prompt_manager.get_active_version("text_analysis") or "1.0.0"
        ai_response = self._make_openai_request(
            prompt_template,
            model=prompt_config.model,
            max_tokens=prompt_config.max_tokens,
            temperature=prompt_config.temperature
        )

        processing_time = time.time() - start_time

        # Check if we should expect JSON output and parse it
        use_json = prompt_config.output_format == "json"
        parsed_analysis = None
        summary = ai_response

        if use_json:
            # Check for empty or whitespace-only response
            if not ai_response or not ai_response.strip():
                self.logger.warning(f"Empty response from OpenAI API for PDF {file_path}, treating as non-JSON")
                use_json = False
                summary = "Empty response from AI analysis"
            else:
                try:
                    import json
                    # Clean the response to remove markdown code blocks
                    cleaned_response = self._clean_json_response(ai_response)
                    parsed_analysis = json.loads(cleaned_response)
                    # Extract summary from parsed JSON if available
                    if isinstance(parsed_analysis, dict):
                        summary = parsed_analysis.get('summary', ai_response)
                        self.logger.debug(f"Successfully parsed JSON response for PDF: {file_path}")
                except json.JSONDecodeError as e:
                    # If JSON parsing fails when expected, log the full response for debugging
                    error_msg = f"Failed to parse JSON response from OpenAI API for PDF {file_path}: {str(e)}"
                    self.logger.error(error_msg)
                    # Print full response for debugging (not just to log)
                    print(f"\n[JSON PARSE ERROR] Failed to parse response for {file_path.name}")
                    print(f"Error: {str(e)}")
                    print(f"Response that failed to parse:")
                    print("-" * 80)
                    print(ai_response[:1000] if len(ai_response) > 1000 else ai_response)
                    if len(ai_response) > 1000:
                        print(f"... (truncated, total length: {len(ai_response)} characters)")
                    print("-" * 80)
                    raise ContentProcessorError(
                        error_msg,
                        error_type="json_parsing_error",
                        original_error=e
                    )

        content_metadata = ContentAnalysis(
            content_type="document",
            file_category="pdf",
            summary=summary if use_json else "PDF processed via OCR",
            detected_language=parsed_analysis.get('language') if parsed_analysis else None
        )

        processing_info = self._create_processing_info(
            status="success",
            ai_model=prompt_config.model,
            prompt_version=prompt_version,
            processing_time=processing_time
        )

        # Structure the data_content based on whether we have parsed JSON
        if parsed_analysis:
            # Include the parsed JSON analysis
            data_content = parsed_analysis
        else:
            # Include text and raw analysis
            data_content = {"text": original_text[:max_chars], "analysis": ai_response}

        return FileContentOutput(
            processing_info=processing_info,
            content_metadata=content_metadata,  # Renamed from content_analysis
            data_content=data_content,  # Now includes parsed JSON when available
            data_summary=summary,  # Extracted summary
            data_pdf_content=original_text  # Full original text content
        )

    def _process_pdf_with_vision(self, file_path: Path, start_time: float) -> FileContentOutput:
        """Process PDF using Vision API on rendered pages."""
        results = []

        try:
            pdf_doc = pdfium.PdfDocument(file_path)
            prompt_config = self.prompt_manager.get_prompt("universal_document")
            prompt_version = self.prompt_manager.get_active_version("universal_document") or "1.0.0"

            # Process each page (limit to first 3 pages for performance)
            max_pages = min(3, len(pdf_doc))
            for i in range(max_pages):
                page = pdf_doc[i]

                # Render page to image
                bitmap = page.render(scale=2)
                pil_image = bitmap.to_pil()

                # Convert to base64
                buffered = io.BytesIO()
                pil_image.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

                # Analyze with Vision API
                prompt_template = self.prompt_manager.get_prompt_template("universal_document")
                ai_response = self._make_openai_request(
                    prompt_template,
                    image_base64=img_base64,
                    model=prompt_config.model,
                    max_tokens=prompt_config.max_tokens,
                    temperature=prompt_config.temperature
                )

                # Parse JSON if expected
                use_json = prompt_config.output_format == "json"
                if use_json and ai_response:
                    try:
                        import json
                        # Clean the response to remove markdown code blocks
                        cleaned_response = self._clean_json_response(ai_response)
                        parsed_response = json.loads(cleaned_response)
                        results.append({
                            "page": i + 1,
                            "analysis": parsed_response  # Store parsed JSON
                        })
                    except json.JSONDecodeError as e:
                        # If JSON parsing fails when expected, log the full response for debugging
                        error_msg = f"Failed to parse JSON from Vision API for PDF page {i+1}: {str(e)}"
                        self.logger.error(error_msg)
                        # Print full response for debugging
                        print(f"\n[JSON PARSE ERROR] Failed to parse Vision API response for page {i+1}")
                        print(f"Error: {str(e)}")
                        print(f"Response that failed to parse:")
                        print("-" * 80)
                        print(ai_response[:1000] if len(ai_response) > 1000 else ai_response)
                        if len(ai_response) > 1000:
                            print(f"... (truncated, total length: {len(ai_response)} characters)")
                        print("-" * 80)
                        raise ContentProcessorError(
                            error_msg,
                            error_type="json_parsing_error",
                            original_error=e
                        )
                else:
                    results.append({
                        "page": i + 1,
                        "analysis": ai_response  # Store raw response
                    })

            processing_time = time.time() - start_time

            content_metadata = ContentAnalysis(
                content_type="document",
                file_category="pdf",
                summary=f"PDF processed via Vision API ({max_pages} pages)"
            )

            processing_info = self._create_processing_info(
                status="success",
                ai_model=prompt_config.model,
                prompt_version=prompt_version,
                processing_time=processing_time
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata,  # Renamed from content_analysis
                data_content={"pages": results},  # Renamed from extracted_data
                data_summary=f"PDF with {len(results)} analyzed pages",  # Add summary
                data_pdf_content=str(results)  # Store page analyses in type-specific field
            )

        except Exception as e:
            raise ContentProcessorError(
                f"Vision API processing failed: {str(e)}",
                error_type="vision_processing_failed",
                original_error=e
            )


class SheetContentHandler(BaseContentHandler):
    """Handler for spreadsheet files (CSV, Excel)."""

    SUPPORTED_EXTENSIONS = {'.csv', '.xls', '.xlsx'}

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported spreadsheet type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(self, file_path: Path, existing_metadata: Optional[Dict[str, Any]] = None) -> FileContentOutput:
        """Process spreadsheet file."""
        import time
        start_time = time.time()

        try:
            # Read spreadsheet data
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            # Convert to JSON for AI analysis
            json_data = df.to_json(orient="records")

            # Truncate if too large
            max_chars = 6000
            if len(json_data) > max_chars:
                json_data = json_data[:max_chars] + "\n[... data truncated ...]"

            # Get the active prompt (which will use the active version)
            prompt_name = "spreadsheet_analysis"
            prompt_config = self.prompt_manager.get_active_prompt(prompt_name)
            prompt_version = self.prompt_manager.get_active_version(prompt_name)

            if not prompt_config or not prompt_version:
                raise ContentProcessorError(
                    f"Prompt '{prompt_name}' not found",
                    error_type="prompt_not_found"
                )

            # Check if we should expect JSON output
            use_json = prompt_config.output_format == "json"

            # Get AI analysis
            prompt_template = self.prompt_manager.get_prompt_template(
                prompt_name,
                content=json_data
            )

            ai_response = self._make_openai_request(
                prompt_template,
                model=prompt_config.model,
                max_tokens=prompt_config.max_tokens,
                temperature=prompt_config.temperature
            )

            processing_time = time.time() - start_time

            # Parse JSON response if using JSON prompt
            structured_analysis = None
            text_summary = ai_response
            structured_data = df.to_dict('records') if len(df) <= 100 else []

            if use_json:
                try:
                    import json
                    # Clean the response to remove markdown code blocks
                    cleaned_response = self._clean_json_response(ai_response)
                    structured_analysis = json.loads(cleaned_response)
                    # Create a text summary from the JSON data
                    if isinstance(structured_analysis, dict):
                        text_summary = structured_analysis.get('summary', ai_response)
                        # Merge the AI analysis into structured_data if it's a dict
                        if not structured_data:  # If we didn't include raw data due to size
                            structured_data = [structured_analysis]  # Wrap in list as expected by model
                except json.JSONDecodeError as e:
                    # If JSON parsing fails, treat as regular text
                    self.logger.warning(f"Failed to parse JSON response for {file_path}: {str(e)}")
                    # Print response for debugging
                    print(f"\n[JSON PARSE WARNING] Failed to parse response for spreadsheet {file_path.name}")
                    print(f"Error: {str(e)}")
                    print(f"Response that failed to parse:")
                    print("-" * 80)
                    print(ai_response[:1000] if len(ai_response) > 1000 else ai_response)
                    if len(ai_response) > 1000:
                        print(f"... (truncated, total length: {len(ai_response)} characters)")
                    print("-" * 80)
                    structured_analysis = None

            content_metadata = ContentAnalysis(
                content_type="spreadsheet",
                file_category="spreadsheet",
                summary=text_summary if use_json and structured_analysis else f"Spreadsheet with {len(df)} rows and {len(df.columns)} columns"
            )

            processing_info = self._create_processing_info(
                status="success",
                ai_model=prompt_config.model,
                prompt_version=prompt_version,
                processing_time=processing_time
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata,  # Renamed from content_analysis
                data_content=structured_analysis,  # Renamed from extracted_data
                data_summary=text_summary,  # Renamed from text_summary
                data_spreadsheet_content=json_data  # Renamed from raw_content, type-specific field
            )

        except Exception as e:
            processing_time = time.time() - start_time
            processing_info = self._create_processing_info(
                status="error",
                error_message=str(e),
                processing_time=processing_time
            )

            content_metadata = ContentAnalysis(
                content_type="spreadsheet",
                file_category="spreadsheet"
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata  # Renamed from content_analysis
            )


class DocumentContentHandler(BaseContentHandler):
    """Handler for document files (docx, doc) via conversion to images."""

    SUPPORTED_EXTENSIONS = {'.docx', '.doc'}

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported document type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(self, file_path: Path, existing_metadata: Optional[Dict[str, Any]] = None) -> FileContentOutput:
        """Process document by converting to images and using Vision API."""
        import time
        start_time = time.time()

        try:
            # Convert document to PDF first, then process with Vision API
            # This reuses the pattern from generate_context.py

            results = self._convert_and_analyze_document(file_path)

            processing_time = time.time() - start_time

            content_metadata = ContentAnalysis(
                content_type="document",
                file_category="office_document",
                summary="Document processed via Vision API conversion"
            )

            processing_info = self._create_processing_info(
                status="success" if results else "error",
                ai_model="gpt-4o",
                processing_time=processing_time,
                error_message="Conversion failed" if not results else None
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata,  # Renamed from content_analysis
                data_content={"document_analysis": results} if results else None,  # Renamed from extracted_data
                data_summary="Document analyzed via Vision API" if results else "Document processing failed",
                data_document_content=str(results) if results else None  # Type-specific field
            )

        except Exception as e:
            processing_time = time.time() - start_time
            processing_info = self._create_processing_info(
                status="error",
                error_message=str(e),
                processing_time=processing_time
            )

            content_metadata = ContentAnalysis(
                content_type="document",
                file_category="office_document"
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata  # Renamed from content_analysis
            )

    def _convert_and_analyze_document(self, file_path: Path) -> List[Dict[str, Any]]:
        """Convert document to images and analyze with Vision API."""
        temp_pdf = None

        try:
            if file_path.suffix.lower() == '.docx':
                # Create temporary PDF
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                    temp_pdf = temp_file.name

                # Convert docx to PDF
                from docx2pdf import convert as docx_to_pdf
                docx_to_pdf(str(file_path), temp_pdf)

                # Process PDF with Vision API (reuse PDF handler logic)
                if os.path.exists(temp_pdf) and os.path.getsize(temp_pdf) > 0:
                    pdf_handler = PDFContentHandler(self.openai_client, self.prompt_manager, self.config)
                    result = pdf_handler._process_pdf_with_vision(Path(temp_pdf), 0)
                    return result.extracted_data.get("pages", []) if result.extracted_data else []

            return [{"error": "Unsupported document format or conversion failed"}]

        except Exception as e:
            self.logger.error(f"Document conversion failed: {e}")
            return [{"error": f"Document conversion failed: {str(e)}"}]

        finally:
            # Clean up temporary file
            if temp_pdf and os.path.exists(temp_pdf):
                try:
                    os.unlink(temp_pdf)
                except Exception:
                    pass  # Ignore cleanup errors