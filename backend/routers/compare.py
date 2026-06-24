"""Plan-assisted validation API — compare drawing specs against site measurements."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config import OUTPUTS_DIR, UPLOADS_DIR
from modules.drawing_parser import extract_dimensions, drawing_to_plan_schema
from modules.plan_comparator import compare_drawing_to_site
from modules.scale_calibrator import calibrate_scale
from models.yolo_detector import detect_elements
from modules.preprocessor import preprocess_image
from modules.geometric_analyser import analyse_element
from modules.compliance_engine import _load_rules, evaluate_element
from schemas.inspection import (
    ComparePlanResponse,
    ComparisonItem,
    ComparisonSummary,
    Ruleset,
)
from services.session_store import save_session

router = APIRouter(prefix="/api", tags=["compare"])


@router.post("/compare-plan", response_model=ComparePlanResponse)
async def compare_plan(
    drawing: UploadFile = File(..., description="Floor plan or structural drawing (PDF or image)"),
    site_image: UploadFile = File(..., description="Site photo for measurement extraction"),
    ruleset: str = Form("IS456"),
    px_per_mm: Optional[float] = Form(None, description="Optional manual scale factor (px/mm)"),
):
    """Compare expected drawing dimensions against site measurements.

    Workflow:
    1. Parse the drawing PDF/image to extract expected dimensions
    2. Run detection + geometric analysis on the site photo
    3. Compare expected vs actual values
    4. Return structured comparison results
    """
    batch_id = uuid.uuid4().hex[:8]
    work_dir = UPLOADS_DIR / batch_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # Save drawing
    drawing_suffix = Path(drawing.filename or "drawing.pdf").suffix or ".pdf"
    drawing_path = work_dir / f"drawing{drawing_suffix}"
    with drawing_path.open("wb") as f:
        shutil.copyfileobj(drawing.file, f)

    # Save site image
    img_suffix = Path(site_image.filename or "photo.jpg").suffix or ".jpg"
    img_path = work_dir / f"photo{img_suffix}"
    with img_path.open("wb") as f:
        shutil.copyfileobj(site_image.file, f)

    # 1. Parse drawing
    try:
        drawing_data = extract_dimensions(drawing_path, px_per_mm=px_per_mm)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse drawing: {exc}")

    # 2. Run detection + analysis on site image
    import cv2
    import numpy as np

    bgr = cv2.imread(str(img_path))
    if bgr is None:
        raise HTTPException(status_code=422, detail="Could not load site image")

    from modules.preprocessor import preprocess_image
    pre = preprocess_image(bgr)
    detections = detect_elements(pre.colour_bgr)

    try:
        rules = _load_rules(Ruleset(ruleset))
    except Exception:
        rules = _load_rules(Ruleset.IS456)

    site_elements = []
    for i, det in enumerate(detections):
        geo = analyse_element(pre.grayscale, det, px_per_mm=px_per_mm)
        el_result = evaluate_element(det, geo, rules, i + 1)
        site_elements.append(el_result)

    # 3. Compare drawing vs site
    comparison_result = compare_drawing_to_site(drawing_data, site_elements, px_per_mm=px_per_mm)
    comparisons_data = comparison_result.get("comparisons", [])
    summary_data = comparison_result.get("summary", {})
    by_cat = comparison_result.get("by_category", {})

    # Build response
    comparisons = [
        ComparisonItem(**c) for c in comparisons_data
    ]
    summary = ComparisonSummary(
        total=summary_data.get("total", 0),
        passed=summary_data.get("pass", 0),
        warning=summary_data.get("warning", 0),
        fail=summary_data.get("fail", 0),
        compliance_pct=summary_data.get("compliance_pct", 0.0),
    )

    return ComparePlanResponse(
        drawing=drawing_data,
        comparisons=comparisons,
        summary=summary,
        by_category=by_cat,
    )
