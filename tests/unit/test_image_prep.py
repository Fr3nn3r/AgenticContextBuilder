"""Tests for image preprocessing utilities (image_prep.py)."""

import io
from pathlib import Path

import pytest
from PIL import Image

from context_builder.utils.image_prep import prepare_pil_for_vision, prepare_file_for_vision


def _make_image(w: int, h: int, mode: str = "RGB", color="red") -> Image.Image:
    """Helper to create a solid-color PIL Image."""
    return Image.new(mode, (w, h), color=color)


# --- prepare_pil_for_vision ---


class TestPreparePilForVision:
    def test_small_image_not_upscaled(self):
        """Images smaller than max_dimension should keep their original size."""
        img = _make_image(800, 600)
        data, mime = prepare_pil_for_vision(img, max_dimension=2048)
        result = Image.open(io.BytesIO(data))
        assert result.size == (800, 600)

    def test_large_image_capped(self):
        """Images larger than max_dimension should be downscaled."""
        img = _make_image(4000, 3000)
        data, mime = prepare_pil_for_vision(img, max_dimension=2048)
        result = Image.open(io.BytesIO(data))
        assert max(result.size) == 2048

    def test_aspect_ratio_preserved(self):
        """Downscaled images should preserve aspect ratio."""
        img = _make_image(4000, 2000)  # 2:1 ratio
        data, _ = prepare_pil_for_vision(img, max_dimension=2048)
        result = Image.open(io.BytesIO(data))
        w, h = result.size
        assert abs(w / h - 2.0) < 0.02  # allow rounding error

    def test_rgba_converted_to_rgb(self):
        """RGBA images should be converted to RGB for JPEG."""
        img = _make_image(100, 100, mode="RGBA", color=(255, 0, 0, 128))
        data, mime = prepare_pil_for_vision(img)
        result = Image.open(io.BytesIO(data))
        assert result.mode == "RGB"
        assert mime == "image/jpeg"

    def test_output_always_jpeg(self):
        """Output should always be JPEG regardless of input."""
        img = _make_image(100, 100, mode="RGB")
        data, mime = prepare_pil_for_vision(img)
        assert mime == "image/jpeg"
        # Verify JPEG magic bytes
        assert data[:2] == b"\xff\xd8"

    def test_max_dimension_zero_disables_capping(self):
        """max_dimension=0 should skip resizing."""
        img = _make_image(5000, 4000)
        data, _ = prepare_pil_for_vision(img, max_dimension=0)
        result = Image.open(io.BytesIO(data))
        assert result.size == (5000, 4000)

    def test_quality_affects_file_size(self):
        """Lower quality should produce smaller files."""
        img = _make_image(1000, 1000)
        data_high, _ = prepare_pil_for_vision(img, jpeg_quality=95)
        data_low, _ = prepare_pil_for_vision(img, jpeg_quality=30)
        assert len(data_low) < len(data_high)

    def test_grayscale_preserved(self):
        """Grayscale (mode L) images should remain grayscale in JPEG."""
        img = _make_image(200, 200, mode="L", color=128)
        data, _ = prepare_pil_for_vision(img)
        result = Image.open(io.BytesIO(data))
        assert result.mode == "L"

    def test_palette_image_converted(self):
        """Palette (mode P) images should be converted to RGB."""
        img = _make_image(100, 100, mode="P")
        data, _ = prepare_pil_for_vision(img)
        result = Image.open(io.BytesIO(data))
        assert result.mode == "RGB"


# --- prepare_file_for_vision ---


class TestPrepareFileForVision:
    def test_file_loading(self, tmp_path: Path):
        """Should load an image file and return JPEG bytes."""
        img = _make_image(640, 480)
        file_path = tmp_path / "test.png"
        img.save(file_path, format="PNG")

        data, mime = prepare_file_for_vision(file_path)
        assert mime == "image/jpeg"
        assert data[:2] == b"\xff\xd8"

    def test_file_respects_max_dimension(self, tmp_path: Path):
        """File-based function should honour max_dimension."""
        img = _make_image(4000, 3000)
        file_path = tmp_path / "big.png"
        img.save(file_path, format="PNG")

        data, _ = prepare_file_for_vision(file_path, max_dimension=1024)
        result = Image.open(io.BytesIO(data))
        assert max(result.size) == 1024
