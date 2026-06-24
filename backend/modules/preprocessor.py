"""OpenCV image preprocessing pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from config import MAX_IMAGE_EDGE_PX


@dataclass
class PreprocessResult:
    """Colour BGR image ready for detection + grayscale for edge analysis."""

    colour_bgr: np.ndarray
    grayscale: np.ndarray
    scale_factor: float  # resize ratio applied (original / processed longest edge)
    quality_flags: list[str]


def _resize_longest_edge(bgr: np.ndarray, max_edge: int) -> tuple[np.ndarray, float]:
    h, w = bgr.shape[:2]
    longest = max(h, w)
    if longest <= max_edge:
        return bgr, 1.0
    scale = max_edge / float(longest)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, 1.0 / scale


def _assess_quality(bgr: np.ndarray, gray: np.ndarray) -> list[str]:
    flags: list[str] = []
    mean_brightness = float(np.mean(gray))
    if mean_brightness < 45:
        flags.append("Photo may be too dark — consider re-uploading with better lighting.")
    if mean_brightness > 230:
        flags.append("Photo may be overexposed — details could be lost.")

    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if lap_var < 80:
        flags.append("Photo appears blurry — measurements may be unreliable.")

    # Rough tilt estimate via dominant line angle spread
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 80, minLineLength=40, maxLineGap=10)
    if lines is not None and len(lines) >= 5:
        angles = []
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1))) % 90
            angles.append(min(ang, 90 - ang))
        if float(np.std(angles)) > 25:
            flags.append("Photo may be taken at a steep angle (>45°) — perspective correction limited in MVP.")

    return flags


def preprocess_image(bgr: np.ndarray, max_edge: int = MAX_IMAGE_EDGE_PX) -> PreprocessResult:
    """
    Resize, enhance contrast, denoise, and produce grayscale for geometric analysis.

    Perspective correction is deferred until a reliable rectangular reference is detected
    (door frame / wall edge) in Phase 2+.
    """
    resized, scale_factor = _resize_longest_edge(bgr, max_edge)

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    if gray.shape[0] > 5 and gray.shape[1] > 5:
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

    quality_flags = _assess_quality(resized, gray)
    return PreprocessResult(
        colour_bgr=resized,
        grayscale=gray,
        scale_factor=scale_factor,
        quality_flags=quality_flags,
    )
