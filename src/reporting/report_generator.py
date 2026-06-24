"""Report generation placeholders for the Day 1 MVP."""

from __future__ import annotations

import textwrap
from dataclasses import asdict
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from src.logic.rules import Finding


def _format_finding_line(finding: Finding) -> str:
    sev = finding.severity.upper()
    return f"- [{sev}] {finding.title}: {finding.message}"


def generate_inspection_summary(
    *,
    file_name: str,
    score: int,
    status: str,
    findings: list[Finding],
    metrics: dict[str, Any] | None = None,
) -> str:
    """Generate a plain-language inspection summary for the UI + downloads."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []

    lines.append("SiteCheck-AI Inspection Summary")
    lines.append(f"Timestamp: {ts}")
    lines.append(f"Image: {file_name}")
    lines.append(f"Score: {score}/100")
    lines.append(f"Status: {status}")
    lines.append("")

    if findings:
        lines.append("Findings:")
        for f in findings:
            lines.append(_format_finding_line(f))
    else:
        lines.append("Findings:")
        lines.append("- [INFO] No rule-based issues detected (preliminary).")

    if metrics:
        lines.append("")
        lines.append("Metrics (debug/explainability):")
        # Keep this compact for MVP; values are simple scalars.
        for k in sorted(metrics.keys()):
            v = metrics[k]
            if isinstance(v, float):
                lines.append(f"- {k}: {v:.4f}")
            else:
                lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Note: This is a preliminary, image-based check intended to assist inspection, not replace engineering approval.")
    return "\n".join(lines)


def findings_as_dicts(findings: list[Finding]) -> list[dict[str, Any]]:
    """Convenience for displaying findings in Streamlit tables."""
    out: list[dict[str, Any]] = []
    for f in findings:
        d = asdict(f)
        if d.get("details") is None:
            d["details"] = {}
        out.append(d)
    return out


def generate_pdf_report_bytes(summary_text: str, title: str = "SiteCheck-AI Report") -> bytes:
    """
    Build a minimal A4 PDF from inspection summary text.

    Title and timestamp appear at the top; the summary is written line-by-line
    with simple wrapping and pagination.
    """
    buffer = BytesIO()
    _, page_h = A4
    margin_x = 50
    margin_bottom = 50
    line_height = 12
    max_chars = 95

    c = canvas.Canvas(buffer, pagesize=A4)
    y = page_h - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin_x, y, title[:120])
    y -= line_height * 2

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.setFont("Helvetica", 10)
    c.drawString(margin_x, y, f"Generated: {ts}")
    y -= line_height * 2

    c.setFont("Helvetica", 9)
    for raw_line in summary_text.splitlines():
        wrapped = textwrap.wrap(raw_line, width=max_chars) or [""]
        for segment in wrapped:
            if y < margin_bottom:
                c.showPage()
                c.setFont("Helvetica", 9)
                y = page_h - margin_bottom
            c.drawString(margin_x, y, segment[:500])
            y -= line_height

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
