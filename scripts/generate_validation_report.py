#!/usr/bin/env python3
"""Script to run end-to-end geometric and compliance validation on 5 test cases."""

import sys
import os
from pathlib import Path

# Add backend to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import cv2
import numpy as np
import json
from unittest.mock import patch

from schemas.inspection import Detection, Ruleset, UnitSystem
from schemas.plan import PlanSchema, DoorSpec
from services.pipeline import process_inspection
import models.yolo_detector
import modules.plan_parser

# Output directory for validation assets
VALIDATION_DIR = Path(__file__).resolve().parent.parent / "test_assets" / "validation_run"
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

def create_base_canvas(color=(30, 30, 30)):
    """Create a dark slate canvas to simulate a premium digital construction photo."""
    img = np.zeros((600, 600, 3), dtype=np.uint8)
    img[:] = color
    # Draw a faint grid background to look like a construction scanner view
    for x in range(0, 600, 50):
        cv2.line(img, (x, 0), (x, 600), (45, 45, 45), 1)
    for y in range(0, 600, 50):
        cv2.line(img, (0, y), (600, y), (45, 45, 45), 1)
    return img

def draw_wall(img, tilt_deg, x_center=150, color=(200, 200, 200)):
    """Draw a vertical wall element with a given tilt angle."""
    h, w = img.shape[:2]
    rad = np.radians(tilt_deg)
    dx = int((h - 100) * np.tan(rad))
    # Line endpoints
    pt1 = (x_center - dx // 2, 50)
    pt2 = (x_center + dx // 2, 550)
    cv2.line(img, pt1, pt2, color, 8)
    # Draw wall boundaries/hatching slightly faint
    cv2.line(img, (pt1[0] - 20, pt1[1]), (pt2[0] - 20, pt2[1]), (color[0]//2, color[1]//2, color[2]//2), 2)
    cv2.line(img, (pt1[0] + 20, pt1[1]), (pt2[0] + 20, pt2[1]), (color[0]//2, color[1]//2, color[2]//2), 2)

def draw_beam(img, tilt_deg, y_center=100, color=(100, 150, 220)):
    """Draw a horizontal beam element with a given tilt angle."""
    h, w = img.shape[:2]
    rad = np.radians(tilt_deg)
    dy = int((w - 100) * np.tan(rad))
    pt1 = (50, y_center - dy // 2)
    pt2 = (550, y_center + dy // 2)
    cv2.line(img, pt1, pt2, color, 12)

def draw_door_frame(img, x_left=350, x_right=500, y_top=200, y_bottom=580, gap_left_tilt=0.0, gap_right_tilt=0.0, color=(240, 240, 240)):
    """Draw left and right vertical edges of a door frame with optional tilt for asymmetry."""
    # Left edge
    l_rad = np.radians(gap_left_tilt)
    l_dx = int((y_bottom - y_top) * np.tan(l_rad))
    pt_l1 = (x_left, y_top)
    pt_l2 = (x_left + l_dx, y_bottom)
    cv2.line(img, pt_l1, pt_l2, color, 6)

    # Right edge
    r_rad = np.radians(gap_right_tilt)
    r_dx = int((y_bottom - y_top) * np.tan(r_rad))
    pt_r1 = (x_right, y_top)
    pt_r2 = (x_right + r_dx, y_bottom)
    cv2.line(img, pt_r1, pt_r2, color, 6)

    # Header (top)
    cv2.line(img, pt_l1, pt_r1, color, 6)

def main():
    print("Generating synthetic validation images...")

    # Case 1: Wall Plumb PASS (0.5 degree tilt = ~0.87 cm/m, calibrated via plan door)
    img1 = create_base_canvas()
    draw_wall(img1, tilt_deg=0.5, x_center=150)
    draw_door_frame(img1, x_left=350, x_right=500, y_top=200, y_bottom=580)
    img1_path = VALIDATION_DIR / "case1_wall_plumb_pass.jpg"
    cv2.imwrite(str(img1_path), img1)

    # Case 2: Wall Plumb UNCALIBRATED (2.5 degree tilt = ~4.3 cm/m, but no door/plan for calibration)
    img2 = create_base_canvas()
    draw_wall(img2, tilt_deg=2.5, x_center=300)
    img2_path = VALIDATION_DIR / "case2_wall_plumb_uncalibrated.jpg"
    cv2.imwrite(str(img2_path), img2)

    # Case 3: Wall Plumb FAIL (3.8 degree tilt = ~6.6 cm/m, calibrated via auto-door)
    img3 = create_base_canvas()
    draw_wall(img3, tilt_deg=3.8, x_center=150)
    draw_door_frame(img3, x_left=350, x_right=500, y_top=200, y_bottom=580)
    img3_path = VALIDATION_DIR / "case3_wall_plumb_fail.jpg"
    cv2.imwrite(str(img3_path), img3)

    # Case 4: Beam Level WARNING (0.45 degree tilt = ~7.8 mm/m, calibrated via auto-door)
    img4 = create_base_canvas()
    draw_beam(img4, tilt_deg=0.45, y_center=100)
    draw_door_frame(img4, x_left=300, x_right=450, y_top=220, y_bottom=580)
    img4_path = VALIDATION_DIR / "case4_beam_level_warning.jpg"
    cv2.imwrite(str(img4_path), img4)

    # Case 5: Door Alignment FAIL (High gap asymmetry, calibrated by door itself)
    img5 = create_base_canvas()
    # Draw door frame with highly tilted/skewed sides (left is straight, right is tilted 2.5 degrees)
    draw_door_frame(img5, x_left=150, x_right=350, y_top=150, y_bottom=550, gap_left_tilt=0.0, gap_right_tilt=2.8)
    img5_path = VALIDATION_DIR / "case5_door_alignment_fail.jpg"
    cv2.imwrite(str(img5_path), img5)

    print("Images saved in test_assets/validation_run.")

    # Setup mocked detection returns based on file name to isolate tests and ensure accuracy
    mock_detections = {
        "case1_wall_plumb_pass.jpg": [
            Detection(label="wall", confidence=0.92, bbox=[100, 30, 200, 570]),
            Detection(label="door", confidence=0.88, bbox=[340, 190, 510, 590])
        ],
        "case2_wall_plumb_uncalibrated.jpg": [
            Detection(label="wall", confidence=0.91, bbox=[250, 30, 350, 570])
        ],
        "case3_wall_plumb_fail.jpg": [
            Detection(label="wall", confidence=0.93, bbox=[100, 30, 200, 570]),
            Detection(label="door", confidence=0.89, bbox=[340, 190, 510, 590])
        ],
        "case4_beam_level_warning.jpg": [
            Detection(label="beam", confidence=0.90, bbox=[40, 80, 560, 120]),
            Detection(label="door", confidence=0.87, bbox=[290, 210, 460, 590])
        ],
        "case5_door_alignment_fail.jpg": [
            Detection(label="door", confidence=0.94, bbox=[130, 130, 370, 570])
        ]
    }

    def custom_detect_elements(bgr_img):
        # We find which photo this corresponds to by checking dimensions/content matches
        # or we patch it to intercept the current filename.
        # But we can look at the active test file processed by pipeline.
        return active_detections

    # Create a dummy plan PDF path for case 1
    dummy_plan_path = VALIDATION_DIR / "mock_plan.pdf"
    dummy_plan_path.write_text("Mock Plan content for OCR matching.", encoding="utf-8")

    # Mock parse_plan_file to return a door with exact width
    mock_plan_schema = PlanSchema(
        doors=[DoorSpec(id="D1", width_mm=900.0, height_mm=2100.0)]
    )

    photo_paths = [img1_path, img2_path, img3_path, img4_path, img5_path]

    print("Running process_inspection pipeline on all 5 images...")
    
    # We will run them one by one or as a batch. Let's run as a batch!
    # To set active_detections dynamically during batch process_inspection, we'll override detect_elements
    # using a stateful mock.
    class StatefulDetector:
        def __init__(self, mock_map):
            self.mock_map = mock_map
            self.current_idx = 0

        def detect(self, bgr_img):
            fname = photo_paths[self.current_idx].name
            print(f"Mocking YOLO detections for {fname}")
            dets = self.mock_map[fname]
            self.current_idx += 1
            return dets

    detector_instance = StatefulDetector(mock_detections)

    with patch("services.pipeline.detect_elements", side_effect=detector_instance.detect), \
         patch("services.pipeline.parse_plan_file", return_value=mock_plan_schema):
        
        session = process_inspection(
            photo_paths=photo_paths,
            plan_path=dummy_plan_path,
            unit_system=UnitSystem.METRIC,
            ruleset=Ruleset.IS456
        )

    print(f"Inspection Pipeline successfully completed. Session ID: {session.session_id}")
    print(f"Compliance Score: {session.compliance_score}/100")

    # Save session JSON output
    session_json_path = VALIDATION_DIR / "validation_results.json"
    session_json_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
    print(f"JSON output saved to: {session_json_path}")

    # Copy output annotated files and PDF report to validation_run folder for clean packaging
    output_session_dir = BACKEND_DIR / "outputs" / session.session_id
    
    for idx, path in enumerate(photo_paths):
        annotated_name = f"annotated_{idx:02d}.png"
        src_annotated = output_session_dir / annotated_name
        dest_annotated = VALIDATION_DIR / f"annotated_{path.stem}.png"
        if src_annotated.exists():
            import shutil
            shutil.copy2(src_annotated, dest_annotated)
            print(f"Annotated image saved: {dest_annotated}")

    src_pdf = Path(session.report_path)
    dest_pdf = VALIDATION_DIR / "inspection_report.pdf"
    if src_pdf.exists():
        import shutil
        shutil.copy2(src_pdf, dest_pdf)
        print(f"Inspection PDF Report saved: {dest_pdf}")

if __name__ == "__main__":
    main()
