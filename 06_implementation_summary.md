# SiteCheck-AI (MVP) — Implementation Summary + Core Logic

This document summarizes what is implemented in the current MVP, how the code is structured, and the exact core logic used to generate results (score + findings + report).

---

## 1) What is implemented (current MVP)

- A Streamlit web app to upload **one** construction-site image (beam/column fabrication stage).
- Resizing + optional cropping to focus on the region of interest.
- Computer vision previews:
  - grayscale preview
  - Canny edges preview
  - Hough line-segment detection + overlay image
- Explainable rule-based inspection:
  - basic element-type guess (beam-like vs column-like) from line orientations
  - basic alignment / tilt check
  - basic spacing-regularity check
  - basic image-signal checks (too blurry/dark vs too cluttered)
- A simple compliance score (0–100) + readable status text.
- Report generation:
  - plain-text summary
  - PDF export
  - downloads for report + intermediate images (edges/overlay)
  - optional saving of outputs into `reports/run_<timestamp>/`

---

## 2) Code structure (modules + responsibilities)

- `app.py`: Streamlit UI + full pipeline orchestration (calls into `src/...` and renders outputs).
- `src/vision/preprocess.py`: image I/O + resizing/cropping + PNG conversion helpers.
- `src/vision/feature_extract.py`: edges (Canny), line detection (HoughLinesP), and orientation summary.
- `src/logic/rules.py`: explainable rule checks that output `Finding` objects + numeric metrics.
- `src/logic/scoring.py`: converts findings into score/status.
- `src/reporting/report_generator.py`: builds report text + PDF bytes from summary text.

---

## 3) End-to-end pipeline (what happens after upload)

High-level flow (what you can say in a demo):

1. User uploads an image (JPG/PNG).
2. We correct orientation (phone EXIF), resize it, and optionally crop margins.
3. Convert image to OpenCV format (BGR).
4. Compute edges using Canny.
5. Detect straight line segments using probabilistic Hough transform.
6. Summarize whether lines are mostly vertical or horizontal (beam-like vs column-like guess).
7. Run rule checks to produce **findings** (explainable warnings) + **metrics** (numbers we show).
8. Convert findings → score (0–100) + status text.
9. Generate a text report + PDF, and allow downloads / saving.

Pseudo-code:

```text
image = load_image(upload)
image = resize_image_keep_aspect(image)
image = crop_percent_margins(image)  # optional

bgr   = pil_rgb_to_bgr(to_rgb_array(image))
edges = compute_edges(bgr, blur, canny_low, canny_high)
lines = detect_lines_hough(bgr, edges, hough_params)
orientation = summarize_line_orientations(lines, vertical_tol, horizontal_tol)

findings, metrics = run_rule_checks(edges, lines, orientation, image_size, tolerances)
score_result = calculate_compliance_score(findings)

summary_text = generate_inspection_summary(file_name, score_result, findings, metrics)
pdf_bytes = generate_pdf_report_bytes(summary_text)
```

---

## 4) Core logic details (what each step actually does)

### A) Preprocessing (`src/vision/preprocess.py`)

- `load_image(uploaded_file)`
  - rewinds the stream (`seek(0)`) to avoid Streamlit rerun issues
  - loads via PIL + applies `ImageOps.exif_transpose()` to correct phone-camera rotation
- `resize_image_keep_aspect(image, max_width)`
  - if `image.width > max_width`, resize to `max_width` while preserving aspect ratio
  - uses LANCZOS resampling for better quality
- `crop_percent_margins(image, left_pct, right_pct, top_pct, bottom_pct)` (optional)
  - removes margins as percentages (clamped to 0–40%)
  - ensures at least 1 pixel remains in width/height

### B) Edge detection (`src/vision/feature_extract.py`)

- `compute_edges(bgr, blur_ksize, canny_low, canny_high)`
  - convert to grayscale
  - optional Gaussian blur (kernel auto-fixed to an odd number)
  - run Canny edge detection to get a binary edge map

### C) Line detection (`src/vision/feature_extract.py`)

- `detect_lines_hough(bgr, edges, threshold, min_line_length, max_line_gap)`
  - uses OpenCV `HoughLinesP` to detect **line segments**
  - draws all detected segments on a green overlay for explainability
  - returns:
    - `edges`
    - `line_overlay_bgr` (image with lines drawn)
    - `lines` array (or `None`)

### D) Beam-like vs Column-like guess (`src/vision/feature_extract.py`)

- `summarize_line_orientations(lines, vertical_tol_deg, horizontal_tol_deg)`
  - for each line segment `(x1,y1,x2,y2)`:
    - compute angle in degrees using `atan2(dy, dx)`
    - classify as:
      - **horizontal** if angle is near `0°` or `180°` (within `horizontal_tol_deg`)
      - **vertical** if angle is near `90°` (within `vertical_tol_deg`)
      - else **other**
  - compute ratios:
    - `vertical_ratio = vertical_count / total`
    - `horizontal_ratio = horizontal_count / total`
  - guess logic:
    - **Column-like** if `vertical_ratio` is dominant
    - **Beam-like** if `horizontal_ratio` is dominant
    - else **Unknown / Mixed**

This is intentionally explainable and meant for MVP demos (not perfect structural recognition).

---

## 5) Rule-based inspection (findings + metrics)

All rule checks are in `src/logic/rules.py` and return:

- `findings: list[Finding]` where a `Finding` has:
  - `code` (stable identifier)
  - `severity` (`info` | `minor` | `moderate` | `major`)
  - `title`, `message`
  - optional `details` (numbers used by the rule)
- `metrics: dict` (debug/explainability numbers shown in the UI)

### Rule 1: Image signal quality (edge density)

- Compute `edge_density = (# of edge pixels) / (width * height)`
- If `edge_density < 0.002` → `LOW_VISUAL_SIGNAL` (moderate)
  - Interpretation: photo may be blurry / too dark / too far.
- If `edge_density > 0.18` → `HIGH_NOISE_OR_CLUTTER` (minor)
  - Interpretation: background clutter or noise; cropping helps.

### Rule 2: Not enough detected lines

- If `orientation.num_lines < 15` → `TOO_FEW_LINES` (moderate)
  - Interpretation: can’t trust geometry checks if not enough segments are detected.

### Rule 3: Alignment / tilt (mean deviation)

Based on the chosen analysis mode:

- Choose `analysis_mode`:
  - if guess is **Column-like**, analyze **vertical**
  - if guess is **Beam-like**, analyze **horizontal**
  - otherwise choose whichever has more detected lines
- For the chosen family:
  - compute average angle deviation from perfect vertical/horizontal
  - if mean deviation > `12°`:
    - add `VERTICAL_MISALIGNMENT` or `HORIZONTAL_MISALIGNMENT`
    - severity becomes `major` if mean deviation > `18°`, else `moderate`

Important note for explanation: some tilt may come from camera angle; we call this “possible misalignment”.

### Rule 4: Spacing consistency (cluster + coefficient of variation)

Goal: estimate whether bar spacing looks regular.

- Take line midpoints:
  - vertical mode: use X midpoints (`vertical_x`)
  - horizontal mode: use Y midpoints (`horizontal_y`)
- Cluster positions so multiple segments on the same bar count once:
  - cluster tolerance:
    - `tol_px = max(6, 0.01 * image_width)` for vertical
    - `tol_px = max(6, 0.01 * image_height)` for horizontal
  - clustering returns a list of estimated “bar center” positions
- If there are enough clustered centers (>= 6):
  - compute adjacent gaps (`diff(centers_sorted)`)
  - compute `cv = std(gaps) / mean(gaps)` (coefficient of variation)
  - if `cv > 0.55` → irregular spacing finding:
    - `IRREGULAR_VERTICAL_SPACING` or `IRREGULAR_HORIZONTAL_SPACING` (moderate)

### Rule 5 (info): Mixed scene

- If there are many lines (>= 20) but neither family dominates:
  - add `MIXED_ORIENTATION` (info)
  - recommendation: crop to focus on a single element.

---

## 6) Scoring logic (0–100)

Implemented in `src/logic/scoring.py`:

- Start `score = 100`
- Deduct points by severity:
  - `minor`: -5
  - `moderate`: -12
  - `major`: -20
  - `info`: 0
- Clamp score to `[0, 100]`

Status text:

- If findings include `LOW_VISUAL_SIGNAL` or `TOO_FEW_LINES`:
  - `Preliminary: Low confidence (image signal too weak)`
- Else:
  - `>= 85`: `Preliminary: Looks OK`
  - `>= 70`: `Preliminary: Minor issues (review suggested)`
  - `>= 50`: `Preliminary: Needs review`
  - `< 50`: `Preliminary: High concern`

This is deliberately labeled “Preliminary” because it’s image-only and not a formal structural certification.

---

## 7) Reporting + outputs

Reporting is in `src/reporting/report_generator.py`:

- `generate_inspection_summary(...)` builds a plain-language text report including:
  - timestamp, file name, score, status
  - findings formatted as bullet lines
  - optional metrics section (compact numbers for explainability)
- `generate_pdf_report_bytes(summary_text)` renders the report to an A4 PDF using ReportLab.

In `app.py` the user can:

- download:
  - report as TXT
  - report as PDF
  - edges image (PNG)
  - overlay image (PNG)
- optionally save everything to:
  - `reports/run_<timestamp>/`

---

## 8) Limitations (what we should say clearly)

- This MVP uses simple heuristics; it does **not** measure real-world dimensions (no scale).
- “Beam-like” / “Column-like” is a best-effort guess from line orientations, not a guaranteed classifier.
- Tilt can be caused by the camera angle, not only by actual misalignment.
- Occlusions, clutter, and lighting can reduce line detection reliability.

---

## 9) How to run (demo)

From the project folder:

```bash
cd SiteCheck-AI
pip install -r requirements.txt
streamlit run app.py
```

