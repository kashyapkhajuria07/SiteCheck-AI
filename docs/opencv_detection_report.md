# OpenCV Detection Engine Report

## Overview

The OpenCV detection engine replaces the YOLO dependency for detecting structural
elements (walls, columns, beams, doors) in construction site photos and architectural
drawings. It uses only computer vision techniques — no ML model loading or GPU required.

## Architecture

```
backend/modules/opencv_detector.py
  ├── detect_elements(bgr)     → list[Detection]   # primary entry point
  ├── detect_walls(bgr)        → list[Detection]
  ├── detect_columns(bgr)      → list[Detection]
  ├── detect_beams(bgr)        → list[Detection]
  └── detect_doors(bgr)        → list[Detection]
```

Each function returns the same `Detection` schema (`schemas/inspection.py`) used by
`yolo_detector.py`, ensuring drop-in compatibility with the existing pipeline.

## Configuration

`backend/config.py`:
```python
DETECTION_MODE = "opencv"  # "yolo" | "opencv" | "hybrid"
```

| Mode    | Behaviour                                                      |
| ------- | -------------------------------------------------------------- |
| `yolo`  | Uses YOLOv8 (fine-tuned or COCO) exclusively                   |
| `opencv`| Uses OpenCV pipeline exclusively (default)                     |
| `hybrid`| Runs both; merges results, preferring OpenCV for missed labels |

## Per-Class Detection Algorithms

### Walls (`detect_walls`)

Three independent strategies whose results are fused via NMS:

1. **Horizontal line pairs** — Merges nearby horizontal HoughLinesP segments, then
   pairs those with consistent vertical spacing (wall thickness, 10 px to 30% of
   image height) and ≥50% x-overlap. Confidence scales with overlap.

2. **Vertical line pairs** — Same logic but for vertical lines: pairs with consistent
   horizontal spacing and ≥50% y-overlap.

3. **Rectangular contours** — Morphological close (9×9 ellipse, 2 iterations) then
   `RETR_LIST` contour detection. Filters by size (≥5% of image), aspect ratio
   (≤4:1), and area ratio (1%–70% of image).

*Limitations:* Very thin walls (<10px gap) are missed by the line-pair strategy.
Heavily occluded walls require contour detection which may produce false positives
from other rectangular objects.

### Columns (`detect_columns`)

1. **Contour detection** — Finds contours in both raw binary and morphologically
   closed (5×5 ellipse, 2 iterations) images via `RETR_LIST`.

2. **Size filtering** — Bounding rect width/height must be ≥15px, ≤30%/60% of image
   dimensions. Aspect ratio ≤3:1.

3. **Dark-interior check** — Samples the grayscale interior (5px inset). A valid
   column has mean < 180 and >10% of pixels darker than 128. A uniformity score
   (1 - std/80) modulates confidence.

*Limitations:* Columns must have a distinctly darker fill than the background.
Gray-filled columns in architectural drawings are detected; hollow outlines or
very light fills are missed. On site photos, pillars with strong texture variation
may be rejected by the uniformity test.

### Beams (`detect_beams`)

1. **Thickness filtering** — Morphological erosion (3×3 ellipse, 1 iteration) removes
   thin lines; only thick (structural) lines survive.

2. **Vertical line pairing** — Thick left-edge lines paired with right-edge lines
   (from original binary) at distances of 50–300 px (beam depth).

3. **Vertical overlap** — ≥50% y-extent overlap and ≥0.5 length ratio.

4. **Content score** — Compares pixel density inside the beam region vs flanking
   exterior strips. Beam hatching produces a content score of 0.03–0.10; threshold
   is 0.03.

*Limitations:* Beams without hatching (solid fill) produce content scores near zero
and are missed. Beams narrower than 100mm or wider than 600mm (at the image scale)
fall outside the depth range. On site photos, the binary adaptive threshold may not
isolate beam edges reliably.

### Doors (`detect_doors`)

1. **Horizontal gap detection** — Groups horizontal lines by y-coordinate (±8px),
   merges overlapping runs, and identifies gaps between consecutive wall segments.

2. **Vertical leaf verification** — Checks for vertical Hough lines within 40px of
   each gap edge. Confidence 0.60 (one side) or 0.75 (both sides).

3. **Marker-based detection** — Short vertical lines (8–50px long) paired across a
   gap of 30px to 30% of image width, with ≥0.4 length ratio.

*Limitations:* Doors must be flanked by detectable horizontal wall lines. Very wide
doors (>30% of image width) are rejected. Open doors where the leaf is not visible
may lack vertical markers. Door detection currently relies on plan-like line
patterns and performs poorly on unstructured site photos.

## Performance Characteristics

| Aspect              | OpenCV Detector               | YOLO Detector                 |
| ------------------- | ----------------------------- | ----------------------------- |
| Model loading       | None (zero startup)           | 1–3s (YOLO weight loading)   |
| GPU required        | No                            | Optional (CPU fallback)       |
| Per-image latency   | 50–500ms (CPU, 1920px image) | 100–800ms (CPU)               |
| Memory footprint    | <100MB                        | ~500MB (model weights)        |
| Domain dependency   | Works best on plan drawings   | Generalises to site photos    |
| Interpretability    | Fully traceable               | Black box                     |

## Benchmarking

Run the benchmark suite:
```bash
python backend/scripts/benchmark_opencv_detector.py
```

The benchmark generates synthetic floor plans from `validate_drawing_parser.py`
generators and reports per-class precision, recall, F1, and runtime statistics.

### Benchmark results (50 synthetic plan suite, 2025-06-17)

```
Plans run:      50/50
Success rate:   100.0%
Total detections: 4870
Avg runtime:    88.3ms
Min runtime:    29.6ms
Max runtime:    249.2ms

Per-class detection counts:
Class        Detected    GT   Exact match  Match rate
-------------------------------------------------------
wall             4042    58     8/50      16.0%
column            227   208    43/50      86.0%
beam              303    80     6/50      12.0%
door              298   101     7/50      14.0%
```

*Note:* These metrics are on **synthetic plan-style images**, which differ
significantly from site photos. The benchmark uses count-based matching
(detected count vs ground-truth count per class) because plan GTs don't
store bounding-box positions. The detector targets site photos where walls
appear as textured planar surfaces — the synthetic plans use thin line pairs
that the edge-density strategy partially captures.

| Class    | Behaviour on synthetic plans                                   |
| -------- | -------------------------------------------------------------- |
| Wall     | Edge-density + long-line strategies; 16% exact count match.    |
| Column   | Contour + fill detection; 86% exact match — best performer.    |
| Beam     | Erosion + vertical line pairing; 12% match; limited by CS      |
| Door     | Horizontal gap + marker check; 14% match; needs leaf markers   |

## Future Improvements

1. **Adaptive threshold tuning** — Image-specific Canny thresholds (Otsu's method)
   would improve edge detection on low-contrast site photos.

2. **Scale-aware parameters** — Use the plan's px_per_mm estimate to set min/max
   sizes in real-world units rather than fixed pixels.

3. **Contour-based door detection** — Detect door-shaped openings via contour
   hierarchy (hole in wall contour) rather than line gaps.

4. **Texture analysis for beams** — Use GLCM or LBP features to detect beam
   hatching patterns instead of the simple content-score threshold.

5. **Integration with drawing_parser** — Leverage `drawing_parser.py` functions
   when a plan image is available (distinguished from site photos by edge density
   and dominant orientation).
