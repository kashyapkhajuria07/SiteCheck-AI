"""OpenCV-based scene classifier for structural inspection eligibility.

Determines whether an uploaded image depicts a construction site, structural
frame, interior room, floor plan, or unknown scene — without any ML model.
"""

from __future__ import annotations

from enum import Enum

import cv2
import numpy as np


class SceneType(str, Enum):
    CONSTRUCTION_SITE = "construction_site"
    STRUCTURAL_FRAME = "structural_frame"
    INTERIOR_ROOM = "interior_room"
    FLOOR_PLAN = "floor_plan"
    UNKNOWN = "unknown"


_ALLOWED_SCENES = {SceneType.CONSTRUCTION_SITE, SceneType.STRUCTURAL_FRAME}


def is_allowed_scene(scene_type: SceneType) -> bool:
    return scene_type in _ALLOWED_SCENES


def classify_scene(image: np.ndarray) -> tuple[SceneType, float]:
    """Classify image scene type using pure OpenCV heuristics.

    Returns (scene_type, confidence) where confidence is 0.0–1.0.
    """
    h, w = image.shape[:2]
    if h == 0 or w == 0:
        return SceneType.UNKNOWN, 0.0

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    edge_density = float(np.mean(edges > 0))

    # ── Feature computations ──
    features = _compute_features(image, gray, hsv, edges, h, w)

    # ── Score each scene type ──
    scores = {
        SceneType.FLOOR_PLAN: _score_floor_plan(features),
        SceneType.CONSTRUCTION_SITE: _score_construction_site(features),
        SceneType.STRUCTURAL_FRAME: _score_structural_frame(features),
        SceneType.INTERIOR_ROOM: _score_interior_room(features),
    }

    best = max(scores, key=scores.get)
    confidence = scores[best]
    return best, confidence


def _compute_features(
    image: np.ndarray, gray: np.ndarray, hsv: np.ndarray,
    edges: np.ndarray, h: int, w: int,
) -> dict:
    total_px = h * w

    # Color metrics
    color_px = float(np.sum(np.std(image, axis=2) > 30)) / total_px
    gray_px = float(np.sum(np.std(image, axis=2) < 15)) / total_px
    saturation = float(np.mean(hsv[:, :, 1])) / 255.0
    value = float(np.mean(hsv[:, :, 2])) / 255.0

    # Edge density (already computed)
    edge_density = float(np.mean(edges > 0))

    # Binary / high-contrast detection (floor plan indicator)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    black_white_ratio = float(np.mean(otsu > 0)) if total_px > 0 else 0.0

    thin_line_score = _thin_line_ratio(edges, h, w)

    # Texture / complexity
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Color distribution — concrete vs furniture
    lower_conc = np.array([0, 0, 100], dtype=np.uint8)
    upper_conc = np.array([180, 50, 200], dtype=np.uint8)
    concrete_mask = cv2.inRange(hsv, lower_conc, upper_conc)
    concrete_ratio = float(np.mean(concrete_mask > 0))

    # Warm colors (wood/furniture)
    lower_warm = np.array([0, 30, 60], dtype=np.uint8)
    upper_warm = np.array([40, 255, 255], dtype=np.uint8)
    warm_mask = cv2.inRange(hsv, lower_warm, upper_warm)
    warm_ratio = float(np.mean(warm_mask > 0))

    # Vertical / horizontal line balance
    v_lines, h_lines = _count_oriented_lines(edges, w, h)

    # Ceiling grid detection: dense grid pattern in upper 25%
    upper_third = edges[:int(h * 0.25), :]
    ceil_edge_density = float(np.mean(upper_third > 0)) if upper_third.size > 0 else 0.0

    # Furniture-like contour detection (desk/chair blobs)
    furniture_score = _detect_furniture_contours(gray, total_px)

    # Large uniform region detection (walls, concrete surfaces)
    uniform_score = _detect_uniform_regions(gray, total_px)

    return {
        "color_px": color_px,
        "gray_px": gray_px,
        "saturation": saturation,
        "value": value,
        "edge_density": edge_density,
        "black_white_ratio": black_white_ratio,
        "thin_line_score": thin_line_score,
        "laplacian_var": laplacian_var,
        "concrete_ratio": concrete_ratio,
        "warm_ratio": warm_ratio,
        "v_lines": v_lines,
        "h_lines": h_lines,
        "ceil_edge_density": ceil_edge_density,
        "furniture_score": furniture_score,
        "uniform_score": uniform_score,
        "h": h,
        "w": w,
    }


def _thin_line_ratio(edges: np.ndarray, h: int, w: int) -> float:
    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=30,
        minLineLength=20, maxLineGap=5,
    )
    if lines is None:
        return 0.0
    line_pixels = min(len(lines) * 40, h * w * 0.5)
    return line_pixels / (h * w)


def _count_oriented_lines(edges: np.ndarray, w: int, h: int) -> tuple[int, int]:
    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=40,
        minLineLength=30, maxLineGap=10,
    )
    if lines is None:
        return 0, 0
    v_count, h_count = 0, 0
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        if dx > dy * 2:
            h_count += 1
        elif dy > dx * 2:
            v_count += 1
    return v_count, h_count


def _detect_furniture_contours(gray: np.ndarray, total_px: int) -> float:
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    furniture_px = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 500 or area > total_px * 0.4:
            continue
        x, y, cw, ch = cv2.boundingRect(cnt)
        aspect = max(cw, ch) / min(cw, ch) if min(cw, ch) > 0 else 1
        if 0.3 < aspect < 5.0:
            furniture_px += area
    return min(1.0, furniture_px / (total_px * 0.3))


def _detect_uniform_regions(gray: np.ndarray, total_px: int) -> float:
    blur = cv2.GaussianBlur(gray, (31, 31), 0)
    gray_f = gray.astype(np.float32)
    blur_f = blur.astype(np.float32)
    local_std = cv2.absdiff(gray_f, blur_f)
    _, uniform_mask = cv2.threshold(local_std, 15, 255, cv2.THRESH_BINARY_INV)
    uniform_ratio = float(np.mean(uniform_mask > 0))
    return uniform_ratio


# ── Scene scoring functions ──


def _score_floor_plan(f: dict) -> float:
    score = 0.0
    if f["black_white_ratio"] > 0.05 and f["black_white_ratio"] < 0.5:
        score += 0.25
    if f["thin_line_score"] > 0.01:
        score += 0.20
    if f["color_px"] < 0.3:
        score += 0.15
    if f["gray_px"] > 0.6:
        score += 0.10
    if f["saturation"] < 0.15:
        score += 0.10
    if f["edge_density"] > 0.05 and f["edge_density"] < 0.3:
        score += 0.10
    if f["laplacian_var"] > 200:
        score += 0.10
    return min(1.0, score)


def _score_construction_site(f: dict) -> float:
    score = 0.0
    if f["concrete_ratio"] > 0.15:
        score += 0.20
    if f["uniform_score"] > 0.5:
        score += 0.15
    if f["warm_ratio"] < 0.08:
        score += 0.10
    if f["edge_density"] > 0.08:
        score += 0.10
    if f["furniture_score"] < 0.02:
        score += 0.15
    if 0.02 < f["saturation"] < 0.25:
        score += 0.10
    if f["value"] < 0.6:
        score += 0.10
    if f["color_px"] > 0.3:
        score += 0.10
    return min(1.0, score)


def _score_structural_frame(f: dict) -> float:
    score = 0.0
    if f["v_lines"] > 5 and f["h_lines"] > 3:
        score += 0.25
    line_ratio = f["v_lines"] / max(f["h_lines"], 1)
    if 0.5 < line_ratio < 3.0:
        score += 0.10
    if f["concrete_ratio"] > 0.10:
        score += 0.10
    if 0.05 < f["saturation"] < 0.30:
        score += 0.10
    if f["furniture_score"] < 0.05:
        score += 0.10
    if f["edge_density"] > 0.06:
        score += 0.10
    if f["uniform_score"] > 0.4:
        score += 0.10
    if f["warm_ratio"] < 0.10:
        score += 0.10
    if f["ceil_edge_density"] < 0.15:
        score += 0.05
    return min(1.0, score)


def _score_interior_room(f: dict) -> float:
    score = 0.0
    if f["furniture_score"] > 0.05:
        score += 0.25
    if f["warm_ratio"] > 0.08:
        score += 0.15
    if f["ceil_edge_density"] > 0.12:
        score += 0.15
    if f["saturation"] > 0.20:
        score += 0.10
    if f["color_px"] > 0.4:
        score += 0.10
    if f["uniform_score"] < 0.5:
        score += 0.05
    if 0.03 < f["warm_ratio"] < 0.30:
        score += 0.05
    if f["laplacian_var"] > 100:
        score += 0.05
    if f["concrete_ratio"] < 0.20:
        score += 0.05
    return min(1.0, score)
