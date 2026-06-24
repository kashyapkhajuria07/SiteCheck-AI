# SiteCheck AI - Phase 1 Repository Audit

## 1. Overview
The current repository consists of a Next.js frontend and a FastAPI backend. It utilizes a YOLOv8 model for object detection (currently fine-tuned for beams and columns). The system is starting to drift towards being a generic object detector, but the core product goal is a construction inspection platform focusing on geometric analysis (plumbness, levelness, dimensions) and compliance against rulesets like IS456.

## 2. Existing Modules
- **`yolo_detector.py`**: Handles detection using custom weights (`CUSTOM_YOLO`) or a heuristic fallback. Currently only processes classes like `beam` and `column` correctly from the YOLO model. Includes NMS and heuristic detection for walls, doors, beams, columns, and rebar.
- **`geometric_analyser.py`**: Contains `HoughLinesP` based geometric checks. Currently implements basic dominant line deviation for walls/columns (vertical mode), beams/slabs (horizontal mode), rebar spacing, and door alignment gap asymmetry. Uses `cm/m` and `mm/m` units for walls and beams respectively.
- **`compliance_engine.py`**: Loads JSON rulesets (`IS456.json`, `NBC2016.json`) and generates `PASS`, `WARNING`, `FAIL`, `INCONCLUSIVE` statuses based on deviations (e.g., wall plumb, beam level, door alignment, rebar spacing). Computes an overall compliance score.
- **`overlay_renderer.py`**: Draws bounding boxes, statuses, and deviation labels on images. Supports deviation arrows.
- **`report_generator.py`**: Generates PDF reports summarizing compliance scores, element findings (with status, deviation, unit, and message), and includes thumbnails of annotated photos.
- **`plan_parser.py`**: Extracts basic OCR dimensions from plans.
- **`preprocessor.py`**: Resizes, enhances contrast, denoises, and produces grayscale versions of images for geometric analysis. Assesses image quality.
- **`pipeline.py`**: Orchestrates the entire flow (preprocessing -> detection -> scaling -> geometric analysis -> compliance -> overlay -> report generation).

## 3. Missing Modules & Features
- **`scale_calibrator.py`**: Missing. The scale estimation logic is currently spread and hardcoded inside `pipeline.py` (e.g., `_estimate_px_per_mm`), using a reference door width. Needs to be a dedicated module to handle Mode A (Plan available) and Mode B (Standard assumptions).
- **Dedicated Test Suite**: The `tests/` directory is missing. We need tests for `wall_plumb_detection`, `beam_levelness`, `door_alignment`, and `compliance_scoring`.
- **Full Detection Classes**: While the classes list has `wall`, `column`, `beam`, `door`, `window`, `rebar`, `slab`, the actual YOLO logic and geometric checks need refactoring to cleanly support and expand to all these classes.

## 4. Technical Debt & Placeholder Logic
- **Scale Calculation**: `pipeline.py` contains basic scale calibration logic `_estimate_px_per_mm`. This should be decoupled into a proper `scale_calibrator.py`.
- **Yolo Detector**: `yolo_detector.py`'s `detect_elements` has hardcoded fallbacks and merging logic between heuristic and YOLO. It lacks clean interfaces like `detect_walls()`, `detect_doors()`, etc., to prepare for dataset expansion.
- **Geometric Analysis**: `geometric_analyser.py` relies on `analyse_element` which is a monolithic function handling all logic inside if-statements. Needs to be refactored into distinct functions `analyze_wall_plumb()`, `analyze_beam_levelness()`, `analyze_column_verticality()`, `analyze_door_alignment()`.
- **Plan Parser**: `plan_parser.py` is a stub for Phase 3 OCR dimension extraction.

## 5. Current YOLO Integration Status
- The YOLO model uses custom weights or falls back to COCO/heuristics.
- Custom weights are primarily used for `beam` and `column` detection right now, but the labels are mapped down to `CONSTRUCTION_CLASSES`.

## 6. Current Geometric Analysis Status
- Plumbness for walls/columns is measured using vertical edge extraction and angle deviation via Hough Lines.
- Levelness for beams/slabs uses horizontal edge extraction.
- Door alignment checks left/right gaps.
- The outputs use `cm/m` (walls) and `mm/m` (beams).
- Lacks isolated entry functions (`analyze_wall_plumb()`, etc.) as requested.

## 7. Current Report Generation Status
- Uses ReportLab to generate an A4 PDF with a title page showing compliance score, pass/fail counts, and a table of findings.
- Need to upgrade the report structure to exactly match: Page 1 (score, counts), Page 2+ (Findings table with Element, Measurement, Expected, Deviation, Status), embedded annotated images, and Final page (Recommendations). Currently, it lumps everything in one continuous flow.
