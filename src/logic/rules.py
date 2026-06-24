"""Rule-based inspection checks for the MVP (Day 3).

This module intentionally uses simple, explainable heuristics based on edges and detected line segments.
The output is a list of findings that can be scored and shown to the user.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Literal, Optional

import numpy as np

from src.vision.feature_extract import OrientationSummary

Severity = Literal["info", "minor", "moderate", "major"]


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    title: str
    message: str
    details: dict[str, Any] | None = None


def _line_angle_deg(x1: int, y1: int, x2: int, y2: int) -> float:
    dx = float(x2 - x1)
    dy = float(y2 - y1)
    angle = abs(math.degrees(math.atan2(dy, dx)))  # [0, 180)
    return angle % 180.0


def _cluster_positions(values: np.ndarray, tol_px: float) -> list[float]:
    """Cluster 1D positions so multiple segments on the same bar count once."""
    if values.size == 0:
        return []

    values = np.sort(values.astype(float))
    clusters: list[list[float]] = [[float(values[0])]]

    for v in values[1:]:
        if abs(float(v) - clusters[-1][-1]) <= tol_px:
            clusters[-1].append(float(v))
        else:
            clusters.append([float(v)])

    return [float(np.mean(c)) for c in clusters]


def _coef_of_variation(gaps: np.ndarray) -> float:
    if gaps.size == 0:
        return 0.0
    mean = float(np.mean(gaps))
    if mean <= 1e-6:
        return 0.0
    return float(np.std(gaps) / mean)


def run_rule_checks(
    *,
    width: int,
    height: int,
    edges: np.ndarray,
    lines: Optional[np.ndarray],
    orientation: OrientationSummary,
    vertical_tol_deg: float = 20.0,
    horizontal_tol_deg: float = 20.0,
) -> tuple[list[Finding], dict[str, Any]]:
    """
    Run rule-based checks and return (findings, metrics).

    Metrics are useful for debugging and for displaying small explainable numbers in the UI.
    """
    findings: list[Finding] = []

    total_px = float(width * height)
    edge_px = float(np.count_nonzero(edges))
    edge_density = edge_px / total_px if total_px else 0.0

    metrics: dict[str, Any] = {
        "edge_density": edge_density,
        "num_lines": orientation.num_lines,
        "orientation_guess": orientation.guess,
        "vertical_ratio": orientation.vertical_ratio,
        "horizontal_ratio": orientation.horizontal_ratio,
    }

    # Image quality / signal checks.
    if edge_density < 0.002:
        findings.append(
            Finding(
                code="LOW_VISUAL_SIGNAL",
                severity="moderate",
                title="Low Visual Signal",
                message="Very few edges detected. The photo may be blurry, too dark, or too far away.",
                details={"edge_density": edge_density},
            )
        )
    elif edge_density > 0.18:
        findings.append(
            Finding(
                code="HIGH_NOISE_OR_CLUTTER",
                severity="minor",
                title="High Noise / Clutter",
                message="Many edges detected. The background may be cluttered or the image may be noisy. Cropping can help.",
                details={"edge_density": edge_density},
            )
        )

    if orientation.num_lines < 15:
        findings.append(
            Finding(
                code="TOO_FEW_LINES",
                severity="moderate",
                title="Not Enough Detected Lines",
                message="Line detection found too few line segments for reliable checks. Try adjusting thresholds or use a clearer photo.",
                details={"num_lines": orientation.num_lines},
            )
        )

    # If there are no lines, stop further geometry checks.
    if lines is None or len(lines) == 0:
        return findings, metrics

    # Classify lines by orientation.
    vertical_angles: list[float] = []
    horizontal_angles: list[float] = []
    vertical_x: list[float] = []
    horizontal_y: list[float] = []

    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = _line_angle_deg(int(x1), int(y1), int(x2), int(y2))

        # Horizontal: close to 0 or 180.
        if angle <= horizontal_tol_deg or angle >= (180.0 - horizontal_tol_deg):
            horizontal_angles.append(angle if angle <= 90 else 180.0 - angle)
            horizontal_y.append((float(y1) + float(y2)) / 2.0)
            continue

        # Vertical: close to 90.
        if abs(angle - 90.0) <= vertical_tol_deg:
            vertical_angles.append(abs(angle - 90.0))
            vertical_x.append((float(x1) + float(x2)) / 2.0)
            continue

    metrics["vertical_line_count"] = len(vertical_angles)
    metrics["horizontal_line_count"] = len(horizontal_angles)

    # Decide which family to analyze for spacing and alignment.
    mode: Literal["vertical", "horizontal", "unknown"]
    if "Column-like" in orientation.guess:
        mode = "vertical"
    elif "Beam-like" in orientation.guess:
        mode = "horizontal"
    else:
        mode = "vertical" if len(vertical_angles) >= len(horizontal_angles) else "horizontal"

    metrics["analysis_mode"] = mode

    # Alignment check: average angle deviation.
    if mode == "vertical" and len(vertical_angles) >= 10:
        mean_dev = float(np.mean(np.array(vertical_angles, dtype=float)))
        metrics["mean_vertical_deviation_deg"] = mean_dev
        if mean_dev > 12.0:
            findings.append(
                Finding(
                    code="VERTICAL_MISALIGNMENT",
                    severity="major" if mean_dev > 18.0 else "moderate",
                    title="Possible Misalignment (Vertical)",
                    message="Detected vertical lines show noticeable tilt. This may indicate misaligned bars or camera tilt.",
                    details={"mean_deviation_deg": mean_dev},
                )
            )
    elif mode == "horizontal" and len(horizontal_angles) >= 10:
        mean_dev = float(np.mean(np.array(horizontal_angles, dtype=float)))
        metrics["mean_horizontal_deviation_deg"] = mean_dev
        if mean_dev > 12.0:
            findings.append(
                Finding(
                    code="HORIZONTAL_MISALIGNMENT",
                    severity="major" if mean_dev > 18.0 else "moderate",
                    title="Possible Misalignment (Horizontal)",
                    message="Detected horizontal lines show noticeable tilt. This may indicate misaligned bars or camera tilt.",
                    details={"mean_deviation_deg": mean_dev},
                )
            )

    # Spacing consistency check: cluster bar positions then measure gap variation.
    tol_px = max(6.0, 0.01 * float(width if mode == "vertical" else height))
    metrics["cluster_tolerance_px"] = tol_px

    if mode == "vertical" and len(vertical_x) >= 12:
        centers = _cluster_positions(np.array(vertical_x, dtype=float), tol_px=tol_px)
        metrics["vertical_cluster_count"] = len(centers)
        if len(centers) >= 6:
            gaps = np.diff(np.array(sorted(centers), dtype=float))
            cv = _coef_of_variation(gaps)
            metrics["vertical_spacing_cv"] = cv
            if cv > 0.55:
                findings.append(
                    Finding(
                        code="IRREGULAR_VERTICAL_SPACING",
                        severity="moderate",
                        title="Irregular Spacing (Vertical Bars)",
                        message="Detected vertical bar spacing appears inconsistent. This may indicate uneven bar placement or occlusion.",
                        details={"spacing_cv": cv, "bar_count_est": len(centers)},
                    )
                )
    elif mode == "horizontal" and len(horizontal_y) >= 12:
        centers = _cluster_positions(np.array(horizontal_y, dtype=float), tol_px=tol_px)
        metrics["horizontal_cluster_count"] = len(centers)
        if len(centers) >= 6:
            gaps = np.diff(np.array(sorted(centers), dtype=float))
            cv = _coef_of_variation(gaps)
            metrics["horizontal_spacing_cv"] = cv
            if cv > 0.55:
                findings.append(
                    Finding(
                        code="IRREGULAR_HORIZONTAL_SPACING",
                        severity="moderate",
                        title="Irregular Spacing (Horizontal Bars)",
                        message="Detected horizontal bar spacing appears inconsistent. This may indicate uneven placement or occlusion.",
                        details={"spacing_cv": cv, "bar_count_est": len(centers)},
                    )
                )

    # Informational note if the scene is mixed.
    if orientation.num_lines >= 20 and (orientation.vertical_ratio < 0.55 and orientation.horizontal_ratio < 0.55):
        findings.append(
            Finding(
                code="MIXED_ORIENTATION",
                severity="info",
                title="Mixed Orientation",
                message="The scene has a mix of vertical and horizontal lines. Consider cropping to focus on a single element.",
                details={"vertical_ratio": orientation.vertical_ratio, "horizontal_ratio": orientation.horizontal_ratio},
            )
        )

    return findings, metrics

