"""Structural ROI filter — removes non-structural detections.

Applies lightweight heuristics to reject detections overlapping known
non-structural regions: desks, chairs, curtains, ceiling grids, windows,
people, monitors, etc.
"""

from __future__ import annotations

import cv2
import numpy as np

from schemas.inspection import Detection


def filter_structural(
    image: np.ndarray,
    detections: list[Detection],
    scene_type: str = "",
) -> list[Detection]:
    """Filter out detections that overlap non-structural regions.

    Returns only detections that pass all applicable filters.
    """
    if not detections:
        return []

    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    # Precompute non-structural region masks
    non_structural_masks = _build_non_structural_masks(image, gray, h, w)

    filtered: list[Detection] = []
    for det in detections:
        if _is_non_structural(det, non_structural_masks, h, w):
            continue
        filtered.append(det)

    return filtered


def _build_non_structural_masks(
    image: np.ndarray, gray: np.ndarray, h: int, w: int,
) -> dict:
    masks: dict = {}

    # ── Lower 40% region (desk/chair zone) ──
    lower_zone_y = int(h * 0.6)
    lower_mask = np.zeros((h, w), dtype=np.uint8)
    lower_mask[lower_zone_y:, :] = 255
    masks["lower_40pct"] = lower_mask

    # ── Upper 25% region (ceiling zone) ──
    upper_zone_y = int(h * 0.25)
    upper_mask = np.zeros((h, w), dtype=np.uint8)
    upper_mask[:upper_zone_y, :] = 255
    masks["upper_25pct"] = upper_mask

    # ── Edge-dense regions (clutter: furniture, curtains) ──
    edges = cv2.Canny(gray, 30, 100, apertureSize=3)
    density = cv2.GaussianBlur(edges.astype(np.float32), (31, 31), 0)
    _, clutter_mask = cv2.threshold(density, 25, 255, cv2.THRESH_BINARY)
    clutter_mask = clutter_mask.astype(np.uint8)
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    clutter_mask = cv2.morphologyEx(clutter_mask, cv2.MORPH_CLOSE, close_k, iterations=2)
    masks["clutter"] = clutter_mask

    # ── High-saturation regions (colorful objects: chairs, boards) ──
    if len(image.shape) == 3:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        _, sat_mask = cv2.threshold(sat, 80, 255, cv2.THRESH_BINARY)
        sat_mask = cv2.morphologyEx(sat_mask, cv2.MORPH_OPEN,
                                     cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
        masks["high_saturation"] = sat_mask
    else:
        masks["high_saturation"] = np.zeros((h, w), dtype=np.uint8)

    # ── Window detection: bright regions near edges with low texture ──
    if len(image.shape) == 3:
        bright = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)[1]
        texture = cv2.Laplacian(gray, cv2.CV_64F).astype(np.uint8)
        _, low_texture = cv2.threshold(texture, 10, 255, cv2.THRESH_BINARY_INV)
        window_candidate = cv2.bitwise_and(bright, low_texture)
        window_mask = cv2.morphologyEx(window_candidate, cv2.MORPH_CLOSE,
                                        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)), iterations=2)
        _, window_mask = cv2.threshold(window_mask, 1, 255, cv2.THRESH_BINARY)
        masks["window"] = window_mask
    else:
        masks["window"] = np.zeros((h, w), dtype=np.uint8)

    return masks


def _is_non_structural(
    det: Detection, masks: dict, h: int, w: int,
) -> bool:
    x1, y1, x2, y2 = det.bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return False

    box_area = (x2 - x1) * (y2 - y1)
    if box_area <= 0:
        return False

    def _overlap_ratio(mask_name: str) -> float:
        mask_roi = masks[mask_name][y1:y2, x1:x2]
        overlap = float(np.sum(mask_roi > 0))
        return overlap / box_area if box_area > 0 else 0.0

    # ── Desk/Chair filter: small object in lower 40% with furniture aspect ──
    lower_overlap = _overlap_ratio("lower_40pct")
    if lower_overlap > 0.5:
        bw, bh = x2 - x1, y2 - y1
        aspect = max(bw, bh) / min(bw, bh) if min(bw, bh) > 0 else 1
        if 0.3 < aspect < 3.0 and box_area < h * w * 0.08:
            return True

    # ── Ceiling grid filter: dense grid in upper 25% ──
    upper_overlap = _overlap_ratio("upper_25pct")
    if upper_overlap > 0.3:
        return True

    # ── High-clutter rejection ──
    clutter_overlap = _overlap_ratio("clutter")
    if clutter_overlap > 0.6:
        return True

    # ── High-saturation object rejection ──
    sat_overlap = _overlap_ratio("high_saturation")
    if sat_overlap > 0.4:
        return True

    # ── Window reclassification: bright, low-texture regions ──
    window_overlap = _overlap_ratio("window")
    if window_overlap > 0.5 and det.label == "wall":
        return True

    return False
