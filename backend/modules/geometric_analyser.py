"""Geometric checks for walls, beams, and rebar regions using RANSAC-based dominant line clustering."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from schemas.inspection import Detection, Measurement


@dataclass
class GeometryFinding:
    check_type: str
    angle_deg: float
    deviation_per_m: float  # cm/m for walls, mm/m for beams
    unit: str
    message: str
    measurements: list[Measurement]


def _line_angle_deg(x1: int, y1: int, x2: int, y2: int) -> float:
    return abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 180.0


def _line_length(x1: int, y1: int, x2: int, y2: int) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _crop_bbox(gray: np.ndarray, bbox: list[int]) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    h, w = gray.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return gray
    return gray[y1:y2, x1:x2]


def _sliding_window_cluster(
    candidates: list[tuple[float, float, list[int]]],
    window_size: float = 1.0,
) -> Optional[tuple[float, float, float, int, list[list[int]]]]:
    """Find the best cluster of lines in angle-deviation space.

    Scoring rewards both total line length AND non-zero deviation so that
    structural edges (tilted) are preferred over zero-tilt texture noise.

    Returns (median_deviation, weighted_deviation, std, n_inliers, coords) or None.
    """
    if len(candidates) < 2:
        return None

    sorted_cands = sorted(candidates, key=lambda c: c[0])
    best_score = -1.0
    best_cluster: list[tuple[float, float, list[int]]] = []

    for i, (dev, length, coords) in enumerate(sorted_cands):
        lo = dev
        hi = dev + window_size
        cluster = [(d, l, c) for d, l, c in sorted_cands if lo <= d <= hi]
        if len(cluster) < 2:
            continue
        total_length = sum(l for _, l, _ in cluster)
        cluster_devs = [d for d, _, _ in cluster]
        sorted_d = sorted(cluster_devs)
        p75 = sorted_d[min(len(sorted_d) - 1, int(len(sorted_d) * 0.75))]
        # Score rewards total length and biases toward non-zero deviation
        score = total_length * (0.3 + p75)
        if score > best_score:
            best_score = score
            best_cluster = cluster

    if len(best_cluster) < 2:
        return None

    devs = [d for d, _, _ in best_cluster]
    lengths = [l for _, l, _ in best_cluster]
    total_w = sum(lengths)
    w_dev = sum(d * l for d, l in zip(devs, lengths)) / total_w
    sorted_devs = sorted(devs)
    # Use 75th percentile to avoid under-measurement from near-zero texture lines
    p75_idx = min(len(sorted_devs) - 1, int(len(sorted_devs) * 0.75))
    p75_dev = sorted_devs[p75_idx]
    std = float(np.std(devs)) if len(devs) > 1 else 0.0

    return (p75_dev, w_dev, std, len(best_cluster), [c for _, _, c in best_cluster])


def _dominant_line_deviation(
    region: np.ndarray,
    *,
    mode: str,
    vertical_tol: float = 6.0,
    horizontal_tol: float = 3.0,
) -> Optional[tuple[float, float, int, float, list[list[int]]]]:
    """Return (dominant_deviation_deg, span_px, line_count, confidence, lines).

    v3: Uses sliding-window clustering to find the densest angle region,
    re-estimates with tightened inlier threshold, and reports the median
    deviation to avoid dilution by zero-tilt texture edges.
    """
    if region.size == 0 or region.shape[0] < 20 or region.shape[1] < 20:
        return None

    if mode == "vertical":
        min_len = max(30, int(region.shape[0] * 0.15))
    else:
        min_len = max(30, int(region.shape[1] * 0.15))

    edges = cv2.Canny(region, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 40,
                            minLineLength=min_len, maxLineGap=8)
    if lines is None or len(lines) == 0:
        return None

    tol = vertical_tol if mode == "vertical" else horizontal_tol

    candidates: list[tuple[float, float, list[int]]] = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = _line_angle_deg(int(x1), int(y1), int(x2), int(y2))
        length = _line_length(int(x1), int(y1), int(x2), int(y2))
        if mode == "vertical":
            dev = abs(angle - 90.0)
        else:
            dev = min(angle, abs(angle - 180.0))
        if dev <= tol:
            candidates.append((dev, length, [int(x1), int(y1), int(x2), int(y2)]))

    if len(candidates) < 2:
        return None

    # ── Length-based noise rejection ──────────────────────────────
    candidates.sort(key=lambda c: c[1], reverse=True)
    max_length = candidates[0][1]
    length_threshold = max_length * 0.30
    strong = [c for c in candidates if c[1] >= length_threshold]
    if len(strong) < 3:
        strong = candidates[: max(3, len(candidates))]

    # ── Sliding-window clustering ─────────────────────────────────
    # Try tight window first (1.0°), fall back to wider window (2.0°)
    result = _sliding_window_cluster(strong, window_size=1.0)
    if result is None:
        result = _sliding_window_cluster(strong, window_size=2.0)
    if result is None and len(strong) >= 2:
        # Last resort: use all strong lines (weighted average)
        total_w = sum(l for _, l, _ in strong)
        w_dev = sum(d * l for d, l, _ in strong) / total_w
        devs = [d for d, _, _ in strong]
        sorted_d = sorted(devs)
        p75_idx = min(len(sorted_d) - 1, int(len(sorted_d) * 0.75))
        result = (sorted_d[p75_idx], w_dev, float(np.std(devs)), len(strong), [c for _, _, c in strong])
    if result is None:
        return None

    median_dev, w_dev, std, n_lines, inlier_coords = result

    # ── Confidence scoring ────────────────────────────────────────
    total_cands = len(candidates)
    inlier_ratio = n_lines / max(total_cands, 1)
    conf = min(0.95, 0.4 + inlier_ratio * 0.4 + n_lines * 0.015 - std * 0.03)
    conf = max(0.15, conf)

    span = float(region.shape[0] if mode == "vertical" else region.shape[1])

    return (median_dev, span, n_lines, conf, inlier_coords)


def _deg_to_offset_per_m(angle_deg: float, unit: str) -> float:
    rad = math.radians(angle_deg)
    offset_mm_per_m = math.tan(rad) * 1000.0
    if unit == "cm/m":
        return offset_mm_per_m / 10.0
    return offset_mm_per_m


def _gradient_deviation_vertical(region: np.ndarray) -> Optional[tuple[float, float, int, float]]:
    """Gradient-based vertical edge deviation using Sobel_x per row."""
    h, w = region.shape
    blurred = cv2.GaussianBlur(region, (5, 5), 1.0)
    sobel_x = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=5)
    step = max(1, h // 100)
    left_pts: list[tuple[float, float]] = []
    right_pts: list[tuple[float, float]] = []

    for y in range(0, h, step):
        row_grad = np.abs(sobel_x[y, :])
        peak_val = float(np.max(row_grad))
        if peak_val < 30:
            continue
        grad_sorted = np.argsort(row_grad)[::-1]
        peaks = []
        examined = set()
        for p in grad_sorted:
            p_idx = int(p)
            if p_idx in examined:
                continue
            for dp in range(-5, 6):
                examined.add(p_idx + dp)
            peaks.append(p_idx)
            if len(peaks) >= 2:
                break
        if len(peaks) < 2:
            continue
        peaks.sort()
        first, last = peaks[0], peaks[-1]
        if last - first < 20:
            continue
        def _subpixel(row, center):
            c = int(center)
            if c < 1 or c >= len(row) - 1:
                return float(center)
            y0, y1, y2 = float(row[c-1]), float(row[c]), float(row[c+1])
            if abs(y0 + y2 - 2*y1) < 1e-10:
                return float(center)
            return float(center) + (y0 - y2) / (2 * (y0 + y2 - 2*y1))
        left_pts.append((float(y), _subpixel(row_grad, first)))
        right_pts.append((float(y), _subpixel(row_grad, last)))

    if len(left_pts) < 6 or len(right_pts) < 6:
        return None

    def _fit_robust(pts):
        xs = np.array([p[0] for p in pts], dtype=np.float64)
        ys = np.array([p[1] for p in pts], dtype=np.float64)
        for _ in range(3):
            A = np.vstack([xs, np.ones_like(xs)]).T
            m, c = np.linalg.lstsq(A, ys, rcond=None)[0]
            resid = ys - (m * xs + c)
            std_r = float(np.std(resid))
            if std_r < 0.5:
                break
            mask = np.abs(resid) < 2.0 * std_r
            if np.sum(mask) < 4:
                break
            xs, ys = xs[mask], ys[mask]
        return m, c, xs, ys

    left_m, _, left_xs, _ = _fit_robust(left_pts)
    right_m, _, right_xs, _ = _fit_robust(right_pts)
    if len(left_xs) < 4 or len(right_xs) < 4:
        return None

    avg_m = (left_m + right_m) / 2.0
    angle = abs(math.degrees(math.atan2(1.0, avg_m))) % 180.0
    dev = abs(angle - 90.0)
    if dev > 6.0:
        return None
    slope_diff = abs(left_m - right_m)
    conf = min(0.95, max(0.15, 0.7 - slope_diff * 30))
    n = len(left_xs) + len(right_xs)
    return (dev, float(h), n, conf)


def analyze_vertical_element(gray: np.ndarray, bbox: list[int], label: str, px_per_mm: Optional[float] = None) -> list[GeometryFinding]:
    findings: list[GeometryFinding] = []
    region = _crop_bbox(gray, bbox)

    result = _dominant_line_deviation(region, mode="vertical", vertical_tol=6.0)
    filtered_lines: list = []
    if result is None:
        grad = _gradient_deviation_vertical(region)
        if grad:
            median_dev, span_px, n_lines, confidence = grad
            result = (median_dev, span_px, n_lines, confidence, filtered_lines)

    if result:
        median_dev, span_px, n_lines, confidence, filtered_lines = result
        dev_cm_per_m = _deg_to_offset_per_m(median_dev, "cm/m")
        evidence = [f"Found {n_lines} vertical edges", f"Deviation: {median_dev:.2f}°"]
        measurements = [
            Measurement(
                name="plumb_angle_deg",
                value=round(median_dev, 2),
                unit="deg",
                estimated=False,
                confidence=round(confidence, 2),
                evidence=evidence,
                details={"line_count": n_lines, "lines": filtered_lines},
            ),
            Measurement(
                name="plumb_offset",
                value=round(dev_cm_per_m, 2),
                unit="cm/m",
                estimated=px_per_mm is None,
                confidence=round(confidence, 2),
                evidence=evidence,
            ),
        ]
        findings.append(
            GeometryFinding(
                check_type="wall_plumb",
                angle_deg=median_dev,
                deviation_per_m=dev_cm_per_m,
                unit="cm/m",
                message=f"{label}: vertical deviation {dev_cm_per_m:.2f} cm/m ({median_dev:.1f}° from plumb).",
                measurements=measurements,
            )
        )
    return findings


def _gradient_based_deviation(
    region: np.ndarray,
    *,
    mode: str,
    horizontal_tol: float = 3.0,
    vertical_tol: float = 6.0,
) -> Optional[tuple[float, float, int, float]]:
    """Return (deviation_deg, span_px, n_columns, confidence) via per-column
    edge tracking.

    For horizontal mode (beams): tracks row of max horizontal-gradient per
    column and fits a line to estimate the precise edge angle.  Uses all
    edge pixels across the full width, giving sub-pixel angular resolution.
    """
    if region.size == 0 or region.shape[0] < 20 or region.shape[1] < 20:
        return None

    tol = vertical_tol if mode == "vertical" else horizontal_tol
    h, w = region.shape

    if mode == "horizontal":
        blurred = cv2.GaussianBlur(region, (5, 5), 1.0)
        sobel_y = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=5)
        step = max(1, w // 150)
        top_pts: list[tuple[float, float]] = []
        bot_pts: list[tuple[float, float]] = []

        for x in range(0, w, step):
            col_grad = np.abs(sobel_y[:, x])
            peak_val = float(np.max(col_grad))
            if peak_val < 30:
                continue
            # Find the two strongest gradient peaks (top and bottom edges)
            grad_sorted = np.argsort(col_grad)[::-1]
            peaks = []
            examined = set()
            for p in grad_sorted:
                p_idx = int(p)
                if p_idx in examined:
                    continue
                # Mark neighborhood as examined
                for dp in range(-5, 6):
                    examined.add(p_idx + dp)
                peaks.append(p_idx)
                if len(peaks) >= 2:
                    break
            if len(peaks) < 2:
                continue
            peaks.sort()
            first, last = peaks[0], peaks[-1]
            if last - first < 20:
                continue

            # Sub-pixel refinement via parabola
            def _subpixel(col, center):
                c = int(center)
                if c < 1 or c >= len(col) - 1:
                    return float(center)
                y0, y1, y2 = float(col[c-1]), float(col[c]), float(col[c+1])
                if abs(y0 + y2 - 2*y1) < 1e-10:
                    return float(center)
                return float(center) + (y0 - y2) / (2 * (y0 + y2 - 2*y1))

            top_sub = _subpixel(col_grad, first)
            bot_sub = _subpixel(col_grad, last)
            top_pts.append((float(x), top_sub))
            bot_pts.append((float(x), bot_sub))

        if len(top_pts) < 6 or len(bot_pts) < 6:
            return None

        # Fit line with outlier rejection (remove points > 2 std from fit)
        def _fit_robust(pts):
            xs = np.array([p[0] for p in pts], dtype=np.float64)
            ys = np.array([p[1] for p in pts], dtype=np.float64)
            for _ in range(3):
                A = np.vstack([xs, np.ones_like(xs)]).T
                m, c = np.linalg.lstsq(A, ys, rcond=None)[0]
                resid = ys - (m * xs + c)
                std_r = float(np.std(resid))
                if std_r < 0.5:
                    break
                mask = np.abs(resid) < 2.0 * std_r
                if np.sum(mask) < 4:
                    break
                xs, ys = xs[mask], ys[mask]
            return m, c, xs, ys

        top_m, top_c, top_xs, top_ys = _fit_robust(top_pts)
        bot_m, bot_c, bot_xs, bot_ys = _fit_robust(bot_pts)

        if len(top_xs) < 4 or len(bot_xs) < 4:
            return None

        avg_m = (top_m + bot_m) / 2.0
        angle = abs(math.degrees(math.atan2(avg_m, 1.0))) % 180.0
        dev = min(angle, abs(angle - 180.0))
        if dev > tol:
            return None

        top_resid = top_ys - (top_m * top_xs + top_c)
        bot_resid = bot_ys - (bot_m * bot_xs + bot_c)
        combined_std = float(np.std(np.concatenate([top_resid, bot_resid])))
        slope_diff = abs(top_m - bot_m)
        conf = min(0.95, max(0.15, 0.8 - slope_diff * 30 - combined_std * 0.1))
        n = len(top_xs) + len(bot_xs)
        span = float(w)
        return (dev, span, n, conf)

    return None


def analyze_horizontal_element(gray: np.ndarray, bbox: list[int], label: str, px_per_mm: Optional[float] = None) -> list[GeometryFinding]:
    findings: list[GeometryFinding] = []
    region = _crop_bbox(gray, bbox)

    # Method 1: HoughLinesP
    hough_result = _dominant_line_deviation(region, mode="horizontal", horizontal_tol=3.0)
    # Method 2: Gradient-based edge tracking (sub-degree resolution)
    grad_result = _gradient_based_deviation(region, mode="horizontal", horizontal_tol=3.0)

    hough_angle = hough_result[0] if hough_result else None
    grad_angle = grad_result[0] if grad_result else None

    # ── Select best angle ───────────────────────────────────────────
    selected_angle: Optional[float] = None
    hough_conf: Optional[float] = hough_result[3] if hough_result else None
    grad_conf: Optional[float] = grad_result[3] if grad_result else None
    n_lines: int = 0
    confidence: float = 0.0
    details: dict = {}

    if grad_angle is not None and hough_angle is not None:
        details["hough_angle_deg"] = round(hough_angle, 3)
        details["gradient_angle_deg"] = round(grad_angle, 3)
        # Prefer gradient-based measurement for sub-degree tilts where
        # Hough quantization causes under-reporting.
        # Always take the larger of the two to counter under-measurement.
        selected_angle = max(hough_angle, grad_angle)
        n_lines = max(hough_result[2] if hough_result else 0,
                      grad_result[2] if grad_result else 0)
        confidence = max(hough_conf or 0, grad_conf or 0)
        details["selected_method"] = "max"
        # Override: prefer gradient when Hough reports ~0° (can't resolve)
        # and gradient finds a clear structural edge (high confidence)
        if hough_angle < 0.3 and grad_angle >= 0.15 and (grad_conf or 0) > 0.5:
            selected_angle = grad_angle
            n_lines = grad_result[2]
            confidence = grad_conf or hough_conf or 0.5
            details["selected_method"] = "gradient"
    elif grad_angle is not None:
        selected_angle = grad_angle
        n_lines = grad_result[2]
        confidence = grad_conf or 0.5
        details["selected_method"] = "gradient_only"
    elif hough_angle is not None:
        selected_angle = hough_angle
        n_lines = hough_result[2]
        confidence = hough_conf or 0.5
        details["selected_method"] = "hough_only"

    if selected_angle is not None:
        dev_mm_per_m = _deg_to_offset_per_m(selected_angle, "mm/m")
        evidence = [
            f"Found {n_lines} edges, deviation: {selected_angle:.2f}°",
            f"Method: {details.get('selected_method', 'unknown')}",
        ]
        measurements = [
            Measurement(
                name="level_angle_deg",
                value=round(selected_angle, 2),
                unit="deg",
                estimated=False,
                confidence=round(confidence, 2),
                evidence=evidence,
                details={
                    "line_count": n_lines,
                    **details,
                },
            ),
            Measurement(
                name="level_offset",
                value=round(dev_mm_per_m, 2),
                unit="mm/m",
                estimated=px_per_mm is None,
                confidence=round(confidence, 2),
                evidence=evidence,
            ),
        ]
        findings.append(
            GeometryFinding(
                check_type="beam_level",
                angle_deg=selected_angle,
                deviation_per_m=dev_mm_per_m,
                unit="mm/m",
                message=f"{label}: level deviation {dev_mm_per_m:.2f} mm/m ({selected_angle:.1f}° from level).",
                measurements=measurements,
            )
        )
    return findings


def analyze_door_alignment(gray: np.ndarray, bbox: list[int], px_per_mm: Optional[float] = None) -> list[GeometryFinding]:
    """Measure door-frame gap asymmetry using independent jamb clustering.

    v3: Detects left/right jamb lines independently via x-position k-means,
    uses sliding-window clustering to find dominant displacement per jamb,
    computes frame corners, skew, and rectangularity.
    """
    findings: list[GeometryFinding] = []
    region = _crop_bbox(gray, bbox)
    h, w = region.shape[:2]
    if w < 30 or h < 30:
        return findings

    edges = cv2.Canny(region, 50, 150)
    min_len = max(40, int(h * 0.20))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 30,
                            minLineLength=min_len, maxLineGap=10)
    if lines is None or len(lines) == 0:
        return findings

    # ── Collect near-vertical lines, compute displacement ─────────
    vert_tol = 5.0  # degrees from vertical
    all_lines_data: list[tuple[float, float, float, list[int]]] = []  # (avg_x, disp, length, coords)

    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = _line_angle_deg(int(x1), int(y1), int(x2), int(y2))
        if abs(angle - 90.0) > vert_tol:
            continue
        length = _line_length(int(x1), int(y1), int(x2), int(y2))
        avg_x = (x1 + x2) / 2.0

        if y1 > y2:
            x1, y1, x2, y2 = x2, y2, x1, y1
        dy = float(y2 - y1)
        disp = ((x2 - x1) / dy * h) if dy > 0 else 0.0

        coords = [int(x1), int(y1), int(x2), int(y2)]
        all_lines_data.append((avg_x, disp, length, coords))

    if len(all_lines_data) < 2:
        return findings

    # ── Split into left/right via simple 2-means clustering ──────
    xs = np.array([d[0] for d in all_lines_data])
    if len(xs) < 2:
        return findings
    # Simple k-means with k=2 (no sklearn dependency)
    c1, c2 = float(np.min(xs)), float(np.max(xs))
    for _ in range(10):
        g1 = xs[abs(xs - c1) <= abs(xs - c2)]
        g2 = xs[abs(xs - c1) > abs(xs - c2)]
        if len(g1) > 0: c1 = float(np.mean(g1))
        if len(g2) > 0: c2 = float(np.mean(g2))
    left_label = 0 if c1 < c2 else 1
    left_group = [all_lines_data[i] for i in range(len(all_lines_data))
                  if (0 if abs(xs[i] - c1) <= abs(xs[i] - c2) else 1) == left_label]
    right_group = [all_lines_data[i] for i in range(len(all_lines_data))
                   if (0 if abs(xs[i] - c1) <= abs(xs[i] - c2) else 1) != left_label]

    # ── Dominant displacement per jamb via sliding-window clustering ──
    def _dominant_disp(group: list[tuple[float, float, float, list[int]]]) -> tuple[float, int]:
        if len(group) < 2:
            if len(group) == 1:
                return group[0][1], 1
            return 0.0, 0
        # Sort by length, keep strong lines
        group.sort(key=lambda x: x[2], reverse=True)
        max_l = group[0][2]
        strong = [g for g in group if g[2] >= max_l * 0.30]
        if len(strong) < 2:
            strong = group[:2]

        # Cluster displacement values with sliding window
        disp_cands = [(d[1], d[2], d[3]) for d in strong]  # (disp, length, coords)
        result = _sliding_window_cluster(disp_cands, window_size=3.0)
        if result is None:
            wd = sum(d[1] * d[2] for d in strong) / sum(d[2] for d in strong)
            return wd, len(strong)
        median_disp, _, _, n, _ = result
        return median_disp, n

    left_disp, n_left = _dominant_disp(left_group)
    right_disp, n_right = _dominant_disp(right_group)

    asym_px = abs(left_disp - right_disp)

    if px_per_mm:
        asym_val = asym_px / px_per_mm
        unit = "mm"
    else:
        asym_val = float(asym_px)
        unit = "px"

    # ── Frame skew and rectangularity ─────────────────────────────
    # Estimate frame corners from left/right line clusters
    left_xs = [d[3][0] for d in left_group] + [d[3][2] for d in left_group]
    right_xs = [d[3][0] for d in right_group] + [d[3][2] for d in right_group]
    left_mean_x = float(np.mean(left_xs)) if left_xs else w / 3.0
    right_mean_x = float(np.mean(right_xs)) if right_xs else 2.0 * w / 3.0

    frame_width_px = right_mean_x - left_mean_x
    frame_skew = abs(left_disp - right_disp) / max(frame_width_px, 1.0) if frame_width_px > 0 else 0.0
    rectangularity = 1.0 - min(1.0, frame_skew * 2.0)

    confidence = 0.85 if h > 100 else 0.5
    if n_left < 2 or n_right < 2:
        confidence *= 0.5
    if rectangularity < 0.5:
        confidence *= 0.8

    evidence = [
        f"Left jamb: {n_left} lines, disp={left_disp:.1f}px; "
        f"Right jamb: {n_right} lines, disp={right_disp:.1f}px",
        f"Frame skew: {frame_skew:.3f}, rectangularity: {rectangularity:.2f}",
    ]

    findings.append(
        GeometryFinding(
            check_type="door_alignment",
            angle_deg=0.0,
            deviation_per_m=asym_val,
            unit=unit,
            message=f"Door frame gap asymmetry ≈ {asym_val:.1f} {unit} (rectangularity={rectangularity:.2f}).",
            measurements=[
                Measurement(
                    name="gap_asymmetry",
                    value=round(asym_val, 1),
                    unit=unit,
                    estimated=px_per_mm is None,
                    confidence=confidence,
                    evidence=evidence,
                    details={
                        "left_disp_px": round(left_disp, 1),
                        "right_disp_px": round(right_disp, 1),
                        "n_left": n_left,
                        "n_right": n_right,
                        "frame_skew": round(frame_skew, 3),
                        "rectangularity": round(rectangularity, 2),
                        "frame_width_px": round(frame_width_px, 1),
                    },
                )
            ],
        )
    )
    return findings


def analyze_rebar_spacing(gray: np.ndarray, bbox: list[int], px_per_mm: Optional[float] = None) -> list[GeometryFinding]:
    findings: list[GeometryFinding] = []
    region = _crop_bbox(gray, bbox)
    edges = cv2.Canny(region, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 30, minLineLength=15, maxLineGap=6)
    if lines is not None and len(lines) >= 4:
        centres = []
        filtered_lines = []
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            centres.append((float(x1 + x2) / 2.0, float(y1 + y2) / 2.0))
            filtered_lines.append([int(x1), int(y1), int(x2), int(y2)])
        xs = np.array([c[0] for c in centres])
        ys = np.array([c[1] for c in centres])
        use_x = float(np.std(xs)) >= float(np.std(ys))
        positions = np.sort(xs if use_x else ys)
        gaps_px = np.diff(positions)
        gaps_px = gaps_px[gaps_px > 3]
        if gaps_px.size >= 2:
            mean_gap_px = float(np.mean(gaps_px))
            std_gap_px = float(np.std(gaps_px))
            if px_per_mm:
                mean_mm = mean_gap_px / px_per_mm
                unit = "mm"
                val = mean_mm
            else:
                unit = "px"
                val = mean_gap_px
            confidence = min(0.9, 0.4 + (len(positions) * 0.05))
            evidence = [f"Detected {len(positions)} rebar instances", f"Spacing std dev: {std_gap_px:.1f} px"]
            findings.append(
                GeometryFinding(
                    check_type="rebar_spacing",
                    angle_deg=0.0,
                    deviation_per_m=val,
                    unit=unit,
                    message=f"Rebar mean spacing ≈ {val:.1f} {unit} (σ={std_gap_px:.1f} px).",
                    measurements=[
                        Measurement(
                            name="mean_spacing",
                            value=round(val, 1),
                            unit=unit,
                            estimated=px_per_mm is None,
                            confidence=round(confidence, 2),
                            evidence=evidence,
                            details={"std_px": std_gap_px, "bar_count_est": int(len(positions)), "lines": filtered_lines},
                        )
                    ],
                )
            )
    return findings


def analyse_element(
    gray: np.ndarray,
    detection: Detection,
    *,
    px_per_mm: Optional[float] = None,
) -> list[GeometryFinding]:
    """Run plumb/level/spacing checks inside a detected element bounding box."""
    label = detection.label.lower()
    
    if label in {"wall", "column", "door frame", "gate frame"}:
        return analyze_vertical_element(gray, detection.bbox, detection.label, px_per_mm)
    
    if label in {"beam", "slab"}:
        return analyze_horizontal_element(gray, detection.bbox, detection.label, px_per_mm)
        
    if label == "door":
        return analyze_door_alignment(gray, detection.bbox, px_per_mm)
        
    if label == "rebar":
        return analyze_rebar_spacing(gray, detection.bbox, px_per_mm)

    return []
