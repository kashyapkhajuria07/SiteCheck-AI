"""Scale calibration to convert pixels into real-world units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import REFERENCE_DOOR_WIDTH_MM
from schemas.plan import PlanSchema
from schemas.inspection import Detection

@dataclass
class ScaleCalibration:
    px_per_mm: Optional[float]
    mode: str
    confidence: str  # "high", "medium", "low"
    estimated: bool
    evidence: list[str]


def _estimate_from_door_width(detections: list[Detection]) -> Optional[float]:
    for d in detections:
        if d.label == "door" and len(d.bbox) == 4:
            width_px = d.bbox[2] - d.bbox[0]
            if width_px > 20:
                return width_px / REFERENCE_DOOR_WIDTH_MM
    return None


def calibrate_scale(detections: list[Detection], plan: Optional[PlanSchema] = None) -> ScaleCalibration:
    """
    Mode A: Plan available. Use OCR dimensions.
    Mode B: No plan. Use standard assumptions (e.g. door width 900mm).
    """
    if plan:
        # Mode A: Plan available
        door_width_px = None
        for d in detections:
            if d.label == "door" and len(d.bbox) == 4:
                door_width_px = d.bbox[2] - d.bbox[0]
                break
        
        if door_width_px and door_width_px > 20 and plan.doors:
            plan_door_mm = plan.doors[0].width_mm
            px_per_mm = door_width_px / plan_door_mm
            return ScaleCalibration(
                px_per_mm=px_per_mm,
                mode="Mode A (Plan)",
                confidence="high",
                estimated=False,
                evidence=["Matched detected door with OCR plan dimension."]
            )
        
        # If plan is provided but we can't match features, fallback to low confidence
        return ScaleCalibration(
            px_per_mm=None,
            mode="Mode A (Plan)",
            confidence="low",
            estimated=True,
            evidence=["Plan provided but could not match physical features to OCR dimensions."]
        )

    # Mode B: No plan, heuristic
    fallback_px_per_mm = _estimate_from_door_width(detections)
    if fallback_px_per_mm:
        return ScaleCalibration(
            px_per_mm=fallback_px_per_mm,
            mode="Mode B (Heuristic)",
            confidence="medium",
            estimated=True,
            evidence=[f"Estimated using standard door width assumption ({REFERENCE_DOOR_WIDTH_MM}mm)"]
        )

    return ScaleCalibration(
        px_per_mm=None,
        mode="Mode B (None)",
        confidence="low",
        estimated=True,
        evidence=["No reliable reference objects found for scale calibration."]
    )
