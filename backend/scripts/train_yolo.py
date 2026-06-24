#!/usr/bin/env python3
"""
Fine-tune YOLOv8n on SiteCheck construction classes.

Prerequisites:
  1. python backend/scripts/prepare_yolo_dataset.py
  2. Images present under data/yolo/images/{train,val}

Usage (from repo root):
  python backend/scripts/train_yolo.py
  python backend/scripts/train_yolo.py --epochs 80 --imgsz 640

Best weights are copied to backend/models/weights/sitecheck_yolov8n.pt
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def train(
    *,
    epochs: int = 50,
    imgsz: int = 640,
    batch: int = 8,
    base_weights: str = "yolov8n.pt",
    project_name: str = "sitecheck",
) -> Path:
    root = _repo_root()
    yolo_dir = root / "data" / "yolo"
    data_yaml = yolo_dir / "data.yaml"

    # Roboflow layout: train/images  |  bootstrap layout: images/train
    train_dir = yolo_dir / "train" / "images"
    if not train_dir.exists() or not any(train_dir.glob("*")):
        train_dir = yolo_dir / "images" / "train"

    if not data_yaml.exists():
        raise FileNotFoundError(f"Missing {data_yaml}")
    if not train_dir.exists() or not any(train_dir.glob("*")):
        raise FileNotFoundError(
            f"No training images found. Expected {yolo_dir}/train/images/ "
            f"(Roboflow) or {yolo_dir}/images/train/ (bootstrap)."
        )

    from ultralytics import YOLO

    import os

    os.chdir(root)

    weights_out = root / "backend" / "models" / "weights"
    weights_out.mkdir(parents=True, exist_ok=True)
    deploy_path = weights_out / "sitecheck_yolov8n.pt"

    runs_dir = root / "runs" / "detect"
    runs_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(base_weights)
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=str(runs_dir),
        name=project_name,
        exist_ok=True,
        patience=15,
        save=True,
        plots=True,
    )

    best_src = runs_dir / project_name / "weights" / "best.pt"
    if not best_src.exists():
        best_src = runs_dir / project_name / "weights" / "last.pt"
    if not best_src.exists():
        raise FileNotFoundError("Training finished but no best.pt / last.pt found.")

    shutil.copy2(best_src, deploy_path)
    print(f"\n✓ Deployed model → {deploy_path}")
    print(f"  Metrics: {results}")
    print("Restart the backend to load the new weights.")
    return deploy_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train SiteCheck YOLOv8 detector")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--base", type=str, default="yolov8n.pt", help="Base checkpoint")
    args = parser.parse_args()

    train(
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        base_weights=args.base,
    )


if __name__ == "__main__":
    main()
