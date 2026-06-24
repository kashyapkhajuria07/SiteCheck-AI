"""Rule-based compliance scoring using JSON rulesets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import RULES_DIR
from modules.geometric_analyser import GeometryFinding
from schemas.inspection import (
    ComplianceReport,
    Detection,
    ElementResult,
    ElementStatus,
    Ruleset,
)

_SEVERITY_MAP = {
    ElementStatus.PASS: "NONE",
    ElementStatus.WARNING: "MODERATE",
    ElementStatus.FAIL: "HIGH",
    ElementStatus.INCONCLUSIVE: "INDETERMINATE",
}


def _load_rules(ruleset: Ruleset) -> dict[str, Any]:
    filename = f"{ruleset.value}.json"
    path = RULES_DIR / filename
    if not path.exists():
        path = RULES_DIR / "IS456.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _severity(status: ElementStatus) -> str:
    return _SEVERITY_MAP.get(status, "NONE")


def _deviation_pct(dev: float, warn: float, fail: float) -> float:
    if dev >= fail:
        return round((dev - fail) / fail * 100, 1)
    if dev >= warn:
        return round((dev - warn) / warn * 100, 1)
    return 0.0


def _allowed_value_str(warn: float, fail: float, unit: str) -> str:
    return f"{warn} {unit} (warn) / {fail} {unit} (fail)"


def _interpretation_wall_plumb(dev: float, warn: float, fail: float) -> str:
    if dev >= fail:
        return (
            f"The wall plumbness deviation of {dev:.2f} cm/m exceeds the "
            f"IS:456 fail threshold of {fail} cm/m. This indicates significant "
            f"out-of-plumb that requires structural review and corrective action."
        )
    if dev >= warn:
        return (
            f"The wall plumbness deviation of {dev:.2f} cm/m exceeds the "
            f"IS:456 warning threshold of {warn} cm/m but remains within the "
            f"fail limit of {fail} cm/m. Corrective measures recommended "
            f"during finishing stages."
        )
    return (
        f"The wall plumbness deviation of {dev:.2f} cm/m is within the "
        f"IS:456 allowable tolerance of {warn} cm/m. No structural concern."
    )


def _interpretation_beam_level(dev: float, warn: float, fail: float) -> str:
    if dev >= fail:
        return (
            f"The beam levelness deviation of {dev:.2f} mm/m exceeds the "
            f"IS:456 fail threshold of {fail} mm/m. This indicates a "
            f"structural-level concern requiring immediate engineering review."
        )
    if dev >= warn:
        return (
            f"The beam levelness deviation of {dev:.2f} mm/m exceeds the "
            f"IS:456 warning threshold of {warn} mm/m but remains within the "
            f"fail limit of {fail} mm/m. Monitor during remaining construction."
        )
    return (
        f"The beam levelness deviation of {dev:.2f} mm/m is within the "
        f"IS:456 allowable tolerance of {warn} mm/m. Acceptable."
    )


def _interpretation_door(asym: float, max_asym: float) -> str:
    if asym > max_asym * 2:
        return (
            f"The door frame gap asymmetry of {asym:.1f} mm significantly exceeds "
            f"the maximum allowable asymmetry of {max_asym} mm. Frame requires "
            f"realignment; check hinge seating and frame plumb."
        )
    if asym > max_asym:
        return (
            f"The door frame gap asymmetry of {asym:.1f} mm exceeds the "
            f"allowable limit of {max_asym} mm. Minor frame adjustment recommended."
        )
    return (
        f"The door frame gap asymmetry of {asym:.1f} mm is within the "
        f"allowable limit of {max_asym} mm. No action required."
    )


def _interpretation_rebar(measurement_val: float, default_mm: float, tol_pct: float) -> str:
    pct_diff = abs(measurement_val - default_mm) / default_mm * 100
    if pct_diff > tol_pct * 2:
        return (
            f"Rebar spacing of {measurement_val:.1f} mm deviates significantly "
            f"from the specified {default_mm} mm (±{tol_pct}% tolerance). "
            f"Structural review recommended."
        )
    if pct_diff > tol_pct:
        return (
            f"Rebar spacing of {measurement_val:.1f} mm is outside the "
            f"±{tol_pct}% tolerance from {default_mm} mm. Monitor during placement."
        )
    return (
        f"Rebar spacing of {measurement_val:.1f} mm is within the "
        f"±{tol_pct}% tolerance of {default_mm} mm. Acceptable."
    )


def _recommendation_wall_plumb(status: ElementStatus, dev: float, warn: float, fail: float) -> str:
    if status == ElementStatus.FAIL:
        return "Immediate structural review required. Investigate formwork movement, footing settlement, or construction error."
    if status == ElementStatus.WARNING:
        return "Monitor during subsequent pours. Apply corrective measures if deviation approaches fail threshold."
    return "No action required."


def _recommendation_beam_level(status: ElementStatus, dev: float, warn: float, fail: float) -> str:
    if status == ElementStatus.FAIL:
        return "Immediate engineering assessment required. Check shoring stability and formwork alignment."
    if status == ElementStatus.WARNING:
        return "Monitor levelness during curing. Adjust formwork for subsequent pours if trend continues."
    return "No action required."


def _recommendation_door(status: ElementStatus, asym: float, max_asym: float) -> str:
    if status == ElementStatus.FAIL:
        return "Realign door frame urgently. Check hinge alignment, frame fixing, and wall plumb at opening."
    if status == ElementStatus.WARNING:
        return "Adjust door frame alignment. Verify hinge plate seating and frame squareness."
    return "No action required."


def _recommendation_rebar(pct_diff: float, tol_pct: float) -> str:
    if pct_diff > tol_pct * 2:
        return "Review rebar placement drawings. Consult structural engineer for corrective action."
    if pct_diff > tol_pct:
        return "Adjust rebar spacing during next placement to meet specification."
    return "No action required."


def evaluate_element(
    detection: Detection,
    geometry_findings: list[GeometryFinding],
    rules: dict[str, Any],
    element_index: int,
) -> ElementResult:
    status = ElementStatus.PASS
    deviation: float | None = None
    unit = "cm"
    messages: list[str] = []
    measurements = []
    reason: str | None = None

    allowed_value: str | None = None
    deviation_pct: float | None = None
    engineering_interpretation: str | None = None
    recommendation: str | None = None
    confidence_score: float = 0.0

    for gf in geometry_findings:
        messages.append(gf.message)
        measurements.extend(gf.measurements)

        is_estimated = any(m.estimated for m in gf.measurements)

        if is_estimated:
            candidate_status = ElementStatus.INCONCLUSIVE
            reason = "scale_not_calibrated"
            status = _worst_status(status, candidate_status)
            continue

        if gf.check_type == "wall_plumb":
            deviation = gf.deviation_per_m
            unit = "cm/m"
            warn = float(rules.get("wall_plumb", {}).get("warning_cm_per_m", 1.5))
            fail = float(rules.get("wall_plumb", {}).get("fail_cm_per_m", 3.0))
            candidate_status = _status_from_wall_plumb(gf.deviation_per_m, rules)
            status = _worst_status(status, candidate_status)
            allowed_value = _allowed_value_str(warn, fail, unit)
            deviation_pct = _deviation_pct(gf.deviation_per_m, warn, fail)
            engineering_interpretation = _interpretation_wall_plumb(gf.deviation_per_m, warn, fail)
            recommendation = _recommendation_wall_plumb(candidate_status, gf.deviation_per_m, warn, fail)
        elif gf.check_type == "beam_level":
            deviation = gf.deviation_per_m
            unit = "mm/m"
            warn = float(rules.get("beam_level", {}).get("warning_mm_per_m", 5.0))
            fail = float(rules.get("beam_level", {}).get("fail_mm_per_m", 10.0))
            candidate_status = _status_from_beam_level(gf.deviation_per_m, rules)
            status = _worst_status(status, candidate_status)
            allowed_value = _allowed_value_str(warn, fail, unit)
            deviation_pct = _deviation_pct(gf.deviation_per_m, warn, fail)
            engineering_interpretation = _interpretation_beam_level(gf.deviation_per_m, warn, fail)
            recommendation = _recommendation_beam_level(candidate_status, gf.deviation_per_m, warn, fail)
        elif gf.check_type == "door_alignment":
            deviation = gf.deviation_per_m
            unit = gf.unit
            max_asym = float(rules.get("door_alignment", {}).get("max_gap_asymmetry_mm", 15))
            candidate_status = _status_from_door(gf.deviation_per_m, rules)
            status = _worst_status(status, candidate_status)
            allowed_value = f"≤ {max_asym} mm"
            if gf.deviation_per_m > 0:
                deviation_pct = round((gf.deviation_per_m - max_asym) / max_asym * 100, 1) if gf.deviation_per_m > max_asym else 0.0
            engineering_interpretation = _interpretation_door(gf.deviation_per_m, max_asym)
            recommendation = _recommendation_door(candidate_status, gf.deviation_per_m, max_asym)
        elif gf.check_type == "rebar_spacing":
            default_mm = float(rules.get("rebar_spacing", {}).get("default_spacing_mm", 150))
            tol_pct = float(rules.get("rebar_spacing", {}).get("tolerance_pct", 10))
            val = gf.measurements[0].value
            unit = gf.unit
            deviation = val
            pct_diff = abs(val - default_mm) / default_mm * 100
            if pct_diff > tol_pct * 2:
                status = _worst_status(status, ElementStatus.FAIL)
            elif pct_diff > tol_pct:
                status = _worst_status(status, ElementStatus.WARNING)
            allowed_value = f"{default_mm} mm ± {tol_pct}%"
            deviation_pct = round(pct_diff, 1)
            engineering_interpretation = _interpretation_rebar(val, default_mm, tol_pct)
            recommendation = _recommendation_rebar(pct_diff, tol_pct)

        # Average confidence from measurements
        if gf.measurements:
            confs = [m.confidence for m in gf.measurements]
            confidence_score = round(sum(confs) / len(confs) * 100, 1)

    if not geometry_findings:
        status = ElementStatus.INCONCLUSIVE
        reason = "no_measurements_extracted"
        messages.append("No reliable geometric measurements extracted for this region.")
        engineering_interpretation = "Insufficient visual data for geometric analysis. Re-capture with better lighting and angle."
        recommendation = "Re-capture photo ensuring the element is clearly visible with adequate lighting."

    return ElementResult(
        element_id=f"E{element_index:03d}",
        label=detection.label,
        location=f"bbox {detection.bbox}",
        status=status,
        deviation=deviation,
        expected=None,
        unit=unit,
        reason=reason,
        measurements=measurements,
        message=" ".join(messages),
        bbox=detection.bbox,
        allowed_value=allowed_value,
        deviation_pct=deviation_pct,
        severity=_severity(status),
        engineering_interpretation=engineering_interpretation,
        recommendation=recommendation,
        confidence_score=confidence_score,
    )


def _worst_status(a: ElementStatus, b: ElementStatus) -> ElementStatus:
    order = {
        ElementStatus.PASS: 0,
        ElementStatus.INCONCLUSIVE: 1,
        ElementStatus.WARNING: 2,
        ElementStatus.FAIL: 3,
    }
    return a if order[a] >= order[b] else b


def _status_from_wall_plumb(dev_cm_per_m: float, rules: dict[str, Any]) -> ElementStatus:
    wall = rules.get("wall_plumb", {})
    warn = float(wall.get("warning_cm_per_m", 1.5))
    fail = float(wall.get("fail_cm_per_m", 3.0))
    if dev_cm_per_m >= fail:
        return ElementStatus.FAIL
    if dev_cm_per_m >= warn:
        return ElementStatus.WARNING
    return ElementStatus.PASS


def _status_from_beam_level(dev_mm_per_m: float, rules: dict[str, Any]) -> ElementStatus:
    beam = rules.get("beam_level", {})
    warn = float(beam.get("warning_mm_per_m", 5.0))
    fail = float(beam.get("fail_mm_per_m", 10.0))
    if dev_mm_per_m >= fail:
        return ElementStatus.FAIL
    if dev_mm_per_m >= warn:
        return ElementStatus.WARNING
    return ElementStatus.PASS


def _status_from_door(asym_mm: float, rules: dict[str, Any]) -> ElementStatus:
    door = rules.get("door_alignment", {})
    max_asym = float(door.get("max_gap_asymmetry_mm", 15))
    if asym_mm > max_asym * 2:
        return ElementStatus.FAIL
    if asym_mm > max_asym:
        return ElementStatus.WARNING
    return ElementStatus.PASS


def build_compliance_report(
    elements: list[ElementResult],
    ruleset: Ruleset,
) -> ComplianceReport:
    rules = _load_rules(ruleset)
    if not elements:
        return ComplianceReport(
            score=0.0,
            elements=[],
            critical_issues=["No structural elements detected."],
            recommendations=["Upload a clearer photo with visible walls, beams, or columns."],
            sqi=0.0,
            confidence_score=0.0,
        )

    scores = []
    critical: list[str] = []
    recommendations: list[str] = []
    pass_c = warning_c = fail_c = inconclusive_c = 0
    confidence_total = 0.0

    for el in elements:
        confidence_total += el.confidence_score
        if el.status == ElementStatus.PASS:
            scores.append(100)
            pass_c += 1
        elif el.status == ElementStatus.WARNING:
            scores.append(60)
            warning_c += 1
            recommendations.append(f"Monitor {el.label}: {el.message}")
        elif el.status == ElementStatus.FAIL:
            scores.append(0)
            fail_c += 1
            critical.append(f"{el.label} — {el.message}")
            if el.recommendation:
                recommendations.append(f"[Immediate] {el.label}: {el.recommendation}")
        else:
            scores.append(40)
            inconclusive_c += 1
            recommendations.append(f"Re-capture photo for {el.label} — {el.recommendation or 'measurement inconclusive.'}")

    score = round(sum(scores) / len(scores), 1)
    confidence_score = round(confidence_total / len(elements), 1) if elements else 0.0
    return ComplianceReport(
        score=score,
        elements=elements,
        critical_issues=critical,
        recommendations=recommendations,
        pass_count=pass_c,
        warning_count=warning_c,
        fail_count=fail_c,
        inconclusive_count=inconclusive_c,
        sqi=score,
        confidence_score=confidence_score,
    )
