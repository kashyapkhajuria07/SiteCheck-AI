# Phase 2 — YOLOv8 Construction Detector

## Goal

Fine-tune YOLOv8 on construction-specific classes and use those weights in the inspection API instead of COCO + heuristics.

**Classes:** `wall`, `column`, `beam`, `door`, `window`, `rebar`, `slab`

## Quick workflow

### 1. Add training images

Place photos under:

```text
data/raw/beams/      → labeled as beam
data/raw/columns/    → labeled as column
data/raw/mixed/      → use filenames like BEAM_OK_001.jpg, COLUMN_DEFECT_002.jpg
```

Or export a Roboflow dataset in **YOLOv8** format into `data/yolo/`:

```text
data/yolo/
├── data.yaml
├── train/images  + train/labels
├── valid/images  + valid/labels
└── test/images   + test/labels   (optional)
```

**Imported dataset:** `construction-element-detection` — classes `beam`, `column` (nc: 2).

### 2. Prepare YOLO dataset (bootstrap labels)

Creates `data/yolo/images/` + `labels/` with an initial full-frame box per image:

```bash
python backend/scripts/prepare_yolo_dataset.py
```

### 3. Train

```bash
python backend/scripts/train_yolo.py --epochs 50 --imgsz 640
```

Weights deploy to: `backend/models/weights/sitecheck_yolov8n.pt`

### 4. Restart backend

```bash
./scripts/start-backend.sh
```

Check: `curl http://127.0.0.1:8000/api/health` → `"detection_mode": "custom_yolo"`

## Roboflow (recommended for real boxes)

1. Create a project on [roboflow.com](https://roboflow.com) with the 7 classes above.
2. Label bounding boxes on site photos (or use a public construction dataset).
3. Export → **YOLOv8** format.
4. Unzip into `data/yolo/` so you have `images/train`, `labels/train`, etc.
5. Ensure `data/yolo/data.yaml` `names` match your export.
6. Run `train_yolo.py` (skip `prepare_yolo_dataset.py` if you have real boxes).

## Environment override

```bash
export SITECHECK_YOLO_WEIGHTS=/path/to/custom.pt
```

## Detection modes

| Mode | When |
|------|------|
| `custom_yolo` | `backend/models/weights/sitecheck_yolov8n.pt` exists |
| `coco_yolo` | Ultralytics loads but no custom weights |
| `heuristic` | YOLO unavailable or zero detections (custom model still falls back if empty) |

## Improving accuracy

- Replace bootstrap full-frame labels with real bounding boxes.
- Aim for 200+ labeled images per class (more for `wall` / `rebar`).
- Use `--epochs 80` and review metrics in `runs/detect/sitecheck/`.
- Add hard negatives (cluttered sites, blurry photos) to reduce false positives.
