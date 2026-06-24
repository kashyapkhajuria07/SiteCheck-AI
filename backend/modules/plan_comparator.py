"""Compare drawing-expected dimensions against site-measured dimensions.

Input:
  - Drawing JSON from drawing_parser
  - Site measurement JSON from inspection pipeline (ElementResult list)

Output:
  ComparisonResult with per-element deviations and summary statistics.
"""

from __future__ import annotations

from typing import Any, Optional

from schemas.inspection import ElementResult, ElementStatus

# Tolerance defaults (matching IS:456 style rules)
_TOLERANCE_PCT = 10.0  # % deviation before WARNING
_FAIL_PCT = 20.0       # % deviation before FAIL


def _status_from_deviation_pct(dev_pct: float) -> ElementStatus:
    if dev_pct > _FAIL_PCT:
        return ElementStatus.FAIL
    if dev_pct > _TOLERANCE_PCT:
        return ElementStatus.WARNING
    return ElementStatus.PASS


def compare_element(
    element_type: str,
    expected: float,
    actual: float,
    unit: str = "mm",
) -> dict[str, Any]:
    """Compare a single expected vs actual measurement.

    Returns:
    {
        "element": element_type,
        "expected": expected,
        "actual": actual,
        "deviation_mm": abs(expected - actual),
        "deviation_pct": abs(expected - actual) / expected * 100 if expected else 0,
        "status": "PASS" | "WARNING" | "FAIL"
    }
    """
    deviation_mm = abs(expected - actual)
    deviation_pct = (deviation_mm / expected * 100) if expected > 0 else 100.0
    status = _status_from_deviation_pct(deviation_pct)

    return {
        "element": element_type,
        "expected": expected,
        "actual": actual,
        "deviation_mm": round(deviation_mm, 1),
        "deviation_pct": round(deviation_pct, 1),
        "unit": unit,
        "status": status.value,
    }


def compare_drawing_to_site(
    drawing_json: dict[str, Any],
    site_elements: list[ElementResult],
    px_per_mm: Optional[float] = None,
) -> dict[str, Any]:
    """Compare all drawing-expected dimensions against site measurements.

    Args:
        drawing_json: Output from drawing_parser.extract_dimensions()
        site_elements: ElementResult list from inspection pipeline
        px_per_mm: Optional scale factor to convert site px values to mm

    Returns:
    {
        "comparisons": [ ... per-element comparison ... ],
        "summary": {
            "total": 0,
            "pass": 0,
            "warning": 0,
            "fail": 0,
            "compliance_pct": 0.0
        },
        "by_category": { ... group by element_type ... }
    }
    """
    comparisons: list[dict[str, Any]] = []
    by_category: dict[str, dict[str, int]] = {}

    # Extract site measurements grouped by label
    site_doors: list[ElementResult] = [e for e in site_elements if e.label.lower() == "door"]
    site_walls: list[ElementResult] = [e for e in site_elements if e.label.lower() in {"wall", "column"}]
    site_beams: list[ElementResult] = [e for e in site_elements if e.label.lower() == "beam"]

    # ── Doors ──
    drawing_doors = drawing_json.get("doors", [])
    for i, dd in enumerate(drawing_doors):
        expected_w = dd.get("width_mm", 900)
        # Find matching site door by index
        actual_w = None
        if i < len(site_doors):
            actual_w = site_doors[i].deviation if site_doors[i].deviation else None
        if actual_w is None and px_per_mm:
            # Fallback: compute from bbox width
            if i < len(site_doors) and len(site_doors[i].bbox) == 4:
                bbox = site_doors[i].bbox
                actual_w = (bbox[2] - bbox[0]) / px_per_mm
        if actual_w is not None:
            comp = compare_element("door", expected_w, actual_w, "mm")
            comparisons.append(comp)
            _add_to_category(by_category, "door", comp["status"])

    # ── Walls / Columns ──
    drawing_columns = drawing_json.get("columns", [])
    for i, dc in enumerate(drawing_columns):
        expected_w = dc.get("width_mm", 300)
        actual_w = None
        if i < len(site_walls) and len(site_walls[i].bbox) == 4 and px_per_mm:
            bbox = site_walls[i].bbox
            actual_w = (bbox[2] - bbox[0]) / px_per_mm
        if actual_w is not None:
            comp = compare_element("column", expected_w, actual_w, "mm")
            comparisons.append(comp)
            _add_to_category(by_category, "column", comp["status"])

    drawing_walls = drawing_json.get("walls", [])
    for i, dw in enumerate(drawing_walls):
        expected_t = dw.get("thickness_mm", 230)
        actual_t = None
        wall_idx = len(drawing_columns) + i
        if wall_idx < len(site_walls) and len(site_walls[wall_idx].bbox) == 4 and px_per_mm:
            bbox = site_walls[wall_idx].bbox
            actual_t = (bbox[2] - bbox[0]) / px_per_mm
        if actual_t is not None:
            comp = compare_element("wall", expected_t, actual_t, "mm")
            comparisons.append(comp)
            _add_to_category(by_category, "wall", comp["status"])

    # ── Beams ──
    drawing_beams = drawing_json.get("beams", [])
    for i, db in enumerate(drawing_beams):
        expected_d = db.get("depth_mm", 450)
        actual_d = None
        if i < len(site_beams) and len(site_beams[i].bbox) == 4 and px_per_mm:
            bbox = site_beams[i].bbox
            actual_d = (bbox[3] - bbox[1]) / px_per_mm
        if actual_d is not None:
            comp = compare_element("beam", expected_d, actual_d, "mm")
            comparisons.append(comp)
            _add_to_category(by_category, "beam", comp["status"])

    # ── Summary ──
    total = len(comparisons)
    pass_c = sum(1 for c in comparisons if c["status"] == "PASS")
    warn_c = sum(1 for c in comparisons if c["status"] == "WARNING")
    fail_c = sum(1 for c in comparisons if c["status"] == "FAIL")
    compliance_pct = (pass_c / total * 100) if total > 0 else 0.0

    return {
        "comparisons": comparisons,
        "summary": {
            "total": total,
            "pass": pass_c,
            "warning": warn_c,
            "fail": fail_c,
            "compliance_pct": round(compliance_pct, 1),
        },
        "by_category": by_category,
    }


def _add_to_category(by_category: dict, key: str, status: str):
    if key not in by_category:
        by_category[key] = {"total": 0, "pass": 0, "warning": 0, "fail": 0}
    by_category[key]["total"] += 1
    if status == "PASS":
        by_category[key]["pass"] += 1
    elif status == "WARNING":
        by_category[key]["warning"] += 1
    elif status == "FAIL":
        by_category[key]["fail"] += 1
