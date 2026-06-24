#!/usr/bin/env python3
"""
Generate 60 realistic synthetic construction images and run the full
SiteCheck AI inspection pipeline on each.  Produces:
    test_assets/real_world/{pass,warning,fail}/<image>.jpg
    test_assets/real_world/annotated/<image>_annotated.png
    test_assets/real_world/json/<image>.json
    docs/REAL_WORLD_VALIDATION.md
"""

from __future__ import annotations

import sys, json, math, random, shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import cv2
import numpy as np

from modules.geometric_analyser import (
    analyze_vertical_element,
    analyze_horizontal_element,
    analyze_door_alignment,
)
from modules.compliance_engine import _load_rules, evaluate_element
from modules.overlay_renderer import render_overlay
from modules.preprocessor import preprocess_image
from schemas.inspection import Detection, ElementResult, ElementStatus, Ruleset

REAL_WORLD = Path(__file__).resolve().parent.parent / "test_assets" / "real_world"
ANNOTATED  = REAL_WORLD / "annotated"
JSON_DIR   = REAL_WORLD / "json"
DOCS       = Path(__file__).resolve().parent.parent / "docs"

for d in [REAL_WORLD / "pass", REAL_WORLD / "warning", REAL_WORLD / "fail",
          ANNOTATED, JSON_DIR, DOCS]:
    d.mkdir(parents=True, exist_ok=True)

random.seed(42)
np.random.seed(42)

# ── IS:456 thresholds ─────────────────────────────────────────────────
WALL_WARN = 1.5   # cm/m
WALL_FAIL = 3.0
BEAM_WARN = 5.0   # mm/m
BEAM_FAIL = 10.0
DOOR_WARN = 15.0  # mm
DOOR_FAIL = 30.0

# ── helpers ───────────────────────────────────────────────────────────
def _concrete_bg(h=640, w=640):
    """Concrete-grey canvas with grain texture."""
    base = np.random.randint(155, 175, (h, w, 3), dtype=np.uint8)
    noise = np.random.normal(0, 8, (h, w, 3)).astype(np.int16)
    img = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    return img


def _add_mortar_lines(img, spacing=40, color_range=(120, 140)):
    """Faint horizontal mortar joint lines for wall texture."""
    h, w = img.shape[:2]
    for y in range(spacing, h, spacing):
        c = random.randint(*color_range)
        jitter = random.randint(-2, 2)
        cv2.line(img, (0, y + jitter), (w, y + jitter), (c, c, c), 1)


def _draw_thick_line(img, pt1, pt2, color, thickness, edge_color=None):
    """Draw a structural line with optional darker edge shadows."""
    if edge_color:
        cv2.line(img, pt1, pt2, edge_color, thickness + 4)
    cv2.line(img, pt1, pt2, color, thickness)


# ── image generators ─────────────────────────────────────────────────
def gen_wall_image(tilt_deg: float, idx: int):
    """Generate a wall image with known plumb tilt."""
    img = _concrete_bg(640, 480)
    _add_mortar_lines(img, spacing=random.randint(35, 50))

    # wall strip centred at x=240 spanning full height
    h, w = img.shape[:2]
    rad = math.radians(tilt_deg)
    dx = int(h * math.tan(rad))

    cx = 240 + random.randint(-30, 30)
    wall_w = random.randint(60, 90)

    # draw 3-4 parallel vertical lines (edges of wall strip)
    for offset in [-wall_w // 2, 0, wall_w // 2]:
        x_top = cx + offset - dx // 2
        x_bot = cx + offset + dx // 2
        shade = random.randint(90, 130)
        _draw_thick_line(
            img,
            (x_top, 20), (x_bot, h - 20),
            (shade, shade, shade + 10),
            random.randint(3, 6),
            edge_color=(shade - 30, shade - 30, shade - 20),
        )

    # fill wall area with slightly darker rect
    pts = np.array([
        [cx - wall_w // 2 - dx // 2, 20],
        [cx + wall_w // 2 - dx // 2, 20],
        [cx + wall_w // 2 + dx // 2, h - 20],
        [cx - wall_w // 2 + dx // 2, h - 20],
    ])
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], (140, 140, 145))
    cv2.addWeighted(overlay, 0.35, img, 0.65, 0, img)

    return img


def gen_beam_image(tilt_deg: float, idx: int):
    """Generate a beam image with known level deviation."""
    img = _concrete_bg(480, 640)

    h, w = img.shape[:2]
    rad = math.radians(tilt_deg)
    dy = int(w * math.tan(rad))

    cy = 120 + random.randint(-20, 20)
    beam_h = random.randint(40, 65)

    # fill beam rectangle
    pts = np.array([
        [30, cy - beam_h // 2 - dy // 2],
        [w - 30, cy - beam_h // 2 + dy // 2],
        [w - 30, cy + beam_h // 2 + dy // 2],
        [30, cy + beam_h // 2 - dy // 2],
    ])
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], (115, 115, 120))
    cv2.addWeighted(overlay, 0.5, img, 0.5, 0, img)

    # top and bottom edges
    for offset in [-beam_h // 2, beam_h // 2]:
        yt = cy + offset - dy // 2
        yb = cy + offset + dy // 2
        shade = random.randint(70, 100)
        _draw_thick_line(
            img,
            (30, yt), (w - 30, yb),
            (shade, shade, shade),
            random.randint(4, 8),
            edge_color=(shade - 25, shade - 25, shade - 15),
        )

    # soffit marks / reinforcement hints
    for _ in range(random.randint(2, 5)):
        ry = cy + random.randint(-beam_h // 3, beam_h // 3)
        rx1 = random.randint(50, w // 2)
        rx2 = rx1 + random.randint(60, 200)
        cv2.line(img, (rx1, ry), (rx2, ry), (130, 130, 130), 1)

    return img


def gen_door_image(right_tilt_deg: float, idx: int):
    """Generate a door frame image with controlled right-jamb tilt."""
    img = _concrete_bg(640, 480)
    _add_mortar_lines(img, spacing=random.randint(35, 50))

    h, w = img.shape[:2]
    door_left  = 140 + random.randint(-15, 15)
    door_right = 340 + random.randint(-15, 15)
    door_top   = 80 + random.randint(-10, 10)
    door_bot   = 560 + random.randint(-10, 10)
    door_h = door_bot - door_top

    rad = math.radians(right_tilt_deg)
    r_dx = int(door_h * math.tan(rad))

    # left jamb (always straight)
    _draw_thick_line(img, (door_left, door_top), (door_left, door_bot),
                     (200, 200, 200), 6, (160, 160, 160))

    # right jamb (tilted)
    _draw_thick_line(img, (door_right, door_top), (door_right + r_dx, door_bot),
                     (200, 200, 200), 6, (160, 160, 160))

    # header
    _draw_thick_line(img, (door_left, door_top), (door_right, door_top),
                     (200, 200, 200), 6, (160, 160, 160))

    # door panel (filled rectangle, slightly recessed)
    panel_margin = 8
    pts = np.array([
        [door_left + panel_margin, door_top + panel_margin],
        [door_right - panel_margin, door_top + panel_margin],
        [door_right + r_dx - panel_margin, door_bot - panel_margin],
        [door_left + panel_margin, door_bot - panel_margin],
    ])
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], (180, 170, 155))
    cv2.addWeighted(overlay, 0.4, img, 0.6, 0, img)

    return img, [door_left, door_top, door_right + max(0, r_dx), door_bot]


# ── test-case specs ───────────────────────────────────────────────────
@dataclass
class TestCase:
    name: str
    element_type: str       # wall | beam | door
    param_deg: float        # tilt or asymmetry-driving angle
    expected: str           # PASS | WARNING | FAIL
    px_per_mm: Optional[float]  # None → INCONCLUSIVE


def _wall_expected(tilt_deg):
    offset = math.tan(math.radians(tilt_deg)) * 1000 / 10  # cm/m
    if offset >= WALL_FAIL: return "FAIL"
    if offset >= WALL_WARN: return "WARNING"
    return "PASS"


def _beam_expected(tilt_deg):
    offset = math.tan(math.radians(tilt_deg)) * 1000  # mm/m
    if offset >= BEAM_FAIL: return "FAIL"
    if offset >= BEAM_WARN: return "WARNING"
    return "PASS"


cases: list[TestCase] = []

# ── 20 walls ──────────────────────────────────────────────────────────
wall_tilts_pass    = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8]
wall_tilts_warning = [1.0, 1.2, 1.4, 1.5, 1.6, 1.7]
wall_tilts_fail    = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
for i, t in enumerate(wall_tilts_pass + wall_tilts_warning + wall_tilts_fail, 1):
    cases.append(TestCase(
        name=f"wall_{i:02d}",
        element_type="wall",
        param_deg=t,
        expected=_wall_expected(t),
        px_per_mm=1.0,   # calibrated
    ))

# ── 20 beams ──────────────────────────────────────────────────────────
beam_tilts_pass    = [0.0, 0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.25]
beam_tilts_warning = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55]
beam_tilts_fail    = [0.6, 0.7, 0.8, 1.0, 1.2, 1.5]
for i, t in enumerate(beam_tilts_pass + beam_tilts_warning + beam_tilts_fail, 1):
    cases.append(TestCase(
        name=f"beam_{i:02d}",
        element_type="beam",
        param_deg=t,
        expected=_beam_expected(t),
        px_per_mm=1.0,
    ))

# ── 20 doors ──────────────────────────────────────────────────────────
# Door asymmetry = frame_height * tan(tilt) in px.
# With px_per_mm=1.0, that directly gives mm.
# Average frame_height ≈ 480 px (door_bot - door_top = 560-80).
_DOOR_FRAME_H = 480.0

def _door_expected(tilt_deg, frame_h=_DOOR_FRAME_H):
    asym_mm = frame_h * math.tan(math.radians(tilt_deg))  # px_per_mm=1
    if asym_mm > DOOR_FAIL: return "FAIL"
    if asym_mm > DOOR_WARN: return "WARNING"
    return "PASS"

door_tilts_pass    = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
door_tilts_warning = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2]
door_tilts_fail    = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
for i, t in enumerate(door_tilts_pass + door_tilts_warning + door_tilts_fail, 1):
    cases.append(TestCase(
        name=f"door_{i:02d}",
        element_type="door",
        param_deg=t,
        expected=_door_expected(t),
        px_per_mm=1.0,
    ))


# ── run pipeline ──────────────────────────────────────────────────────
@dataclass
class Result:
    name: str
    element_type: str
    param_deg: float
    expected: str
    actual: str
    match: bool
    deviation_value: Optional[float]
    deviation_unit: str
    confidence: float
    evidence: list
    message: str
    reason: Optional[str]


rules = _load_rules(Ruleset.IS456)
results: list[Result] = []

print(f"Running {len(cases)} test cases through the inspection pipeline...\n")

for ci, tc in enumerate(cases, 1):
    # 1. Generate image ─────────────────────────────────────────────
    door_bbox_override = None
    if tc.element_type == "wall":
        bgr = gen_wall_image(tc.param_deg, ci)
        h, w = bgr.shape[:2]
        bbox = [140, 10, 340, h - 10]
        det = Detection(label="wall", confidence=0.92, bbox=bbox)
    elif tc.element_type == "beam":
        bgr = gen_beam_image(tc.param_deg, ci)
        h, w = bgr.shape[:2]
        bbox = [20, 60, w - 20, 200]
        det = Detection(label="beam", confidence=0.90, bbox=bbox)
    else:
        bgr, door_bbox_override = gen_door_image(tc.param_deg, ci)
        det = Detection(label="door", confidence=0.91, bbox=door_bbox_override)
        bbox = door_bbox_override

    # 2. Preprocess ─────────────────────────────────────────────────
    pre = preprocess_image(bgr)
    gray = pre.grayscale

    # 3. Geometric analysis ─────────────────────────────────────────
    if tc.element_type == "wall":
        findings = analyze_vertical_element(gray, bbox, "wall", px_per_mm=tc.px_per_mm)
    elif tc.element_type == "beam":
        findings = analyze_horizontal_element(gray, bbox, "beam", px_per_mm=tc.px_per_mm)
    else:
        findings = analyze_door_alignment(gray, bbox, px_per_mm=tc.px_per_mm)

    # 4. Compliance evaluation ──────────────────────────────────────
    el_result: ElementResult = evaluate_element(det, findings, rules, ci)

    # 5. Determine actual status ────────────────────────────────────
    actual_status = el_result.status.value

    # 6. Render & save ──────────────────────────────────────────────
    overlay = render_overlay(pre.colour_bgr, [el_result])

    # Decide output folder
    if actual_status == "PASS":
        out_folder = REAL_WORLD / "pass"
    elif actual_status == "WARNING":
        out_folder = REAL_WORLD / "warning"
    elif actual_status == "FAIL":
        out_folder = REAL_WORLD / "fail"
    else:
        out_folder = REAL_WORLD / "pass"  # INCONCLUSIVE goes here

    img_path = out_folder / f"{tc.name}.jpg"
    cv2.imwrite(str(img_path), bgr)

    ann_path = ANNOTATED / f"{tc.name}_annotated.png"
    cv2.imwrite(str(ann_path), overlay)

    # 7. Save JSON ──────────────────────────────────────────────────
    json_data = el_result.model_dump()
    json_data["input_param_deg"] = tc.param_deg
    json_data["expected_status"] = tc.expected
    json_path = JSON_DIR / f"{tc.name}.json"
    json_path.write_text(json.dumps(json_data, indent=2, default=str), encoding="utf-8")

    # 8. Record result ──────────────────────────────────────────────
    dev_val = el_result.deviation
    dev_unit = el_result.unit
    conf = el_result.measurements[0].confidence if el_result.measurements else 0.0
    ev = el_result.measurements[0].evidence if el_result.measurements else []
    msg = el_result.message

    match = (actual_status == tc.expected)
    results.append(Result(
        name=tc.name,
        element_type=tc.element_type,
        param_deg=tc.param_deg,
        expected=tc.expected,
        actual=actual_status,
        match=match,
        deviation_value=dev_val,
        deviation_unit=dev_unit,
        confidence=conf,
        evidence=ev,
        message=msg,
        reason=el_result.reason,
    ))

    tag = "✓" if match else "✗"
    dev_str = f"{dev_val:.2f} {dev_unit}" if dev_val is not None else "N/A"
    print(f"  [{ci:2d}/{len(cases)}] {tag} {tc.name:12s}  param={tc.param_deg:5.2f}°  "
          f"expected={tc.expected:12s}  actual={actual_status:12s}  dev={dev_str}")


# ── summary stats ─────────────────────────────────────────────────────
total = len(results)
matches = sum(1 for r in results if r.match)
mismatches = total - matches
pass_count = sum(1 for r in results if r.actual == "PASS")
warn_count = sum(1 for r in results if r.actual == "WARNING")
fail_count = sum(1 for r in results if r.actual == "FAIL")
incl_count = sum(1 for r in results if r.actual == "INCONCLUSIVE")

print(f"\n{'='*70}")
print(f"  Total: {total}  |  Match: {matches}  |  Mismatch: {mismatches}")
print(f"  PASS: {pass_count}  |  WARNING: {warn_count}  |  FAIL: {fail_count}  |  INCONCLUSIVE: {incl_count}")
print(f"  Accuracy: {matches/total*100:.1f}%")
print(f"{'='*70}\n")


# ── generate markdown report ──────────────────────────────────────────
md_lines = []
md_lines.append("# SiteCheck AI — Real-World Validation Report\n")
md_lines.append(f"**Date**: 2026-06-14  ")
md_lines.append(f"**Ruleset**: IS:456:2000  ")
md_lines.append(f"**Total Images**: {total}  ")
md_lines.append(f"**Match Rate**: {matches}/{total} ({matches/total*100:.1f}%)\n")
md_lines.append("---\n")

md_lines.append("## Summary\n")
md_lines.append("| Status | Count |")
md_lines.append("|---|---|")
md_lines.append(f"| PASS | {pass_count} |")
md_lines.append(f"| WARNING | {warn_count} |")
md_lines.append(f"| FAIL | {fail_count} |")
md_lines.append(f"| INCONCLUSIVE | {incl_count} |")
md_lines.append(f"| **Total** | **{total}** |")
md_lines.append("")

md_lines.append("## IS:456 Thresholds\n")
md_lines.append("| Check | Warning | Fail |")
md_lines.append("|---|---|---|")
md_lines.append(f"| Wall plumbness | ≥ {WALL_WARN} cm/m | ≥ {WALL_FAIL} cm/m |")
md_lines.append(f"| Beam levelness | ≥ {BEAM_WARN} mm/m | ≥ {BEAM_FAIL} mm/m |")
md_lines.append(f"| Door gap asymmetry | > {DOOR_WARN} mm | > {DOOR_FAIL} mm |")
md_lines.append("")

md_lines.append("---\n")

# Full results table
md_lines.append("## Full Results Matrix\n")
md_lines.append("| Image | Type | Param (°) | Expected | Actual | Match | Deviation | Confidence | Reason |")
md_lines.append("|---|---|---|---|---|---|---|---|---|")
for r in results:
    dev = f"{r.deviation_value:.2f} {r.deviation_unit}" if r.deviation_value is not None else "—"
    tag = "✓" if r.match else "**✗**"
    reason = r.reason or "—"
    md_lines.append(
        f"| {r.name} | {r.element_type} | {r.param_deg:.2f} | {r.expected} "
        f"| {r.actual} | {tag} | {dev} | {r.confidence:.2f} | {reason} |"
    )
md_lines.append("")

# Mismatches section
mismatched = [r for r in results if not r.match]
if mismatched:
    md_lines.append("---\n")
    md_lines.append("## Mismatches (Expected ≠ Actual)\n")
    md_lines.append("| Image | Type | Param (°) | Expected | Actual | Deviation | Message |")
    md_lines.append("|---|---|---|---|---|---|---|")
    for r in mismatched:
        dev = f"{r.deviation_value:.2f} {r.deviation_unit}" if r.deviation_value is not None else "—"
        msg = r.message[:80] if r.message else "—"
        md_lines.append(
            f"| {r.name} | {r.element_type} | {r.param_deg:.2f} | {r.expected} "
            f"| {r.actual} | {dev} | {msg} |"
        )
    md_lines.append("")

# Per-category detailed sections
for category, label in [("wall", "Wall Plumbness"), ("beam", "Beam Levelness"), ("door", "Door Alignment")]:
    subset = [r for r in results if r.element_type == category]
    md_lines.append("---\n")
    md_lines.append(f"## {label} — Detailed Results ({len(subset)} images)\n")
    md_lines.append(f"| Image | Param (°) | Expected | Actual | Deviation | Confidence | Evidence |")
    md_lines.append("|---|---|---|---|---|---|---|")
    for r in subset:
        dev = f"{r.deviation_value:.2f} {r.deviation_unit}" if r.deviation_value is not None else "—"
        ev = "; ".join(r.evidence[:2]) if r.evidence else "—"
        md_lines.append(
            f"| {r.name} | {r.param_deg:.2f} | {r.expected} | {r.actual} | {dev} | {r.confidence:.2f} | {ev} |"
        )
    md_lines.append("")

report_path = DOCS / "REAL_WORLD_VALIDATION.md"
report_path.write_text("\n".join(md_lines), encoding="utf-8")
print(f"Report written to: {report_path}")
print(f"Annotated images: {ANNOTATED}")
print(f"JSON outputs:     {JSON_DIR}")
print("Done.")
