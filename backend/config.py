"""Application settings and filesystem paths."""

from __future__ import annotations

from pathlib import Path

# Repo root is one level above backend/
BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent

UPLOADS_DIR = BACKEND_ROOT / "uploads"
OUTPUTS_DIR = BACKEND_ROOT / "outputs"
RULES_DIR = BACKEND_ROOT / "rules"
CUSTOM_YOLO_WEIGHTS = BACKEND_ROOT / "models" / "weights" / "sitecheck_yolov8n.pt"
YOLO_DATA_YAML = PROJECT_ROOT / "data" / "yolo" / "data.yaml"

# Image processing defaults
MAX_IMAGE_EDGE_PX = 1920
DEFAULT_RULESET = "IS456"
DEFAULT_UNIT_SYSTEM = "metric"

# CORS — allow local Next.js dev server
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Detection mode: yolo, opencv, or hybrid
DETECTION_MODE = "opencv"

# YOLO inference (only used when DETECTION_MODE is "yolo" or "hybrid")
YOLO_IMGSZ = 640
MIN_DETECTION_CONFIDENCE = 0.35

# Heuristic detection / geometry thresholds (Phase 1 MVP)
WALL_PLUMB_WARNING_CM_PER_M = 1.5
WALL_PLUMB_FAIL_CM_PER_M = 3.0
BEAM_LEVEL_WARNING_MM_PER_M = 5.0
BEAM_LEVEL_FAIL_MM_PER_M = 10.0

# Standard reference for scale estimation when no plan is provided (IS door width)
REFERENCE_DOOR_WIDTH_MM = 900.0

# Debug visualization flag
DEBUG_OVERLAYS = True
