# intake/processors/content_support/handlers/pdf/strategies/page_processor.py
# PDF page rendering and processing utilities
# Handles conversion of PDF pages to images for Vision API

import io
import base64
import logging
from typing import Optional


class PageProcessor:
    """Handles PDF page rendering and image conversion."""

    def __init__(self, render_scale: float = 2.0):
        """
        Initialize page processor.

        Args:
            render_scale: Scale factor for rendering PDF pages
        """
        self.render_scale = render_scale
        self.logger = logging.getLogger(__name__)

    def render_page_to_base64(self, page, format: str = "PNG") -> str:
        """
        Render a PDF page to base64-encoded image.

        Args:
            page: PDF page object (from pypdfium2)
            format: Image format (PNG, JPEG)

        Returns:
            Base64-encoded image string
        """
        try:
            # Render page to bitmap
            bitmap = page.render(scale=self.render_scale)

            # Convert to PIL image
            pil_image = bitmap.to_pil()

            # Convert to base64
            buffered = io.BytesIO()
            pil_image.save(buffered, format=format)
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            return img_base64

        except Exception as e:
            self.logger.error(f"Failed to render PDF page: {str(e)}")
            raise

    def render_page_to_pil(self, page):
        """
        Render a PDF page to PIL Image.

        Args:
            page: PDF page object

        Returns:
            PIL Image object
        """
        try:
            bitmap = page.render(scale=self.render_scale)
            return bitmap.to_pil()
        except Exception as e:
            self.logger.error(f"Failed to render page to PIL: {str(e)}")
            raise

    def get_page_dimensions(self, page) -> dict:
        """
        Get dimensions of a PDF page.

        Args:
            page: PDF page object

        Returns:
            Dictionary with width and height
        """
        try:
            width = page.get_width()
            height = page.get_height()
            return {
                "width": width,
                "height": height,
                "aspect_ratio": width / height if height > 0 else 0
            }
        except Exception as e:
            self.logger.error(f"Failed to get page dimensions: {str(e)}")
            return {"width": 0, "height": 0, "aspect_ratio": 0}