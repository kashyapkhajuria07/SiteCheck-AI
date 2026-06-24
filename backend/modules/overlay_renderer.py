"""Draw colour-coded bounding boxes and deviation labels on inspection images."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from schemas.inspection import ElementResult, ElementStatus

_STATUS_COLOUR = {
    ElementStatus.PASS: (180, 180, 180),
    ElementStatus.WARNING: (0, 180, 255),
    ElementStatus.FAIL: (0, 0, 255),
    ElementStatus.INCONCLUSIVE: (180, 180, 180),
}

_LEGEND_H = 28


def _draw_legend(canvas: np.ndarray, elements: list[ElementResult]) -> np.ndarray:
    h, w = canvas.shape[:2]
    bar = np.full((_LEGEND_H, w, 3), 245, dtype=np.uint8)
    cv2.rectangle(bar, (0, 0), (w - 1, _LEGEND_H - 1), (200, 200, 200), 1)

    legend_items = [
        ("Fail", (0, 0, 255)),
        ("Warning", (0, 180, 255)),
        ("Pass", (180, 180, 180)),
        ("Inconclusive", (180, 180, 180)),
    ]
    x = 10
    for label, colour in legend_items:
        cv2.rectangle(bar, (x, 6), (x + 14, 20), colour, -1)
        cv2.putText(
            bar, label, (x + 18, 18),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 80), 1, cv2.LINE_AA,
        )
        x += len(label) * 10 + 36

    stats: dict[str, int] = {}
    for el in elements:
        stats[el.status.value] = stats.get(el.status.value, 0) + 1
    parts = [f"{k}: {v}" for k, v in sorted(stats.items())]
    stat_str = " | ".join(parts) + f" | Total: {len(elements)}"
    stat_x = w - 10 - len(stat_str) * 5
    cv2.putText(
        bar, stat_str, (stat_x, 18),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1, cv2.LINE_AA,
    )

    return np.vstack([bar, canvas])


def render_overlay(
    bgr: np.ndarray,
    elements: list[ElementResult],
) -> np.ndarray:
    """Return annotated BGR image with boxes, deviation labels, and legend."""
    canvas = bgr.copy()

    for el in elements:
        if len(el.bbox) != 4:
            continue
        x1, y1, x2, y2 = el.bbox
        colour = _STATUS_COLOUR.get(el.status, (200, 200, 200))
        thickness = 3 if el.status == ElementStatus.FAIL else 2
        cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, thickness)

        label_parts = [el.label, el.status.value]
        if el.deviation is not None:
            label_parts.append(f"{el.deviation:.1f}{el.unit}")
        if el.confidence_score:
            label_parts.append(f"({el.confidence_score:.0f}%)")
        label = " — ".join(label_parts)

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        text_bg = max(0, y1 - th - 8)
        cv2.rectangle(canvas, (x1, text_bg), (x1 + tw + 6, y1), colour, -1)
        text_colour = (0, 0, 0) if el.status == ElementStatus.FAIL else (255, 255, 255)
        cv2.putText(
            canvas,
            label,
            (x1 + 3, max(12, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

        if el.status in {ElementStatus.WARNING, ElementStatus.FAIL} and el.deviation:
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            arrow_len = min(60, (x2 - x1) // 4)
            cv2.arrowedLine(
                canvas,
                (cx - arrow_len, cy),
                (cx + arrow_len, cy),
                colour,
                2,
                tipLength=0.3,
            )

        from config import DEBUG_OVERLAYS

        if DEBUG_OVERLAYS:
            for m in el.measurements:
                if m.details and "lines" in m.details:
                    for line in m.details["lines"]:
                        lx1, ly1, lx2, ly2 = line
                        cv2.line(canvas, (x1 + lx1, y1 + ly1), (x1 + lx2, y1 + ly2), (255, 0, 255), 1)

    return _draw_legend(canvas, elements)


def save_overlay_image(bgr: np.ndarray, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), bgr)
    return str(path)
