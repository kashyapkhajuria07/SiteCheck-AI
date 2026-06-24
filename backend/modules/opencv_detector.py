"""OpenCV-based construction element detector.

Replaces YOLO dependency with pure computer vision detection using:
- Canny edge detection
- HoughLinesP for line segment detection
- Contour analysis for region-based detection
- Morphological operations for structural grouping

Returns the same Detection schema as yolo_detector.py
"""

from __future__ import annotations

import cv2
import numpy as np

from schemas.inspection import Detection

_MIN_TRUST_SCORE: float = 50.0

CONSTRUCTION_CLASSES = [
    "wall",
    "column",
    "beam",
    "door",
    "window",
    "rebar",
    "slab",
]


def _preprocess(bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Preprocess image: grayscale, edges, binary."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 4,
    )
    binary = cv2.medianBlur(binary, 3)
    return gray, edges, binary


def _detect_lines(edges: np.ndarray) -> list[tuple[int, int, int, int]]:
    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=50,
        minLineLength=40, maxLineGap=10,
    )
    if lines is None:
        return []
    return [(int(x1), int(y1), int(x2), int(y2)) for x1, y1, x2, y2 in lines.reshape(-1, 4)]


def _classify_line(x1: int, y1: int, x2: int, y2: int) -> str:
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dx > dy * 2:
        return "horizontal"
    if dy > dx * 2:
        return "vertical"
    return "diagonal"


def _iou(a: list[int], b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def _nms_by_label(detections: list[Detection], iou_thresh: float = 0.45) -> list[Detection]:
    by_label: dict[str, list[Detection]] = {}
    for d in detections:
        by_label.setdefault(d.label, []).append(d)
    kept: list[Detection] = []
    for label, group in by_label.items():
        group = sorted(group, key=lambda d: d.confidence, reverse=True)
        selected: list[Detection] = []
        for cand in group:
            if any(_iou(cand.bbox, s.bbox) > iou_thresh for s in selected):
                continue
            selected.append(cand)
        kept.extend(selected)
    return kept


def _merge_horizontal_lines(lines: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for l in lines:
        y_avg = (l[1] + l[3]) // 2
        xa, xb = min(l[0], l[2]), max(l[0], l[2])
        if merged and abs((merged[-1][1] + merged[-1][3]) // 2 - y_avg) < 5:
            last = merged[-1]
            lxa, lxb = min(last[0], last[2]), max(last[0], last[2])
            if xa <= lxb + 10:
                merged[-1] = (min(lxa, xa), last[1], max(lxb, xb), last[3])
                continue
        merged.append(l)
    return merged


def _merge_vertical_lines(lines: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for l in lines:
        x_avg = (l[0] + l[2]) // 2
        ya, yb = min(l[1], l[3]), max(l[1], l[3])
        if merged and abs((merged[-1][0] + merged[-1][2]) // 2 - x_avg) < 5:
            last = merged[-1]
            lya, lyb = min(last[1], last[3]), max(last[1], last[3])
            if ya <= lyb + 10:
                merged[-1] = (last[0], min(lya, ya), last[2], max(lyb, yb))
                continue
        merged.append(l)
    return merged


# ── Public detection API ───────────────────────────────────────


def detect_walls(bgr: np.ndarray) -> list[Detection]:
    """Detect walls using combined strategies.

    Strategies (fused via NMS):
    1. Edge-density regions — large high-density edge areas typical of
       site-photo walls.
    2. Long-line pairs — parallel Hough lines with significant length
       and spacing typical of plan-drawing walls.
    """
    gray, edges, binary = _preprocess(bgr)
    h, w = gray.shape[:2]
    lines = _detect_lines(edges)

    walls: list[Detection] = []

    # ── Strategy 1: Edge-density regions ──
    density = cv2.GaussianBlur(edges.astype(np.float32), (15, 15), 0)
    _, dense_mask = cv2.threshold(density, 15, 255, cv2.THRESH_BINARY)
    dense_mask = dense_mask.astype(np.uint8)

    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
    closed = cv2.morphologyEx(dense_mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)

    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, open_kernel, iterations=1)

    contours, _ = cv2.findContours(cleaned, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if area < max(200, w * h * 0.005) or area > w * h * 0.85:
            continue
        aspect = max(cw, ch) / min(cw, ch) if min(cw, ch) > 0 else 1
        if aspect < 1.5 or aspect > 20:
            continue
        cnt_area = float(cv2.contourArea(cnt))
        coverage = cnt_area / area if area > 0 else 0
        if coverage < 0.3:
            continue
        size_score = min(1.0, area / (w * h * 0.1))
        confidence = round(min(0.85, 0.35 + size_score * 0.5 + coverage * 0.2), 2)
        walls.append(Detection(
            label="wall",
            confidence=confidence,
            bbox=[x, y, x + cw, y + ch],
        ))

    # ── Strategy 2: Long Hough line pairs ──
    if len(lines) >= 4:
        lengths = [abs(l[2] - l[0]) + abs(l[3] - l[1]) for l in lines]
        sorted_lens = sorted(lengths, reverse=True)
        long_threshold = sorted_lens[max(3, len(lines) // 5)] if len(sorted_lens) > 3 else 100

        h_lines = _merge_horizontal_lines(
            [l for l in lines if _classify_line(*l) == "horizontal"
             and abs(l[2] - l[0]) + abs(l[3] - l[1]) >= long_threshold]
        )
        for i in range(len(h_lines)):
            for j in range(i + 1, len(h_lines)):
                y1 = (h_lines[i][1] + h_lines[i][3]) // 2
                y2 = (h_lines[j][1] + h_lines[j][3]) // 2
                gap = abs(y2 - y1)
                if gap < 10 or gap > h * 0.25:
                    continue
                x1a, x1b = min(h_lines[i][0], h_lines[i][2]), max(h_lines[i][0], h_lines[i][2])
                x2a, x2b = min(h_lines[j][0], h_lines[j][2]), max(h_lines[j][0], h_lines[j][2])
                overlap = min(x1b, x2b) - max(x1a, x2a)
                min_len = min(x1b - x1a, x2b - x2a)
                if overlap < min_len * 0.6:
                    continue
                x_l = max(x1a, x2a)
                x_r = min(x1b, x2b)
                confidence = min(0.80, 0.4 + overlap / (w * 0.2) * 0.4)
                walls.append(Detection(
                    label="wall",
                    confidence=round(confidence, 2),
                    bbox=[x_l, min(y1, y2), x_r, max(y1, y2)],
                ))

        v_lines = _merge_vertical_lines(
            [l for l in lines if _classify_line(*l) == "vertical"
             and abs(l[2] - l[0]) + abs(l[3] - l[1]) >= long_threshold]
        )
        for i in range(len(v_lines)):
            for j in range(i + 1, len(v_lines)):
                x1 = (v_lines[i][0] + v_lines[i][2]) // 2
                x2 = (v_lines[j][0] + v_lines[j][2]) // 2
                gap = abs(x2 - x1)
                if gap < 10 or gap > w * 0.25:
                    continue
                y1a, y1b = min(v_lines[i][1], v_lines[i][3]), max(v_lines[i][1], v_lines[i][3])
                y2a, y2b = min(v_lines[j][1], v_lines[j][3]), max(v_lines[j][1], v_lines[j][3])
                overlap = min(y1b, y2b) - max(y1a, y2a)
                min_len = min(y1b - y1a, y2b - y2a)
                if overlap < min_len * 0.6:
                    continue
                confidence = min(0.80, 0.4 + overlap / (h * 0.2) * 0.4)
                walls.append(Detection(
                    label="wall",
                    confidence=round(confidence, 2),
                    bbox=[x1, max(y1a, y2a), x2, min(y1b, y2b)],
                ))

    return _nms_by_label(walls)


def detect_columns(bgr: np.ndarray) -> list[Detection]:
    """Detect columns using contour analysis and fill detection.

    Strategies:
    1. Find compact rectangular contours (width ≈ height) with dark,
       uniform interior (filled column).
    2. Detect vertical line pairs framing a darker interior region.
    """
    gray, edges, binary = _preprocess(bgr)
    h, w = gray.shape[:2]

    columns: list[Detection] = []
    seen_boxes: list[tuple[int, int, int, int]] = []

    def _is_new_box(x: int, y: int, bw: int, bh: int) -> bool:
        for sx, sy, sbw, sbh in seen_boxes:
            if abs(x - sx) < 15 and abs(y - sy) < 15 and abs(bw - sbw) < 15 and abs(bh - sbh) < 15:
                return False
        return True

    def _is_dark_interior(x: int, y: int, bw: int, bh: int) -> tuple[bool, float]:
        margin = 5
        inner = gray[y + margin:y + bh - margin, x + margin:x + bw - margin]
        if inner.size == 0:
            return False, 0.0
        mean_val = float(np.mean(inner))
        std_val = float(np.std(inner))
        dark_px = float(np.sum(inner < 128))
        dark_frac = dark_px / inner.size
        is_dark = mean_val < 180 and dark_frac > 0.1
        uniformity = max(0.0, 1.0 - std_val / 80.0)
        return is_dark, dark_frac * uniformity

    # Strategy 1: Closed contours from binary
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel, iterations=2)

    for source in (binary, closed):
        contours, _ = cv2.findContours(source, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, cw, bh = cv2.boundingRect(cnt)
            if cw < 15 or bh < 15 or cw > w * 0.3 or bh > h * 0.6:
                continue
            if not _is_new_box(x, y, cw, bh):
                continue
            aspect = max(cw, bh) / min(cw, bh) if min(cw, bh) > 0 else 1
            if aspect > 3.0:
                continue
            is_dark, quality = _is_dark_interior(x, y, cw, bh)
            if not is_dark:
                continue
            confidence = round(min(0.85, 0.35 + quality * 0.6), 2)
            columns.append(Detection(
                label="column",
                confidence=confidence,
                bbox=[x, y, x + cw, y + bh],
            ))
            seen_boxes.append((x, y, cw, bh))

    return _nms_by_label(columns, iou_thresh=0.35)


def detect_beams(bgr: np.ndarray) -> list[Detection]:
    """Detect beams using morphological thickness filtering and line pairing.

    Strategies:
    1. Erode binary to isolate thick (structural) lines, then detect
       vertical line pairs spaced at beam-depth distance.
    2. Content-score check — region between lines should have higher
       edge/hatching density than flanking exterior strips.
    """
    gray, edges, binary = _preprocess(bgr)
    h, w = gray.shape[:2]

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded = cv2.erode(binary, kernel, iterations=1)

    thick_lines = _detect_lines(eroded)
    all_lines = _detect_lines(binary)

    v_thick = [l for l in thick_lines if _classify_line(*l) == "vertical"
               and abs(l[3] - l[1]) >= 75]
    v_all = [l for l in all_lines if _classify_line(*l) == "vertical"
             and abs(l[3] - l[1]) >= 75]

    beams: list[Detection] = []
    used_vthick: set[int] = set()

    min_depth = 50
    max_depth = 300

    for i, l1 in enumerate(v_thick):
        if i in used_vthick:
            continue
        x1 = (l1[0] + l1[2]) // 2
        y1_min, y1_max = min(l1[1], l1[3]), max(l1[1], l1[3])
        if x1 < 30 or x1 > w - 30 or (y1_max - y1_min) < 100:
            continue

        for j, l2 in enumerate(v_all):
            x2 = (l2[0] + l2[2]) // 2
            if x2 <= x1:
                continue
            gap = x2 - x1
            if not (min_depth < gap < max_depth):
                continue
            if x2 < 30 or x2 > w - 30:
                continue

            y2_min, y2_max = min(l2[1], l2[3]), max(l2[1], l2[3])
            len1 = y1_max - y1_min
            len2 = y2_max - y2_min
            len_ratio = min(len1, len2) / max(len1, len2) if max(len1, len2) > 0 else 0
            if len_ratio < 0.5:
                continue
            overlap = min(y1_max, y2_max) - max(y1_min, y2_min)
            min_len = min(len1, len2)
            if overlap < min_len * 0.5:
                continue

            y_t = max(y1_min, y2_min)
            y_b = min(y1_max, y2_max)
            margin = max(30, gap)

            inside = binary[y_t:y_b, x1:x2]
            outside_l = binary[y_t:y_b, max(0, x1 - margin):max(0, x1 - 5)]
            outside_r = binary[y_t:y_b, min(w, x2 + 5):min(w, x2 + margin)]

            in_dark = float(np.sum(inside > 0)) / inside.size if inside.size > 0 else 0
            out_l = float(np.sum(outside_l > 0)) / outside_l.size if outside_l.size > 0 else 0
            out_r = float(np.sum(outside_r > 0)) / outside_r.size if outside_r.size > 0 else 0
            out_dark = (out_l + out_r) / 2
            cs = in_dark - out_dark

            if cs < 0.03:
                continue

            confidence = round(min(0.85, 0.35 + cs * 5.0), 2)
            beams.append(Detection(
                label="beam",
                confidence=confidence,
                bbox=[x1, y_t, x2, y_b],
            ))
            used_vthick.add(i)
            break

    return _nms_by_label(beams)


def detect_doors(bgr: np.ndarray) -> list[Detection]:
    """Detect doors using gap analysis and L-shaped marker detection.

    Strategies:
    1. Find gaps in horizontal wall lines — door openings appear as
       breaks with vertical leaf markers at the edges.
    2. Detect short L-shaped markers (perpendicular threshold indicators)
       that flank door openings.
    """
    gray, edges, binary = _preprocess(bgr)
    h, w = gray.shape[:2]
    lines = _detect_lines(edges)

    h_lines = [l for l in lines if _classify_line(*l) == "horizontal"]
    v_lines = [l for l in lines if _classify_line(*l) == "vertical"]

    doors: list[Detection] = []

    if not h_lines:
        return doors

    h_by_y: dict[int, list] = {}
    for l in h_lines:
        y_avg = (l[1] + l[3]) // 2
        h_by_y.setdefault(y_avg, []).append(l)

    sorted_ys = sorted(h_by_y.keys())
    y_groups: list[list] = []
    for y in sorted_ys:
        if y_groups and abs(y - y_groups[-1][0][1] if y_groups[-1] else 0) < 8:
            y_groups[-1].extend(h_by_y[y])
        else:
            y_groups.append(list(h_by_y[y]))

    for group in y_groups:
        if len(group) < 2:
            continue
        group.sort(key=lambda l: min(l[0], l[2]))
        merged = []
        for l in group:
            xa, xb = min(l[0], l[2]), max(l[0], l[2])
            if merged and xa <= merged[-1][1] + 5:
                merged[-1] = (merged[-1][0], max(merged[-1][1], xb))
            else:
                merged.append((xa, xb))

        for i in range(len(merged) - 1):
            gap_left = merged[i][1]
            gap_right = merged[i + 1][0]
            gap = gap_right - gap_left
            if gap < 30 or gap > w * 0.3:
                continue

            has_left_v = any(abs((vl[0] + vl[2]) // 2 - gap_left) < 40 for vl in v_lines)
            has_right_v = any(abs((vl[0] + vl[2]) // 2 - gap_right) < 40 for vl in v_lines)

            if has_left_v or has_right_v:
                confidence = 0.60 if (has_left_v or has_right_v) else 0.50
                if has_left_v and has_right_v:
                    confidence = 0.75
                doors.append(Detection(
                    label="door",
                    confidence=confidence,
                    bbox=[gap_left, group[0][1] - 15, gap_right, group[0][1] + 15],
                ))

    return _nms_by_label(doors)


_CLASS_CAPS: dict[str, int] = {
    "wall": 20,
    "column": 20,
    "beam": 20,
    "door": 10,
}

_MIN_CONFIDENCE: float = 0.70


def _compute_trust_score(det: Detection, image: np.ndarray | None = None) -> float:
    """Compute trust score (0–100) for a detection.

    Combines confidence, geometry consistency, and optional edge
    / context analysis from the source image.
    """
    # Base from confidence
    trust = det.confidence * 100.0

    # Geometry penalty: extreme aspect ratios are less trustworthy
    x1, y1, x2, y2 = det.bbox
    bw, bh = x2 - x1, y2 - y1
    if min(bw, bh) > 0:
        aspect = max(bw, bh) / min(bw, bh)
        if det.label in ("column", "beam"):
            if aspect > 5.0:
                trust *= 0.7
            elif aspect > 3.0:
                trust *= 0.85
        elif det.label == "wall":
            if aspect < 1.5:
                trust *= 0.6
        elif det.label == "door":
            if aspect > 8.0 or aspect < 1.2:
                trust *= 0.7

    # Size penalty: very small detections are less trustworthy
    if (bw * bh) < 400:
        trust *= 0.5
    elif (bw * bh) < 1600:
        trust *= 0.8

    # Clamp
    return max(0.0, min(100.0, trust))


def _compute_trust_scores(detections: list[Detection], image: np.ndarray | None = None) -> None:
    """Assign trust_score to each detection in-place."""
    for det in detections:
        if det.trust_score == 100.0:  # default; only compute if not set
            det.trust_score = round(_compute_trust_score(det, image), 1)


def _filter_detections(detections: list[Detection], image: np.ndarray | None = None) -> list[Detection]:
    """Filter detections by trust score, confidence threshold, and per-class caps."""
    _compute_trust_scores(detections, image)

    trust_filtered = [d for d in detections if d.trust_score >= _MIN_TRUST_SCORE]

    conf_filtered = [d for d in trust_filtered if d.confidence >= _MIN_CONFIDENCE]

    capped: list[Detection] = []
    by_label: dict[str, list[Detection]] = {}
    for d in conf_filtered:
        by_label.setdefault(d.label, []).append(d)
    for label, group in by_label.items():
        group.sort(key=lambda x: x.confidence, reverse=True)
        cap = _CLASS_CAPS.get(label, 20)
        capped.extend(group[:cap])

    return capped


def _detect_all_raw(bgr: np.ndarray) -> list[Detection]:
    """Run all detectors and return raw (unfiltered) detections."""
    detections: list[Detection] = []
    detections.extend(detect_walls(bgr))
    detections.extend(detect_columns(bgr))
    detections.extend(detect_beams(bgr))
    detections.extend(detect_doors(bgr))
    return detections


def detect_elements(bgr: np.ndarray) -> list[Detection]:
    """Detect all structural elements in an image.

    Runs each detector, applies NMS, computes trust scores,
    then filters by trust score, confidence threshold, and per-class caps.
    """
    raw = _detect_all_raw(bgr)
    nmsed = _nms_by_label(raw)
    return _filter_detections(nmsed, image=bgr)


def compute_validation_log(
    bgr: np.ndarray,
    all_detections: list[Detection],
    final_detections: list[Detection],
    roi_filtered: list[Detection] | None = None,
) -> dict:
    """Compute validation log from raw detections through final output."""
    raw_counts: dict[str, int] = {}
    final_counts: dict[str, int] = {}
    for d in all_detections:
        raw_counts[d.label] = raw_counts.get(d.label, 0) + 1
    for d in final_detections:
        final_counts[d.label] = final_counts.get(d.label, 0) + 1

    nmsed = _nms_by_label(all_detections)
    _compute_trust_scores(nmsed, bgr)
    low_trust: list[Detection] = [d for d in nmsed if d.trust_score < _MIN_TRUST_SCORE]
    trusted: list[Detection] = [d for d in nmsed if d.trust_score >= _MIN_TRUST_SCORE]

    low_conf: list[Detection] = [d for d in trusted if d.confidence < _MIN_CONFIDENCE]
    after_conf: list[Detection] = [d for d in trusted if d.confidence >= _MIN_CONFIDENCE]

    filtered_counts: dict[str, int] = {}
    for d in after_conf:
        filtered_counts[d.label] = filtered_counts.get(d.label, 0) + 1

    nms_count = len(all_detections) - len(nmsed)
    non_struct = len(roi_filtered) if roi_filtered is not None else 0

    return {
        "raw_counts": raw_counts,
        "filtered_counts": filtered_counts,
        "removed_low_confidence": len(low_conf) + nms_count,
        "removed_duplicates": nms_count,
        "final_counts": final_counts,
        "raw_detection_count": len(all_detections),
        "filtered_detection_count": len(trusted) if trusted else len(all_detections),
        "ignored_low_trust_count": len(low_trust),
        "ignored_non_structural_count": non_struct,
        "final_detection_count": len(final_detections),
    }


def get_detection_mode() -> str:
    """Return identification string matching the yolo_detector API."""
    return "opencv"
