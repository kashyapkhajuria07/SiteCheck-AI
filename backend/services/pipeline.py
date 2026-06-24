"""End-to-end inspection pipeline orchestrating CV modules."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import DETECTION_MODE, OUTPUTS_DIR, REFERENCE_DOOR_WIDTH_MM, UPLOADS_DIR

if DETECTION_MODE == "yolo":
    from models.yolo_detector import detect_elements as _detect_elements, get_detection_mode as _get_detection_mode
elif DETECTION_MODE == "opencv":
    from modules.opencv_detector import detect_elements as _detect_elements, get_detection_mode as _get_detection_mode
else:  # hybrid — run both and merge
    from models.yolo_detector import detect_elements as _yolo_detect
    from models.yolo_detector import get_detection_mode as _yolo_get_mode
    from modules.opencv_detector import detect_elements as _cv_detect
    from modules.opencv_detector import get_detection_mode as _cv_get_mode

    def _detect_elements(bgr):
        yolo_dets = _yolo_detect(bgr)
        cv_dets = _cv_detect(bgr)
        seen_labels = {d.label for d in yolo_dets}
        for d in cv_dets:
            if d.label not in seen_labels:
                yolo_dets.append(d)
                seen_labels.add(d.label)
            elif d.confidence > max((x.confidence for x in yolo_dets if x.label == d.label), default=0):
                yolo_dets = [x for x in yolo_dets if x.label != d.label] + [d]
        return yolo_dets

    def _get_detection_mode():
        return f"hybrid({_yolo_get_mode()}+{_cv_get_mode()})"

detect_elements = _detect_elements
get_detection_mode = _get_detection_mode
from modules.compliance_engine import _load_rules, build_compliance_report, evaluate_element
from modules.geometric_analyser import analyse_element
from modules.overlay_renderer import render_overlay, save_overlay_image
from modules.plan_parser import parse_plan_file
from modules.scale_calibrator import calibrate_scale
from modules.preprocessor import preprocess_image
from modules.report_generator import generate_inspection_pdf
from modules.scene_classifier import SceneType, classify_scene, is_allowed_scene
from modules.roi_filter import filter_structural
from schemas.inspection import (
    ComplianceReport,
    InspectionSession,
    PhotoResult,
    Ruleset,
    UnitSystem,
    ValidationLog,
)
from services.session_store import save_session


_SCENE_SANITY_LIMIT = 50  # max detections before marking low confidence


def _count_by_label(elements) -> dict[str, int]:
    counts: dict[str, int] = {}
    for el in elements:
        label = el.label.lower()
        counts[label] = counts.get(label, 0) + 1
    return counts


def _build_unsupported_session(
    session_id: str,
    session_dir: Path,
    bgr: np.ndarray,
    scene_type: SceneType,
    scene_confidence: float,
    photo_paths: list[Path],
    unit_system: UnitSystem,
    ruleset: Ruleset,
    project_name: str,
    inspection_date: str,
) -> InspectionSession:
    """Build a session for an unsupported scene type (no detection run)."""
    photo_results: list[PhotoResult] = []
    val_photo_count = 0
    for idx, photo_path in enumerate(photo_paths):
        val_photo_count += 1
        annotated_name = f"annotated_{idx:02d}.png"
        annotated_path = session_dir / annotated_name
        pre = preprocess_image(bgr) if idx == 0 else None
        overlay_img = bgr.copy() if bgr is not None else np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.putText(overlay_img, "UNSUPPORTED SCENE", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.imwrite(str(annotated_path), overlay_img)

        photo_results.append(
            PhotoResult(
                photo_id=f"P{idx:03d}",
                file_name=photo_path.name,
                annotated_image_url=f"/api/files/{session_id}/{annotated_name}",
                elements=[],
                quality_flags=pre.quality_flags if pre else [],
            )
        )

    if not inspection_date:
        inspection_date = datetime.now().strftime("%Y-%m-%d")

    pdf_path = session_dir / f"inspection_report_{session_id}.pdf"
    generate_inspection_pdf(
        session_id=session_id,
        compliance=ComplianceReport(
            score=0.0, elements=[], sqi=0.0, confidence_score=0.0,
            critical_issues=["Scene type not suitable for structural analysis."],
            recommendations=["Upload a construction site or structural frame image."],
        ),
        photos=photo_results,
        ruleset=ruleset,
        unit_system=unit_system,
        output_path=pdf_path,
        project_name=project_name,
        inspection_date=inspection_date,
        photo_count=len(photo_paths),
        element_counts={},
        coverage_pct=0.0,
        measurement_confidence=0.0,
        low_confidence=False,
        scene_type=scene_type.value,
        scene_confidence=scene_confidence,
    )

    session = InspectionSession(
        session_id=session_id,
        status="unsupported_scene",
        unit_system=unit_system,
        ruleset=ruleset,
        compliance_score=0.0,
        photos=photo_results,
        report_path=str(pdf_path),
        plan_provided=False,
        detection_mode=get_detection_mode(),
        project_name=project_name,
        inspection_date=inspection_date,
        low_confidence=False,
        validation_log=ValidationLog(
            scene_type=scene_type.value,
            scene_confidence=round(scene_confidence, 2),
        ),
    )
    save_session(session, OUTPUTS_DIR)
    return session


def process_inspection(
    *,
    photo_paths: list[Path],
    plan_path: Path | None,
    unit_system: UnitSystem,
    ruleset: Ruleset,
    project_name: str = "Untitled Project",
    inspection_date: str = "",
) -> InspectionSession:
    session_id = uuid.uuid4().hex[:12]
    session_dir = OUTPUTS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    plan_schema = parse_plan_file(plan_path) if plan_path else None
    plan_px_per_mm: float | None = None

    # ── Phase 1 & 2: Scene classification + eligibility gate ──
    bgr = None
    for p in photo_paths:
        bgr = cv2.imread(str(p))
        if bgr is not None:
            break

    if bgr is None:
        raise RuntimeError("No readable photos found.")

    scene_type, scene_confidence = classify_scene(bgr)

    if not is_allowed_scene(scene_type):
        return _build_unsupported_session(
            session_id, session_dir, bgr, scene_type, scene_confidence,
            photo_paths, unit_system, ruleset, project_name, inspection_date,
        )

    # ── Allowed scene: run detection pipeline ──
    all_elements = []
    photo_results: list[PhotoResult] = []
    total_raw = 0
    total_roi_removed = 0
    total_low_trust = 0
    scene_overloaded = False
    val_log_dict: dict = {
        "scene_type": scene_type.value,
        "scene_confidence": round(scene_confidence, 2),
        "raw_detection_count": 0,
        "filtered_detection_count": 0,
        "ignored_low_trust_count": 0,
        "ignored_non_structural_count": 0,
        "final_detection_count": 0,
    }

    for idx, photo_path in enumerate(photo_paths):
        bgr = cv2.imread(str(photo_path))
        if bgr is None:
            continue

        pre = preprocess_image(bgr)

        # Capture raw unfiltered detections for validation logging
        if DETECTION_MODE == "opencv":
            from modules.opencv_detector import _detect_all_raw, compute_validation_log
            raw_detections = _detect_all_raw(pre.colour_bgr)
            detections = detect_elements(pre.colour_bgr)
            total_raw += sum(1 for d in raw_detections)

            # Phase 3: ROI filtering (remove non-structural detections)
            roi_filtered = filter_structural(pre.colour_bgr, detections, scene_type=scene_type.value)
            roi_removed = len(detections) - len(roi_filtered)
            total_roi_removed += roi_removed

            # Phase 4: Trust score filtering
            from modules.opencv_detector import _compute_trust_scores, _MIN_TRUST_SCORE
            _compute_trust_scores(roi_filtered, pre.colour_bgr)
            trusted = [d for d in roi_filtered if d.trust_score >= _MIN_TRUST_SCORE]
            low_trust_count = len(roi_filtered) - len(trusted)
            total_low_trust += low_trust_count

            detections = trusted

            val_log = compute_validation_log(pre.colour_bgr, raw_detections, detections,
                                             roi_filtered=roi_filtered)
        else:
            detections = detect_elements(pre.colour_bgr)
            val_log = {}
            total_raw += len(detections)

        scene_overloaded = total_raw > _SCENE_SANITY_LIMIT

        calibration = calibrate_scale(detections, plan_schema)

        rules = _load_rules(ruleset)
        photo_elements = []
        for i, det in enumerate(detections):
            geo = analyse_element(pre.grayscale, det, px_per_mm=calibration.px_per_mm)
            el_result = evaluate_element(det, geo, rules, len(all_elements) + i + 1)
            photo_elements.append(el_result)
            all_elements.append(el_result)

        overlay = render_overlay(pre.colour_bgr, photo_elements)
        annotated_name = f"annotated_{idx:02d}.png"
        annotated_path = session_dir / annotated_name
        save_overlay_image(overlay, annotated_path)

        photo_results.append(
            PhotoResult(
                photo_id=f"P{idx:03d}",
                file_name=photo_path.name,
                annotated_image_url=f"/api/files/{session_id}/{annotated_name}",
                elements=photo_elements,
                quality_flags=pre.quality_flags,
            )
        )

    low_confidence = scene_overloaded or len(all_elements) > _SCENE_SANITY_LIMIT

    if low_confidence:
        compliance = ComplianceReport(
            score=0.0,
            elements=all_elements,
            critical_issues=["Excessive detections — inspection quality compromised. Re-capture with better framing."],
            recommendations=["Retake photos ensuring structural elements fill the frame.", "Reduce scene complexity and re-inspect."],
            sqi=0.0,
            confidence_score=0.0,
        )
    else:
        compliance: ComplianceReport = build_compliance_report(all_elements, ruleset)

    if not inspection_date:
        inspection_date = datetime.now().strftime("%Y-%m-%d")

    pdf_path = session_dir / f"inspection_report_{session_id}.pdf"
    total_el = len(all_elements)
    measured_el = sum(1 for e in all_elements if e.status.value != "INCONCLUSIVE")
    cov_pct = round(measured_el / total_el * 100, 1) if total_el > 0 else 0.0
    avg_conf = round(
        sum(e.confidence_score for e in all_elements if e.status.value != "INCONCLUSIVE") / measured_el, 1
    ) if measured_el > 0 else 0.0

    # Merge validation log
    val_log_dict.update(val_log)
    val_log_dict["scene_overloaded"] = scene_overloaded

    generate_inspection_pdf(
        session_id=session_id,
        compliance=compliance,
        photos=photo_results,
        ruleset=ruleset,
        unit_system=unit_system,
        output_path=pdf_path,
        project_name=project_name,
        inspection_date=inspection_date,
        photo_count=len(photo_paths),
        element_counts=_count_by_label(all_elements),
        coverage_pct=cov_pct,
        measurement_confidence=avg_conf,
        low_confidence=low_confidence,
        scene_type=scene_type.value,
        scene_confidence=scene_confidence,
    )

    session = InspectionSession(
        session_id=session_id,
        status="low_confidence" if low_confidence else "completed",
        unit_system=unit_system,
        ruleset=ruleset,
        compliance_score=0.0 if low_confidence else compliance.score,
        photos=photo_results,
        report_path=str(pdf_path),
        plan_provided=plan_path is not None,
        detection_mode=get_detection_mode(),
        project_name=project_name,
        inspection_date=inspection_date,
        low_confidence=low_confidence,
        validation_log=ValidationLog(**val_log_dict) if val_log_dict else None,
    )
    save_session(session, OUTPUTS_DIR)
    return session
