"""Architectural plan parsing — Phase 3 stub with OCR-ready interface."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from schemas.plan import BeamSpec, ColumnSpec, DoorSpec, PlanSchema, RoomSpec

# Dimension patterns: 4500, 4.5m, 4500mm, 15'-0"
_DIM_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*m\b", re.I),
    re.compile(r"(\d+)\s*mm\b", re.I),
    re.compile(r"(\d{3,5})\b"),
]


def _parse_dimension_mm(text: str) -> Optional[float]:
    text = text.strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*m\b", text, re.I)
    if m:
        return float(m.group(1)) * 1000
    m = re.search(r"(\d+)\s*mm\b", text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"^(\d{3,5})$", text)
    if m:
        val = float(m.group(1))
        return val if val > 100 else val * 1000  # bare numbers assumed mm if small
    return None


def parse_plan_file(plan_path: Path) -> PlanSchema:
    """
    Parse an architectural plan (PDF or image).

    MVP: returns empty schema with a note. Full pdf2image + pytesseract pipeline
    is wired in Phase 3. We still accept the upload so the API contract is stable.
    """
    suffix = plan_path.suffix.lower()
    schema = PlanSchema()

    if suffix == ".pdf":
        # Phase 3: pdf2image.convert_from_path(plan_path, dpi=300)
        schema.raw_text_blocks.append(
            "[Plan PDF received — OCR dimension extraction available in Phase 3]"
        )
        return schema

    # Image plan — attempt basic OCR if pytesseract is installed
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(plan_path)
        text = pytesseract.image_to_string(img)
        schema.raw_text_blocks = [line.strip() for line in text.splitlines() if line.strip()]
        dims = [_parse_dimension_mm(t) for t in schema.raw_text_blocks]
        dims = [d for d in dims if d]
        if len(dims) >= 2:
            schema.rooms.append(RoomSpec(id="R1", width_mm=dims[0], depth_mm=dims[1]))
        if len(dims) >= 4:
            schema.doors.append(DoorSpec(id="D1", width_mm=dims[2], height_mm=dims[3]))
    except Exception:
        schema.raw_text_blocks.append(
            "[Plan image received — install pytesseract for OCR dimension extraction]"
        )

    return schema


def estimate_px_per_mm_from_plan(plan: PlanSchema, door_bbox_width_px: float) -> Optional[float]:
    """Calibrate photo scale using plan door width vs detected door width in pixels."""
    if not plan.doors or door_bbox_width_px <= 0:
        return None
    door_mm = plan.doors[0].width_mm
    return door_bbox_width_px / door_mm
