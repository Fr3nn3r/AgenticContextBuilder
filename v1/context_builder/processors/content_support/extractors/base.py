# intake/processors/content_support/extractors/base.py
# Base extraction strategy interface for all content extraction methods

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class PageExtractionResult:
    """Result from extracting a single page."""
    page_number: int
    status: str  # success | unreadable_content | error
    content: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ExtractionResult:
    """Complete extraction result for a method."""
    method: str
    status: str  # success | partial_success | error | skipped
    pages: List[PageExtractionResult]
    error: Optional[str] = None
    total_processing_time: Optional[float] = None


class ExtractionStrategy(ABC):
    """Base class for all extraction strategies."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize extraction strategy with configuration."""
        self.config = config or {}
        self._setup()

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this extraction method."""
        pass

    @property
    @abstractmethod
    def supports_file_types(self) -> List[str]:
        """List of supported file types (e.g., ['pdf', 'image'])."""
        pass

    @property
    @abstractmethod
    def supports_batch_processing(self) -> bool:
        """Whether this method can process multiple pages at once."""
        pass

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this method requires an API key."""
        pass

    @property
    @abstractmethod
    def max_file_size_mb(self) -> float:
        """Maximum file size this method can handle in MB."""
        pass

    @abstractmethod
    def _setup(self) -> None:
        """Setup method called during initialization."""
        pass

    @abstractmethod
    def validate_requirements(self) -> Tuple[bool, Optional[str]]:
        """
        Check if method requirements are met (libraries, API keys, etc).

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    @abstractmethod
    def extract_page(self, file_path: Path, page_num: int, total_pages: int) -> PageExtractionResult:
        """
        Extract content from a single page.

        Args:
            file_path: Path to the file
            page_num: Page number to extract (1-indexed)
            total_pages: Total number of pages in the document

        Returns:
            PageExtractionResult with extraction details
        """
        pass

    @abstractmethod
    def get_total_pages(self, file_path: Path) -> int:
        """
        Get total number of pages in the file.

        Args:
            file_path: Path to the file

        Returns:
            Total number of pages (1 for non-paginated files like images)
        """
        pass

    def can_handle(self, file_path: Path) -> bool:
        """
        Check if this strategy can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if the strategy can handle this file
        """
        # Check file type
        file_ext = file_path.suffix.lower().lstrip('.')

        # Map common extensions to file types
        type_mapping = {
            'pdf': 'pdf',
            'jpg': 'image',
            'jpeg': 'image',
            'png': 'image',
            'gif': 'image',
            'bmp': 'image',
            'tiff': 'image',
            'webp': 'image',
            'docx': 'document',
            'doc': 'document'
        }

        file_type = type_mapping.get(file_ext)
        if not file_type or file_type not in self.supports_file_types:
            return False

        # Check file size
        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                return False
        except:
            return False

        return True

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract content from the entire file.

        Args:
            file_path: Path to the file

        Returns:
            ExtractionResult with all pages
        """
        import time

        # Validate requirements first
        is_valid, error_msg = self.validate_requirements()
        if not is_valid:
            return ExtractionResult(
                method=self.name,
                status="skipped",
                pages=[],
                error=error_msg
            )

        # Check if we can handle this file
        if not self.can_handle(file_path):
            return ExtractionResult(
                method=self.name,
                status="skipped",
                pages=[],
                error=f"Cannot handle file type or size for {file_path.name}"
            )

        # Get total pages
        try:
            total_pages = self.get_total_pages(file_path)
        except Exception as e:
            return ExtractionResult(
                method=self.name,
                status="error",
                pages=[],
                error=f"Failed to get page count: {str(e)}"
            )

        # Extract each page
        pages = []
        total_time = 0
        success_count = 0
        error_count = 0
        unreadable_count = 0

        for page_num in range(1, total_pages + 1):
            if total_pages > 1:
                logger.info(f"Processing page {page_num}/{total_pages} with {self.name}...")
            start_time = time.time()
            try:
                page_result = self.extract_page(file_path, page_num, total_pages)
                page_result.processing_time = time.time() - start_time
                pages.append(page_result)

                # Track status counts
                if page_result.status == "success":
                    success_count += 1
                elif page_result.status == "unreadable_content":
                    unreadable_count += 1
                else:
                    error_count += 1

                total_time += page_result.processing_time

            except Exception as e:
                pages.append(PageExtractionResult(
                    page_number=page_num,
                    status="error",
                    error=str(e),
                    processing_time=time.time() - start_time
                ))
                error_count += 1
                total_time += time.time() - start_time

        # Determine overall status
        # Status hierarchy:
        # - success: All pages processed successfully (including unreadable_content)
        # - partial_success: Some pages succeeded, some failed
        # - error: All pages failed
        if error_count == 0:
            status = "success"
        elif success_count > 0 or unreadable_count > 0:
            status = "partial_success"
        else:
            status = "error"

        return ExtractionResult(
            method=self.name,
            status=status,
            pages=pages,
            total_processing_time=total_time
        )