"""Azure Document Intelligence API implementation for data ingestion."""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any

# Ensure .env is loaded (fallback in case not loaded by main.py)
from dotenv import load_dotenv
_project_root = Path(__file__).resolve().parent.parent.parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

from context_builder.ingestion import (
    DataIngestion,
    APIError,
    ConfigurationError,
    IngestionFactory,
)
from context_builder.utils.file_utils import get_file_metadata

logger = logging.getLogger(__name__)


class AzureDocumentIntelligenceIngestion(DataIngestion):
    """
    Azure Document Intelligence API implementation for document extraction.

    This implementation uses Azure's prebuilt-layout model to extract:
    - Markdown-formatted text content (saved to separate .md file)
    - Document structure (pages, paragraphs, tables)
    - Language detection
    - OCR with high resolution

    Output format:
    - JSON metadata file with document statistics and reference to markdown file
    - Separate .md file containing the extracted text content
    """

    def __init__(self):
        """Initialize Azure Document Intelligence ingestion."""
        super().__init__()

        # Get Azure credentials from environment
        self.endpoint = os.getenv("AZURE_DI_ENDPOINT")
        self.api_key = os.getenv("AZURE_DI_API_KEY")

        # Debug: log what we found
        logger.info(f"[AzureDI] AZURE_DI_ENDPOINT from env: {self.endpoint[:30] if self.endpoint else 'NOT FOUND'}...")
        logger.info(f"[AzureDI] All env keys containing AZURE: {[k for k in os.environ.keys() if 'AZURE' in k]}")

        if not self.endpoint:
            raise ConfigurationError(
                "AZURE_DI_ENDPOINT not found in environment variables. "
                "Please set it in your .env file."
            )

        if not self.api_key:
            raise ConfigurationError(
                "AZURE_DI_API_KEY not found in environment variables. "
                "Please set it in your .env file."
            )

        # Initialize Azure DI client
        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.ai.documentintelligence import DocumentIntelligenceClient

            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key)
            )
            logger.debug("Azure Document Intelligence client initialized successfully")
        except ImportError:
            raise ConfigurationError(
                "azure-ai-documentintelligence package not installed. "
                "Please install it with: pip install azure-ai-documentintelligence"
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize Azure DI client: {e}")

        # Configuration
        self.model_id = "prebuilt-layout"
        self.timeout = 300  # 5 minutes for document processing
        self.retries = 3
        self.features = ["ocrHighResolution", "languages", "styleFont"]
        self.output_dir = None  # Output directory for markdown files (set by caller)
        self.save_markdown = True  # Save markdown file alongside JSON (default: True)

        logger.debug(
            f"Using model: {self.model_id}, features: {self.features}"
        )

    def _call_api_with_retry(self, file_bytes: bytes, attempt: int = 0) -> Any:
        """
        Call Azure DI API with retry logic and exponential backoff.

        Args:
            file_bytes: Binary content of the file to process
            attempt: Current retry attempt number

        Returns:
            Azure DI analysis result

        Raises:
            APIError: If all retries exhausted
        """
        try:
            from azure.ai.documentintelligence.models import (
                AnalyzeDocumentRequest,
                DocumentContentFormat
            )

            logger.debug(f"Calling Azure DI API with model: {self.model_id}")

            # Start analysis
            poller = self.client.begin_analyze_document(
                model_id=self.model_id,
                body=AnalyzeDocumentRequest(bytes_source=file_bytes),
                output_content_format=DocumentContentFormat.MARKDOWN,
                features=self.features,
            )

            # Wait for completion with timeout
            result = poller.result(timeout=self.timeout)
            return result

        except Exception as e:
            error_str = str(e).lower()
            is_retryable = any(
                keyword in error_str
                for keyword in ["rate", "429", "500", "502", "503", "504", "timeout", "throttl"]
            )

            if is_retryable and attempt < self.retries - 1:
                # Exponential backoff: 2^attempt * base_delay
                wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{self.retries}): {e}. "
                    f"Retrying in {wait_time} seconds..."
                )
                time.sleep(wait_time)
                return self._call_api_with_retry(file_bytes, attempt + 1)
            else:
                # Map to appropriate error type
                if "unauthorized" in error_str or "authentication" in error_str or "403" in error_str:
                    raise ConfigurationError(f"Invalid API key or endpoint: {e}")
                elif "rate" in error_str or "429" in error_str or "throttl" in error_str:
                    raise APIError(f"Rate limit exceeded after {self.retries} retries: {e}")
                elif "timeout" in error_str:
                    raise APIError(f"Request timed out after {self.retries} retries: {e}")
                else:
                    raise APIError(f"API call failed after {self.retries} retries: {e}")

    def _save_markdown(self, markdown_content: str, source_path: Path, output_dir: Path) -> str:
        """
        Save markdown content to file.

        Args:
            markdown_content: Markdown text to save
            source_path: Original source file path
            output_dir: Directory to save markdown file

        Returns:
            Relative path to the saved markdown file

        Raises:
            IOError: If file cannot be written
        """
        try:
            # Create markdown filename based on source file
            md_filename = source_path.stem + "_acquired.md"
            md_path = output_dir / md_filename

            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            # Write markdown content
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Return relative path from output directory
            return md_filename

        except Exception as e:
            logger.error(f"Failed to save markdown file: {e}")
            raise IOError(f"Cannot write markdown file: {e}")

    def _extract_metadata(self, result: Any, markdown_path: str | None, processing_time_ms: int) -> Dict[str, Any]:
        """
        Extract meaningful metadata from Azure DI result.

        Args:
            result: Azure DI analysis result
            markdown_path: Path to saved markdown file (None if not saved)
            processing_time_ms: Processing time in milliseconds

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            "model_id": self.model_id,
            "processing_time_ms": processing_time_ms,
        }

        # Only include markdown_file if it was saved
        if markdown_path:
            metadata["markdown_file"] = markdown_path

        # Extract page count
        if hasattr(result, 'pages') and result.pages:
            metadata["total_pages"] = len(result.pages)

        # Extract language (from first detected language)
        if hasattr(result, 'languages') and result.languages:
            # Get the most confident language
            primary_lang = max(result.languages, key=lambda lang: lang.confidence if hasattr(lang, 'confidence') else 0)
            metadata["language"] = primary_lang.locale if hasattr(primary_lang, 'locale') else "unknown"

        # Extract paragraph count
        if hasattr(result, 'paragraphs') and result.paragraphs:
            metadata["paragraph_count"] = len(result.paragraphs)

        # Extract table information
        if hasattr(result, 'tables') and result.tables:
            metadata["table_count"] = len(result.tables)
            metadata["tables"] = [
                {
                    "table_index": idx,
                    "row_count": table.row_count if hasattr(table, 'row_count') else 0,
                    "column_count": table.column_count if hasattr(table, 'column_count') else 0,
                }
                for idx, table in enumerate(result.tables)
            ]

        return metadata

    def _process_implementation(self, filepath: Path) -> Dict[str, Any]:
        """
        Process file using Azure Document Intelligence API.

        Args:
            filepath: Path to file to process

        Returns:
            Dictionary containing metadata and reference to markdown file

        Raises:
            APIError: If API call fails
            IOError: If file operations fail
        """
        logger.info(f"Processing with Azure Document Intelligence: {filepath}")

        # Get file metadata first
        result = get_file_metadata(filepath)

        try:
            # Read file bytes
            with open(filepath, "rb") as f:
                file_bytes = f.read()

            # Track processing time
            start_time = time.time()

            # Call Azure DI API
            di_result = self._call_api_with_retry(file_bytes)

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Get markdown content
            markdown_content = di_result.content if hasattr(di_result, 'content') else ""

            if not markdown_content:
                logger.warning("No markdown content returned from Azure DI")
                markdown_content = "# No content extracted\n\nThe document processing completed but no text content was extracted."

            # Save markdown to file if enabled
            markdown_filename = None
            if self.save_markdown:
                # Determine output directory
                # Use self.output_dir if set by caller, otherwise use source file directory
                output_dir = self.output_dir if self.output_dir else filepath.parent
                markdown_filename = self._save_markdown(markdown_content, filepath, output_dir)

            # Extract metadata
            di_metadata = self._extract_metadata(di_result, markdown_filename, processing_time_ms)

            # Merge with file metadata
            result.update(di_metadata)

            # Add full Azure DI JSON output
            result["raw_azure_di_output"] = di_result.as_dict()

            pages_processed = result.get('total_pages', 0)
            logger.info(
                f"Successfully processed {filepath.name}: "
                f"{pages_processed} pages, "
                f"{result.get('table_count', 0)} tables, "
                f"{result.get('paragraph_count', 0)} paragraphs"
            )

            # Note: Removed misleading warning about 2-page limit.
            # The free tier limit was 2 pages, but many documents genuinely have 2 pages.
            # If you suspect truncation, check the source PDF page count vs pages_processed.

            return result

        except Exception as e:
            error_msg = f"Failed to process file: {str(e)}"
            logger.error(error_msg)

            # Check for specific error types
            if "unauthorized" in str(e).lower() or "authentication" in str(e).lower():
                raise ConfigurationError("Invalid API key or endpoint")
            elif "rate" in str(e).lower() or "throttl" in str(e).lower():
                raise APIError("Rate limit exceeded. Please try again later.")
            elif "timeout" in str(e).lower():
                raise APIError("Request timed out. Please try again.")
            else:
                raise APIError(error_msg)


# Auto-register with factory
IngestionFactory.register("azure-di", AzureDocumentIntelligenceIngestion)
