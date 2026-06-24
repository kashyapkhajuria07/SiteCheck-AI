#!/usr/bin/env python3
"""
Prepare a YOLO-format dataset from SiteCheck raw images.

Bootstrap mode (no bbox CSV yet):
  - data/raw/beams/   → class beam
  - data/raw/columns/ → class column
  - data/raw/mixed/   → class from filename prefix (BEAM_, COLUMN_, etc.)

Each image gets a single full-frame bounding box (90% coverage) so you can
fine-tune YOLO before full box annotations exist. Replace with real labels later.

Usage (from repo root):
  python backend/scripts/prepare_yolo_dataset.py
  python backend/scripts/prepare_yolo_dataset.py --val-ratio 0.2
"""

from __future__ import annotations

import argparse
import random
import re
import shutil
from pathlib import Path

# Folder name → YOLO class id (must match data/yolo/data.yaml)
FOLDER_TO_CLASS: dict[str, int] = {
    "beams": 2,
    "beam": 2,
    "columns": 1,
    "column": 1,
    "walls": 0,
    "wall": 0,
    "doors": 3,
    "door": 3,
    "windows": 4,
    "window": 4,
    "rebar": 5,
    "slabs": 6,
    "slab": 6,
    "mixed": -1,  # infer from filename
}

FILENAME_PREFIX_CLASS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"^BEAM", re.I), 2),
    (re.compile(r"^COLUMN", re.I), 1),
    (re.compile(r"^WALL", re.I), 0),
    (re.compile(r"^DOOR", re.I), 3),
    (re.compile(r"^WINDOW", re.I), 4),
    (re.compile(r"^REBAR", re.I), 5),
    (re.compile(r"^SLAB", re.I), 6),
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _infer_class_from_name(name: str) -> int | None:
    stem = Path(name).stem.upper()
    for pattern, cls_id in FILENAME_PREFIX_CLASS:
        if pattern.search(stem):
            return cls_id
    return None


def _full_frame_label(class_id: int, margin: float = 0.05) -> str:
    """YOLO normalized label: class cx cy w h (single box covering most of image)."""
    cx, cy = 0.5, 0.5
    w = h = 1.0 - 2 * margin
    return f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n"


def _collect_images(raw_dir: Path) -> list[tuple[Path, int]]:
    pairs: list[tuple[Path, int]] = []
    if not raw_dir.exists():
        return pairs

    for sub in sorted(raw_dir.iterdir()):
        if not sub.is_dir():
            continue
        folder_key = sub.name.lower()
        default_cls = FOLDER_TO_CLASS.get(folder_key, -1)
        for img in sub.rglob("*"):
            if img.suffix.lower() not in IMAGE_EXTS:
                continue
            if default_cls >= 0:
                pairs.append((img, default_cls))
            else:
                inferred = _infer_class_from_name(img.name)
                if inferred is not None:
                    pairs.append((img, inferred))

    # Also pick up images directly under raw/ (no subfolder)
    for img in raw_dir.iterdir():
        if img.is_file() and img.suffix.lower() in IMAGE_EXTS:
            inferred = _infer_class_from_name(img.name)
            if inferred is not None:
                pairs.append((img, inferred))

    return pairs


def prepare_dataset(*, val_ratio: float = 0.2, seed: int = 42) -> int:
    root = _repo_root()
    raw_dir = root / "data" / "raw"
    yolo_dir = root / "data" / "yolo"

    pairs = _collect_images(raw_dir)
    if not pairs:
        print(f"No images found under {raw_dir}")
        print("Add JPG/PNG files to data/raw/beams/, data/raw/columns/, etc.")
        return 0

    random.seed(seed)
    random.shuffle(pairs)
    n_val = max(1, int(len(pairs) * val_ratio)) if len(pairs) > 1 else 0
    val_set = set(id(p) for p, _ in pairs[:n_val])

    for split in ("train", "val"):
        (yolo_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (yolo_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {"train": 0, "val": 0}

    for img_path, class_id in pairs:
        split = "val" if id(img_path) in val_set else "train"
        dest_name = f"{img_path.stem}_{class_id}{img_path.suffix.lower()}"
        dest_img = yolo_dir / "images" / split / dest_name
        dest_lbl = yolo_dir / "labels" / split / f"{dest_img.stem}.txt"

        shutil.copy2(img_path, dest_img)
        dest_lbl.write_text(_full_frame_label(class_id), encoding="utf-8")
        counts[split] += 1

    print(f"Prepared {counts['train']} train + {counts['val']} val images → {yolo_dir}")
    print("Next: python backend/scripts/train_yolo.py")
    return counts["train"] + counts["val"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare YOLO dataset from raw images")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    n = prepare_dataset(val_ratio=args.val_ratio, seed=args.seed)
    if n == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
