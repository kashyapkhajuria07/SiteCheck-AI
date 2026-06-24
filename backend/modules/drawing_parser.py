"""Floor plan / structural drawing parser using OpenCV + EasyOCR.

Extracts expected dimensions (doors, walls, columns, beams) from
architectural drawings (PDF or image) and returns structured JSON.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from modules.plan_parser import PlanSchema
from schemas.plan import BeamSpec, ColumnSpec, DoorSpec, RoomSpec

try:
    import easyocr

    _EASYOCR_AVAILABLE = True
    _ocr_reader = None
except ImportError:
    _EASYOCR_AVAILABLE = False
    _ocr_reader = None

try:
    from pdf2image import convert_from_path

    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    _PDF2IMAGE_AVAILABLE = False

try:
    import pytesseract

    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False


# ── dimension regex ────────────────────────────────────────────

_DIM_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*m", re.I),
    re.compile(r"(\d+)\s*mm", re.I),
    re.compile(r"\b(\d{3,5})\b"),
]


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None and _EASYOCR_AVAILABLE:
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


def _parse_dimension_mm(text: str) -> Optional[float]:
    text = text.strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*m", text, re.I)
    if m:
        return float(m.group(1)) * 1000
    m = re.search(r"(\d+)\s*mm", text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"\b(\d{3,5})\b", text)
    if m:
        val = float(m.group(1))
        return val if val > 100 else val * 1000
    return None


def _ocr_text_image(img: np.ndarray) -> list[str]:
    blocks: list[str] = []
    reader = _get_ocr_reader()
    if reader:
        results = reader.readtext(img, paragraph=False)
        for _, text, conf in results:
            if conf > 0.3:
                blocks.append(text.strip())
    elif _TESSERACT_AVAILABLE:
        from PIL import Image
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        text = pytesseract.image_to_string(pil_img)
        blocks = [line.strip() for line in text.splitlines() if line.strip()]
    return blocks


def _load_image(path: Path) -> Optional[np.ndarray]:
    suffix = path.suffix.lower()
    pages: list[np.ndarray] = []

    if suffix == ".pdf":
        if not _PDF2IMAGE_AVAILABLE:
            return None
        pil_pages = convert_from_path(str(path), dpi=200)
        for p in pil_pages:
            arr = cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR)
            pages.append(arr)
    else:
        img = cv2.imread(str(path))
        if img is not None:
            pages.append(img)

    if not pages:
        return None
    # Return the first page (or composite for multi-page)
    return pages[0]


def _preprocess(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Adaptive threshold to handle varied drawing styles
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 4
    )
    # Denoise
    denoised = cv2.medianBlur(binary, 3)
    return denoised


def _detect_lines(binary: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Detect straight line segments using probabilistic Hough transform."""
    lines = cv2.HoughLinesP(
        binary, rho=1, theta=np.pi / 180, threshold=50,
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


def _detect_doors_from_image(binary: np.ndarray, lines: list[tuple[int, int, int, int]],
                              px_per_mm_est: float) -> list[dict[str, Any]]:
    """Detect door openings from plan.

    Strategy 1: Gap in horizontal wall lines — verified with vertical door leaf
    or frame lines flanking the gap, and wall continuity above/below.
    Strategy 2: Door threshold L-markers (short perpendicular lines flanking opening).
    """
    doors: list[dict[str, Any]] = []
    h_img, w_img = binary.shape

    h_lines = [l for l in lines if _classify_line(*l) == "horizontal"]
    v_lines = [l for l in lines if _classify_line(*l) == "vertical"]

    if not h_lines:
        return doors

    door_min_gap_px = 600 * px_per_mm_est
    door_max_gap_px = 1500 * px_per_mm_est

    def _has_nearby_vertical(x: int, y: int, vlines: list, radius: int = 60) -> bool:
        """Check if a vertical line exists near (x, y) — could be a door leaf or frame."""
        for vl in vlines:
            vx = (vl[0] + vl[2]) // 2
            vy_mid = (vl[1] + vl[3]) // 2
            if abs(vx - x) < radius and abs(vy_mid - y) < radius * 4:
                return True
        return False

    def _has_wall_continuity(bin_img: np.ndarray, x_l: int, x_r: int, y: int, height: int,
                             min_dark_frac: float = 0.25) -> bool:
        """Check that wall material exists to the LEFT and RIGHT of the gap.
        
        Samples narrow horizontal strips flanking the gap (30px wide, adjacent to gap edges).
        Returns True if at least ONE side has sufficient dark pixels.
        """
        h_img, w_img = bin_img.shape
        strip_y_t = max(0, y - 6)
        strip_y_b = min(h_img, y + 6)
        # Left strip — sample immediately adjacent to left gap edge
        left_x_l = max(0, x_l - 35)
        left_x_r = max(5, x_l - 5)
        left_region = bin_img[strip_y_t:strip_y_b, left_x_l:left_x_r]
        dark_left = float(np.sum(left_region > 0)) / left_region.size if left_region.size > 0 else 0
        # Right strip — sample immediately adjacent to right gap edge
        right_x_l = min(w_img - 5, x_r + 5)
        right_x_r = min(w_img, x_r + 35)
        right_region = bin_img[strip_y_t:strip_y_b, right_x_l:right_x_r]
        dark_right = float(np.sum(right_region > 0)) / right_region.size if right_region.size > 0 else 0
        return dark_left > min_dark_frac or dark_right > min_dark_frac

    # ── Strategy 1: Gap in horizontal lines ──
    h_by_y: dict[int, list[tuple[int, int, int, int]]] = {}
    for l in h_lines:
        y_avg = (l[1] + l[3]) // 2
        h_by_y.setdefault(y_avg, []).append(l)
    sorted_ys = sorted(h_by_y.keys())
    y_groups: list[list[tuple[int, int, int, int]]] = []
    last_y_val = None
    for y in sorted_ys:
        if last_y_val is not None and abs(y - last_y_val) < 8:
            y_groups[-1].extend(h_by_y[y])
        else:
            y_groups.append(h_by_y[y][:])
        last_y_val = y

    for group in y_groups:
        if len(group) < 2:
            continue
        group.sort(key=lambda l: min(l[0], l[2]))
        merged: list[tuple[int, int]] = []
        for x1, _, x2, _ in group:
            xa, xb = min(x1, x2), max(x1, x2)
            if merged and xa <= merged[-1][1] + 5:
                merged[-1] = (merged[-1][0], max(merged[-1][1], xb))
            else:
                merged.append((xa, xb))
        group_y = (group[0][1] + group[0][3]) // 2

        # Directly scan the binary to find wall pixel runs at this y-level.
        # This is more reliable than Hough for detecting short wall segments
        # between adjacent doors.
        strip = binary[max(0, group_y-2):min(binary.shape[0], group_y+3), :]
        wall_present = np.sum(strip > 0, axis=0) > 2  # at least 3 rows have wall
        # Find runs of wall
        wall_runs: list[tuple[int, int]] = []
        in_run = False
        run_start = 0
        for cx in range(wall_present.shape[0]):
            if wall_present[cx] and not in_run:
                run_start = cx
                in_run = True
            elif not wall_present[cx] and in_run:
                if cx - run_start >= 30:  # min segment length
                    wall_runs.append((run_start, cx))
                in_run = False
        if in_run and wall_present.shape[0] - run_start >= 30:
            wall_runs.append((run_start, wall_present.shape[0]))

        # Process each gap between wall runs
        for gi in range(len(wall_runs) - 1):
            gap_left = wall_runs[gi][1]
            gap_right = wall_runs[gi + 1][0]
            gap = gap_right - gap_left
            if gap < door_min_gap_px:
                continue
            wall_cont = _has_wall_continuity(binary, gap_left, gap_right, group_y, int(30 * px_per_mm_est))
            if not wall_cont:
                continue

            # Find vertical door leaf lines inside/at the gap edges
            v_at_left = [vl for vl in v_lines if abs((vl[0]+vl[2])//2 - gap_left) < 50 and abs((vl[1]+vl[3])//2 - group_y) < 200]
            v_at_right = [vl for vl in v_lines if abs((vl[0]+vl[2])//2 - gap_right) < 50 and abs((vl[1]+vl[3])//2 - group_y) < 200]
            v_inside = [vl for vl in v_lines if gap_left < (vl[0]+vl[2])//2 < gap_right and abs((vl[1]+vl[3])//2 - group_y) < 200]

            has_left_v = len(v_at_left) > 0
            has_right_v = len(v_at_right) > 0

            if gap <= door_max_gap_px:
                if (has_left_v or has_right_v):
                    doors.append({
                        "id": f"D{len(doors) + 1}",
                        "width_mm": round(gap / px_per_mm_est, 0),
                        "height_mm": 2100.0,
                        "x_px": gap_left,
                        "y_px": group_y,
                        "width_px": gap,
                    })
            elif v_inside:
                # Multiple adjacent doors: build anchors from vertical markers plus
                # any short wall runs that were found in the direct scan.
                vxs = sorted(set((vl[0]+vl[2])//2 for vl in v_inside))
                for wr in wall_runs:
                    if wr[0] > gap_left and wr[1] < gap_right:
                        vx = (wr[0] + wr[1]) // 2
                        if abs(vx - gap_left) > 20 and abs(vx - gap_right) > 20:
                            vxs.append(vx)
                vxs = sorted(set(vxs))
                # When Hough misses vertical markers and overlapping erasures merge,
                # split the gap into evenly-spaced doors using markers as hints.
                est_doors = max(2, len(vxs))  # At least 2 doors for large gap
                # Refine estimate: if we have markers, position doors around them
                if len(vxs) >= 2:
                    anchors = [gap_left]
                    for vx in vxs:
                        dw = vx - anchors[-1]
                        if dw >= door_min_gap_px:
                            anchors.append(vx)
                    if anchors[-1] < gap_right:
                        anchors.append(gap_right)
                else:
                    # Evenly split the gap
                    each = gap // est_doors
                    anchors = [gap_left]
                    current = gap_left
                    if vxs:
                        # If 1 marker exists, use it as a hinge, centered in a door
                        dw_from_left = vxs[0] - gap_left
                        if dw_from_left >= door_min_gap_px * 0.5:
                            anchors.append(vxs[0])
                    while current + each < gap_right:
                        current += each
                        if current < gap_right:
                            anchors.append(current)
                    if anchors[-1] < gap_right:
                        anchors.append(gap_right)
                    anchors = sorted(set(a for a in anchors if gap_left <= a <= gap_right))
                for ai in range(len(anchors) - 1):
                    al = anchors[ai]
                    ar = anchors[ai + 1]
                    dw = ar - al
                    if door_min_gap_px <= dw <= door_max_gap_px:
                        doors.append({
                            "id": f"D{len(doors) + 1}",
                            "width_mm": round(dw / px_per_mm_est, 0),
                            "height_mm": 2100.0,
                            "x_px": al,
                            "y_px": group_y,
                            "width_px": dw,
                        })

        # Edge door: virtual gap at wall boundary (using direct scan wall_runs)
        if wall_runs:
            fs = wall_runs[0]
            left_edge_gap = fs[0] - 0
            if door_min_gap_px <= left_edge_gap <= door_max_gap_px:
                has_v = any(abs((vl[0]+vl[2])//2 - 5) < 60 for vl in v_lines)
                if has_v and _has_wall_continuity(binary, 0, fs[0], group_y, int(30 * px_per_mm_est)):
                    doors.append({
                        "id": f"D{len(doors) + 1}",
                        "width_mm": round(left_edge_gap / px_per_mm_est, 0),
                        "height_mm": 2100.0,
                        "x_px": 0,
                        "y_px": group_y,
                        "width_px": left_edge_gap,
                    })
            ls = wall_runs[-1]
            right_edge_gap = w_img - ls[1]
            if door_min_gap_px <= right_edge_gap <= door_max_gap_px:
                has_v = any(abs((vl[0]+vl[2])//2 - (w_img - 5)) < 60 for vl in v_lines)
                if has_v and _has_wall_continuity(binary, ls[1], w_img, group_y, int(30 * px_per_mm_est)):
                    doors.append({
                        "id": f"D{len(doors) + 1}",
                        "width_mm": round(right_edge_gap / px_per_mm_est, 0),
                        "height_mm": 2100.0,
                        "x_px": ls[1],
                        "y_px": group_y,
                        "width_px": right_edge_gap,
                    })

    # ── Strategy 2: Door threshold L-markers ──
    for v1_idx, v1 in enumerate(v_lines):
        y1_min, y1_max = min(v1[1], v1[3]), max(v1[1], v1[3])
        v1_len = y1_max - y1_min
        if v1_len < 8 or v1_len > 50:
            continue
        x1 = (v1[0] + v1[2]) // 2
        for v2 in v_lines[v1_idx + 1:]:
            y2_min, y2_max = min(v2[1], v2[3]), max(v2[1], v2[3])
            v2_len = y2_max - y2_min
            if v2_len < 8 or v2_len > 50:
                continue
            len_ratio = min(v1_len, v2_len) / max(v1_len, v2_len)
            if len_ratio < 0.4:
                continue
            x2 = (v2[0] + v2[2]) // 2
            gap = abs(x2 - x1)
            if door_min_gap_px <= gap <= door_max_gap_px:
                y_overlap = min(y1_max, y2_max) - max(y1_min, y2_min)
                if y_overlap > 0:
                    w_mm = gap / px_per_mm_est
                    new_id = f"D{len(doors) + 1}"
                    # Verify wall continuity
                    marker_y = min(y1_min, y2_min)
                    wall_cont = _has_wall_continuity(binary, min(x1, x2), max(x1, x2), marker_y,
                                                     int(20 * px_per_mm_est))
                    if wall_cont and not any(d["id"] == new_id for d in doors):
                        doors.append({
                            "id": new_id,
                            "width_mm": round(w_mm, 0),
                            "height_mm": 2100.0,
                            "x_px": min(x1, x2),
                            "y_px": marker_y,
                            "width_px": gap,
                        })

    deduped: list[dict[str, Any]] = []
    for d in sorted(doors, key=lambda x: (x["x_px"], -x["width_px"])):
        if not any(abs(d["x_px"] - dd["x_px"]) < door_min_gap_px * 0.5 for dd in deduped):
            deduped.append(d)
    return deduped


def _detect_columns(gray: np.ndarray, binary: np.ndarray, lines: list[tuple[int, int, int, int]],
                    px_per_mm_est: float) -> list[dict[str, Any]]:
    """Detect columns as rectangular filled regions.

    Adaptive threshold makes filled gray columns appear as rings in the binary
    (only edge pixels survive). We use the original gray image to verify that
    the region inside each candidate contour is dark — this correctly identifies
    gray-filled columns while rejecting line-artifacts.

    Cross-hatched columns (no fill, just outline + diagonal lines) are handled
    by checking the closed binary as well.
    """
    h, w = binary.shape

    # Closing helps detect cross-hatched columns (outline + diagonal lines)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel, iterations=2)

    columns: list[dict[str, Any]] = []
    seen_boxes: list[tuple[int, int, int, int]] = []

    min_col_size = 150 * px_per_mm_est
    max_col_size = 800 * px_per_mm_est
    min_col_area = min_col_size * min_col_size

    def _is_new_box(x: int, y: int, bw: int, bh: int) -> bool:
        for sx, sy, sbw, sbh in seen_boxes:
            if abs(x - sx) < 20 and abs(y - sy) < 20 and abs(bw - sbw) < 20 and abs(bh - sbh) < 20:
                return False
        return True

    def _is_dark_interior(contour, g_img: np.ndarray) -> bool:
        """Check if the interior of a contour is substantially dark in the gray image.
        
        Samples the region 5px inside the bounding box and checks for dark
        pixels (gray value < 128). Columns are drawn with dark fill/hatching.
        """
        cx, cy, cbw, cbh = cv2.boundingRect(contour)
        margin = 5
        inner = g_img[cy+margin:cy+cbh-margin, cx+margin:cx+cbw-margin]
        if inner.size == 0:
            return False
        dark_frac = float(np.sum(inner < 128)) / inner.size
        return dark_frac > 0.15

    # Search on both original binary (ring contours) and closed binary (solid blobs).
    # For ring contours, the contour AREA is much smaller than the bounding rect area,
    # so we use bounding rect dimensions for the size check instead of contour area.
    for source_binary in (binary, closed):
        contours, _ = cv2.findContours(source_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw < min_col_size or bh < min_col_size or bw > max_col_size or bh > max_col_size:
                continue
            if not _is_new_box(x, y, bw, bh):
                continue
            aspect = max(bw, bh) / min(bw, bh) if min(bw, bh) > 0 else 1
            if aspect >= 2.5:
                continue
            # Reject only contours that are suspiciously large (>80% of image)
            if bw > w * 0.8 or bh > h * 0.8:
                continue
            # Verify dark interior on original gray
            if not _is_dark_interior(cnt, gray):
                continue
            size_mm = min(bw, bh) / px_per_mm_est
            columns.append({
                "id": f"C{len(columns) + 1}",
                "width_mm": round(size_mm, 0),
                "x_px": x,
                "y_px": y,
                "width_px": bw,
                "height_px": bh,
            })
            seen_boxes.append((x, y, bw, bh))

    return columns


def _detect_walls(binary: np.ndarray, lines: list[tuple[int, int, int, int]],
                  px_per_mm_est: float) -> list[dict[str, Any]]:
    """Detect wall lines and estimate thickness from parallel line pairs.
    
    1. Merge near-identical horizontal lines before pairing.
    2. Require >60% overlap and similar line lengths.
    3. Each line used at most once (prevents one bottom line matching many top lines).
    """
    h_lines = [l for l in lines if _classify_line(*l) == "horizontal"]

    min_wall_len = 200 * px_per_mm_est
    h_lines = [l for l in h_lines if abs(l[2] - l[0]) >= min_wall_len]

    # Merge near-identical lines (same y, overlapping x-range)
    h_lines.sort(key=lambda l: (l[1] + l[3]) // 2)
    merged_h: list[tuple[int, int, int, int]] = []
    for l in h_lines:
        y_avg = (l[1] + l[3]) // 2
        xa, xb = min(l[0], l[2]), max(l[0], l[2])
        if merged_h and abs((merged_h[-1][1] + merged_h[-1][3]) // 2 - y_avg) < 5:
            last = merged_h[-1]
            lxa, lxb = min(last[0], last[2]), max(last[0], last[2])
            if xa <= lxb + 10:
                merged_h[-1] = (min(lxa, xa), last[1], max(lxb, xb), last[3])
                continue
        merged_h.append(l)
    h_lines = merged_h

    h_lines.sort(key=lambda l: (l[1] + l[3]) // 2)
    walls: list[dict[str, Any]] = []

    min_wall_thick = 80 * px_per_mm_est
    max_wall_thick = 400 * px_per_mm_est

    used_indices: set[int] = set()

    for i, l1 in enumerate(h_lines):
        if i in used_indices:
            continue
        y1_avg = (l1[1] + l1[3]) // 2
        x1_min, x1_max = min(l1[0], l1[2]), max(l1[0], l1[2])
        l1_len = x1_max - x1_min

        for j, l2 in enumerate(h_lines):
            if j <= i or j in used_indices:
                continue
            y2_avg = (l2[1] + l2[3]) // 2
            if y2_avg <= y1_avg:
                continue
            gap = y2_avg - y1_avg
            if not (min_wall_thick < gap < max_wall_thick):
                continue
            x2_min, x2_max = min(l2[0], l2[2]), max(l2[0], l2[2])
            l2_len = x2_max - x2_min
            overlap = min(x1_max, x2_max) - max(x1_min, x2_min)
            min_len = min(l1_len, l2_len)

            # Require >70% overlap
            if overlap < min_len * 0.7:
                continue

            # Similar line lengths (both must be within 60% of each other)
            len_ratio = min(l1_len, l2_len) / max(l1_len, l2_len) if max(l1_len, l2_len) > 0 else 0
            if len_ratio < 0.6:
                continue

            walls.append({
                "id": f"W{len(walls) + 1}",
                "thickness_mm": round(gap / px_per_mm_est, 0),
                "y_px": y1_avg,
                "x_start": min(x1_min, x2_min),
                "x_end": max(x1_max, x2_max),
            })
            used_indices.add(i)
            used_indices.add(j)
            break

    if walls:
        walls.sort(key=lambda w: (w["y_px"], w["x_start"]))
        merged: list[dict[str, Any]] = []
        for w in walls:
            if merged and abs(w["y_px"] - merged[-1]["y_px"]) < 15:
                last = merged[-1]
                if w["x_start"] <= last["x_end"] + 50:
                    last["x_end"] = max(last["x_end"], w["x_end"])
                    last["thickness_mm"] = round(
                        (last["thickness_mm"] + w["thickness_mm"]) / 2, 0
                    )
                    continue
            merged.append(dict(w))
        walls = merged

    return walls


def _detect_beams(gray: np.ndarray, binary: np.ndarray, lines: list[tuple[int, int, int, int]],
                  px_per_mm_est: float) -> list[dict[str, Any]]:
    """Detect beam representations using morphological thickness filtering.

    Beams are drawn with thicker lines (5px) and diagonal hatching between the
    two edges. Uses 1 iteration of erosion (removes thin 1px lines but keeps
    3+px lines). The region between the pair is checked for hatching content.
    """
    min_depth = 100 * px_per_mm_est
    max_depth = 600 * px_per_mm_est
    min_span = 150 * px_per_mm_est

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded = cv2.erode(binary, kernel, iterations=1)

    thick_lines = _detect_lines(eroded)
    v_thick = [l for l in thick_lines if _classify_line(*l) == "vertical"
               and abs(l[3] - l[1]) >= min_span]

    v_all = [l for l in lines if _classify_line(*l) == "vertical"
             and abs(l[3] - l[1]) >= min_span]

    h_img, w_img = gray.shape

    thick_x_set: set[int] = set()
    for l in v_thick:
        x_avg = (l[0] + l[2]) // 2
        thick_x_set.add(x_avg)
    thick_x_range: set[int] = set()
    for x in thick_x_set:
        for dx in range(-6, 7):
            thick_x_range.add(x + dx)

    def _is_thick(l: tuple[int, int, int, int]) -> bool:
        x = (l[0] + l[2]) // 2
        return x in thick_x_range

    def _content_score(bin_img: np.ndarray, x_l: int, x_r: int, y_t: int, y_b: int) -> float:
        """Ratio of dark pixels inside vs outside the region between two lines.
        
        Beams have hatching/material between the edges, while accidental pairs
        (e.g., column edges, wall corners) have empty space between them.
        Uses a wider comparison margin to catch hatching pattern.
        """
        if x_r <= x_l or y_b <= y_t:
            return 0.0
        margin = max(30, (x_r - x_l))
        # Wider outside strips
        outside_l = bin_img[y_t:y_b, max(0, x_l - margin):max(0, x_l - 5)]
        outside_r = bin_img[y_t:y_b, min(w_img, x_r + 5):min(w_img, x_r + margin)]
        inside = bin_img[y_t:y_b, x_l:x_r]
        in_dark = float(np.sum(inside > 0))
        out_dark = float(np.sum(outside_l > 0)) + float(np.sum(outside_r > 0))
        total_out = outside_l.size + outside_r.size
        if total_out == 0:
            return 0.0
        out_ratio = out_dark / total_out
        in_ratio = in_dark / inside.size if inside.size > 0 else 0
        return in_ratio - out_ratio

    beams: list[dict[str, Any]] = []
    used_vthick: set[int] = set()

    for i, l1 in enumerate(v_thick):
        if i in used_vthick:
            continue
        x1_avg = (l1[0] + l1[2]) // 2
        y1_min, y1_max = min(l1[1], l1[3]), max(l1[1], l1[3])

        if x1_avg < 60 or x1_avg > w_img - 60:
            continue
        if y1_min < 20 or y1_max > h_img - 20:
            continue

        for j, l2 in enumerate(v_all):
            x2_avg = (l2[0] + l2[2]) // 2
            if x2_avg <= x1_avg:
                continue
            gap = x2_avg - x1_avg
            if not (min_depth < gap < max_depth):
                continue

            if x2_avg < 60 or x2_avg > w_img - 60:
                continue
            y2_min, y2_max = min(l2[1], l2[3]), max(l2[1], l2[3])
            if y2_min < 20 or y2_max > h_img - 20:
                continue

            # At least one of the pair must be thick (survive erosion)
            if not _is_thick(l1) and not _is_thick(l2):
                continue

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
            cs = _content_score(binary, x1_avg, x2_avg, y_t, y_b)
            if cs < 0.03:
                continue

            depth_mm = gap / px_per_mm_est
            beams.append({
                "id": f"B{len(beams) + 1}",
                "depth_mm": round(depth_mm, 0),
                "width_mm": round(depth_mm * 0.5, 0),
                "x_px": x1_avg,
                "y_start": y_t,
                "y_end": y_b,
            })
            used_vthick.add(i)
            break

    return beams


def _estimate_scale_via_ocr_text(ocr_blocks: list[str]) -> Optional[float]:
    """Try to estimate px_per_mm from OCR text containing dimension strings.

    Looks for patterns like "4500", "4.5m", "4500mm" and tries to correlate
    with image size. This is a heuristic — returns a rough estimate.
    """
    dims = [_parse_dimension_mm(t) for t in ocr_blocks]
    dims = [d for d in dims if d]
    if len(dims) >= 2:
        # Use the average of the smallest dimensions as a typical reference
        small_dims = sorted(dims)[:3]
        avg_dim_mm = sum(small_dims) / len(small_dims)
        # Assume the drawing page is roughly A3 (420mm wide) or A4 (210mm)
        # and the largest dimension represents the full width
        return 1.0  # fallback — caller can use 1.0 as identity
    return None


# ── main public API ────────────────────────────────────────────


def extract_dimensions(drawing_path: Path, px_per_mm: Optional[float] = None) -> dict[str, Any]:
    """Parse a floor plan / structural drawing and extract element dimensions.

    Returns structured JSON:
    {
        "doors": [{"id": "D1", "width_mm": 900}],
        "columns": [{"id": "C1", "width_mm": 300}],
        "beams": [{"id": "B1", "depth_mm": 450}],
        "walls": [{"id": "W1", "thickness_mm": 230}]
    }
    """
    img = _load_image(drawing_path)
    if img is None:
        return {"doors": [], "columns": [], "beams": [], "walls": [], "_error": "Could not load drawing file"}

    h, w = img.shape[:2]
    binary = _preprocess(img)
    lines = _detect_lines(binary)

    # OCR
    ocr_blocks = _ocr_text_image(img)

    # Estimate px_per_mm if not provided
    if px_per_mm is None or px_per_mm <= 0:
        # Default: assume A4 page (210mm wide) as rough reference
        px_per_mm = w / 210.0

    # Detect elements
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    doors = _detect_doors_from_image(binary, lines, px_per_mm)
    columns = _detect_columns(gray, binary, lines, px_per_mm)
    walls = _detect_walls(binary, lines, px_per_mm)
    beams = _detect_beams(gray, binary, lines, px_per_mm)

    result: dict[str, Any] = {
        "doors": doors,
        "columns": columns,
        "beams": beams,
        "walls": walls,
    }

    return result


def detect_doors(drawing_path: Path) -> list[dict[str, Any]]:
    return extract_dimensions(drawing_path).get("doors", [])


def detect_walls(drawing_path: Path) -> list[dict[str, Any]]:
    return extract_dimensions(drawing_path).get("walls", [])


def detect_columns(drawing_path: Path) -> list[dict[str, Any]]:
    return extract_dimensions(drawing_path).get("columns", [])


def detect_beams(drawing_path: Path) -> list[dict[str, Any]]:
    return extract_dimensions(drawing_path).get("beams", [])


def drawing_to_plan_schema(drawing_json: dict[str, Any]) -> PlanSchema:
    """Convert drawing_parser output JSON to existing PlanSchema."""
    schema = PlanSchema()
    for d in drawing_json.get("doors", []):
        schema.doors.append(DoorSpec(
            id=d.get("id", "D?"), width_mm=d.get("width_mm", 900), height_mm=d.get("height_mm", 2100),
        ))
    for c in drawing_json.get("columns", []):
        schema.columns.append(ColumnSpec(
            id=c.get("id", "C?"), section=f"{c.get('width_mm', 300):.0f}x{c.get('width_mm', 300):.0f}",
        ))
    for b in drawing_json.get("beams", []):
        schema.beams.append(BeamSpec(
            id=b.get("id", "B?"), width_mm=b.get("width_mm", 230), depth_mm=b.get("depth_mm", 450),
        ))
    return schema
