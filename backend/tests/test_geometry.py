"""Unit tests for geometric analysis."""

import numpy as np
import pytest
import cv2

from modules.geometric_analyser import analyze_vertical_element, analyze_horizontal_element, analyze_door_alignment
from modules.compliance_engine import evaluate_element, _load_rules
from schemas.inspection import Detection, Ruleset

def create_synthetic_image(mode: str) -> np.ndarray:
    """Create a synthetic image for testing."""
    img = np.zeros((400, 400), dtype=np.uint8)
    if mode == "vertical":
        # Draw a nearly vertical white line
        cv2.line(img, (200, 50), (205, 350), 255, 3)
    elif mode == "horizontal":
        # Draw a nearly horizontal white line
        cv2.line(img, (50, 200), (350, 205), 255, 3)
    elif mode == "door":
        # Draw a door frame (left and right vertical lines)
        cv2.line(img, (100, 50), (100, 350), 255, 3)
        cv2.line(img, (300, 50), (300, 350), 255, 3)
    return img

def test_analyze_vertical_element():
    img = create_synthetic_image("vertical")
    bbox = [0, 0, 400, 400]
    findings = analyze_vertical_element(img, bbox, label="wall", px_per_mm=None)
    
    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_type == "wall_plumb"
    
    # Measurements should include estimated=True since px_per_mm=None
    offset_measurement = next(m for m in finding.measurements if m.name == "plumb_offset")
    assert offset_measurement.estimated is True
    assert offset_measurement.confidence > 0.0

def test_analyze_horizontal_element():
    img = create_synthetic_image("horizontal")
    bbox = [0, 0, 400, 400]
    findings = analyze_horizontal_element(img, bbox, label="beam", px_per_mm=None)
    
    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_type == "beam_level"
    
    offset_measurement = next(m for m in finding.measurements if m.name == "level_offset")
    assert offset_measurement.estimated is True
    assert offset_measurement.confidence > 0.0

def test_analyze_door_alignment():
    img = create_synthetic_image("door")
    bbox = [0, 0, 400, 400]
    findings = analyze_door_alignment(img, bbox, px_per_mm=None)
    
    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_type == "door_alignment"
    
    offset_measurement = next(m for m in finding.measurements if m.name == "gap_asymmetry")
    assert offset_measurement.estimated is True
    assert offset_measurement.confidence > 0.0

def test_compliance_engine_inconclusive():
    img = create_synthetic_image("vertical")
    bbox = [0, 0, 400, 400]
    detection = Detection(label="wall", confidence=0.9, bbox=bbox)
    
    # px_per_mm is None, so it will be estimated
    findings = analyze_vertical_element(img, bbox, label="wall", px_per_mm=None)
    
    rules = _load_rules(Ruleset.IS456)
    result = evaluate_element(detection, findings, rules, element_index=1)
    
    # Since it's estimated, status should be INCONCLUSIVE and reason scale_not_calibrated
    assert result.status.value == "INCONCLUSIVE"
    assert result.reason == "scale_not_calibrated"
