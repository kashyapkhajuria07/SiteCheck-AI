"""Feature extraction helpers for Day 2 (edges, lines, basic geometry)."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

import cv2
import numpy as np


@dataclass(frozen=True)
class LineDetectionResult:
    """Output structure for line detection on an image."""

    edges: np.ndarray
    line_overlay_bgr: np.ndarray
    lines: Optional[np.ndarray]


@dataclass(frozen=True)
class OrientationSummary:
    """A small, explainable summary of detected line orientations."""

    num_lines: int
    vertical_count: int
    horizontal_count: int
    other_count: int
    vertical_ratio: float
    horizontal_ratio: float
    guess: str


def pil_rgb_to_bgr(rgb: np.ndarray) -> np.ndarray:
    """Convert an RGB numpy image to OpenCV's BGR format."""
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def bgr_to_rgb(bgr: np.ndarray) -> np.ndarray:
    """Convert an OpenCV BGR image to RGB for display."""
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def compute_edges(
    bgr: np.ndarray,
    blur_ksize: int = 5,
    canny_low: int = 50,
    canny_high: int = 150,
) -> np.ndarray:
    """Compute Canny edges from a BGR image."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if blur_ksize and blur_ksize > 1:
        # Ensure odd kernel size for GaussianBlur.
        blur_ksize = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
        gray = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)
    edges = cv2.Canny(gray, canny_low, canny_high)
    return edges


def detect_lines_hough(
    bgr: np.ndarray,
    edges: np.ndarray,
    rho: int = 1,
    theta: float = np.pi / 180.0,
    threshold: int = 80,
    min_line_length: int = 40,
    max_line_gap: int = 10,
) -> LineDetectionResult:
    """Detect straight line segments using probabilistic Hough transform."""
    lines = cv2.HoughLinesP(
        edges,
        rho=rho,
        theta=theta,
        threshold=threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )

    overlay = bgr.copy()
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            cv2.line(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)

    return LineDetectionResult(edges=edges, line_overlay_bgr=overlay, lines=lines)


def summarize_line_orientations(
    lines: Optional[np.ndarray],
    vertical_tol_deg: float = 20.0,
    horizontal_tol_deg: float = 20.0,
) -> OrientationSummary:
    """
    Summarize whether the detected line segments are mostly vertical or horizontal.

    This is a simple heuristic for early demos:
    - Column-like images tend to have many vertical bars.
    - Beam-like images tend to have many horizontal bars.
    """
    if lines is None or len(lines) == 0:
        return OrientationSummary(
            num_lines=0,
            vertical_count=0,
            horizontal_count=0,
            other_count=0,
            vertical_ratio=0.0,
            horizontal_ratio=0.0,
            guess="Unknown (no lines detected)",
        )

    vertical = 0
    horizontal = 0
    other = 0

    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        dx = float(x2 - x1)
        dy = float(y2 - y1)
        angle = abs(math.degrees(math.atan2(dy, dx)))  # [0, 180]
        angle = angle % 180.0

        # Horizontal: close to 0 or 180 degrees.
        if angle <= horizontal_tol_deg or angle >= (180.0 - horizontal_tol_deg):
            horizontal += 1
            continue

        # Vertical: close to 90 degrees.
        if abs(angle - 90.0) <= vertical_tol_deg:
            vertical += 1
            continue

        other += 1

    total = vertical + horizontal + other
    vertical_ratio = vertical / total if total else 0.0
    horizontal_ratio = horizontal / total if total else 0.0

    if vertical_ratio > max(0.55, horizontal_ratio + 0.10):
        guess = "Column-like (mostly vertical lines)"
    elif horizontal_ratio > max(0.55, vertical_ratio + 0.10):
        guess = "Beam-like (mostly horizontal lines)"
    else:
        guess = "Unknown / Mixed"

    return OrientationSummary(
        num_lines=total,
        vertical_count=vertical,
        horizontal_count=horizontal,
        other_count=other,
        vertical_ratio=vertical_ratio,
        horizontal_ratio=horizontal_ratio,
        guess=guess,
    )
