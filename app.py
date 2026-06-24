"""Streamlit MVP for construction image upload + basic CV analysis previews."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import cv2
import streamlit as st

from src.logic.scoring import calculate_compliance_score
from src.logic.rules import run_rule_checks
from src.reporting.report_generator import (
    findings_as_dicts,
    generate_inspection_summary,
    generate_pdf_report_bytes,
)
from src.vision.preprocess import (
    crop_percent_margins,
    load_image,
    ndarray_to_png_bytes,
    resize_image_keep_aspect,
    to_grayscale,
    to_rgb_array,
)
from src.vision.feature_extract import (
    bgr_to_rgb,
    compute_edges,
    detect_lines_hough,
    pil_rgb_to_bgr,
    summarize_line_orientations,
)


def _element_guess_short(orientation_guess: str) -> str:
    if "Column-like" in orientation_guess:
        return "Column-like"
    if "Beam-like" in orientation_guess:
        return "Beam-like"
    return "Unknown"


def _safe_filename_component(name: str) -> str:
    base = Path(name).name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:80] or "image"


st.set_page_config(page_title="SiteCheck-AI MVP", layout="wide")

st.title("SiteCheck-AI: Beam and Column Fabrication Verifier")
st.write(
    "Upload one construction image to preview it and view basic details. "
    "This version also shows basic computer vision analysis previews (edges and line detection)."
)

with st.sidebar:
    st.header("Processing Settings")
    max_width = st.slider("Resize max width (px)", min_value=400, max_value=1800, value=960, step=40)
    blur_ksize = st.slider("Blur kernel size", min_value=0, max_value=15, value=5, step=1)
    canny_low = st.slider("Canny low threshold", min_value=0, max_value=250, value=50, step=5)
    canny_high = st.slider("Canny high threshold", min_value=0, max_value=500, value=150, step=5)
    hough_threshold = st.slider("Hough threshold", min_value=10, max_value=250, value=80, step=5)
    min_line_length = st.slider("Min line length", min_value=5, max_value=400, value=40, step=5)
    max_line_gap = st.slider("Max line gap", min_value=0, max_value=80, value=10, step=1)
    vertical_tol = st.slider("Vertical tolerance (deg)", min_value=5, max_value=45, value=20, step=1)
    horizontal_tol = st.slider("Horizontal tolerance (deg)", min_value=5, max_value=45, value=20, step=1)

    st.divider()
    st.subheader("Crop / Focus")
    crop_margins = st.checkbox("Crop margins (recommended)", value=False)
    crop_left = crop_right = crop_top = crop_bottom = 0
    if crop_margins:
        crop_left = st.slider("Crop left (%)", 0, 40, 0, 1)
        crop_right = st.slider("Crop right (%)", 0, 40, 0, 1)
        crop_top = st.slider("Crop top (%)", 0, 40, 0, 1)
        crop_bottom = st.slider("Crop bottom (%)", 0, 40, 0, 1)

    st.divider()
    save_outputs = st.checkbox("Save outputs to reports/", value=False)

uploaded_file = st.file_uploader(
    "Upload an image",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=False,
)

if uploaded_file is None:
    st.info("Please upload one JPG or PNG image to begin.")
else:
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    image = load_image(uploaded_file)
    resized_image = resize_image_keep_aspect(image, max_width=max_width)

    if crop_margins:
        analysis_image = crop_percent_margins(
            resized_image,
            left_pct=float(crop_left),
            right_pct=float(crop_right),
            top_pct=float(crop_top),
            bottom_pct=float(crop_bottom),
        )
    else:
        analysis_image = resized_image

    grayscale_preview = to_grayscale(analysis_image)

    st.success("Image uploaded successfully.")

    st.subheader("Original (resized)")
    if crop_margins:
        c_orig, c_crop = st.columns(2)
        with c_orig:
            st.image(resized_image, caption="Before crop", use_container_width=True)
        with c_crop:
            st.image(
                analysis_image,
                caption="Cropped region used for edges / lines / scoring",
                use_container_width=True,
            )
    else:
        st.image(resized_image, caption="Uploaded image preview", use_container_width=True)

    st.subheader("Image Details")
    st.write(f"**File name:** {uploaded_file.name}")
    st.write(
        f"**Analysis region:** {analysis_image.width} x {analysis_image.height} pixels "
        f"(resized base: {resized_image.width} x {resized_image.height})"
    )

    st.subheader("Preprocessing Preview")
    rgb = to_rgb_array(analysis_image)
    bgr = pil_rgb_to_bgr(rgb)

    # Keep thresholds valid even if the user sets them oddly.
    canny_high = max(int(canny_high), int(canny_low) + 1)
    edges = compute_edges(
        bgr,
        blur_ksize=int(blur_ksize),
        canny_low=int(canny_low),
        canny_high=int(canny_high),
    )
    line_result = detect_lines_hough(
        bgr,
        edges,
        threshold=int(hough_threshold),
        min_line_length=int(min_line_length),
        max_line_gap=int(max_line_gap),
    )
    overlay_rgb = bgr_to_rgb(line_result.line_overlay_bgr)

    col1, col2 = st.columns(2)
    with col1:
        st.image(grayscale_preview, caption="Grayscale", use_container_width=True)
    with col2:
        st.image(edges, caption="Edges (Canny)", use_container_width=True)

    st.subheader("Line Detection Overlay")
    st.image(overlay_rgb, caption="Hough line segments overlay", use_container_width=True)

    orientation = summarize_line_orientations(
        line_result.lines,
        vertical_tol_deg=float(vertical_tol),
        horizontal_tol_deg=float(horizontal_tol),
    )

    st.subheader("Results")
    findings, metrics = run_rule_checks(
        width=analysis_image.width,
        height=analysis_image.height,
        edges=edges,
        lines=line_result.lines,
        orientation=orientation,
        vertical_tol_deg=float(vertical_tol),
        horizontal_tol_deg=float(horizontal_tol),
    )

    score_result = calculate_compliance_score(findings=findings)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Score", f"{score_result['score']}/100")
    m2.metric("Status", score_result["status"])
    m3.metric("Element guess", _element_guess_short(orientation.guess))
    edge_density = float(metrics.get("edge_density", 0.0))
    m4.metric("Edge density", f"{edge_density * 100:.2f}%")
    m5.metric("Line count", int(metrics.get("num_lines", orientation.num_lines)))

    with st.expander("Orientation & detection details", expanded=False):
        st.caption(
            f"Lines: {orientation.num_lines} | "
            f"Vertical: {orientation.vertical_count} | "
            f"Horizontal: {orientation.horizontal_count} | "
            f"Other: {orientation.other_count} | "
            f"Guess: {orientation.guess}"
        )

    if findings:
        st.markdown("**Findings**")
        for f in findings:
            st.markdown(f"- **{f.severity.upper()}**: {f.title}  \n  {f.message}")
    else:
        st.info("No rule-based issues detected (preliminary).")

    summary_text = generate_inspection_summary(
        file_name=uploaded_file.name,
        score=score_result["score"],
        status=score_result["status"],
        findings=findings,
        metrics=metrics,
    )
    pdf_bytes = generate_pdf_report_bytes(summary_text, title="SiteCheck-AI Report")
    edges_png_bytes = ndarray_to_png_bytes(edges)
    overlay_png_bytes = ndarray_to_png_bytes(overlay_rgb)

    with st.expander("Debug tables & full report text", expanded=False):
        st.markdown("**Findings table**")
        st.dataframe(findings_as_dicts(findings), use_container_width=True)
        st.markdown("**Metrics**")
        st.write(metrics)
        st.text_area("Inspection report (text)", summary_text, height=240)

    st.subheader("Downloads")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.download_button(
            label="Report (TXT)",
            data=summary_text,
            file_name="sitecheck_ai_report.txt",
            mime="text/plain",
            use_container_width=True,
            key="dl_txt",
        )
    with d2:
        st.download_button(
            label="Report (PDF)",
            data=pdf_bytes,
            file_name="sitecheck_ai_report.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="dl_pdf",
        )
    with d3:
        st.download_button(
            label="Edges (PNG)",
            data=edges_png_bytes,
            file_name="sitecheck_ai_edges.png",
            mime="image/png",
            use_container_width=True,
            key="dl_edges",
        )
    with d4:
        st.download_button(
            label="Overlay (PNG)",
            data=overlay_png_bytes,
            file_name="sitecheck_ai_overlay.png",
            mime="image/png",
            use_container_width=True,
            key="dl_overlay",
        )

    if save_outputs:
        reports_root = Path("reports")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = reports_root / f"run_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)

        stem = _safe_filename_component(uploaded_file.name)
        overlay_path = run_dir / f"{stem}_overlay.png"
        edges_path = run_dir / f"{stem}_edges.png"
        txt_path = run_dir / f"{stem}_report.txt"
        pdf_path = run_dir / f"{stem}_report.pdf"

        cv2.imwrite(str(edges_path), edges)
        cv2.imwrite(str(overlay_path), line_result.line_overlay_bgr)
        txt_path.write_text(summary_text, encoding="utf-8")
        pdf_path.write_bytes(pdf_bytes)

        saved_names = [overlay_path.name, edges_path.name, txt_path.name, pdf_path.name]
        st.success(f"Saved to `{run_dir}`")
        st.caption("Files: " + ", ".join(saved_names))
