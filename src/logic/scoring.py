"""Scoring placeholders for the Day 1 MVP."""

from __future__ import annotations

from typing import Any

from src.logic.rules import Finding

_SEVERITY_POINTS = {
    "info": 0,
    "minor": 5,
    "moderate": 12,
    "major": 20,
}


def calculate_compliance_score(findings: list[Finding]) -> dict[str, Any]:
    """Convert findings into a simple 0-100 score and a readable status."""
    deductions: list[dict[str, Any]] = []
    score = 100

    for f in findings:
        points = int(_SEVERITY_POINTS.get(f.severity, 0))
        if points <= 0:
            continue
        score -= points
        deductions.append(
            {
                "code": f.code,
                "severity": f.severity,
                "points": points,
                "title": f.title,
            }
        )

    score = max(0, min(100, int(score)))

    # Status is intentionally phrased as "preliminary" since this is image-only.
    if any(f.code in {"LOW_VISUAL_SIGNAL", "TOO_FEW_LINES"} for f in findings):
        status = "Preliminary: Low confidence (image signal too weak)"
    elif score >= 85:
        status = "Preliminary: Looks OK"
    elif score >= 70:
        status = "Preliminary: Minor issues (review suggested)"
    elif score >= 50:
        status = "Preliminary: Needs review"
    else:
        status = "Preliminary: High concern"

    return {"score": score, "status": status, "deductions": deductions}
