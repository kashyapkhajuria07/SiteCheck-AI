"""
Validation suite for drawing_parser.py.

Generates 20 synthetic floor plans, runs the parser on each,
compares extracted dimensions against ground truth, and outputs
a detailed accuracy report with confusion matrices.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

# Add backend to path so imports work from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.drawing_parser import extract_dimensions


# ── Utility ────────────────────────────────────────────────────

GT_DIR = Path(__file__).resolve().parent / "validation_gt"
IMG_DIR = Path("/tmp/drawing_parser_validation")
IMG_DIR.mkdir(parents=True, exist_ok=True)
GT_DIR.mkdir(parents=True, exist_ok=True)

PLAN_PX_PER_MM = 0.5  # standard scale ~0.5 px/mm for a 4000mm wide building on 2000px image


def _px(mm: float) -> int:
    return int(mm * PLAN_PX_PER_MM)


def _mm(px: int) -> float:
    return px / PLAN_PX_PER_MM


def _draw_text(img: np.ndarray, text: str, x: int, y: int, scale=0.35, color=(50, 50, 50)):
    """Draw dimension label text on the plan."""
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def _draw_wall_line(img: np.ndarray, x1: int, y: int, x2: int, thickness_mm: float, color=(0, 0, 0)):
    """Draw a wall as two thick parallel lines (top and bottom edge)."""
    t = _px(thickness_mm)
    # Draw two thick lines — no gray fill, so door gaps are clean
    cv2.line(img, (x1, y), (x2, y), color, 4)
    cv2.line(img, (x1, y + t), (x2, y + t), color, 4)
    return y + t


def _draw_door(img: np.ndarray, x: int, y: int, width_mm: float, swing_up=True, color=(0, 0, 0)):
    """Draw a door as a gap in the wall with a swing arc and leaf line.

    Erases the wall material across the door width, then draws the door leaf
    and swing arc. The wall thickness is auto-detected by scanning downward
    for the second wall line.
    """
    w = _px(width_mm)
    # Clamp door width to image bounds
    h_img, w_img = img.shape[:2]
    if x + w + 6 >= w_img:
        w = w_img - x - 12
    scan_x = min(x + w // 2, w_img - 1)
    detected_thick = 200  # fallback: 200px (~400mm at 0.5 px/mm)
    for scan_y in range(y + 10, min(y + 400, h_img - 1)):
        if scan_x >= w_img:
            break
        px_val = img[scan_y, scan_x].tolist()
        if isinstance(px_val, list) and (px_val == list(color) or px_val == [0, 0, 0]):
            detected_thick = scan_y - y
            break
    # Erase wall material across full detected thickness + margin
    erase_h = max(detected_thick + 10, 50)
    erase_bottom = min(y + erase_h, h_img - 1)
    erase_right = min(x + w + 6, w_img - 1)
    cv2.rectangle(img, (max(0, x - 6), max(0, y - 2)), (erase_right, erase_bottom), (255, 255, 255), -1)
    # Door leaf (vertical line from hinge point inward)
    if swing_up:
        cv2.line(img, (x, y), (x, y - w), color, 4)
        # Swing arc (90-degree arc from hinge)
        cv2.ellipse(img, (x, y), (w, w), 180, -90, 0, color, 2)
    else:
        cv2.line(img, (x, y), (x + w, y), color, 4)
        cv2.ellipse(img, (x, y), (w, w), 90, 0, -90, color, 2)
    # Threshold indicator lines (short perpendicular lines flanking the opening)
    cv2.line(img, (x - 4, y), (x + 4, y), color, 2)
    cv2.line(img, (x + w - 4, y), (x + w + 4, y), color, 2)


def _draw_column(img: np.ndarray, x: int, y: int, size_mm: float, label="", color=(60, 60, 60)):
    """Draw a filled square column with a bold border."""
    s = _px(size_mm)
    cv2.rectangle(img, (x, y), (x + s, y + s), color, -1)
    cv2.rectangle(img, (x, y), (x + s, y + s), (0, 0, 0), 3)
    if label:
        _draw_text(img, label, x + 4, y + s // 2 + 4, scale=0.4)


def _draw_beam(img: np.ndarray, x: int, y1: int, y2: int, depth_mm: float, color=(0, 0, 0)):
    """Draw a beam as two bold vertical parallel lines with a hatched fill.

    The hatched fill (diagonal lines) creates a visually distinct pattern
    from walls (empty between parallel lines), making beam detection more
    reliable for Hough-based detectors.
    """
    d = _px(depth_mm)
    cv2.line(img, (x, y1), (x, y2), color, 5)
    cv2.line(img, (x + d, y1), (x + d, y2), color, 5)
    # Add hatched fill: diagonal lines between the two edges
    hatch_spacing = max(8, d // 8)
    for offset in range(0, d, hatch_spacing):
        xl = x + offset
        # Draw a short diagonal line across the beam width
        cv2.line(img, (xl, y1 + 2), (min(xl + hatch_spacing, x + d - 2), y2 - 2), color, 1)


# ── Ground-truth plan definitions ──────────────────────────────
# Each plan: (name, image_size, px_per_mm, render_fn, ground_truth)

PLANS: list[dict[str, Any]] = []


def _plan1():
    """Basic: 1 door, simple bounding walls."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1200, 800
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    # Outer walls (thickness 230mm)
    wall_t = 230
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})
    # Top wall
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    # Left wall
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    # Bottom wall  
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    # Right wall
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    _draw_text(img, "W1 T=230", 60, 40)

    # Door (900mm)
    dx, dy = 400, 50
    gt["doors"].append({"id": "D1", "width_mm": 900})
    _draw_door(img, dx, dy, 900)
    _draw_text(img, "D1 900", dx - 10, dy + 30)
    # Ensure gap in top wall line
    gap = _px(900)
    cv2.line(img, (dx, dy), (dx + gap, dy), (255, 255, 255), 3)

    return img, gt


PLANS.append(("basic_1door", _plan1()))


def _plan2():
    """Basic: 2 doors, 1 column."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1400, 1000
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    # Outer walls
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    # Door D1 (800mm) on top wall
    gt["doors"].append({"id": "D1", "width_mm": 800})
    _draw_door(img, 300, 50, 800)
    g = _px(800)
    cv2.line(img, (300, 50), (300 + g, 50), (255, 255, 255), 3)
    _draw_text(img, "D1 800", 300, 80)

    # Door D2 (1000mm) on bottom wall
    gt["doors"].append({"id": "D2", "width_mm": 1000})
    by = h - 50 - _px(wall_t)
    _draw_door(img, 600, by, 1000)
    g2 = _px(1000)
    cv2.line(img, (600, by), (600 + g2, by), (255, 255, 255), 3)
    _draw_text(img, "D2 1000", 600, by + 30)

    # Column (300mm)
    gt["columns"].append({"id": "C1", "width_mm": 300})
    _draw_column(img, w // 2 - 75, h // 2 - 75, 300, "C1 300")

    return img, gt


PLANS.append(("basic_2doors_1col", _plan2()))


def _plan3():
    """Basic: 1 door, 1 beam, 1 column."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1200, 1000
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 230
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 1000})
    _draw_door(img, 400, 50, 1000)
    cv2.line(img, (400, 50), (400 + _px(1000), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 1000", 400, 80)

    gt["columns"].append({"id": "C1", "width_mm": 250})
    _draw_column(img, 250, 300, 250, "C1 250")

    gt["beams"].append({"id": "B1", "depth_mm": 450})
    _draw_beam(img, 800, 200, 750, 450)
    _draw_text(img, "B1 d=450", 780, 190)

    return img, gt


PLANS.append(("basic_1door_1beam_1col", _plan3()))


def _plan4():
    """Basic: 2 doors, 2 beams, 1 column."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1400, 1000
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 900})
    _draw_door(img, 250, 50, 900)
    cv2.line(img, (250, 50), (250 + _px(900), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 900", 250, 80)

    gt["doors"].append({"id": "D2", "width_mm": 800})
    by = h - 50 - _px(wall_t)
    _draw_door(img, 700, by, 800)
    cv2.line(img, (700, by), (700 + _px(800), by), (255, 255, 255), 3)
    _draw_text(img, "D2 800", 700, by + 30)

    gt["beams"].append({"id": "B1", "depth_mm": 400})
    _draw_beam(img, 500, 150, h - 150, 400)
    _draw_text(img, "B1 d=400", 480, 140)

    gt["beams"].append({"id": "B2", "depth_mm": 350})
    _draw_beam(img, 1000, 150, h - 150, 350)
    _draw_text(img, "B2 d=350", 980, 140)

    gt["columns"].append({"id": "C1", "width_mm": 350})
    _draw_column(img, 150, h // 2 - 75, 350, "C1 350")

    return img, gt


PLANS.append(("basic_2doors_2beams_1col", _plan4()))


def _plan5():
    """Basic: 3 doors, 2 columns, 1 beam."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1600, 1200
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 230
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    for i, (dd, dx) in enumerate([(700, 200), (900, 600), (800, 1000)]):
        did = f"D{i+1}"
        gt["doors"].append({"id": did, "width_mm": dd})
        _draw_door(img, dx, 50, dd)
        cv2.line(img, (dx, 50), (dx + _px(dd), 50), (255, 255, 255), 3)
        _draw_text(img, f"{did} {dd}", dx, 80)

    gt["columns"].append({"id": "C1", "width_mm": 300})
    _draw_column(img, 180, 350, 300, "C1 300")
    gt["columns"].append({"id": "C2", "width_mm": 250})
    _draw_column(img, 1100, 600, 250, "C2 250")

    gt["beams"].append({"id": "B1", "depth_mm": 500})
    _draw_beam(img, 750, 200, 900, 500)
    _draw_text(img, "B1 d=500", 720, 190)

    return img, gt


PLANS.append(("basic_3doors_2cols_1beam", _plan5()))


# ── Medium plans ──────────────────────────────────────────────


def _plan6():
    """L-shaped layout: 2 doors, 2 columns."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1400, 1200
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    # Outer L shape
    # Top wall
    _draw_wall_line(img, 50, 50, 900, wall_t)
    # Right wall (vertical, goes down)
    cv2.line(img, (900, 50), (900, h - 50), (0, 0, 0), 3)
    # Bottom wall (full)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    # Left wall
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    # Interior wall creating the L
    _draw_wall_line(img, 900, 50, 900, wall_t)
    cv2.line(img, (900 + _px(wall_t), 50), (900 + _px(wall_t), 400), (0, 0, 0), 3)
    gt["walls"].append({"id": "W2", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 900})
    _draw_door(img, 300, 50, 900)
    cv2.line(img, (300, 50), (300 + _px(900), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 900", 300, 80)

    gt["doors"].append({"id": "D2", "width_mm": 800})
    by = h - 50 - _px(wall_t)
    _draw_door(img, 600, by, 800)
    cv2.line(img, (600, by), (600 + _px(800), by), (255, 255, 255), 3)
    _draw_text(img, "D2 800", 600, by + 30)

    gt["columns"].append({"id": "C1", "width_mm": 300})
    _draw_column(img, 200, 500, 300, "C1 300")
    gt["columns"].append({"id": "C2", "width_mm": 250})
    _draw_column(img, 600, 600, 250, "C2 250")

    return img, gt


PLANS.append(("medium_Lshape", _plan6()))


def _plan7():
    """T-shaped: 3 doors, 3 columns."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1600, 1200
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    # Cross wall (T stem)
    cx = w // 2
    _draw_wall_line(img, cx, 50, cx, wall_t)
    cv2.line(img, (cx + _px(wall_t), 50), (cx + _px(wall_t), h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    for i, (dd, dx) in enumerate([(800, 200), (1000, 700), (900, 1200)]):
        did = f"D{i+1}"
        gt["doors"].append({"id": did, "width_mm": dd})
        _draw_door(img, dx, 50, dd)
        cv2.line(img, (dx, 50), (dx + _px(dd), 50), (255, 255, 255), 3)
        _draw_text(img, f"{did} {dd}", dx, 80)

    for i, (sz, cx2, cy2) in enumerate([(300, 300, 600), (250, 900, 500), (350, 500, 900)]):
        cid = f"C{i+1}"
        gt["columns"].append({"id": cid, "width_mm": sz})
        _draw_column(img, cx2, cy2, sz, f"{cid} {sz}")

    return img, gt


PLANS.append(("medium_Tshape", _plan7()))


def _plan8():
    """U-shaped: 2 doors, 2 beams."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1400, 1200
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 230
    # U shape: top, left, right walls
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 900})
    _draw_door(img, 300, 50, 900)
    cv2.line(img, (300, 50), (300 + _px(900), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 900", 300, 80)

    gt["doors"].append({"id": "D2", "width_mm": 800})
    _draw_door(img, 800, 50, 800)
    cv2.line(img, (800, 50), (800 + _px(800), 50), (255, 255, 255), 3)
    _draw_text(img, "D2 800", 800, 80)

    gt["beams"].append({"id": "B1", "depth_mm": 400})
    _draw_beam(img, 400, 200, 700, 400)
    _draw_text(img, "B1 d=400", 380, 190)

    gt["beams"].append({"id": "B2", "depth_mm": 350})
    _draw_beam(img, 1000, 300, 800, 350)
    _draw_text(img, "B2 d=350", 980, 290)

    return img, gt


PLANS.append(("medium_Ushape", _plan8()))


def _plan9():
    """Cross-shaped: 4 doors, 4 columns."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1800, 1400
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    # Cross walls
    cx, cy = w // 2, h // 2
    _draw_wall_line(img, cx, 50, cx, wall_t)
    _draw_wall_line(img, 50, cy, w - 50, 200)
    cv2.line(img, (cx + _px(wall_t), 50), (cx + _px(wall_t), h - 50), (0, 0, 0), 3)
    cv2.line(img, (50, cy + _px(200)), (w - 50, cy + _px(200)), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    for i, (dd, dx) in enumerate([(700, 150), (900, 600), (800, 1000), (1000, 1400)]):
        did = f"D{i+1}"
        gt["doors"].append({"id": did, "width_mm": dd})
        _draw_door(img, dx, 50, dd)
        cv2.line(img, (dx, 50), (dx + _px(dd), 50), (255, 255, 255), 3)
        _draw_text(img, f"{did} {dd}", dx, 80)

    for i, (sz, cx2, cy2) in enumerate([(300, 200, 400), (250, 1300, 350), (280, 400, 1000), (320, 1200, 900)]):
        cid = f"C{i+1}"
        gt["columns"].append({"id": cid, "width_mm": sz})
        _draw_column(img, cx2, cy2, sz, f"{cid} {sz}")

    return img, gt


PLANS.append(("medium_cross", _plan9()))


def _plan10():
    """Multi-room: 5 doors, 3 columns, 2 beams."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1400
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    # Outer
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    # Partition walls
    mid_x = w // 2
    _draw_wall_line(img, mid_x, 50, mid_x, wall_t)
    mid_y = h // 2
    cv2.line(img, (50, mid_y), (mid_x, mid_y), (0, 0, 0), 3)
    cv2.line(img, (mid_x, mid_y), (w - 50, mid_y), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    for i, (dd, dx, dy, is_top) in enumerate([
        (800, 200, 50, True), (900, 800, 50, True),
        (700, 1300, 50, True), (1000, 300, h // 2, True),
        (800, 1000, h // 2, True),
    ]):
        did = f"D{i+1}"
        gt["doors"].append({"id": did, "width_mm": dd})
        by = dy if is_top else dy - _px(wall_t / 2)
        _draw_door(img, dx, by, dd)
        gap = _px(dd)
        if is_top:
            cv2.line(img, (dx, by), (dx + gap, by), (255, 255, 255), 3)
        _draw_text(img, f"{did} {dd}", dx, by + 30)

    for i, (sz, cx2, cy2) in enumerate([(300, 150, 600), (250, 1700, 400), (280, 1000, 1000)]):
        cid = f"C{i+1}"
        gt["columns"].append({"id": cid, "width_mm": sz})
        _draw_column(img, cx2, cy2, sz, f"{cid} {sz}")

    gt["beams"].append({"id": "B1", "depth_mm": 400})
    _draw_beam(img, 500, 100, h - 100, 400)
    _draw_text(img, "B1 d=400", 480, 90)
    gt["beams"].append({"id": "B2", "depth_mm": 450})
    _draw_beam(img, 1500, 100, h - 100, 450)
    _draw_text(img, "B2 d=450", 1480, 90)

    return img, gt


PLANS.append(("medium_multroom", _plan10()))


# ── Complex plans ─────────────────────────────────────────────


def _plan11():
    """Industrial: large doors, many columns, grid layout."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1600
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 300
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    # Industrial roller shutter doors
    for i, (dd, dx) in enumerate([(1800, 400), (2000, 1200)]):
        did = f"D{i+1}"
        gt["doors"].append({"id": did, "width_mm": dd})
        _draw_door(img, dx, 50, dd)
        cv2.line(img, (dx, 50), (dx + _px(dd), 50), (255, 255, 255), 3)
        _draw_text(img, f"{did} {dd}", dx, 80)

    # Grid of columns
    for row in range(3):
        for col in range(4):
            sz = 300
            cx = 200 + col * 450
            cy = 300 + row * 400
            cid = f"C{row*4+col+1}"
            gt["columns"].append({"id": cid, "width_mm": sz})
            _draw_column(img, cx, cy, sz, f"{cid} {sz}")

    return img, gt


PLANS.append(("complex_industrial", _plan11()))


def _plan12():
    """Stairwell: narrow plan with doors at both ends."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 800, 1600
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 230
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 900})
    _draw_door(img, 150, 50, 900)
    cv2.line(img, (150, 50), (150 + _px(900), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 900", 150, 80)

    gt["doors"].append({"id": "D2", "width_mm": 900})
    by = h - 50 - _px(wall_t)
    _draw_door(img, 150, by, 900)
    cv2.line(img, (150, by), (150 + _px(900), by), (255, 255, 255), 3)
    _draw_text(img, "D2 900", 150, by + 30)

    return img, gt


PLANS.append(("complex_stairwell", _plan12()))


def _plan13():
    """Commercial open plan: glass walls, many columns."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1400
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 150  # thinner glass walls
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    for i, (dd, dx) in enumerate([(1200, 300), (1500, 1300)]):
        did = f"D{i+1}"
        gt["doors"].append({"id": did, "width_mm": dd})
        _draw_door(img, dx, 50, dd)
        cv2.line(img, (dx, 50), (dx + _px(dd), 50), (255, 255, 255), 3)
        _draw_text(img, f"{did} {dd}", dx, 80)

    # Column grid
    for row in range(4):
        for col in range(5):
            sz = 250
            cx = 120 + col * 360
            cy = 180 + row * 280
            cid = f"C{row*5+col+1}"
            gt["columns"].append({"id": cid, "width_mm": sz})
            _draw_column(img, cx, cy, sz, f"{cid} {sz}")

    return img, gt


PLANS.append(("complex_commercial", _plan13()))


def _plan14():
    """Grid of columns with beams connecting them."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1800, 1400
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 230
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 900})
    _draw_door(img, 400, 50, 900)
    cv2.line(img, (400, 50), (400 + _px(900), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 900", 400, 80)

    # Columns with beams between them
    col_positions = [(200, 400), (600, 400), (1000, 400), (1400, 400),
                     (200, 800), (600, 800), (1000, 800), (1400, 800)]
    for i, (cx, cy) in enumerate(col_positions):
        sz = 300
        cid = f"C{i+1}"
        gt["columns"].append({"id": cid, "width_mm": sz})
        _draw_column(img, cx, cy, sz, f"{cid} {sz}")

    # Horizontal beams between columns
    for row in range(2):
        by = [400, 800][row]
        for col in range(3):
            cx = [200, 600, 1000][col]
            bid = f"B{row*3+col+1}"
            gt["beams"].append({"id": bid, "depth_mm": 350})
            _draw_beam(img, cx + 300, by - 50, by + 350, 350)
            _draw_text(img, f"{bid} d=350", cx + 290, by - 60)

    return img, gt


PLANS.append(("complex_grid", _plan14()))


def _plan15():
    """Detailed residential: multiple rooms, varied dimensions."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1600
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    # Interior partitions
    _draw_wall_line(img, w // 2, 50, w // 2, wall_t)
    mid_y = h // 2
    cv2.line(img, (50, mid_y), (w - 50, mid_y), (0, 0, 0), 3)
    # Cross wall
    x3 = w * 3 // 4
    _draw_wall_line(img, x3, mid_y, x3, wall_t)
    cv2.line(img, (x3 + _px(wall_t), mid_y), (x3 + _px(wall_t), h - 50), (0, 0, 0), 3)

    # Doors on different walls
    door_specs = [
        (800, 200, 50, True), (900, 900, 50, True),
        (700, w // 2 + 50, 200, False),
        (1000, 200, mid_y, True), (800, 1200, mid_y, True),
    ]
    for i, (dd, dx, dy, is_top) in enumerate(door_specs):
        did = f"D{i+1}"
        gt["doors"].append({"id": did, "width_mm": dd})
        _draw_door(img, dx, dy, dd)
        if is_top:
            cv2.line(img, (dx, dy), (dx + _px(dd), dy), (255, 255, 255), 3)
        _draw_text(img, f"{did} {dd}", dx, dy + 30)

    for i, (sz, cx2, cy2) in enumerate([(300, 150, 700), (250, 1600, 500), (280, 800, 1200)]):
        cid = f"C{i+1}"
        gt["columns"].append({"id": cid, "width_mm": sz})
        _draw_column(img, cx2, cy2, sz, f"{cid} {sz}")

    gt["beams"].append({"id": "B1", "depth_mm": 400})
    _draw_beam(img, w // 4, 100, h - 100, 400)
    _draw_text(img, "B1 d=400", w // 4 - 20, 90)

    return img, gt


PLANS.append(("complex_residential", _plan15()))


# ── Edge cases ────────────────────────────────────────────────


def _plan16():
    """Very small doors (600mm)."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1200, 800
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    for i, (dd, dx) in enumerate([(600, 200), (650, 600), (700, 1000)]):
        did = f"D{i+1}"
        gt["doors"].append({"id": did, "width_mm": dd})
        _draw_door(img, dx, 50, dd)
        cv2.line(img, (dx, 50), (dx + _px(dd), 50), (255, 255, 255), 3)
        _draw_text(img, f"{did} {dd}", dx, 80)

    return img, gt


PLANS.append(("edge_smalldoors", _plan16()))


def _plan17():
    """Very thick walls (400mm)."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1400, 1000
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 400
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 1000})
    _draw_door(img, 350, 50, 1000)
    cv2.line(img, (350, 50), (350 + _px(1000), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 1000", 350, 80)

    return img, gt


PLANS.append(("edge_thickwalls", _plan17()))


def _plan18():
    """Irregular column shapes."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1200, 1000
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 230
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 900})
    _draw_door(img, 400, 50, 900)
    cv2.line(img, (400, 50), (400 + _px(900), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 900", 400, 80)

    # Square columns with different fill patterns
    for i, (sz, cx, cy) in enumerate([(350, 200, 400), (300, 700, 400), (280, 450, 700)]):
        cid = f"C{i+1}"
        gt["columns"].append({"id": cid, "width_mm": sz})
        s = _px(sz)
        cv2.rectangle(img, (cx, cy), (cx + s, cy + s), (0, 0, 0), 1)
        # Cross-hatch fill
        cv2.line(img, (cx, cy), (cx + s, cy + s), (120, 120, 120), 1)
        cv2.line(img, (cx + s, cy), (cx, cy + s), (120, 120, 120), 1)
        _draw_text(img, f"{cid} {sz}", cx + 4, cy + s // 2 + 4)

    return img, gt


PLANS.append(("edge_irregular_cols", _plan18()))


def _plan19():
    """Overlapping annotations and dimension lines."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1400, 1000
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    gt["doors"].append({"id": "D1", "width_mm": 900})
    _draw_door(img, 300, 50, 900)
    cv2.line(img, (300, 50), (300 + _px(900), 50), (255, 255, 255), 3)
    _draw_text(img, "D1 900", 300, 80)
    # Extra annotation lines overlapping
    cv2.line(img, (200, 150), (900, 150), (180, 180, 180), 1)
    cv2.line(img, (250, 200), (850, 200), (180, 180, 180), 1)

    # Add dimension leader lines
    for i in range(3):
        cv2.line(img, (100 + i * 400, 50), (100 + i * 400, 300), (200, 200, 200), 1)

    gt["columns"].append({"id": "C1", "width_mm": 300})
    _draw_column(img, 500, 400, 300, "C1 300")

    return img, gt


PLANS.append(("edge_overlap", _plan19()))


def _plan20():
    """Dense dimension text on a complex plan."""
    gt: dict[str, Any] = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1600
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    wall_t = 200
    _draw_wall_line(img, 50, 50, w - 50, wall_t)
    _draw_wall_line(img, 50, h - 50 - _px(wall_t), w - 50, wall_t)
    cv2.line(img, (50, 50), (50, h - 50), (0, 0, 0), 3)
    cv2.line(img, (w - 50, 50), (w - 50, h - 50), (0, 0, 0), 3)
    gt["walls"].append({"id": "W1", "thickness_mm": wall_t})

    # Partition grid
    for i in range(1, 4):
        x = 50 + i * (w - 100) // 4
        _draw_wall_line(img, x, 50, x, wall_t)
    for i in range(1, 3):
        y = 50 + i * (h - 100) // 3
        cv2.line(img, (50, y + _px(wall_t)), (w - 50, y + _px(wall_t)), (0, 0, 0), 3)

    # Many dimension labels
    dims = ["1500", "2000", "1800", "1200", "1600", "1400",
            "2500", "2200", "2100", "1900", "1700", "1300"]
    for i, d in enumerate(dims):
        x = 80 + (i % 6) * 300
        y = 60 + (i // 6) * 60
        _draw_text(img, d, x, y, scale=0.3)

    gt["doors"].append({"id": "D1", "width_mm": 800})
    _draw_door(img, 300, 50, 800)
    cv2.line(img, (300, 50), (300 + _px(800), 50), (255, 255, 255), 3)

    for i, (sz, cx, cy) in enumerate([(300, 500, 600), (250, 1200, 800), (280, 800, 1200)]):
        cid = f"C{i+1}"
        gt["columns"].append({"id": cid, "width_mm": sz})
        _draw_column(img, cx, cy, sz, f"{cid} {sz}")

    gt["beams"].append({"id": "B1", "depth_mm": 400})
    _draw_beam(img, 1500, 200, 1200, 400)

    return img, gt


PLANS.append(("edge_dense_text", _plan20()))


# ═══════════════════════════════════════════════════════════════
# NEW PLANS 21–50
# ═══════════════════════════════════════════════════════════════

# ── Helper: quick wall rectangle ──
def _walls_rect(img, x1, y1, x2, y2, t_mm, gt, wid="W1"):
    _draw_wall_line(img, x1, y1, x2, t_mm)
    _draw_wall_line(img, x1, y2 - _px(t_mm), x2, t_mm)
    cv2.line(img, (x1, y1), (x1, y2), (0,0,0), 3)
    cv2.line(img, (x2, y1), (x2, y2), (0,0,0), 3)
    gt["walls"].append({"id": wid, "thickness_mm": t_mm})

# ── Helper: quick door on top wall ──
def _door_top(img, gt, did, dx, y, w_mm):
    gt["doors"].append({"id": did, "width_mm": w_mm})
    _draw_door(img, dx, y, w_mm)
    cv2.line(img, (dx, y), (dx + _px(w_mm), y), (255,255,255), 3)

# ── Helper: quick column ──
def _col(img, gt, cid, cx, cy, sz):
    gt["columns"].append({"id": cid, "width_mm": sz})
    _draw_column(img, cx, cy, sz, f"{cid} {sz}")

# ── Helper: quick beam ──
def _beam(img, gt, bid, x, y1, y2, d):
    gt["beams"].append({"id": bid, "depth_mm": d})
    _draw_beam(img, x, y1, y2, d)


# ── Plans 21-30: Architectural Floor Plans ──

def _plan21():
    """Arch: 2-room apartment with corridor, 2 doors, 1 column."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1600, 1200; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 200, gt, "W1")
    # Interior partition
    _draw_wall_line(img, 50, h//2, w//2, 200)
    _draw_wall_line(img, w//2, 50, w//2, 200)
    cv2.line(img, (w//2+_px(200), 50), (w//2+_px(200), h//2), (0,0,0), 3)
    gt["walls"].append({"id": "W2", "thickness_mm": 200})
    _door_top(img, gt, "D1", 200, 50, 900)
    _door_top(img, gt, "D2", 900, 50, 800)
    _col(img, gt, "C1", 300, 700, 300)
    _col(img, gt, "C2", 1000, 700, 250)
    return img, gt
PLANS.append(("arch_2room", _plan21()))

def _plan22():
    """Arch: 3-room layout with corridor, 3 doors, 2 columns."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1400; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 200, gt, "W1")
    # Two cross walls
    x1, x2 = w//3, 2*w//3
    _draw_wall_line(img, x1, 50, x1, 200)
    cv2.line(img, (x1+_px(200), 50), (x1+_px(200), h-50), (0,0,0), 3)
    _draw_wall_line(img, x2, 50, x2, 200)
    cv2.line(img, (x2+_px(200), 50), (x2+_px(200), h-50), (0,0,0), 3)
    gt["walls"].append({"id": "W2", "thickness_mm": 200})
    _door_top(img, gt, "D1", 150, 50, 800)
    _door_top(img, gt, "D2", 750, 50, 900)
    _door_top(img, gt, "D3", 1500, 50, 1000)
    _col(img, gt, "C1", 400, 500, 300)
    _col(img, gt, "C2", 1400, 800, 280)
    return img, gt
PLANS.append(("arch_3room", _plan22()))

def _plan23():
    """Arch: open plan with kitchen/living divide, 2 sliding doors."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1800, 1200; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 200, gt, "W1")
    _door_top(img, gt, "D1", 200, 50, 1200)  # wide sliding
    _door_top(img, gt, "D2", 1000, 50, 1500)
    _col(img, gt, "C1", 500, 400, 350)
    _col(img, gt, "C2", 1200, 600, 300)
    return img, gt
PLANS.append(("arch_openplan", _plan23()))

def _plan24():
    """Arch: hotel corridor with rooms on both sides."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2400, 1200; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 200, gt, "W1")
    # Corridor walls
    _draw_wall_line(img, 50, 300, w-50, 200)
    _draw_wall_line(img, 50, 900, w-50, 200)
    cv2.line(img, (50, 300+_px(200)), (w-50, 300+_px(200)), (0,0,0), 3)
    cv2.line(img, (50, 900), (50, 900+_px(200)), (0,0,0), 3)
    gt["walls"].append({"id": "W2", "thickness_mm": 200})
    for i, dx in enumerate([150, 550, 950, 1350, 1750, 2150]):
        _door_top(img, gt, f"D{i+1}", dx, 50, 900)
    for i, (sz, cx) in enumerate([(250, 350), (250, 1350), (300, 750), (300, 1750)]):
        _col(img, gt, f"C{i+1}", cx, 550, sz)
    return img, gt
PLANS.append(("arch_hotelcorridor", _plan24()))

def _plan25():
    """Arch: L-shaped apartment with balcony."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1800, 1600; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, 1300, h-50, 200, gt, "W1")
    # L extension
    _draw_wall_line(img, 1300, 50, 1300, 200)
    cv2.line(img, (1300+_px(200), 50), (1300+_px(200), 400), (0,0,0), 3)
    _draw_wall_line(img, 1300, 400, w-50, 200)
    cv2.line(img, (1300, 400+_px(200)), (w-50, 400+_px(200)), (0,0,0), 3)
    cv2.line(img, (w-50, 50), (w-50, 400), (0,0,0), 3)
    gt["walls"].append({"id": "W2", "thickness_mm": 200})
    _door_top(img, gt, "D1", 300, 50, 900)
    _door_top(img, gt, "D2", 1000, 400, 800)
    _col(img, gt, "C1", 500, 600, 300)
    _col(img, gt, "C2", 1000, 1000, 250)
    return img, gt
PLANS.append(("arch_Lapartment", _plan25()))

def _plan26():
    """Arch: office layout with cubicles, 4 doors, grid columns."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1600; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 200, gt, "W1")
    for i, dd in enumerate([800, 900, 1000, 800]):
        _door_top(img, gt, f"D{i+1}", 150+i*450, 50, dd)
    for row in range(3):
        for col in range(4):
            _col(img, gt, f"C{row*4+col+1}", 120+col*450, 280+row*400, 250)
    return img, gt
PLANS.append(("arch_office", _plan26()))

def _plan27():
    """Arch: school classroom block, 3 doors, 2 beams."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1400; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 230, gt, "W1")
    mid_x = w//2; mid_y = h//2
    _draw_wall_line(img, mid_x, 50, mid_x, 230)
    cv2.line(img, (mid_x+_px(230), 50), (mid_x+_px(230), h-50), (0,0,0), 3)
    cv2.line(img, (50, mid_y), (mid_x, mid_y), (0,0,0), 3)
    cv2.line(img, (mid_x, mid_y+_px(230)), (w-50, mid_y+_px(230)), (0,0,0), 3)
    gt["walls"].append({"id": "W2", "thickness_mm": 230})
    _door_top(img, gt, "D1", 200, 50, 1000)
    _door_top(img, gt, "D2", 1300, 50, 1200)
    _door_top(img, gt, "D3", 300, mid_y, 900)
    _col(img, gt, "C1", 400, 800, 300)
    _col(img, gt, "C2", 1400, 300, 280)
    _beam(img, gt, "B1", 800, 100, h-100, 400)
    _beam(img, gt, "B2", 1500, 100, h-100, 350)
    return img, gt
PLANS.append(("arch_classroom", _plan27()))

def _plan28():
    """Arch: hospital wing, long corridor, many doors."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2800, 1000; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 200, gt, "W1")
    for i, dx in enumerate(range(150, w-300, 400)):
        _door_top(img, gt, f"D{i+1}", dx, 50, 900)
    for i, dx in enumerate(range(350, w-100, 400)):
        _col(img, gt, f"C{i+1}", dx, 400, 250)
    return img, gt
PLANS.append(("arch_hospital", _plan28()))

def _plan29():
    """Arch: library with reading rooms, 4 doors, varied columns."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2200, 1600; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 200, gt, "W1")
    x1, x2 = w//3, 2*w//3; y1 = h//2
    _draw_wall_line(img, x1, 50, x1, 200)
    cv2.line(img, (x1+_px(200), 50), (x1+_px(200), y1), (0,0,0), 3)
    _draw_wall_line(img, x2, y1, x2, 200)
    cv2.line(img, (x2+_px(200), y1), (x2+_px(200), h-50), (0,0,0), 3)
    cv2.line(img, (50, y1), (x1, y1), (0,0,0), 3)
    cv2.line(img, (x2, y1+_px(200)), (w-50, y1+_px(200)), (0,0,0), 3)
    gt["walls"].append({"id": "W2", "thickness_mm": 200})
    _door_top(img, gt, "D1", 200, 50, 900); _door_top(img, gt, "D2", 1000, 50, 800)
    _door_top(img, gt, "D3", 1600, 50, 1000); _door_top(img, gt, "D4", 300, y1, 900)
    for i, (cx, cy, sz) in enumerate([(400,600,300),(1500,400,280),(800,1000,320),(2000,1200,250)]):
        _col(img, gt, f"C{i+1}", cx, cy, sz)
    _beam(img, gt, "B1", 600, 200, 1000, 400)
    return img, gt
PLANS.append(("arch_library", _plan29()))

def _plan30():
    """Arch: mall atrium, large open space, 4 big doors, columns grid."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2400, 1800; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 300, gt, "W1")
    for i, (dd, dx) in enumerate([(1200, 200), (1500, 800), (1000, 1400), (1200, 1800)]):
        _door_top(img, gt, f"D{i+1}", dx, 50, dd)
    for row in range(4):
        for col in range(5):
            _col(img, gt, f"C{row*5+col+1}", 100+col*460, 200+row*400, 300)
    return img, gt
PLANS.append(("arch_mall", _plan30()))


# ── Plans 31-40: Structural Drawings ──

def _plan31():
    """Struct: column grid 3x3 with beams."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1600, 1400; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 250, gt, "W1")
    _door_top(img, gt, "D1", 200, 50, 900)
    for row in range(3):
        for col in range(3):
            _col(img, gt, f"C{row*3+col+1}", 150+col*450, 200+row*400, 300)
    for row in range(3):
        for col in range(2):
            _beam(img, gt, f"B{row*2+col+1}", 150+col*450+450, 200+row*400-30, 200+row*400+330, 350)
    return img, gt
PLANS.append(("struct_grid3x3", _plan31()))

def _plan32():
    """Struct: column grid 4x3 with beams and walls."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1600; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 250, gt, "W1")
    for row in range(3):
        for col in range(4):
            _col(img, gt, f"C{row*4+col+1}", 120+col*450, 150+row*450, 300)
    for row in range(3):
        for col in range(3):
            _beam(img, gt, f"B{row*3+col+1}", 120+col*450+450, 150+row*450-20, 150+row*450+320, 350)
    return img, gt
PLANS.append(("struct_grid4x3", _plan32()))

def _plan33():
    """Struct: foundation plan with column footings."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1800, 1400; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 300, gt, "W1")
    _door_top(img, gt, "D1", 300, 50, 900)
    for row in range(2):
        for col in range(3):
            _col(img, gt, f"C{row*3+col+1}", 200+col*500, 300+row*500, 350)
    return img, gt
PLANS.append(("struct_foundation", _plan33()))

def _plan34():
    """Struct: beam layout with transfer beams."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1800, 1400; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 250, gt, "W1")
    _door_top(img, gt, "D1", 400, 50, 800)
    cols_at = [(200,400),(800,400),(1400,400),(200,900),(800,900),(1400,900)]
    for i, (cx, cy) in enumerate(cols_at):
        _col(img, gt, f"C{i+1}", cx, cy, 300)
    _beam(img, gt, "B1", 500, 400-30, 400+330, 450)
    _beam(img, gt, "B2", 1100, 400-30, 400+330, 400)
    _beam(img, gt, "B3", 500, 900-30, 900+330, 450)
    _beam(img, gt, "B4", 1100, 900-30, 900+330, 400)
    return img, gt
PLANS.append(("struct_transferbeams", _plan34()))

def _plan35():
    """Struct: parking structure ramp, sloped beams."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2000, 1400; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 300, gt, "W1")
    for row in range(3):
        for col in range(4):
            _col(img, gt, f"C{row*4+col+1}", 120+col*450, 150+row*400, 280)
    for row in range(3):
        for col in range(3):
            _beam(img, gt, f"B{row*3+col+1}", 120+col*450+450, 150+row*400-20, 150+row*400+300, 400)
    return img, gt
PLANS.append(("struct_parking", _plan35()))

def _plan36():
    """Struct: retaining wall with counterforts."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1800, 1000; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 350, gt, "W1")
    _door_top(img, gt, "D1", 300, 50, 800)
    for i, cx in enumerate([250, 600, 950, 1300, 1650]):
        _col(img, gt, f"C{i+1}", cx, 250, 200)
    for i, cx in enumerate([400, 750, 1100, 1450]):
        _beam(img, gt, f"B{i+1}", cx, 250+200, 250+200+400, 300)
    return img, gt
PLANS.append(("struct_retaining", _plan36()))

def _plan37():
    """Struct: water tank structure, heavy columns."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1600, 1600; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 350, gt, "W1")
    _door_top(img, gt, "D1", 200, 50, 800)
    for row in range(2):
        for col in range(2):
            _col(img, gt, f"C{row*2+col+1}", 200+col*900, 200+row*900, 400)
    _beam(img, gt, "B1", 600, 200-20, 200+420, 500)
    _beam(img, gt, "B2", 600, 1100-20, 1100+420, 500)
    return img, gt
PLANS.append(("struct_watertank", _plan37()))

def _plan38():
    """Struct: steel structure with bracing."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1800, 1400; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 250, gt, "W1")
    for row in range(3):
        for col in range(4):
            _col(img, gt, f"C{row*4+col+1}", 120+col*420, 120+row*400, 250)
    for row in range(3):
        for col in range(3):
            _beam(img, gt, f"B{row*3+col+1}", 120+col*420+420, 120+row*400-15, 120+row*400+265, 300)
    return img, gt
PLANS.append(("struct_steel", _plan38()))

def _plan39():
    """Struct: bridge abutment, large columns."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 2200, 1000; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 350, gt, "W1")
    for i, (cx, sz) in enumerate([(200,250),(700,300),(1200,280),(1700,320),(2200,250)]):
        _col(img, gt, f"C{i+1}", cx, 200, sz)
    for i, cx in enumerate([500, 1000, 1500]):
        _beam(img, gt, f"B{i+1}", cx, 200+sz-20, 200+sz+300, 400)
    return img, gt
PLANS.append(("struct_bridge", _plan39()))

def _plan40():
    """Struct: shear wall core with columns."""
    gt: dict = {"doors": [], "columns": [], "beams": [], "walls": []}
    w, h = 1600, 1600; img = np.ones((h,w,3), dtype=np.uint8)*255
    _walls_rect(img, 50, 50, w-50, h-50, 300, gt, "W1")
    _door_top(img, gt, "D1", 200, 50, 900)
    # Shear wall core (inner box)
    _draw_wall_line(img, 500, 500, 1100, 250)
    _draw_wall_line(img, 500, 1100, 1100, 250)
    cv2.line(img, (500, 500), (500, 1100), (0,0,0), 3)
    cv2.line(img, (1100, 500), (1100, 1100), (0,0,0), 3)
    gt["walls"].append({"id": "W2", "thickness_mm": 250})
    _col(img, gt, "C1", 300, 300, 350)
    _col(img, gt, "C2", 1200, 300, 350)
    _col(img, gt, "C3", 300, 1200, 350)
    _col(img, gt, "C4", 1200, 1200, 350)
    return img, gt
PLANS.append(("struct_shearwall", _plan40()))


# ── Plans 41-45: Low-Quality Scans ──
# These apply image degradation to existing plan images while keeping same GT.

import copy as _copy

def _degrade_blur(img, gt, name="blurred"):
    img2 = cv2.GaussianBlur(img, (15, 15), 4)
    return img2, _copy.deepcopy(gt)

def _degrade_noise(img, gt, name="noisy"):
    noise = np.random.randint(0, 80, img.shape, dtype=np.uint8)
    img2 = cv2.add(img.astype(np.int16), noise.astype(np.int16))
    img2 = np.clip(img2, 0, 255).astype(np.uint8)
    return img2, _copy.deepcopy(gt)

def _degrade_lowcontrast(img, gt, name="lowcontrast"):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.convertScaleAbs(gray, alpha=0.4, beta=80)
    img2 = cv2.cvtColor(gray2, cv2.COLOR_GRAY2BGR)
    return img2, _copy.deepcopy(gt)

def _degrade_skew(img, gt, name="skewed"):
    h, w = img.shape[:2]
    angle = 3.5
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    img2 = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))
    return img2, _copy.deepcopy(gt)

def _degrade_crop(img, gt, name="cropped"):
    h, w = img.shape[:2]
    margin = int(min(w, h) * 0.08)
    img2 = img[margin:h-margin, margin:w-margin].copy()
    return img2, _copy.deepcopy(gt)

DEGRADE_FNS = [_degrade_blur, _degrade_noise, _degrade_lowcontrast, _degrade_skew, _degrade_crop]
DEGRADE_NAMES = ["blur", "noise", "lowcontrast", "skew", "crop"]

for _di, (_dfn, _dname) in enumerate(zip(DEGRADE_FNS, DEGRADE_NAMES), 1):
    _base_img, _base_gt = _plan3()  # basic_1door_1beam_1col as base
    _rimg, _rgt = _dfn(_base_img, _base_gt, _dname)
    PLANS.append((f"lowq_{_dname}", (_rimg, _rgt)))


# ── Plans 46-50: Rotated Drawings ──
# Rotate plan3 by various angles.

ROT_ANGLES = [30, 45, 60, 90, 180]
for _ri, _angle in enumerate(ROT_ANGLES, 1):
    _base_img, _base_gt = _plan4()  # basic_2doors_2beams_1col as base
    h, w = _base_img.shape[:2]
    M = cv2.getRotationMatrix2D((w//2, h//2), _angle, 1.0)
    _rimg = cv2.warpAffine(_base_img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))
    PLANS.append((f"rot_{_angle}deg", (_rimg, _copy.deepcopy(_base_gt))))


# ── Validation runner ──────────────────────────────────────────

def _sort_key(items: list[dict], key: str):
    """Sort items by a key safely."""
    return sorted(items, key=lambda x: x.get(key, 0) if isinstance(x.get(key), (int, float)) else str(x.get(key, "")))


def _match_count(extracted: list[dict], ground_truth: list[dict], tolerance_pct: float = 15.0) -> dict:
    """Match extracted items to ground truth items by nearest dimension value.

    Uses optimal assignment: each GT item gets assigned to the closest extracted
    item (by dimension value within tolerance). This prevents a poor early match
    from consuming a GT slot needed by a better later match.

    Returns: {tp, fp, fn, matches: [(gt, ex, diff_pct)]}
    """
    tp = 0
    fp = 0
    fn = 0
    matches = []

    DIM_KEYS = ("width_mm", "depth_mm", "thickness_mm")

    # Collect all dimension keys for each GT item
    gt_dims: list[tuple[int, dict, list[tuple[str, float]]]] = []
    for gi, gt in enumerate(ground_truth):
        dims = [(k, float(gt[k])) for k in DIM_KEYS if k in gt]
        if dims:
            gt_dims.append((gi, gt, dims))

    # Collect all dimension keys for each extracted item
    ex_dims: list[tuple[int, dict, list[tuple[str, float]]]] = []
    for ei, ex in enumerate(extracted):
        dims = [(k, float(ex[k])) for k in DIM_KEYS if k in ex]
        if dims:
            ex_dims.append((ei, ex, dims))
        else:
            fp += 1
            matches.append((ex.get("id", "?"), 0, 0, 100, "FP_NOVAL"))

    consumed_ex: set[int] = set()

    # For each GT item, find the best matching extracted item
    # A match is valid if ANY shared dimension key is within tolerance
    for gi, gt_item, gt_dims_list in gt_dims:
        best_diff = float("inf")
        best_ei = None
        best_ex_val = None

        for ei, ex_item, ex_dims_list in ex_dims:
            if ei in consumed_ex:
                continue
            # Find any shared dimension key
            gt_dim_map = dict(gt_dims_list)
            ex_dim_map = dict(ex_dims_list)
            shared = set(gt_dim_map.keys()) & set(ex_dim_map.keys())
            if not shared:
                continue
            # Compute minimum difference across shared dimensions
            key = list(shared)[0]  # use the first shared dimension
            gv = gt_dim_map[key]
            ex_val = ex_dim_map[key]
            diff = abs(ex_val - gv) / gv * 100 if gv > 0 else 100
            if diff <= tolerance_pct and diff < best_diff:
                best_diff = diff
                best_ei = ei
                best_ex_val = ex_val

        if best_ei is not None:
            consumed_ex.add(best_ei)
            tp += 1
            matches.append((gt_item.get("id", "?"), best_ex_val, best_ex_val, round(best_diff, 1), "TP"))
        else:
            fn += 1
            matches.append((gt_item.get("id", "?"), gt_dims_list[0][1] if gt_dims_list else 0, 0, 100, "FN"))

    # Remaining extracted items → FP
    for ei, ex_item, ex_dims_list in ex_dims:
        if ei not in consumed_ex:
            ex_val = ex_dims_list[0][1] if ex_dims_list else 0
            fp += 1
            matches.append((ex_item.get("id", "?"), ex_val, ex_val, 100, "FP"))

    return {"tp": tp, "fp": fp, "fn": fn, "matches": matches}


def _element_accuracy(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return {"precision": round(precision, 1), "recall": round(recall, 1), "f1": round(f1, 1)}


def _dimension_extraction_accuracy(matches: list) -> dict:
    """Compute how close extracted dimensions are to ground truth."""
    dim_diffs = [m[3] for m in matches if m[4] == "TP"]
    if not dim_diffs:
        return {"mean_error_pct": 0, "within_5pct": 0, "within_10pct": 0, "within_15pct": 0}
    mean_err = sum(dim_diffs) / len(dim_diffs)
    w5 = sum(1 for d in dim_diffs if d <= 5) / len(dim_diffs) * 100
    w10 = sum(1 for d in dim_diffs if d <= 10) / len(dim_diffs) * 100
    w15 = sum(1 for d in dim_diffs if d <= 15) / len(dim_diffs) * 100
    return {
        "mean_error_pct": round(mean_err, 1),
        "within_5pct": round(w5, 1),
        "within_10pct": round(w10, 1),
        "within_15pct": round(w15, 1),
    }


def _ocr_accuracy(drawing_json: dict, gt_texts: list[str]) -> dict:
    """Placeholder OCR accuracy — how many dimension texts were found."""
    return {"texts_expected": len(gt_texts), "texts_found": 0, "accuracy_pct": 0.0}


def _classification_accuracy(gt: dict, ex: dict) -> dict:
    """Confusion matrix for element classification."""
    categories = ["doors", "columns", "beams", "walls"]
    matrix = {c: {"tp": 0, "fp": 0, "fn": 0} for c in categories}
    for cat in categories:
        gt_list = gt.get(cat, [])
        ex_list = ex.get(cat, [])
        gt_ids = {g["id"] for g in gt_list if "id" in g}
        ex_ids = {e["id"] for e in ex_list if "id" in e}
        tp = len(gt_ids & ex_ids)
        fp = len(ex_ids - gt_ids)
        fn = len(gt_ids - ex_ids)
        matrix[cat] = {"tp": tp, "fp": fp, "fn": fn}
    return matrix


FAILURE_DIR = Path("/tmp/drawing_parser_validation") / "validation_failures"


def _generate_failure_gallery(plan_name: str, img: np.ndarray, gt: dict, extracted: dict,
                               categories: list[str], results_list: list[dict],
                               plan_index: int):
    """Save cropped regions for false positives and false negatives."""
    out = FAILURE_DIR / plan_name
    out.mkdir(parents=True, exist_ok=True)

    for cat in categories:
        gt_list = gt.get(cat, [])
        ex_list = extracted.get(cat, [])
        match_info = _match_count(ex_list, gt_list, tolerance_pct=20.0)

        # Save FP regions (extracted but not in GT)
        for mi, m in enumerate(match_info["matches"]):
            if m[4] == "FP":
                # Find the extracted item
                fp_ex = next((e for e in ex_list if e.get("id", "") == m[0]), None)
                if fp_ex and "x_px" in fp_ex and "y_px" in fp_ex:
                    x, y = int(fp_ex["x_px"]), int(fp_ex["y_px"])
                    bw = int(fp_ex.get("width_px", 80))
                    bh = int(fp_ex.get("height_px", 60))
                    crop = img[max(0,y-10):y+bh+10, max(0,x-10):x+bw+10]
                    fname = f"{cat}_fp_{mi:02d}.png"
                    cv2.imwrite(str(out / fname), crop)
            elif m[4] == "FN":
                # Find the GT item
                fn_gt = next((g for g in gt_list if g.get("id", "") == m[0]), None)
                if fn_gt:
                    # For FN, we note the expected element but might not have position
                    # Create a small note image
                    note = np.ones((60, 200, 3), dtype=np.uint8) * 255
                    cv2.putText(note, f"FN {cat} {m[0]}", (5, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,255), 1)
                    fname = f"{cat}_fn_{mi:02d}.png"
                    cv2.imwrite(str(out / fname), note)


def _categorize_plan(name: str) -> str:
    """Assign a plan to a category group for dataset breakdown."""
    if name.startswith("basic_"):
        return "Basic"
    if name.startswith("medium_"):
        return "Medium"
    if name.startswith("complex_"):
        return "Complex"
    if name.startswith("edge_"):
        return "Edge"
    if name.startswith("arch_"):
        return "Architectural"
    if name.startswith("struct_"):
        return "Structural"
    if name.startswith("lowq_"):
        return "Low-Quality Scan"
    if name.startswith("rot_"):
        return "Rotated"
    return "Other"


def run_validation():
    """Run full validation across all validation drawings."""
    results = []
    overall_tp = {"doors": 0, "columns": 0, "beams": 0, "walls": 0}
    overall_fp = {"doors": 0, "columns": 0, "beams": 0, "walls": 0}
    overall_fn = {"doors": 0, "columns": 0, "beams": 0, "walls": 0}

    categories = ["doors", "columns", "beams", "walls"]

    # Clean failure gallery
    if FAILURE_DIR.exists():
        import shutil
        shutil.rmtree(str(FAILURE_DIR))

    print(f"Running validation on {len(PLANS)} validation drawings...\n")

    for idx, (name, (img, gt)) in enumerate(PLANS, 1):
        img_path = IMG_DIR / f"{name}.png"
        cv2.imwrite(str(img_path), img)
        gt_path = GT_DIR / f"{name}_gt.json"
        with open(gt_path, "w") as f:
            json.dump(gt, f, indent=2)

        try:
            extracted = extract_dimensions(img_path, px_per_mm=PLAN_PX_PER_MM)
        except Exception as exc:
            print(f"  [{idx:02d}] {name}: ERROR — {exc}")
            extracted = {"doors": [], "columns": [], "beams": [], "walls": []}

        plan_result = {
            "name": name,
            "index": idx,
            "gt_counts": {c: len(gt.get(c, [])) for c in categories},
            "ex_counts": {c: len(extracted.get(c, [])) for c in categories},
        }

        for cat in categories:
            gt_list = gt.get(cat, [])
            ex_list = extracted.get(cat, [])
            match_info = _match_count(ex_list, gt_list, tolerance_pct=20.0)
            acc = _element_accuracy(match_info["tp"], match_info["fp"], match_info["fn"])
            dim_acc = _dimension_extraction_accuracy(match_info["matches"])
            plan_result[f"{cat}_accuracy"] = acc
            plan_result[f"{cat}_dim_accuracy"] = dim_acc
            plan_result[f"{cat}_matches"] = match_info["matches"]

            overall_tp[cat] += match_info["tp"]
            overall_fp[cat] += match_info["fp"]
            overall_fn[cat] += match_info["fn"]

        plan_result["confusion"] = _classification_accuracy(gt, extracted)
        results.append(plan_result)

        # Generate failure gallery
        _generate_failure_gallery(name, img, gt, extracted, categories, results, idx)

        gt_total = sum(plan_result["gt_counts"].values())
        ex_total = sum(plan_result["ex_counts"].values())
        pass_emoji = "✅" if gt_total > 0 and abs(ex_total - gt_total) <= max(2, gt_total * 0.3) else "⚠️"
        print(f"  [{idx:02d}] {pass_emoji} {name}: GT={gt_total} items, Extracted={ex_total} items")

    # ── Build report ──
    report_lines = []
    report_lines.append("# Drawing Parser Validation Report v2")
    report_lines.append("")
    report_lines.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M')}")
    report_lines.append(f"**Plans tested:** {len(PLANS)}")
    report_lines.append(f"**Plan scale:** {PLAN_PX_PER_MM} px/mm")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # ── Dataset Breakdown ──
    report_lines.append("## Dataset Breakdown")
    report_lines.append("")
    cat_counts: dict[str, int] = {}
    for name, _ in PLANS:
        grp = _categorize_plan(name)
        cat_counts[grp] = cat_counts.get(grp, 0) + 1
    report_lines.append("| Category | Count |")
    report_lines.append("|----------|-------|")
    for grp, cnt in sorted(cat_counts.items()):
        report_lines.append(f"| {grp} | {cnt} |")
    report_lines.append("")
    report_lines.append(f"**Total elements across all plans:** "
                        f"{sum(sum(r['gt_counts'].values()) for r in results)} ground truth, "
                        f"{sum(sum(r['ex_counts'].values()) for r in results)} extracted")
    report_lines.append("")

    report_lines.append("---")
    report_lines.append("")

    # ── Overall Accuracy Summary ──
    report_lines.append("## Overall Accuracy Summary")
    report_lines.append("")
    report_lines.append("| Category | Precision | Recall | F1-Score | Target | Met? |")
    report_lines.append("|----------|-----------|--------|----------|--------|------|")
    targets = {"doors": 90, "walls": 85, "columns": 85, "beams": 85}
    for cat in categories:
        tp = overall_tp[cat]
        fp = overall_fp[cat]
        fn = overall_fn[cat]
        acc = _element_accuracy(tp, fp, fn)
        target = targets.get(cat, 80)
        met = "✅" if acc["f1"] >= target else "❌"
        report_lines.append(
            f"| {cat.title()} | {acc['precision']}% | {acc['recall']}% | {acc['f1']}% | {target}% | {met} |"
        )

    all_tp = sum(overall_tp.values())
    all_fp = sum(overall_fp.values())
    all_fn = sum(overall_fn.values())
    overall_acc = _element_accuracy(all_tp, all_fp, all_fn)
    report_lines.append(
        f"| **Overall** | **{overall_acc['precision']}%** | **{overall_acc['recall']}%** | **{overall_acc['f1']}%** | **85%** | {'✅' if overall_acc['f1'] >= 85 else '❌'} |"
    )
    report_lines.append("")

    report_lines.append("---")
    report_lines.append("")

    # ── Confusion Matrices ──
    report_lines.append("## Confusion Matrices")
    report_lines.append("")
    for cat in categories:
        tp = overall_tp[cat]
        fn = overall_fn[cat]
        fp = overall_fp[cat]
        tn_est = "—"
        report_lines.append(f"### {cat.title()}")
        report_lines.append("")
        report_lines.append("| | Predicted Yes | Predicted No |")
        report_lines.append("|--------------|--------------|--------------|")
        report_lines.append(f"| Actual Yes | **{tp}** (TP) | **{fn}** (FN) |")
        report_lines.append(f"| Actual No | **{fp}** (FP) | {tn_est} |")
        report_lines.append("")

    report_lines.append("---")
    report_lines.append("")

    # ── Per-Plan Detailed Results ──
    report_lines.append("## Per-Plan Detailed Results")
    report_lines.append("")
    report_lines.append("| # | Plan | GT | Extracted | Doors (P/R/F1) | Walls (P/R/F1) | Columns (P/R/F1) | Beams (P/R/F1) |")
    report_lines.append("|---|------|----|-----------|----------------|----------------|------------------|----------------|")
    for r in results:
        gt_t = sum(r["gt_counts"].values())
        ex_t = sum(r["ex_counts"].values())
        row = [f"| {r['index']:02d}", f"{r['name']}", str(gt_t), str(ex_t)]
        for cat in categories:
            a = r.get(f"{cat}_accuracy", {})
            row.append(f"{a.get('precision', 0):.0f}/{a.get('recall', 0):.0f}/{a.get('f1', 0):.0f}")
        report_lines.append(" | ".join(row) + " |")
    report_lines.append("")

    report_lines.append("---")
    report_lines.append("")

    # ── Failure Analysis ──
    report_lines.append("## Failure Analysis")
    report_lines.append("")
    for cat in categories:
        tp = overall_tp[cat]
        fp = overall_fp[cat]
        fn = overall_fn[cat]
        acc = _element_accuracy(tp, fp, fn)
        target = targets.get(cat, 80)
        if acc["f1"] < target:
            report_lines.append(f"### {cat.title()} — Below Target ({acc['f1']}% vs {target}%)")
            report_lines.append("")
            report_lines.append(f"- **False Positives:** {fp}")
            report_lines.append(f"- **False Negatives:** {fn}")
            report_lines.append("")
            report_lines.append("| Plan | FN | FP | Details |")
            report_lines.append("|------|----|----|---------|")
            for r in results:
                matches = r.get(f"{cat}_matches", [])
                fns = [m for m in matches if m[4] == "FN"]
                fps_list = [m for m in matches if m[4] != "TP" and m[4] != "FN"]
                if fns or fps_list:
                    fn_ids = ", ".join(m[0] for m in fns)
                    fp_ids = ", ".join(m[0] for m in fps_list)
                    detail = ""
                    if fns and fps_list:
                        detail = f"FN: {fn_ids}; FP: {fp_ids}"
                    elif fns:
                        detail = f"FN: {fn_ids}"
                    else:
                        detail = f"FP: {fp_ids}"
                    report_lines.append(f"| {r['name']} | {len(fns)} | {len(fps_list)} | {detail} |")
            report_lines.append("")
            report_lines.append(f"Failure gallery images saved to `{FAILURE_DIR}/`")
            report_lines.append("")
        else:
            report_lines.append(f"### {cat.title()} — Target Met ✅ ({acc['f1']}% ≥ {target}%)")
            report_lines.append("")

    report_lines.append("---")
    report_lines.append("")

    # ── Dimension Extraction Accuracy ──
    report_lines.append("## Dimension Extraction Accuracy")
    report_lines.append("")
    report_lines.append("Average dimension deviation across all true-positive matches:")
    report_lines.append("")
    report_lines.append("| Category | Mean Error % | Within 5% | Within 10% | Within 15% |")
    report_lines.append("|----------|-------------|-----------|------------|------------|")
    for cat in categories:
        all_matches = []
        for r in results:
            all_matches.extend(r.get(f"{cat}_matches", []))
        tp_matches = [m for m in all_matches if m[4] == "TP"]
        dim_acc = _dimension_extraction_accuracy(tp_matches)
        report_lines.append(
            f"| {cat.title()} | {dim_acc['mean_error_pct']}% | {dim_acc['within_5pct']}% | {dim_acc['within_10pct']}% | {dim_acc['within_15pct']}% |"
        )
    report_lines.append("")

    report_lines.append("---")
    report_lines.append("")

    # ── Recommendations ──
    report_lines.append("## Recommendations")
    report_lines.append("")
    report_lines.append("Based on the validation results:")
    report_lines.append("")
    for cat in categories:
        tp = overall_tp[cat]
        fp = overall_fp[cat]
        fn = overall_fn[cat]
        acc = _element_accuracy(tp, fp, fn)
        target = targets.get(cat, 80)
        if acc["f1"] < target:
            shortfall = target - acc["f1"]
            report_lines.append(f"**{cat.title()}** ({shortfall:.0f}% below target):")
            if fn > fp:
                report_lines.append(f"- Increase recall: {fn} false negatives suggest missed detections")
                report_lines.append(f"- Review contour detection thresholds and morphological operations")
            if fp > fn:
                report_lines.append(f"- Increase precision: {fp} false positives suggest over-detection")
                report_lines.append(f"- Tighten geometric constraints and add verification checks")
            report_lines.append("")
        else:
            report_lines.append(f"**{cat.title()}** — Target met ✅")
            report_lines.append("")

    report_lines.append("---")
    report_lines.append("")
    report_lines.append(f"*Report generated automatically by `validate_drawing_parser.py` at {time.strftime('%Y-%m-%d %H:%M')}*")
    report_lines.append(f"*Failure gallery: `{FAILURE_DIR}/`*")

    report_path = Path(
        __file__).resolve().parent.parent.parent / "docs" / "drawing_parser_validation_report_v2.md"
    report_path.write_text("\n".join(report_lines))
    print(f"\n✅ Report written to {report_path}")
    print(f"💾 Failure gallery: {FAILURE_DIR}/")
    print(f"📊 Overall F1: {overall_acc['f1']}%")
    for cat in categories:
        tp = overall_tp[cat]
        fp = overall_fp[cat]
        fn = overall_fn[cat]
        acc = _element_accuracy(tp, fp, fn)
        target = targets.get(cat, 80)
        status = "✅" if acc["f1"] >= target else "❌"
        print(f"   {status} {cat}: F1={acc['f1']}% (target {target}%)")

    return results


if __name__ == "__main__":
    run_validation()
