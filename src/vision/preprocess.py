"""Image preprocessing helpers for the Day 1 MVP."""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

import numpy as np
from PIL import Image
from PIL import ImageOps


def load_image(uploaded_file: BinaryIO) -> Image.Image:
    """Load an uploaded file into a PIL image."""
    # Streamlit reruns the app on widget updates; ensure the stream is rewound.
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    image = Image.open(uploaded_file)
    # Handle phone-camera orientation metadata (very common for site photos).
    image = ImageOps.exif_transpose(image)
    # Ensure the underlying stream can be released by materializing pixels now.
    image.load()
    return image


def to_rgb_array(image: Image.Image) -> np.ndarray:
    """Convert a PIL image to an RGB NumPy array."""
    rgb_image = image.convert("RGB")
    return np.array(rgb_image)


def resize_image_keep_aspect(image: Image.Image, max_width: int = 960) -> Image.Image:
    """Resize image to max width while preserving aspect ratio."""
    if image.width <= max_width:
        return image

    ratio = max_width / float(image.width)
    new_size = (max_width, int(image.height * ratio))
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:  # Pillow < 9 compatibility
        resample = Image.LANCZOS
    return image.resize(new_size, resample=resample)


def to_grayscale(image: Image.Image) -> Image.Image:
    """Return a grayscale version of the image."""
    return image.convert("L")


def crop_percent_margins(
    image: Image.Image,
    *,
    left_pct: float,
    right_pct: float,
    top_pct: float,
    bottom_pct: float,
) -> Image.Image:
    """
    Crop the image by removing margins expressed as percentages of width/height.

    Each margin is clamped to [0, 40]. Ensures at least 1px remains in each dimension.
    """
    w, h = image.size
    lp = max(0.0, min(40.0, float(left_pct)))
    rp = max(0.0, min(40.0, float(right_pct)))
    tp = max(0.0, min(40.0, float(top_pct)))
    bp = max(0.0, min(40.0, float(bottom_pct)))

    x0 = int(round(w * lp / 100.0))
    x1 = w - int(round(w * rp / 100.0))
    y0 = int(round(h * tp / 100.0))
    y1 = h - int(round(h * bp / 100.0))

    x1 = max(x0 + 1, min(w, x1))
    y1 = max(y0 + 1, min(h, y1))
    return image.crop((x0, y0, x1, y1))


def pil_to_png_bytes(image: Image.Image) -> bytes:
    """Encode a PIL image as PNG bytes (for Streamlit downloads)."""
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def ndarray_to_png_bytes(arr: np.ndarray) -> bytes:
    """
    Encode a NumPy image as PNG bytes.

    Supports 2D uint8 (grayscale) or 3-channel uint8 RGB.
    """
    buf = BytesIO()
    if arr.ndim == 2:
        Image.fromarray(arr, mode="L").save(buf, format="PNG")
    elif arr.ndim == 3 and arr.shape[2] == 3:
        Image.fromarray(arr.astype(np.uint8), mode="RGB").save(buf, format="PNG")
    else:
        raise ValueError(f"Unsupported array shape for PNG export: {arr.shape}")
    return buf.getvalue()
