"""Image preprocessing utilities for Vision API calls.

Caps resolution and applies JPEG compression before sending images
to the OpenAI Vision API, reducing payload size by 10-20x.
"""

import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import Tuple

from PIL import Image

logger = logging.getLogger(__name__)


def prepare_pil_for_vision(
    img: Image.Image,
    max_dimension: int = 2048,
    jpeg_quality: int = 85,
) -> Tuple[bytes, str]:
    """Downscale and JPEG-compress a PIL image for the Vision API.

    Args:
        img: PIL Image to prepare.
        max_dimension: Cap the longest side to this value (pixels).
            Set to 0 to disable capping (only compress).
        jpeg_quality: JPEG quality (1-100).

    Returns:
        Tuple of (raw JPEG bytes, mime type string "image/jpeg").
    """
    # --- Resize if needed (never upscale) ---
    if max_dimension > 0:
        w, h = img.size
        longest = max(w, h)
        if longest > max_dimension:
            scale = max_dimension / longest
            new_w = int(w * scale)
            new_h = int(h * scale)
            logger.info(
                "Resized image from %dx%d to %dx%d (max_dimension=%d)",
                w, h, new_w, new_h, max_dimension,
            )
            img = img.resize((new_w, new_h), Image.LANCZOS)

    # --- Convert colour mode for JPEG compatibility ---
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # alpha channel
        img = background
    elif img.mode == "P":
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # --- Save as JPEG ---
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality)
    return buf.getvalue(), "image/jpeg"


def prepare_file_for_vision(
    file_path: Path,
    max_dimension: int = 2048,
    jpeg_quality: int = 85,
) -> Tuple[bytes, str]:
    """Load an image file and prepare it for the Vision API.

    Thin wrapper around :func:`prepare_pil_for_vision`.

    Args:
        file_path: Path to image file (JPEG, PNG, BMP, TIFF, etc.).
        max_dimension: Cap the longest side to this value (pixels).
        jpeg_quality: JPEG quality (1-100).

    Returns:
        Tuple of (raw JPEG bytes, mime type string "image/jpeg").
    """
    img = Image.open(file_path)
    return prepare_pil_for_vision(img, max_dimension, jpeg_quality)
