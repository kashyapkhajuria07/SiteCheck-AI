"""Inspection API routes."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config import OUTPUTS_DIR, UPLOADS_DIR
from models.yolo_detector import get_model_info
from schemas.inspection import (
    CoverageStats,
    CriticalFinding,
    HealthResponse,
    InspectResponse,
    InspectionSummary,
    RecommendationGroup,
    ResultsResponse,
    Ruleset,
    UnitSystem,
)
from services.pipeline import process_inspection
from services.session_store import get_session

router = APIRouter(prefix="/api", tags=["inspect"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    info = get_model_info()
    return HealthResponse(
        status="ok",
        model_loaded=info.loaded,
        detection_mode=info.mode.value,
        weights_path=info.weights_path,
        class_names=info.class_names,
    )


@router.post("/inspect", response_model=InspectResponse)
async def inspect_photos(
    photos: List[UploadFile] = File(..., description="Site photos (min 1)"),
    plan: Optional[UploadFile] = File(None),
    unit_system: str = Form("metric"),
    ruleset: str = Form("IS456"),
    project_name: str = Form("Untitled Project"),
    inspection_date: str = Form(""),
):
    if not photos:
        raise HTTPException(status_code=400, detail="At least one photo is required.")

    try:
        unit = UnitSystem(unit_system)
    except ValueError:
        unit = UnitSystem.METRIC

    try:
        rules = Ruleset(ruleset)
    except ValueError:
        rules = Ruleset.IS456

    batch_id = uuid.uuid4().hex[:8]
    upload_dir = UPLOADS_DIR / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    photo_paths: list[Path] = []
    for i, photo in enumerate(photos):
        suffix = Path(photo.filename or "photo.jpg").suffix or ".jpg"
        dest = upload_dir / f"photo_{i:02d}{suffix}"
        with dest.open("wb") as f:
            shutil.copyfileobj(photo.file, f)
        photo_paths.append(dest)

    plan_path: Path | None = None
    if plan and plan.filename:
        plan_suffix = Path(plan.filename).suffix or ".pdf"
        plan_path = upload_dir / f"plan{plan_suffix}"
        with plan_path.open("wb") as f:
            shutil.copyfileobj(plan.file, f)

    session = process_inspection(
        photo_paths=photo_paths,
        plan_path=plan_path,
        unit_system=unit,
        ruleset=rules,
        project_name=project_name,
        inspection_date=inspection_date,
    )

    return InspectResponse(
        session_id=session.session_id,
        status=session.status,
        preview_url=f"/api/results/{session.session_id}",
    )


@router.get("/results/{session_id}", response_model=ResultsResponse)
async def get_results(session_id: str):
    session = get_session(session_id, OUTPUTS_DIR)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    all_elements = []
    annotated_urls = []
    for photo in session.photos:
        all_elements.extend(photo.elements)
        annotated_urls.append(photo.annotated_image_url)

    pass_c = sum(1 for e in all_elements if e.status.value == "PASS")
    warn_c = sum(1 for e in all_elements if e.status.value == "WARNING")
    fail_c = sum(1 for e in all_elements if e.status.value == "FAIL")

    # ── Critical Findings ──
    critical_findings: list[CriticalFinding] = []
    for el in all_elements:
        if el.status.value == "FAIL":
            # Build engineer-friendly summary
            if el.deviation_pct is not None:
                summary = f"{el.label.title()} exceeds allowable tolerance by {el.deviation_pct:.0f}%"
            elif el.deviation is not None:
                summary = f"{el.label.title()} exceeds allowable tolerance ({el.deviation:.2f}{el.unit})"
            else:
                summary = f"{el.label.title()} does not meet compliance requirements"
            critical_findings.append(CriticalFinding(
                element_id=el.element_id,
                label=el.label,
                status=el.status,
                deviation=el.deviation,
                deviation_pct=el.deviation_pct,
                unit=el.unit,
                summary=summary,
                severity=el.severity,
                confidence_score=el.confidence_score,
            ))

    # ── Coverage Stats ──
    total_detected = len(all_elements)
    measured = [e for e in all_elements if e.status.value != "INCONCLUSIVE"]
    successfully_measured = len(measured)
    coverage_pct = round(successfully_measured / total_detected * 100, 1) if total_detected > 0 else 0.0
    avg_confidence = (
        round(sum(e.confidence_score for e in measured) / len(measured), 1)
        if measured else 0.0
    )
    coverage = CoverageStats(
        total_detected=total_detected,
        successfully_measured=successfully_measured,
        coverage_pct=coverage_pct,
        measurement_confidence_pct=avg_confidence,
    )

    # ── AI Inspection Summary ──
    summary_parts: list[str] = []
    if fail_c > 0:
        summary_parts.append(
            f"{fail_c} critical issue{'s' if fail_c != 1 else ''} "
            f"{'were' if fail_c != 1 else 'was'} detected."
        )
        # Find most severe
        worst = max(critical_findings, key=lambda c: c.deviation_pct or 0)
        summary_parts.append(
            f"The most severe issue is {worst.label.lower()} {worst.element_id}, "
            f"exceeding allowable tolerance by {worst.deviation_pct:.0f}%."
        )
    else:
        summary_parts.append("No critical issues were detected.")

    if warn_c > 0:
        warning_labels = sorted(set(
            e.label.title() for e in all_elements if e.status.value == "WARNING"
        ))
        summary_parts.append(
            f"{'Additional ' if fail_c > 0 else ''}"
            f"{warn_c} element{'s' if warn_c != 1 else ''} "
            f"{'require' if warn_c != 1 else 'requires'} attention: "
            f"{', '.join(warning_labels)}."
        )

    if pass_c > 0:
        summary_parts.append(
            f"{pass_c} element{'s' if pass_c != 1 else ''} within compliance limits."
        )

    # Quality warnings
    quality_warnings = set()
    for photo in session.photos:
        quality_warnings.update(photo.quality_flags)
    if quality_warnings:
        summary_parts.append(
            f"Note: Photo quality "
            f"{'concern' if len(quality_warnings) == 1 else 'concerns'} detected "
            f"({' '.join(quality_warnings)}). Measurements may be affected."
        )

    # Confidence note
    if avg_confidence < 70:
        summary_parts.append(
            f"Overall measurement confidence is {avg_confidence:.0f}%. "
            "Consider retaking photos under better conditions."
        )

    ai_summary = InspectionSummary(
        text=" ".join(summary_parts),
        critical_count=fail_c,
        warning_count=warn_c,
        pass_count=pass_c,
        most_severe_element=worst.element_id if fail_c > 0 else None,
        most_severe_deviation_pct=worst.deviation_pct if fail_c > 0 else None,
    )

    # ── Recommendation Groups ──
    imm_items: list[str] = []
    mon_items: list[str] = []
    acc_items: list[str] = []
    for el in all_elements:
        if el.status.value == "FAIL":
            imm_items.append(
                f"{el.label.title()} {el.element_id} exceeds tolerance"
                + (f" by {el.deviation_pct:.0f}%" if el.deviation_pct else "")
            )
        elif el.status.value == "WARNING":
            mon_items.append(
                f"{el.label.title()} {el.element_id} approaching warning threshold"
            )
        elif el.status.value == "PASS":
            acc_items.append(
                f"{el.label.title()} {el.element_id} within compliance limits"
            )

    recommendation_groups = []
    if imm_items:
        recommendation_groups.append(RecommendationGroup(level="immediate", items=imm_items))
    if mon_items:
        recommendation_groups.append(RecommendationGroup(level="monitor", items=mon_items))
    if acc_items:
        recommendation_groups.append(RecommendationGroup(level="acceptable", items=acc_items))

    info = get_model_info()
    return ResultsResponse(
        session_id=session.session_id,
        compliance_score=session.compliance_score,
        pass_count=pass_c,
        warning_count=warn_c,
        fail_count=fail_c,
        elements=all_elements,
        annotated_images=annotated_urls,
        report_url=f"/api/report/{session_id}",
        photos=session.photos,
        detection_mode=session.detection_mode or info.mode.value,
        detection_classes=info.class_names,
        critical_findings=critical_findings,
        coverage=coverage,
        ai_inspection_summary=ai_summary,
        recommendation_groups=recommendation_groups,
        validation_log=session.validation_log,
    )


@router.get("/report/{session_id}")
async def download_report(session_id: str):
    session = get_session(session_id, OUTPUTS_DIR)
    if not session or not session.report_path:
        raise HTTPException(status_code=404, detail="Report not found.")

    pdf_path = Path(session.report_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Report file missing.")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"inspection_report_{session_id}.pdf",
    )


@router.get("/files/{session_id}/{filename}")
async def get_annotated_file(session_id: str, filename: str):
    file_path = OUTPUTS_DIR / session_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path=file_path)
