"""Professional V3 PDF inspection report — SiteCheck AI."""

from __future__ import annotations

import textwrap
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import OUTPUTS_DIR
from schemas.inspection import ComplianceReport, ElementResult, ElementStatus, PhotoResult, Ruleset, UnitSystem

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

PRIMARY = colors.HexColor("#1a237e")
ACCENT = colors.HexColor("#3949ab")
SECONDARY = colors.HexColor("#0d47a1")
BG_LIGHT = colors.HexColor("#f5f5f5")
DARK = colors.HexColor("#212121")

PASS_COLOR = colors.HexColor("#2e7d32")
WARN_COLOR = colors.HexColor("#f57f17")
FAIL_COLOR = colors.HexColor("#c62828")
INCONCLUSIVE_COLOR = colors.HexColor("#757575")

_SECTION_FONT_SIZE = 14
_SUBSECTION_FONT_SIZE = 11
_BODY_FONT_SIZE = 9
_SMALL_FONT_SIZE = 7

_rule_name_map = {
    Ruleset.IS456: "IS:456:2000 — Indian Standard for Plain and Reinforced Concrete",
    Ruleset.NBC2016: "NBC 2016 — National Building Code of India",
    Ruleset.CUSTOM: "Custom Ruleset",
}


def _rule_display_name(ruleset: Ruleset) -> str:
    return _rule_name_map.get(ruleset, ruleset.value)


def _sqi_color(score: float) -> colors.Color:
    if score >= 85:
        return PASS_COLOR
    if score >= 70:
        return WARN_COLOR
    return FAIL_COLOR


def _sqi_label(score: float) -> str:
    if score >= 85:
        return "PASS — Compliant"
    if score >= 70:
        return "WARNING — Marginal"
    return "FAIL — Non-compliant"


_column_style = ParagraphStyle(
    "col", fontSize=_BODY_FONT_SIZE, leading=_BODY_FONT_SIZE + 3, textColor=DARK,
)
_body_style = ParagraphStyle(
    "body", fontSize=_BODY_FONT_SIZE, leading=_BODY_FONT_SIZE + 4, textColor=DARK, alignment=TA_JUSTIFY,
)


def _section_style():
    return ParagraphStyle(
        "section", fontSize=_SECTION_FONT_SIZE, leading=_SECTION_FONT_SIZE + 4, textColor=PRIMARY, spaceBefore=6, spaceAfter=8,
    )


def _subsection_style():
    return ParagraphStyle(
        "subsection", fontSize=_SUBSECTION_FONT_SIZE, leading=_SUBSECTION_FONT_SIZE + 3, textColor=ACCENT, spaceBefore=8, spaceAfter=4,
    )
_badge_style = ParagraphStyle(
    "badge", fontSize=7, leading=9, alignment=TA_CENTER,
)
_card_header_style = ParagraphStyle(
    "cardh", fontSize=9, leading=11, textColor=DARK,
)
_card_body_style = ParagraphStyle(
    "cardb", fontSize=8, leading=11, textColor=DARK,
)
_empty_style = ParagraphStyle("empty", fontSize=1, leading=1)


def _status_badge(status: str) -> Table:
    bg, fg = {
        "PASS": ("#e8f5e9", "#2e7d32"),
        "WARNING": ("#fff8e1", "#f57f17"),
        "FAIL": ("#ffebee", "#c62828"),
        "INCONCLUSIVE": ("#f5f5f5", "#757575"),
    }.get(status, ("#eeeeee", "#212121"))
    s = ParagraphStyle("sb", parent=_badge_style, textColor=colors.HexColor(fg))
    return Table(
        [[Paragraph(status, s)]],
        colWidths=[1.8 * cm],
        rowHeights=[0.45 * cm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(fg)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]),
    )


def _severity_badge(severity: str) -> Paragraph:
    color = {
        "NONE": PASS_COLOR,
        "MODERATE": WARN_COLOR,
        "HIGH": FAIL_COLOR,
        "INDETERMINATE": INCONCLUSIVE_COLOR,
    }.get(severity, DARK)
    return Paragraph(f"<b>{severity}</b>", ParagraphStyle("sevb", fontSize=7, leading=9, textColor=color, alignment=TA_CENTER))


# ── page templates ─────────────────────────────────────────────


class _HeaderFooter:
    def __init__(self, session_id: str, ts: str):
        self.session_id = session_id
        self.ts = ts

    def header(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(PRIMARY)
        canvas.rect(MARGIN, PAGE_H - 1.2 * cm, CONTENT_W, 1.2 * cm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN + 0.3 * cm, PAGE_H - 0.85 * cm, "SiteCheck AI — Structural Inspection Report")
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(PAGE_W - MARGIN - 0.3 * cm, PAGE_H - 0.85 * cm, self.session_id)
        canvas.restoreState()

    def footer(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#bdbdbd"))
        canvas.line(MARGIN, 1.2 * cm, PAGE_W - MARGIN, 1.2 * cm)
        canvas.setFillColor(colors.HexColor("#757575"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN, 0.7 * cm, f"Generated: {self.ts}  |  Confidential")
        canvas.drawRightString(PAGE_W - MARGIN, 0.7 * cm, f"Page {doc.page}")
        canvas.restoreState()


# ── content builders ───────────────────────────────────────────


def _accent_bar(height: float = 0.4 * cm) -> Table:
    t = Table([[Paragraph("", _empty_style)]], colWidths=[CONTENT_W], rowHeights=[height])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PRIMARY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


def _thin_bar(color=ACCENT, height: float = 0.08 * cm) -> Table:
    t = Table([[Paragraph("", _empty_style)]], colWidths=[CONTENT_W], rowHeights=[height])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


# ── Page 1: Cover ──────────────────────────────────────────────


def _cover_page(story, session_id: str, ts: str, ruleset: Ruleset, unit_system: UnitSystem,
                sqi: float, confidence_score: float, project_name: str, inspection_date: str,
                photo_count: int, element_counts: dict[str, int], total_elements: int,
                scene_type: str = ""):
    story.append(Spacer(1, 0.01 * mm))
    story.append(_accent_bar(0.5 * cm))
    story.append(Spacer(1, 3.5 * cm))

    title_style = ParagraphStyle("ct", fontSize=30, leading=36, textColor=PRIMARY, spaceAfter=4, alignment=TA_CENTER)
    story.append(Paragraph("SiteCheck AI", title_style))
    sub_style = ParagraphStyle("cs", fontSize=14, leading=18, textColor=ACCENT, spaceAfter=2, alignment=TA_CENTER)
    story.append(Paragraph("Structural Compliance Inspection Report", sub_style))
    story.append(Spacer(1, 0.3 * cm))

    is_unsupported = scene_type not in ("construction_site", "structural_frame", "")
    if is_unsupported:
        sqi_val_style = ParagraphStyle("sqiv", fontSize=42, leading=50, textColor=colors.HexColor("#9e9e9e"), alignment=TA_CENTER)
        story.append(Paragraph("N/A", sqi_val_style))
        sqi_label_style = ParagraphStyle("sql", fontSize=12, leading=15, textColor=DARK, alignment=TA_CENTER, spaceAfter=2)
        story.append(Paragraph("Structural Quality Index (SQI)", sqi_label_style))
        sqi_cls = ParagraphStyle("sqc", fontSize=10, leading=13, textColor=FAIL_COLOR, alignment=TA_CENTER, spaceAfter=6)
        story.append(Paragraph("NOT ASSESSED", sqi_cls))
    else:
        sqi_val_style = ParagraphStyle("sqiv", fontSize=52, leading=60, textColor=_sqi_color(sqi), alignment=TA_CENTER)
        story.append(Paragraph(f"{sqi:.0f}", sqi_val_style))
        sqi_label_style = ParagraphStyle("sql", fontSize=12, leading=15, textColor=DARK, alignment=TA_CENTER, spaceAfter=2)
        story.append(Paragraph("Structural Quality Index (SQI)", sqi_label_style))
        sqi_cls = ParagraphStyle("sqc", fontSize=9, leading=12, textColor=_sqi_color(sqi), alignment=TA_CENTER, spaceAfter=6)
        story.append(Paragraph(f"{_sqi_label(sqi)}", sqi_cls))

    # SQI gauge bar
    story.append(Spacer(1, 0.3 * cm))
    if not is_unsupported:
        story.append(_sqi_gauge(sqi, CONTENT_W))
    else:
        story.append(Spacer(1, 0.5 * cm))
    story.append(Spacer(1, 1.2 * cm))

    # Metadata table
    element_summary = ", ".join(f"{v} {k}" + ("s" if v > 1 else "") for k, v in sorted(element_counts.items()))
    total_str = f"{total_elements} ({element_summary})" if element_summary else str(total_elements)
    sqi_display = "NOT ASSESSED" if is_unsupported else _sqi_label(sqi)

    info_data = [
        ("Report ID", session_id),
        ("Inspection Date", inspection_date),
        ("Project Name", project_name),
        ("Applicable Standard", _rule_display_name(ruleset)),
        ("Unit System", unit_system.value.title()),
        ("Images Analysed", str(photo_count)),
        ("Elements Analysed", total_str),
        ("Confidence Score", f"{confidence_score:.0f}%"),
        ("SQI Classification", sqi_display),
    ]
    rows = []
    for k, v in info_data:
        rows.append([Paragraph(f"<b>{k}</b>", _column_style), Paragraph(v, _column_style)])
    info_table = Table(rows, colWidths=[4.5 * cm, 10.5 * cm])
    cmds = [
        ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]
    info_table.setStyle(TableStyle(cmds))
    story.append(info_table)
    story.append(Spacer(1, 2.5 * cm))
    story.append(_thin_bar())
    story.append(Spacer(1, 0.3 * cm))
    disc = ParagraphStyle("discc", fontSize=7, leading=9, textColor=colors.HexColor("#9e9e9e"), alignment=TA_CENTER)
    story.append(Paragraph(f"Generated: {ts}  |  This document is confidential", disc))
    story.append(PageBreak())


# ── Page 2: Executive Dashboard ────────────────────────────────


def _sqi_gauge(score: float, width: float) -> Table:
    bar_h = 1.0 * cm
    pct = max(0, min(100, score)) / 100.0
    min_seg = 0.5 * cm
    seg_w = max(width * pct, min_seg)
    rest_w = max(width * (1 - pct), min_seg)
    # Keep total width constant
    total = seg_w + rest_w
    if total > width:
        scale = width / total
        seg_w *= scale
        rest_w *= scale
    color = _sqi_color(score)
    bg = colors.HexColor("#e0e0e0")
    g = ParagraphStyle("g", fontSize=8, textColor=colors.white, alignment=TA_CENTER)
    fill_cell = [[Paragraph(f"{score:.0f}%", g)]] if seg_w > 1.5 * cm else [[Paragraph("", _empty_style)]]
    empty_cell = [[Paragraph("", _empty_style)]]
    t = Table([fill_cell + empty_cell], colWidths=[seg_w, rest_w], rowHeights=[bar_h])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), color),
        ("BACKGROUND", (1, 0), (1, 0), bg),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _executive_dashboard(story, compliance: ComplianceReport,
                         coverage_pct: float = 0.0, measurement_confidence: float = 0.0):
    story.append(Paragraph("Executive Dashboard", _section_style()))
    story.append(Spacer(1, 0.2 * cm))

    # ── SQI + Confidence gauges ──
    story.append(Paragraph("<b>Structural Quality Index (SQI)</b>", _subsection_style()))
    story.append(_sqi_gauge(compliance.sqi, CONTENT_W))
    story.append(Spacer(1, 0.3 * cm))

    # ── Critical Findings Summary Card (below SQI) ──
    fails = [el for el in compliance.elements if el.status == ElementStatus.FAIL]
    if fails:
        card_data = []
        card_data.append([
            Paragraph("<b>Critical Findings</b>",
                      ParagraphStyle("cfh", fontSize=9, leading=12, textColor=colors.white))
        ])
        for el in fails[:5]:  # show top 5
            dev_str = f" by {el.deviation_pct:.0f}%" if el.deviation_pct else ""
            card_data.append([
                Paragraph(
                    f"❌ {el.label.title()} {el.element_id} exceeds tolerance{dev_str}",
                    ParagraphStyle("cfi", fontSize=8, leading=11, textColor=FAIL_COLOR, leftIndent=4)
                )
            ])
        if len(fails) > 5:
            card_data.append([
                Paragraph(f"+ {len(fails) - 5} more critical issues",
                          ParagraphStyle("cfm", fontSize=7, leading=10, textColor=colors.gray, leftIndent=4))
            ])
        card = Table(card_data, colWidths=[CONTENT_W])
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#c62828")),
            ("BOX", (0, 1), (0, -1), 0.5, colors.HexColor("#ffcdd2")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(card)
        story.append(Spacer(1, 0.3 * cm))
    else:
        story.append(Paragraph(
            "<font color='green'>✅ No critical issues detected</font>",
            ParagraphStyle("no_crit", fontSize=9, leading=12, spaceAfter=6)
        ))
        story.append(Spacer(1, 0.2 * cm))

    # Measurement Confidence gauge
    story.append(Paragraph("<b>Measurement Confidence</b>", _subsection_style()))
    story.append(_sqi_gauge(compliance.confidence_score, CONTENT_W))
    story.append(Spacer(1, 0.5 * cm))

    # ── Summary stats table ──
    total = compliance.pass_count + compliance.warning_count + compliance.fail_count + compliance.inconclusive_count
    hdr = ParagraphStyle("dh", fontSize=8, leading=10, textColor=colors.white, alignment=TA_CENTER)
    cell = ParagraphStyle("dc", fontSize=9, leading=12, textColor=DARK, alignment=TA_CENTER)
    summary_data = [
        [Paragraph("Status", hdr), Paragraph("Count", hdr), Paragraph("% of Total", hdr)],
        [Paragraph("✅ Pass", cell), Paragraph(str(compliance.pass_count), cell),
         Paragraph(f"{compliance.pass_count / total * 100:.0f}%" if total else "—", cell)],
        [Paragraph("⚠ Warning", cell), Paragraph(str(compliance.warning_count), cell),
         Paragraph(f"{compliance.warning_count / total * 100:.0f}%" if total else "—", cell)],
        [Paragraph("❌ Fail", cell), Paragraph(str(compliance.fail_count), cell),
         Paragraph(f"{compliance.fail_count / total * 100:.0f}%" if total else "—", cell)],
        [Paragraph("➖ Inconclusive", cell), Paragraph(str(compliance.inconclusive_count), cell),
         Paragraph(f"{compliance.inconclusive_count / total * 100:.0f}%" if total else "—", cell)],
    ]
    bg_colors = [
        ("#e8f5e9", "#2e7d32"),
        ("#fff8e1", "#f57f17"),
        ("#ffebee", "#c62828"),
        ("#f5f5f5", "#757575"),
    ]
    st = Table(summary_data, colWidths=[4 * cm, 2.5 * cm, 3 * cm])
    scmds = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, (bg, _) in enumerate(bg_colors, start=1):
        scmds.append(("BACKGROUND", (0, i), (0, i), colors.HexColor(bg)))
    st.setStyle(TableStyle(scmds))
    story.append(st)
    story.append(Spacer(1, 0.4 * cm))

    # ── Inspection Coverage Card ──
    card_data = [
        [Paragraph("<b>Inspection Coverage</b>",
                   ParagraphStyle("covh", fontSize=9, leading=12, textColor=colors.white))],
        [Paragraph(
            f"Detected Elements: {compliance.pass_count + compliance.warning_count + compliance.fail_count + compliance.inconclusive_count}  |  "
            f"Successfully Measured: {compliance.pass_count + compliance.warning_count + compliance.fail_count}  |  "
            f"Coverage: {coverage_pct:.0f}%  |  "
            f"Measurement Confidence: {measurement_confidence:.0f}%",
            ParagraphStyle("covb", fontSize=8, leading=12, textColor=DARK, leftIndent=4)
        )],
    ]
    cov_card = Table(card_data, colWidths=[CONTENT_W])
    cov_card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), PRIMARY),
        ("BOX", (0, 1), (0, 1), 0.5, colors.HexColor("#e0e0e0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(cov_card)
    story.append(Spacer(1, 0.4 * cm))

    # ── AI Inspection Summary ──
    story.append(Paragraph("<b>AI Inspection Summary</b>", _subsection_style()))
    summary_parts = []
    fail_c = compliance.fail_count
    warn_c = compliance.warning_count
    pass_c = compliance.pass_count
    if fail_c > 0:
        worst = max(fails, key=lambda e: e.deviation_pct or 0) if fails else None
        summary_parts.append(
            f"{fail_c} critical issue{'s' if fail_c != 1 else ''} were detected."
        )
        if worst:
            summary_parts.append(
                f"The most severe issue is {worst.label.lower()} {worst.element_id}, "
                f"exceeding allowable tolerance by {worst.deviation_pct:.0f}%."
            )
    else:
        summary_parts.append("No critical issues were detected.")
    if warn_c > 0:
        warning_labels = sorted(set(e.label.title() for e in compliance.elements if e.status == ElementStatus.WARNING))
        summary_parts.append(
            f"{'Additional ' if fail_c > 0 else ''}{warn_c} element{'s' if warn_c != 1 else ''} "
            f"{'require' if warn_c != 1 else 'requires'} attention: {', '.join(warning_labels)}."
        )
    if pass_c > 0:
        summary_parts.append(
            f"{pass_c} element{'s' if pass_c != 1 else ''} within compliance limits."
        )
    story.append(Paragraph(
        " ".join(summary_parts),
        ParagraphStyle("ais", fontSize=8, leading=12, textColor=DARK, leftIndent=4, spaceAfter=4)
    ))
    story.append(Spacer(1, 0.3 * cm))

    # ── Critical issues detailed ──
    if fails:
        story.append(Paragraph(f"<b>Critical Issues ({len(fails)})</b>", _subsection_style()))
        for el in fails:
            ci_style = ParagraphStyle("ci", fontSize=8, leading=12, textColor=FAIL_COLOR, leftIndent=8, spaceAfter=2)
            story.append(Paragraph(f"<b>{el.element_id}</b> — {el.label}", ci_style))
            story.append(Paragraph(f"Severity: <b>{el.severity}</b> — {el.engineering_interpretation or el.message}", _body_style))
            story.append(Spacer(1, 0.15 * cm))
        story.append(Spacer(1, 0.2 * cm))

    if warnings := [el for el in compliance.elements if el.status == ElementStatus.WARNING]:
        story.append(Paragraph(f"<b>Warning Issues ({len(warnings)})</b>", _subsection_style()))
        for el in warnings:
            wi_style = ParagraphStyle("wi", fontSize=8, leading=12, textColor=WARN_COLOR, leftIndent=8, spaceAfter=2)
            story.append(Paragraph(f"<b>{el.element_id}</b> — {el.label}: {el.message}", wi_style))
            story.append(Spacer(1, 0.1 * cm))

    # ── Future-proof layout sections (placeholder) ──
    story.append(Spacer(1, 0.3 * cm))
    future_sections = [
        ("Structural Quality", compliance.sqi),
        ("Dimensional Compliance", compliance.score),
    ]
    sections_text = "  |  ".join(
        f"<b>{name}</b>: {val:.1f}" for name, val in future_sections
    )
    story.append(Paragraph(
        sections_text,
        ParagraphStyle("fpl", fontSize=7, leading=10, textColor=colors.gray, alignment=TA_CENTER)
    ))

    story.append(PageBreak())


# ── Page 3: Project Information ────────────────────────────────


def _project_information(story, session_id: str, ts: str, ruleset: Ruleset, unit_system: UnitSystem,
                         project_name: str, inspection_date: str, photo_count: int,
                         element_counts: dict[str, int], total_elements: int, compliance: ComplianceReport):
    story.append(Paragraph("Project Information", _section_style()))
    story.append(Spacer(1, 0.2 * cm))

    element_summary = ", ".join(f"{v} {k}" + ("s" if v > 1 else "") for k, v in sorted(element_counts.items()))
    total_str = f"{total_elements} ({element_summary})" if element_summary else str(total_elements)

    rows = [
        [Paragraph("<b>Project Name</b>", _column_style), Paragraph(project_name, _column_style)],
        [Paragraph("<b>Inspection Date</b>", _column_style), Paragraph(inspection_date, _column_style)],
        [Paragraph("<b>Report ID</b>", _column_style), Paragraph(session_id, _column_style)],
        [Paragraph("<b>Applicable Standard</b>", _column_style), Paragraph(_rule_display_name(ruleset), _column_style)],
        [Paragraph("<b>Unit System</b>", _column_style), Paragraph(unit_system.value.title(), _column_style)],
        [Paragraph("<b>Inspector</b>", _column_style), Paragraph("SiteCheck AI v2 — Auto-generated Report", _column_style)],
        [Paragraph("<b>Images Analysed</b>", _column_style), Paragraph(str(photo_count), _column_style)],
        [Paragraph("<b>Elements Found</b>", _column_style), Paragraph(total_str, _column_style)],
        [Paragraph("<b>SQI</b>", _column_style), Paragraph(f"{compliance.sqi:.0f}/100 — {_sqi_label(compliance.sqi)}", _column_style)],
        [Paragraph("<b>Confidence Score</b>", _column_style), Paragraph(f"{compliance.confidence_score:.0f}%", _column_style)],
        [Paragraph("<b>Generated</b>", _column_style), Paragraph(ts, _column_style)],
    ]
    pt = Table(rows, colWidths=[4.5 * cm, 10.5 * cm])
    pcmds = [
        ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]
    pt.setStyle(TableStyle(pcmds))
    story.append(pt)
    story.append(PageBreak())


# ── Pages 4-6: Element Findings (card-style) ───────────────────


def _findings_card(el: ElementResult) -> list:
    elements = []
    elements.append(Spacer(1, 0.15 * cm))

    # Card header
    status_color = {
        ElementStatus.PASS: "#e8f5e9",
        ElementStatus.WARNING: "#fff8e1",
        ElementStatus.FAIL: "#ffebee",
        ElementStatus.INCONCLUSIVE: "#f5f5f5",
    }.get(el.status, "#ffffff")
    border_color = {
        ElementStatus.PASS: "#2e7d32",
        ElementStatus.WARNING: "#f57f17",
        ElementStatus.FAIL: "#c62828",
        ElementStatus.INCONCLUSIVE: "#757575",
    }.get(el.status, "#212121")

    # Confidence indicator
    conf_pct = el.confidence_score
    conf_label = f"Conf: {conf_pct:.0f}%"
    conf_color = PASS_COLOR if conf_pct >= 80 else WARN_COLOR if conf_pct >= 50 else FAIL_COLOR
    conf_style = ParagraphStyle("confbadge", fontSize=7, leading=9, textColor=conf_color)

    header_row = [
        Paragraph(f"<b>{el.element_id}</b>", ParagraphStyle("ch", fontSize=9, leading=11, textColor=DARK)),
        Paragraph(f"<b>{el.label}</b>", ParagraphStyle("cl", fontSize=9, leading=11, textColor=DARK)),
        _status_badge(el.status.value),
        Paragraph(conf_label, conf_style),
    ]
    header_table = Table([header_row], colWidths=[1.5 * cm, 5.5 * cm, 1.5 * cm, 1.5 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(status_color)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))

    # Measurements with context columns
    meas_rows = []
    meas_rows.append([Paragraph("<b>Parameter</b>", _column_style),
                      Paragraph("<b>Measured</b>", _column_style),
                      Paragraph("<b>Allowed</b>", _column_style),
                      Paragraph("<b>Deviation %</b>", _column_style),
                      Paragraph("<b>Severity</b>", _column_style)])

    dev_pct = f"{el.deviation_pct:.1f}%" if el.deviation_pct is not None else "—"
    meas_rows.append([
        Paragraph(el.measurements[0].name if el.measurements else "—", _column_style),
        Paragraph(f"{el.deviation:.2f} {el.unit}" if el.deviation is not None else "—", _column_style),
        Paragraph(el.allowed_value or "—", _column_style),
        Paragraph(dev_pct, _column_style),
        _severity_badge(el.severity),
    ])
    meas_table = Table(meas_rows, colWidths=[2.5 * cm, 2.5 * cm, 3.5 * cm, 2 * cm, 2 * cm])
    meas_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#37474f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd8dc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))

    # Engineer-friendly explanation
    interp = Paragraph(el.engineering_interpretation or "No interpretation available.", _body_style)

    # Recommendation
    rec = Paragraph(f"<b>Recommendation:</b> {el.recommendation or 'No action required.'}",
                    ParagraphStyle("rec", fontSize=8, leading=11, textColor=DARK, leftIndent=4))

    # Wrap everything in a bordered table
    card_data = [[header_table],
                 [Spacer(1, 0.1 * cm)],
                 [meas_table],
                 [Spacer(1, 0.15 * cm)],
                 [Paragraph("<b>Engineering Interpretation</b>", _subsection_style())],
                 [interp],
                 [Spacer(1, 0.1 * cm)],
                 [rec],
                 [Spacer(1, 0.1 * cm)]]
    card_table = Table(card_data, colWidths=[CONTENT_W])
    card_cmds = [
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(border_color)),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    card_table.setStyle(TableStyle(card_cmds))

    elements.append(card_table)
    elements.append(Spacer(1, 0.3 * cm))
    return elements


def _element_findings(story, compliance: ComplianceReport):
    story.append(Paragraph("Element Findings", _section_style()))
    story.append(Spacer(1, 0.1 * cm))
    story.append(Paragraph(
        "Detailed engineering assessment for each detected structural element. "
        "Each card shows measured values against code-allowed tolerances.",
        _body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    for el in compliance.elements:
        for item in _findings_card(el):
            story.append(item)

    story.append(PageBreak())


# ── Visual Evidence ────────────────────────────────────────────


def _visual_evidence(story, session_id: str, photos: list[PhotoResult]):
    story.append(Paragraph("Visual Evidence", _section_style()))
    story.append(Spacer(1, 0.1 * cm))
    story.append(Paragraph(
        "Annotated inspection images with detected element boundaries, "
        "status classification, and measurement overlays.",
        _body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    for idx, photo in enumerate(photos):
        photo_label = f"Image {idx + 1}: {photo.file_name}  ({len(photo.elements)} elements)"
        story.append(Paragraph(f"<b>{photo_label}</b>", _subsection_style()))

        if photo.quality_flags:
            for flag in photo.quality_flags:
                q_style = ParagraphStyle("qf", fontSize=8, leading=10, textColor=WARN_COLOR, leftIndent=10)
                story.append(Paragraph(f"⚠ {flag}", q_style))

        # Annotated overview image
        img_path = OUTPUTS_DIR / session_id / f"annotated_{idx:02d}.png"
        if img_path.exists():
            img = Image(str(img_path))
            aspect = img.drawHeight / float(img.drawWidth)
            img.drawWidth = CONTENT_W
            img.drawHeight = CONTENT_W * aspect
            if img.drawHeight > 14 * cm:
                img.drawHeight = 14 * cm
                img.drawWidth = 14 * cm / aspect
            story.append(Spacer(1, 0.15 * cm))
            story.append(img)
            story.append(Spacer(1, 0.25 * cm))

        # Per-element crop views for non-PASS elements
        non_pass = [el for el in photo.elements if el.status in {ElementStatus.WARNING, ElementStatus.FAIL}]
        if non_pass:
            story.append(Paragraph("<b>Element Close-ups</b>", _subsection_style()))
            for el in non_pass:
                el_label = f"{el.element_id} — {el.label} ({el.status.value})"
                story.append(Paragraph(f"<b>{el_label}</b>", ParagraphStyle("clup", fontSize=8, leading=10, textColor=DARK, leftIndent=6)))

                # Confidence indicator
                conf_pct = el.confidence_score
                conf_label = f"Confidence: {conf_pct:.0f}%"
                conf_color = PASS_COLOR if conf_pct >= 80 else WARN_COLOR if conf_pct >= 50 else FAIL_COLOR
                conf_style = ParagraphStyle("conf", fontSize=7, leading=9, textColor=conf_color, leftIndent=10)
                story.append(Paragraph(conf_label, conf_style))

                if el.measurements:
                    for m in el.measurements:
                        if m.details and "lines" in m.details:
                            evidence = m.evidence or []
                            for ev in evidence:
                                ev_style = ParagraphStyle("ev", fontSize=7, leading=9, textColor=INCONCLUSIVE_COLOR, leftIndent=12)
                                story.append(Paragraph(f"• {ev}", ev_style))
                story.append(Spacer(1, 0.1 * cm))
            story.append(Spacer(1, 0.2 * cm))

        if idx < len(photos) - 1:
            story.append(Spacer(1, 0.3 * cm))

    story.append(PageBreak())


# ── Compliance Matrix ──────────────────────────────────────────


def _compliance_matrix(story, compliance: ComplianceReport):
    story.append(Paragraph("Compliance Matrix", _section_style()))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Summary of compliance status by structural check category.",
        _body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # Build category breakdown
    cat_map: dict[str, dict[str, int]] = {}
    for el in compliance.elements:
        check_type = "Unknown"
        for m in el.measurements:
            if "plumb" in m.name or "offset" in m.name:
                check_type = "Wall Plumb"
            elif "level" in m.name:
                check_type = "Beam Level"
            elif "gap" in m.name or "asymmetry" in m.name:
                check_type = "Door Alignment"
            elif "spacing" in m.name:
                check_type = "Rebar Spacing"
        cat = cat_map.setdefault(check_type, {"total": 0, "pass": 0, "warn": 0, "fail": 0, "inconc": 0})
        cat["total"] += 1
        cat[el.status.value.lower()[:5]] = cat.get(el.status.value.lower()[:5], 0) + 1

    hdr = ParagraphStyle("cmh", fontSize=8, leading=10, textColor=colors.white, alignment=TA_CENTER)
    cell = ParagraphStyle("cmc", fontSize=8, leading=10, textColor=DARK, alignment=TA_CENTER)

    matrix_data = [[Paragraph("Check Type", hdr), Paragraph("Total", hdr),
                    Paragraph("✅ Pass", hdr), Paragraph("⚠ Warn", hdr),
                    Paragraph("❌ Fail", hdr), Paragraph("Compliance %", hdr)]]

    for cat_name in ["Wall Plumb", "Beam Level", "Door Alignment", "Rebar Spacing"]:
        c = cat_map.get(cat_name, {"total": 0, "pass": 0, "warn": 0, "fail": 0, "inconc": 0})
        total_c = c["total"]
        if total_c == 0:
            continue
        pass_c = c["pass"]
        compliance_pct = f"{pass_c / total_c * 100:.0f}%" if total_c else "—"
        matrix_data.append([
            Paragraph(cat_name, cell),
            Paragraph(str(total_c), cell),
            Paragraph(str(c["pass"]), cell),
            Paragraph(str(c["warn"]), cell),
            Paragraph(str(c["fail"]), cell),
            Paragraph(compliance_pct, cell),
        ])

    # Totals row
    t_pass = sum(c["pass"] for c in cat_map.values())
    t_warn = sum(c["warn"] for c in cat_map.values())
    t_fail = sum(c["fail"] for c in cat_map.values())
    t_total = sum(c["total"] for c in cat_map.values())
    total_compliance = f"{t_pass / t_total * 100:.0f}%" if t_total else "—"
    bold_cell = ParagraphStyle("cmcb", fontSize=8, leading=10, textColor=DARK, alignment=TA_CENTER)
    matrix_data.append([
        Paragraph("<b>Total</b>", bold_cell),
        Paragraph(f"<b>{t_total}</b>", bold_cell),
        Paragraph(f"<b>{t_pass}</b>", bold_cell),
        Paragraph(f"<b>{t_warn}</b>", bold_cell),
        Paragraph(f"<b>{t_fail}</b>", bold_cell),
        Paragraph(f"<b>{total_compliance}</b>", bold_cell),
    ])

    mt = Table(matrix_data, colWidths=[3.5 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 2.5 * cm], repeatRows=1)
    mcmds = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8eaf6")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(matrix_data) - 1):
        mcmds.append(("BACKGROUND", (0, i), (-1, i), BG_LIGHT if i % 2 == 0 else colors.white))
    mt.setStyle(TableStyle(mcmds))
    story.append(mt)

    # Compliance rate bars per category
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("<b>Compliance Rate by Category</b>", _subsection_style()))
    for cat_name in ["Wall Plumb", "Beam Level", "Door Alignment", "Rebar Spacing"]:
        c = cat_map.get(cat_name)
        if c is None or c["total"] == 0:
            continue
        rate = c["pass"] / c["total"] * 100
        bar_width = CONTENT_W * 0.6
        min_bar = 0.5 * cm
        fill_w = max(bar_width * rate / 100, min_bar)
        rest_w = max(bar_width - fill_w, min_bar)
        if fill_w + rest_w > bar_width:
            scale = bar_width / (fill_w + rest_w)
            fill_w *= scale
            rest_w *= scale
        color = PASS_COLOR if rate >= 85 else WARN_COLOR if rate >= 50 else FAIL_COLOR
        label = ParagraphStyle("crl", fontSize=7, leading=9, textColor=DARK)
        bar_cell = [[Paragraph("", _empty_style)]]
        empty_cell = [[Paragraph("", _empty_style)]]
        bar_table = Table([bar_cell + empty_cell],
                          colWidths=[fill_w, rest_w],
                          rowHeights=[0.5 * cm])
        bar_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), color),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e0e0e0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        row = [
            Paragraph(cat_name, label),
            bar_table,
            Paragraph(f"{rate:.0f}%", label),
        ]
        rt = Table([row], colWidths=[3 * cm, bar_width, 2 * cm])
        rt.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 4),
            ("RIGHTPADDING", (-1, -1), (-1, -1), 4),
        ]))
        story.append(rt)
        story.append(Spacer(1, 0.1 * cm))

    story.append(PageBreak())


# ── Recommendations ────────────────────────────────────────────


def _recommendations(story, compliance: ComplianceReport):
    story.append(Paragraph("Recommendations & Remedial Actions", _section_style()))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Grouped recommendations based on element severity and status.",
        _body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    fails = [el for el in compliance.elements if el.status == ElementStatus.FAIL]
    warnings = [el for el in compliance.elements if el.status == ElementStatus.WARNING]
    passes = [el for el in compliance.elements if el.status == ElementStatus.PASS]

    # Immediate Action
    story.append(Paragraph(
        f"<font color='{FAIL_COLOR.hexval()}'>■ Immediate Action ({len(fails)})</font>",
        _subsection_style(),
    ))
    if fails:
        for el in fails:
            box_data = [
                [Paragraph(f"<b>{el.element_id}</b> — {el.label}",
                           ParagraphStyle("ri", fontSize=9, leading=12, textColor=FAIL_COLOR))],
                [Paragraph(el.recommendation or "Requires structural review.",
                           ParagraphStyle("rb", fontSize=8, leading=11, textColor=DARK))],
            ]
            box = Table(box_data, colWidths=[CONTENT_W - 0.5 * cm])
            box.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.8, FAIL_COLOR),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffebee")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(box)
            story.append(Spacer(1, 0.15 * cm))
    else:
        story.append(Paragraph("No immediate action required.", _body_style))

    story.append(Spacer(1, 0.3 * cm))

    # Monitor
    story.append(Paragraph(
        f"<font color='{WARN_COLOR.hexval()}'>▲ Monitor ({len(warnings)})</font>",
        _subsection_style(),
    ))
    if warnings:
        for el in warnings:
            box_data = [
                [Paragraph(f"<b>{el.element_id}</b> — {el.label}",
                           ParagraphStyle("wi9", fontSize=9, leading=12, textColor=WARN_COLOR))],
                [Paragraph(el.recommendation or "Monitor during next inspection cycle.",
                           ParagraphStyle("wb8", fontSize=8, leading=11, textColor=DARK))],
            ]
            box = Table(box_data, colWidths=[CONTENT_W - 0.5 * cm])
            box.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.8, WARN_COLOR),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff8e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(box)
            story.append(Spacer(1, 0.15 * cm))
    else:
        story.append(Paragraph("No items requiring monitoring.", _body_style))

    story.append(Spacer(1, 0.3 * cm))

    # Acceptable
    story.append(Paragraph(
        f"<font color='{PASS_COLOR.hexval()}'>● Acceptable ({len(passes)})</font>",
        _subsection_style(),
    ))
    story.append(Paragraph(
        f"{len(passes)} element{'s' if len(passes) != 1 else ''} passed all checks. No action required.",
        _body_style,
    ))
    story.append(Spacer(1, 1.5 * cm))

    # Disclaimer
    disc_style = ParagraphStyle(
        "disc",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#9e9e9e"),
        backColor=BG_LIGHT,
        borderPadding=8,
        alignment=TA_LEFT,
    )
    story.append(Table(
        [[Paragraph(
            "<b>Disclaimer</b><br/>"
            "This report is generated by SiteCheck AI for preliminary assessment purposes only. "
            "Measurements are computed from pixel-level geometry analysis and may not reflect "
            "actual field conditions. Values shown without scale calibration reference are marked "
            "as inconclusive. This report does not substitute for a professional structural "
            "engineer's evaluation.",
            disc_style,
        )]],
        colWidths=[CONTENT_W],
    ))


# ── Appendix: Methodology ──────────────────────────────────────


def _methodology(story, ruleset: Ruleset):
    story.append(Paragraph("Appendix: Methodology & Measurement Notes", _section_style()))
    story.append(Spacer(1, 0.3 * cm))

    rows = [
        [Paragraph("<b>Parameter</b>", _column_style), Paragraph("<b>Value</b>", _column_style)],
        [Paragraph("Detection Method", _column_style), Paragraph("YOLOv8n (heuristic fallback active)", _column_style)],
        [Paragraph("Geometric Analysis", _column_style), Paragraph("HoughLinesP + Sobel gradient tracking", _column_style)],
        [Paragraph("Scale Calibration", _column_style), Paragraph("Reference door width (900 mm) / Plan-based", _column_style)],
        [Paragraph("Confidence Scoring", _column_style), Paragraph("Edge count, inlier ratio, regression residuals", _column_style)],
        [Paragraph("Applicable Standard", _column_style), Paragraph(_rule_display_name(ruleset), _column_style)],
    ]

    mt = Table(rows, colWidths=[5 * cm, 10 * cm])
    mcmds = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]
    for i in range(1, len(rows)):
        mcmds.append(("BACKGROUND", (0, i), (-1, i), BG_LIGHT if i % 2 == 0 else colors.white))
    mt.setStyle(TableStyle(mcmds))
    story.append(mt)
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("<b>Measurement Uncertainty</b>", _subsection_style()))
    uncertainties = [
        "HoughLinesP angular quantization: ~1°",
        "Sub-pixel refinement via parabolic interpolation (Sobel gradient)",
        "Outlier rejection via robust regression (3 iterations, 2σ threshold)",
        "Confidence score accounts for edge count, inlier ratio, and residual std dev",
    ]
    for u in uncertainties:
        story.append(Paragraph(f"• {u}", _body_style))


# ── Plan vs Actual section ─────────────────────────────────────


def _plan_vs_actual(story, plan_comparison: dict[str, Any]):
    story.append(PageBreak())
    story.append(Paragraph("Plan vs Actual Compliance", _section_style()))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Comparison of expected dimensions from the structural drawing "
        "against measured values from site photographs.",
        _body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    comparisons = plan_comparison.get("comparisons", [])
    summary = plan_comparison.get("summary", {})

    # Summary stats
    hdr = ParagraphStyle("pvh", fontSize=8, leading=10, textColor=colors.white, alignment=TA_CENTER)
    cell = ParagraphStyle("pvc", fontSize=8, leading=10, textColor=DARK, alignment=TA_CENTER)

    stat_data = [
        [Paragraph("Metric", hdr), Paragraph("Value", hdr)],
        [Paragraph("Total Comparisons", cell), Paragraph(str(summary.get("total", 0)), cell)],
        [Paragraph("✅ Pass", cell), Paragraph(str(summary.get("passed", 0)), cell)],
        [Paragraph("⚠ Warning", cell), Paragraph(str(summary.get("warning", 0)), cell)],
        [Paragraph("❌ Fail", cell), Paragraph(str(summary.get("fail", 0)), cell)],
        [Paragraph("Compliance %", cell), Paragraph(f"{summary.get('compliance_pct', 0):.0f}%", cell)],
    ]
    st = Table(stat_data, colWidths=[5 * cm, 5 * cm])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(st)
    story.append(Spacer(1, 0.4 * cm))

    if not comparisons:
        story.append(Paragraph("No comparable dimensions found between drawing and site measurements.",
                                _body_style))
        return

    # Details table
    col_headers = [Paragraph("Element", hdr), Paragraph("Expected", hdr),
                   Paragraph("Actual", hdr), Paragraph("Deviation", hdr),
                   Paragraph("Dev %", hdr), Paragraph("Status", hdr)]

    det_style = ParagraphStyle("pvd", fontSize=7, leading=9, textColor=DARK, alignment=TA_CENTER)
    det_style_pct = ParagraphStyle("pvdp", fontSize=7, leading=9, textColor=DARK, alignment=TA_CENTER)
    table_data = [col_headers]

    for c in comparisons:
        dev_color = PASS_COLOR if c["status"] == "PASS" else WARN_COLOR if c["status"] == "WARNING" else FAIL_COLOR
        dev_pct_str = f"{c['deviation_pct']:.1f}%" if c['deviation_pct'] is not None else "—"
        table_data.append([
            Paragraph(c.get("element", "—"), det_style),
            Paragraph(f"{c['expected']:.0f} {c.get('unit', 'mm')}", det_style),
            Paragraph(f"{c['actual']:.1f} {c.get('unit', 'mm')}", det_style),
            Paragraph(f"{c['deviation_mm']:.1f} mm", det_style),
            Paragraph(dev_pct_str, det_style_pct),
            _status_badge(c["status"]),
        ])

    col_w = [2.2 * cm, 2.5 * cm, 2.5 * cm, 2.2 * cm, 1.8 * cm, 2 * cm]
    dt = Table(table_data, colWidths=col_w, repeatRows=1)
    dcmds = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(table_data)):
        dcmds.append(("BACKGROUND", (0, i), (-1, i), BG_LIGHT if i % 2 == 0 else colors.white))
    dt.setStyle(TableStyle(dcmds))
    story.append(dt)
    story.append(Spacer(1, 0.3 * cm))

    # By-category breakdown
    by_cat = plan_comparison.get("by_category", {})
    if by_cat:
        story.append(Paragraph("<b>Breakdown by Category</b>", _subsection_style()))
        cat_data = [[Paragraph("Category", hdr), Paragraph("Total", hdr),
                     Paragraph("Pass", hdr), Paragraph("Warn", hdr), Paragraph("Fail", hdr)]]
        for cat_name, counts in sorted(by_cat.items()):
            cat_data.append([
                Paragraph(cat_name.title(), cell),
                Paragraph(str(counts.get("total", 0)), cell),
                Paragraph(str(counts.get("pass", 0)), cell),
                Paragraph(str(counts.get("warning", 0)), cell),
                Paragraph(str(counts.get("fail", 0)), cell),
            ])
        ct = Table(cat_data, colWidths=[3 * cm, 2 * cm, 2 * cm, 2 * cm, 2 * cm], repeatRows=1)
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e0e0e0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(ct)


# ── Main entry point ───────────────────────────────────────────


def _compact_findings_table(story, compliance: ComplianceReport):
    """Compact single-page findings table instead of per-element cards."""
    story.append(Paragraph("Element Findings", _section_style()))
    story.append(Spacer(1, 0.15 * cm))

    hdr = ParagraphStyle("fh", fontSize=7, leading=9, textColor=colors.white, alignment=TA_CENTER)
    cell = ParagraphStyle("fc", fontSize=7, leading=9, textColor=DARK, alignment=TA_CENTER)

    rows = [[
        Paragraph("ID", hdr),
        Paragraph("Label", hdr),
        Paragraph("Status", hdr),
        Paragraph("Deviation", hdr),
        Paragraph("Severity", hdr),
        Paragraph("Confidence", hdr),
    ]]
    for el in compliance.elements[:40]:
        dev = f"{el.deviation:.1f} {el.unit}" if el.deviation is not None else "—"
        conf = f"{el.confidence_score:.0f}%"
        rows.append([
            Paragraph(el.element_id, cell),
            Paragraph(el.label, cell),
            Paragraph(el.status.value, cell),
            Paragraph(dev, cell),
            Paragraph(el.severity, cell),
            Paragraph(conf, cell),
        ])
    if len(compliance.elements) > 40:
        rows.append([
            Paragraph(f"... +{len(compliance.elements) - 40} more", cell),
            Paragraph("", cell), Paragraph("", cell), Paragraph("", cell),
            Paragraph("", cell), Paragraph("", cell),
        ])

    t = Table(rows, colWidths=[1.2 * cm, 1.8 * cm, 1.8 * cm, 2.5 * cm, 1.5 * cm, 1.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * cm))

    # Legend for non-PASS elements
    non_pass = [el for el in compliance.elements if el.status != ElementStatus.PASS]
    if non_pass:
        story.append(Paragraph("<b>Issues Requiring Attention:</b>", _subsection_style()))
        for el in non_pass[:10]:
            icon = "⚠" if el.status == ElementStatus.WARNING else "❌"
            story.append(Paragraph(
                f"{icon} <b>{el.element_id}</b> — {el.label}: {el.message}",
                ParagraphStyle("ni", fontSize=7, leading=10, textColor=DARK, leftIndent=6),
            ))
        if len(non_pass) > 10:
            story.append(Paragraph(
                f"... +{len(non_pass) - 10} more issues",
                ParagraphStyle("nm", fontSize=7, leading=9, textColor=colors.gray, leftIndent=6),
            ))


def _compact_recommendations(story, compliance: ComplianceReport):
    """Single-page recommendations section."""
    story.append(Paragraph("Recommendations", _section_style()))
    story.append(Spacer(1, 0.15 * cm))

    immediate = [el for el in compliance.elements if el.status == ElementStatus.FAIL]
    monitor = [el for el in compliance.elements if el.status == ElementStatus.WARNING]

    if immediate:
        story.append(Paragraph("<b>Immediate Action Required</b>", _subsection_style()))
        for el in immediate[:5]:
            rec = el.recommendation or "Review and take corrective action."
            story.append(Paragraph(
                f"❌ <b>{el.element_id}</b> ({el.label}): {rec}",
                ParagraphStyle("ir", fontSize=8, leading=11, textColor=FAIL_COLOR, leftIndent=6, spaceAfter=3),
            ))
        if len(immediate) > 5:
            story.append(Paragraph(f"... +{len(immediate) - 5} more", _body_style))

    if monitor:
        story.append(Paragraph("<b>Monitor</b>", _subsection_style()))
        for el in monitor[:5]:
            rec = el.recommendation or "Monitor during construction."
            story.append(Paragraph(
                f"⚠ <b>{el.element_id}</b> ({el.label}): {rec}",
                ParagraphStyle("mr", fontSize=8, leading=11, textColor=WARN_COLOR, leftIndent=6, spaceAfter=3),
            ))
        if len(monitor) > 5:
            story.append(Paragraph(f"... +{len(monitor) - 5} more", _body_style))

    if not immediate and not monitor:
        story.append(Paragraph("No corrective actions required.", _body_style))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("<b>Methodology</b>", _subsection_style()))
    story.append(Paragraph(
        "This report was generated using SiteCheck AI computer vision analysis. "
        "Detection is performed via OpenCV edge analysis and geometric measurement. "
        "Compliance is evaluated against the selected building code ruleset. "
        "All measurements should be verified by a qualified structural engineer.",
        ParagraphStyle("meth", fontSize=7, leading=10, textColor=DARK, leftIndent=4),
    ))


def generate_inspection_pdf(
    *,
    session_id: str,
    compliance: ComplianceReport,
    photos: list[PhotoResult],
    ruleset: Ruleset,
    unit_system: UnitSystem,
    output_path: Path,
    project_name: str = "Untitled Project",
    inspection_date: str = "",
    photo_count: int = 0,
    element_counts: dict[str, int] | None = None,
    plan_comparison: Optional[dict[str, Any]] = None,
    coverage_pct: float = 0.0,
    measurement_confidence: float = 0.0,
    low_confidence: bool = False,
    scene_type: str = "",
    scene_confidence: float = 0.0,
) -> bytes:
    """Build V3 professional engineering inspection PDF (max 10 pages)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=MARGIN, leftMargin=MARGIN,
        topMargin=2.4 * cm, bottomMargin=2 * cm,
    )
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    hf = _HeaderFooter(session_id, ts)

    if not inspection_date:
        inspection_date = datetime.now().strftime("%Y-%m-%d")
    ec = element_counts or {}
    total_elements = len(compliance.elements)
    is_unsupported = scene_type not in ("construction_site", "structural_frame", "")

    story = []

    # Page 1: Cover
    _cover_page(story, session_id, ts, ruleset, unit_system,
                compliance.sqi, compliance.confidence_score,
                project_name, inspection_date,
                photo_count, ec, total_elements,
                scene_type=scene_type)
    story.append(PageBreak())

    # ── Unsupported scene: compliance NOT performed ──
    if is_unsupported:
        story.append(Paragraph("Inspection Status", _section_style()))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(
            f"<font color='{FAIL_COLOR.hexval()}'><b>UNSUPPORTED SCENE</b></font>",
            ParagraphStyle("us1", fontSize=14, leading=18, alignment=TA_CENTER, spaceAfter=6),
        ))
        status_data = [
            ["Scene Type", scene_type.replace("_", " ").title()],
            ["Scene Confidence", f"{scene_confidence * 100:.0f}%"],
            ["Compliance Assessment", "<font color='#c62828'><b>NOT PERFORMED</b></font>"],
            ["Reason", "Image unsuitable for structural compliance inspection."],
        ]
        st = Table(status_data, colWidths=[4 * cm, 10 * cm])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e0e0e0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(st)
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            "⚠ Structural Compliance Index (SQI) and FAIL/WARNING/PASS "
            "verdicts are <b>not applicable</b> for this inspection. "
            "No detection, measurement, or compliance analysis was performed.",
            ParagraphStyle("us2", fontSize=9, leading=13, textColor=DARK, leftIndent=4),
        ))
        if photos:
            story.append(PageBreak())
            _visual_evidence(story, session_id, photos)
        doc.build(story, onFirstPage=hf.header, onLaterPages=lambda c, d: (hf.header(c, d), hf.footer(c, d)))
        pdf_bytes = buffer.getvalue()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
        return pdf_bytes

    # ── Low confidence: warning with scene info ──
    if low_confidence:
        story.append(Paragraph("Inspection Status", _section_style()))
        story.append(Spacer(1, 0.15 * cm))
        lp = ParagraphStyle("lcp", fontSize=9, leading=13, textColor=DARK, leftIndent=4, spaceAfter=4)
        status_rows = [
            ["Status", "<font color='#f57f17'><b>LOW CONFIDENCE</b></font>"],
            ["Scene Type", scene_type.replace("_", " ").title() if scene_type else "—"],
            ["Compliance Assessment", "<font color='#f57f17'><b>NOT PERFORMED</b></font>"],
            ["Reason", "Excessive detections — scene too complex or insufficient quality."],
        ]
        st = Table(status_rows, colWidths=[4 * cm, 10 * cm])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e0e0e0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(st)
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            "Results shown below are <b>for reference only</b> and should not "
            "be used for compliance decisions. Retake photos ensuring structural "
            "elements fill the frame.",
            lp,
        ))
        if photos:
            story.append(PageBreak())
            _visual_evidence(story, session_id, photos)
        doc.build(story, onFirstPage=hf.header, onLaterPages=lambda c, d: (hf.header(c, d), hf.footer(c, d)))
        pdf_bytes = buffer.getvalue()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
        return pdf_bytes

    # ── Normal report: 6-page layout ──
    story.append(PageBreak())
    _executive_dashboard(story, compliance, coverage_pct, measurement_confidence)
    story.append(PageBreak())
    _project_information(story, session_id, ts, ruleset, unit_system,
                         project_name, inspection_date,
                         photo_count, ec, total_elements, compliance)
    story.append(PageBreak())
    _compact_findings_table(story, compliance)
    if photos:
        story.append(PageBreak())
        _visual_evidence(story, session_id, photos)
    story.append(PageBreak())
    _compact_recommendations(story, compliance)

    doc.build(story, onFirstPage=hf.header, onLaterPages=lambda c, d: (hf.header(c, d), hf.footer(c, d)))
    pdf_bytes = buffer.getvalue()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)
    return pdf_bytes
