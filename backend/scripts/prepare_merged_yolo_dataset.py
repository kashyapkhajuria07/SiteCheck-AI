#!/usr/bin/env python3
"""Prepare the merged SiteCheck YOLOv8 detection dataset without training."""

from __future__ import annotations

import argparse
import ast
import collections
import dataclasses
import hashlib
import json
import math
import os
import random
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

IMAGE_EXTS = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
TARGET_TRAIN_RATIO = 0.8
DEFAULT_SEED = 42
CLIP_EPSILON = 1e-6


@dataclasses.dataclass(frozen=True)
class SourceItem:
    source_name: str
    source_display_name: str
    image_path: Path
    label_lines: tuple[str, ...]
    original_split: str


@dataclasses.dataclass
class ParsedLabel:
    target_class_id: int
    line: str
    source_class_name: str
    clipped: bool = False
    converted_polygon: bool = False


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_class_name(name: str) -> str:
    normalized = name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def sanitize_stem(stem: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return sanitized[:80] or "image"


def load_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as mapping_file:
        mapping = json.load(mapping_file)

    taxonomy = {int(class_id): name for class_id, name in mapping["taxonomy"].items()}
    expected = {0: "beam", 1: "column", 2: "wall", 3: "rebar", 4: "slab"}
    if taxonomy != expected:
        raise ValueError(f"Unexpected taxonomy in {path}: {taxonomy}")

    return mapping


def strip_yaml_value(raw_value: str) -> str:
    value = raw_value.split("#", 1)[0].strip()
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    return value


def parse_inline_names(raw_value: str) -> list[str] | None:
    value = raw_value.strip()
    if not value:
        return None

    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None

    if isinstance(parsed, list):
        return [str(name) for name in parsed]
    if isinstance(parsed, dict):
        names_by_id = {int(key): value for key, value in parsed.items()}
        return [str(names_by_id[index]) for index in sorted(names_by_id)]
    return None


def parse_yolo_yaml(data_yaml: Path) -> dict[str, Any]:
    lines = data_yaml.read_text(encoding="utf-8").splitlines()
    names: list[str] | None = None
    split_paths: dict[str, str] = {}
    dataset_path: str | None = None

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.split("#", 1)[0].rstrip()
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            index += 1
            continue

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value = strip_yaml_value(raw_value)

        if key == "path":
            dataset_path = value
        elif key in {"train", "val", "valid", "test"}:
            split_paths[key] = value
        elif key == "names":
            names = parse_inline_names(value)
            if names is None:
                names_by_id: dict[int, str] = {}
                lookahead = index + 1
                while lookahead < len(lines):
                    child_line = lines[lookahead]
                    if child_line.strip() and not child_line.startswith((" ", "\t", "-")):
                        break
                    child_stripped = child_line.strip()
                    if child_stripped.startswith("-"):
                        names_by_id[len(names_by_id)] = strip_yaml_value(child_stripped[1:])
                    elif ":" in child_stripped:
                        child_key, child_value = child_stripped.split(":", 1)
                        if child_key.strip().isdigit():
                            names_by_id[int(child_key.strip())] = strip_yaml_value(child_value)
                    lookahead += 1
                names = [names_by_id[class_id] for class_id in sorted(names_by_id)]
                index = lookahead - 1
        index += 1

    if names is None:
        raise ValueError(f"Could not parse class names from {data_yaml}")

    return {"names": names, "path": dataset_path, "splits": split_paths}


def resolve_dataset_base(data_yaml: Path, dataset_path: str | None) -> Path:
    if not dataset_path:
        return data_yaml.parent

    path = Path(dataset_path)
    if path.is_absolute():
        return path

    first_try = (data_yaml.parent / path).resolve()
    if first_try.exists():
        return first_try
    return data_yaml.parent


def label_dir_for_image_dir(image_dir: Path) -> Path:
    parts = list(image_dir.parts)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == "images":
            parts[index] = "labels"
            return Path(*parts)
    return image_dir.parent / "labels"


def resolve_split_image_dir(base_dir: Path, data_yaml: Path, split_path: str) -> Path:
    path = Path(split_path)
    if path.is_absolute():
        return path

    first_try = (base_dir / path).resolve()
    if first_try.exists():
        return first_try
    return (data_yaml.parent / path).resolve()


def discover_split_dirs(data_yaml: Path, yaml_info: dict[str, Any]) -> list[tuple[str, Path, Path]]:
    base_dir = resolve_dataset_base(data_yaml, yaml_info["path"])
    discovered: list[tuple[str, Path, Path]] = []
    seen: set[tuple[str, Path, Path]] = set()

    for split_name, split_path in yaml_info["splits"].items():
        normalized_split = "val" if split_name == "valid" else split_name
        image_dir = resolve_split_image_dir(base_dir, data_yaml, split_path)
        label_dir = label_dir_for_image_dir(image_dir)
        key = (normalized_split, image_dir, label_dir)
        if image_dir.exists() and key not in seen:
            discovered.append(key)
            seen.add(key)

    for split_name in ("train", "val", "valid", "test"):
        normalized_split = "val" if split_name == "valid" else split_name
        candidates = [
            (base_dir / split_name / "images", base_dir / split_name / "labels"),
            (base_dir / "images" / split_name, base_dir / "labels" / split_name),
            (data_yaml.parent / split_name / "images", data_yaml.parent / split_name / "labels"),
            (data_yaml.parent / "images" / split_name, data_yaml.parent / "labels" / split_name),
        ]
        for image_dir, label_dir in candidates:
            key = (normalized_split, image_dir.resolve(), label_dir.resolve())
            if image_dir.exists() and key not in seen:
                discovered.append(key)
                seen.add(key)

    return discovered


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = (destination / member.filename).resolve()
            try:
                member_path.relative_to(destination_resolved)
            except ValueError as error:
                raise ValueError(f"Unsafe zip member path: {member.filename}")
        archive.extractall(destination)


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "SiteCheck-AI dataset prep"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def stream_url_to_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "SiteCheck-AI dataset prep"})
    with urllib.request.urlopen(request, timeout=300) as response:
        with destination.open("wb") as output_file:
            shutil.copyfileobj(response, output_file)


def resolve_roboflow_version(dataset_config: dict[str, Any], api_key: str) -> str:
    requested_version = str(dataset_config.get("version", "latest"))
    if requested_version != "latest":
        return requested_version

    workspace = dataset_config["workspace"]
    project = dataset_config["project"]
    query = urllib.parse.urlencode({"api_key": api_key})
    metadata_url = f"https://api.roboflow.com/{workspace}/{project}?{query}"
    metadata = request_json(metadata_url)
    project_metadata = metadata.get("project", metadata)
    versions = project_metadata.get("versions", [])
    version_ids: list[int] = []
    for version in versions:
        if isinstance(version, int):
            version_ids.append(version)
        elif isinstance(version, dict):
            for key in ("id", "version", "version_number"):
                value = version.get(key)
                if isinstance(value, int):
                    version_ids.append(value)
                    break
                if isinstance(value, str) and value.isdigit():
                    version_ids.append(int(value))
                    break

    if not version_ids:
        raise ValueError(
            f"Could not determine latest Roboflow version for {workspace}/{project}. "
            "Set an explicit version in dataset_mapping.json."
        )

    return str(max(version_ids))


def download_roboflow_dataset(
    dataset_config: dict[str, Any],
    raw_dir: Path,
    force_download: bool,
    api_key: str,
) -> Path:
    source_dir = raw_dir / dataset_config["name"]
    existing_yaml = find_data_yaml(source_dir)
    if existing_yaml and not force_download:
        return source_dir

    if source_dir.exists():
        shutil.rmtree(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    version = resolve_roboflow_version(dataset_config, api_key)
    workspace = dataset_config["workspace"]
    project = dataset_config["project"]
    export_format = dataset_config.get("format", "yolov8")
    query = urllib.parse.urlencode({"api_key": api_key})
    download_url = (
        f"https://api.roboflow.com/{workspace}/{project}/{version}/download/"
        f"{export_format}?{query}"
    )

    downloads_dir = raw_dir / "_downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    zip_path = downloads_dir / f"{dataset_config['name']}.zip"

    request = urllib.request.Request(
        download_url,
        headers={"User-Agent": "SiteCheck-AI dataset prep"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            payload = json.loads(response.read().decode("utf-8"))
            link = payload.get("link") or payload.get("download") or payload.get("url")
            if not link:
                raise ValueError(f"Roboflow download response did not include a link: {payload}")
            stream_url_to_file(link, zip_path)
        else:
            with zip_path.open("wb") as output_file:
                shutil.copyfileobj(response, output_file)

    safe_extract_zip(zip_path, source_dir)
    if not find_data_yaml(source_dir):
        raise FileNotFoundError(f"Downloaded dataset has no data.yaml: {source_dir}")
    return source_dir


def find_data_yaml(source_dir: Path) -> Path | None:
    if not source_dir.exists():
        return None
    candidates = sorted(source_dir.rglob("data.yaml"), key=lambda path: len(path.parts))
    return candidates[0] if candidates else None


def ensure_sources(
    mapping: dict[str, Any],
    raw_dir: Path,
    skip_download: bool,
    force_download: bool,
    api_key: str | None,
) -> dict[str, Path]:
    source_dirs: dict[str, Path] = {}
    missing_downloads: list[str] = []

    for dataset_config in mapping["datasets"]:
        source_name = dataset_config["name"]
        source_dir = raw_dir / source_name
        if find_data_yaml(source_dir) and not force_download:
            source_dirs[source_name] = source_dir
            continue

        if skip_download:
            missing_downloads.append(source_name)
            continue

        if dataset_config.get("provider") != "roboflow":
            raise ValueError(f"Unsupported provider for {source_name}: {dataset_config.get('provider')}")
        if not api_key:
            missing_downloads.append(source_name)
            continue

        source_dirs[source_name] = download_roboflow_dataset(
            dataset_config=dataset_config,
            raw_dir=raw_dir,
            force_download=force_download,
            api_key=api_key,
        )

    if missing_downloads:
        names = ", ".join(missing_downloads)
        raise RuntimeError(
            "Missing source datasets: "
            f"{names}. Set ROBOFLOW_API_KEY or place extracted YOLOv8 datasets under "
            f"{raw_dir}/<dataset name>/data.yaml."
        )

    return source_dirs


def target_id_from_mapping(value: Any, taxonomy: dict[int, str]) -> int | None:
    if isinstance(value, int):
        return value if value in taxonomy else None
    if isinstance(value, str):
        normalized_value = normalize_class_name(value)
        for class_id, class_name in taxonomy.items():
            if normalize_class_name(class_name) == normalized_value:
                return class_id
    return None


def build_source_mapping(
    mapping: dict[str, Any],
    dataset_config: dict[str, Any],
) -> tuple[dict[str, int], dict[str, int]]:
    taxonomy = {int(class_id): name for class_id, name in mapping["taxonomy"].items()}
    name_mapping: dict[str, int] = {}
    id_mapping: dict[str, int] = {}

    for source_name, target in mapping.get("class_aliases", {}).items():
        target_id = target_id_from_mapping(target, taxonomy)
        if target_id is not None:
            name_mapping[normalize_class_name(source_name)] = target_id

    for source_name, target in dataset_config.get("source_class_mapping", {}).items():
        target_id = target_id_from_mapping(target, taxonomy)
        if target_id is not None:
            name_mapping[normalize_class_name(source_name)] = target_id

    for source_id, target in dataset_config.get("source_id_mapping", {}).items():
        target_id = target_id_from_mapping(target, taxonomy)
        if target_id is not None:
            id_mapping[str(source_id)] = target_id

    return name_mapping, id_mapping


def source_class_name(source_class_id: int, source_names: list[str]) -> str:
    if 0 <= source_class_id < len(source_names):
        return source_names[source_class_id]
    return f"id:{source_class_id}"


def map_source_class(
    source_class_id: int,
    source_names: list[str],
    name_mapping: dict[str, int],
    id_mapping: dict[str, int],
) -> tuple[int | None, str]:
    class_name = source_class_name(source_class_id, source_names)
    if str(source_class_id) in id_mapping:
        return id_mapping[str(source_class_id)], class_name

    normalized_name = normalize_class_name(class_name)
    return name_mapping.get(normalized_name), class_name


def is_finite_normalized(values: list[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def clipped_bbox_from_bbox(coords: list[float]) -> tuple[tuple[float, float, float, float] | None, bool]:
    center_x, center_y, width, height = coords
    if not is_finite_normalized(coords) or width <= 0 or height <= 0:
        return None, False

    x_min = center_x - width / 2
    y_min = center_y - height / 2
    x_max = center_x + width / 2
    y_max = center_y + height / 2

    clipped = (
        x_min < 0 - CLIP_EPSILON
        or y_min < 0 - CLIP_EPSILON
        or x_max > 1 + CLIP_EPSILON
        or y_max > 1 + CLIP_EPSILON
    )

    x_min = min(1.0, max(0.0, x_min))
    y_min = min(1.0, max(0.0, y_min))
    x_max = min(1.0, max(0.0, x_max))
    y_max = min(1.0, max(0.0, y_max))

    if x_max <= x_min or y_max <= y_min:
        return None, clipped

    return (
        (x_min + x_max) / 2,
        (y_min + y_max) / 2,
        x_max - x_min,
        y_max - y_min,
    ), clipped


def bbox_from_polygon(coords: list[float]) -> tuple[tuple[float, float, float, float] | None, bool]:
    if len(coords) < 6 or len(coords) % 2 != 0 or not is_finite_normalized(coords):
        return None, False

    x_values = coords[0::2]
    y_values = coords[1::2]
    clipped = any(value < 0 - CLIP_EPSILON or value > 1 + CLIP_EPSILON for value in coords)
    x_min = min(1.0, max(0.0, min(x_values)))
    y_min = min(1.0, max(0.0, min(y_values)))
    x_max = min(1.0, max(0.0, max(x_values)))
    y_max = min(1.0, max(0.0, max(y_values)))

    if x_max <= x_min or y_max <= y_min:
        return None, clipped

    return (
        (x_min + x_max) / 2,
        (y_min + y_max) / 2,
        x_max - x_min,
        y_max - y_min,
    ), clipped


def parse_label_line(
    line: str,
    source_names: list[str],
    name_mapping: dict[str, int],
    id_mapping: dict[str, int],
) -> tuple[ParsedLabel | None, str | None]:
    parts = line.strip().split()
    if not parts:
        return None, None

    try:
        source_class_id = int(parts[0])
        coords = [float(value) for value in parts[1:]]
    except ValueError:
        return None, "invalid_numeric_values"

    target_class_id, class_name = map_source_class(
        source_class_id=source_class_id,
        source_names=source_names,
        name_mapping=name_mapping,
        id_mapping=id_mapping,
    )
    if target_class_id is None:
        return None, f"unmapped:{class_name}"

    if len(coords) == 4:
        bbox, clipped = clipped_bbox_from_bbox(coords)
        converted_polygon = False
    else:
        bbox, clipped = bbox_from_polygon(coords)
        converted_polygon = True

    if bbox is None:
        return None, "invalid_bbox"

    center_x, center_y, width, height = bbox
    remapped_line = (
        f"{target_class_id} {center_x:.6f} {center_y:.6f} "
        f"{width:.6f} {height:.6f}"
    )
    return (
        ParsedLabel(
            target_class_id=target_class_id,
            line=remapped_line,
            source_class_name=class_name,
            clipped=clipped,
            converted_polygon=converted_polygon,
        ),
        None,
    )


def validate_image_file(image_path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            image.verify()
            return image.width > 0 and image.height > 0
    except Exception:
        return False


def image_paths_under(image_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in image_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )


def collect_source_items(
    mapping: dict[str, Any],
    source_dirs: dict[str, Path],
    keep_empty_images: bool,
) -> tuple[list[SourceItem], dict[str, Any]]:
    stats: dict[str, Any] = {
        "sources": {},
        "validation": {
            "invalid_images": 0,
            "missing_label_files": 0,
            "invalid_label_rows": 0,
            "removed_unmapped_labels": 0,
            "empty_images_skipped": 0,
            "clipped_boxes": 0,
            "segmentation_polygons_converted": 0,
        },
    }
    items: list[SourceItem] = []

    for dataset_config in mapping["datasets"]:
        source_name = dataset_config["name"]
        display_name = dataset_config.get("display_name", source_name)
        source_dir = source_dirs[source_name]
        data_yaml = find_data_yaml(source_dir)
        if not data_yaml:
            raise FileNotFoundError(f"Missing data.yaml for {source_name}: {source_dir}")

        yaml_info = parse_yolo_yaml(data_yaml)
        source_names = yaml_info["names"]
        name_mapping, id_mapping = build_source_mapping(mapping, dataset_config)
        split_dirs = discover_split_dirs(data_yaml, yaml_info)
        source_stats = {
            "display_name": display_name,
            "data_yaml": str(data_yaml),
            "source_classes": source_names,
            "images_seen": 0,
            "images_kept": 0,
            "labels_seen": 0,
            "labels_kept": 0,
            "class_counts": collections.Counter(),
            "removed_by_reason": collections.Counter(),
            "removed_by_source_class": collections.Counter(),
        }

        for original_split, image_dir, label_dir in split_dirs:
            for image_path in image_paths_under(image_dir):
                source_stats["images_seen"] += 1
                if not validate_image_file(image_path):
                    stats["validation"]["invalid_images"] += 1
                    source_stats["removed_by_reason"]["invalid_image"] += 1
                    continue

                relative_image = image_path.relative_to(image_dir)
                label_path = label_dir / relative_image.with_suffix(".txt")
                parsed_labels: list[ParsedLabel] = []
                if not label_path.exists():
                    stats["validation"]["missing_label_files"] += 1
                    source_stats["removed_by_reason"]["missing_label_file"] += 1
                else:
                    for label_line in label_path.read_text(encoding="utf-8").splitlines():
                        if not label_line.strip():
                            continue
                        source_stats["labels_seen"] += 1
                        parsed_label, removal_reason = parse_label_line(
                            line=label_line,
                            source_names=source_names,
                            name_mapping=name_mapping,
                            id_mapping=id_mapping,
                        )
                        if parsed_label:
                            parsed_labels.append(parsed_label)
                            source_stats["labels_kept"] += 1
                            source_stats["class_counts"][parsed_label.target_class_id] += 1
                            if parsed_label.clipped:
                                stats["validation"]["clipped_boxes"] += 1
                            if parsed_label.converted_polygon:
                                stats["validation"]["segmentation_polygons_converted"] += 1
                        elif removal_reason:
                            source_stats["removed_by_reason"][removal_reason] += 1
                            if removal_reason.startswith("unmapped:"):
                                stats["validation"]["removed_unmapped_labels"] += 1
                                source_class = removal_reason.split(":", 1)[1]
                                source_stats["removed_by_source_class"][source_class] += 1
                            else:
                                stats["validation"]["invalid_label_rows"] += 1

                if not parsed_labels and not keep_empty_images:
                    stats["validation"]["empty_images_skipped"] += 1
                    source_stats["removed_by_reason"]["no_target_labels"] += 1
                    continue

                source_stats["images_kept"] += 1
                items.append(
                    SourceItem(
                        source_name=source_name,
                        source_display_name=display_name,
                        image_path=image_path,
                        label_lines=tuple(label.line for label in parsed_labels),
                        original_split=original_split,
                    )
                )

        stats["sources"][source_name] = counter_to_dict(source_stats)

    return items, stats


def counter_to_dict(value: Any) -> Any:
    if isinstance(value, collections.Counter):
        return {str(key): count for key, count in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, dict):
        return {key: counter_to_dict(child_value) for key, child_value in value.items()}
    if isinstance(value, list):
        return [counter_to_dict(child_value) for child_value in value]
    return value


def split_items(items: list[SourceItem], train_ratio: float, seed: int) -> dict[str, list[SourceItem]]:
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    train_count = int(round(len(shuffled) * train_ratio))
    if len(shuffled) > 1:
        train_count = min(len(shuffled) - 1, max(1, train_count))
    return {"train": shuffled[:train_count], "val": shuffled[train_count:]}


def clean_output_dir(output_dir: Path) -> None:
    for child_name in ("train", "val", "valid", "test", "images", "labels"):
        child_path = output_dir / child_name
        if child_path.exists():
            shutil.rmtree(child_path)
    for file_name in ("data.yaml", "dataset_report.md", "dataset_stats.json"):
        file_path = output_dir / file_name
        if file_path.exists():
            file_path.unlink()


def unique_output_name(item: SourceItem, index: int) -> str:
    digest = hashlib.sha1(str(item.image_path).encode("utf-8")).hexdigest()[:10]
    return (
        f"{item.source_name}_{index:06d}_"
        f"{sanitize_stem(item.image_path.stem)}_{digest}{item.image_path.suffix.lower()}"
    )


def write_split_dataset(
    output_dir: Path,
    splits: dict[str, list[SourceItem]],
    mapping: dict[str, Any],
    clean_output: bool,
) -> dict[str, Any]:
    if clean_output:
        clean_output_dir(output_dir)

    taxonomy = {int(class_id): name for class_id, name in mapping["taxonomy"].items()}
    split_stats: dict[str, Any] = {}
    global_index = 0

    for split_name, split_items_for_name in splits.items():
        image_out_dir = output_dir / split_name / "images"
        label_out_dir = output_dir / split_name / "labels"
        image_out_dir.mkdir(parents=True, exist_ok=True)
        label_out_dir.mkdir(parents=True, exist_ok=True)

        class_counts: collections.Counter[int] = collections.Counter()
        label_count = 0
        for item in split_items_for_name:
            output_name = unique_output_name(item, global_index)
            global_index += 1
            output_image = image_out_dir / output_name
            output_label = label_out_dir / f"{Path(output_name).stem}.txt"
            shutil.copy2(item.image_path, output_image)
            output_label.write_text("\n".join(item.label_lines) + "\n", encoding="utf-8")

            for label_line in item.label_lines:
                class_id = int(label_line.split()[0])
                class_counts[class_id] += 1
                label_count += 1

        split_stats[split_name] = {
            "images": len(split_items_for_name),
            "labels": label_count,
            "class_counts": {
                taxonomy[class_id]: class_counts.get(class_id, 0)
                for class_id in sorted(taxonomy)
            },
        }

    return split_stats


def write_data_yaml(output_dir: Path, mapping: dict[str, Any], root: Path) -> None:
    taxonomy = {int(class_id): name for class_id, name in mapping["taxonomy"].items()}
    names_lines = "\n".join(f"  {class_id}: {taxonomy[class_id]}" for class_id in sorted(taxonomy))
    try:
        dataset_path = output_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        dataset_path = output_dir.resolve().as_posix()
    content = (
        f"path: {dataset_path}\n"
        "train: train/images\n"
        "val: val/images\n"
        "\n"
        f"nc: {len(taxonomy)}\n"
        "names:\n"
        f"{names_lines}\n"
    )
    (output_dir / "data.yaml").write_text(content, encoding="utf-8")


def validate_output_dataset(output_dir: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    taxonomy = {int(class_id): name for class_id, name in mapping["taxonomy"].items()}
    validation = {
        "missing_label_files": 0,
        "orphan_label_files": 0,
        "invalid_rows": 0,
        "invalid_class_ids": 0,
        "invalid_boxes": 0,
    }

    for split_name in ("train", "val"):
        image_dir = output_dir / split_name / "images"
        label_dir = output_dir / split_name / "labels"
        image_stems = {image_path.stem for image_path in image_paths_under(image_dir)}
        label_stems = {label_path.stem for label_path in label_dir.glob("*.txt")}
        validation["missing_label_files"] += len(image_stems - label_stems)
        validation["orphan_label_files"] += len(label_stems - image_stems)

        for label_path in label_dir.glob("*.txt"):
            for row in label_path.read_text(encoding="utf-8").splitlines():
                if not row.strip():
                    continue
                parts = row.split()
                if len(parts) != 5:
                    validation["invalid_rows"] += 1
                    continue
                try:
                    class_id = int(parts[0])
                    coords = [float(value) for value in parts[1:]]
                except ValueError:
                    validation["invalid_rows"] += 1
                    continue
                if class_id not in taxonomy:
                    validation["invalid_class_ids"] += 1
                bbox, _ = clipped_bbox_from_bbox(coords)
                if bbox is None:
                    validation["invalid_boxes"] += 1

    return validation


def write_reports(
    output_dir: Path,
    mapping: dict[str, Any],
    split_stats: dict[str, Any],
    source_stats: dict[str, Any],
    final_validation: dict[str, Any],
    train_ratio: float,
    seed: int,
) -> None:
    taxonomy = {int(class_id): name for class_id, name in mapping["taxonomy"].items()}
    stats = {
        "generated_at_unix": int(time.time()),
        "taxonomy": {str(class_id): taxonomy[class_id] for class_id in sorted(taxonomy)},
        "train_ratio": train_ratio,
        "seed": seed,
        "splits": split_stats,
        "sources": source_stats["sources"],
        "pre_merge_validation": source_stats["validation"],
        "final_validation": final_validation,
    }
    (output_dir / "dataset_stats.json").write_text(
        json.dumps(counter_to_dict(stats), indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "# SiteCheck AI Dataset Statistics Report",
        "",
        "## Target taxonomy",
        "",
    ]
    for class_id in sorted(taxonomy):
        report_lines.append(f"- {class_id}: {taxonomy[class_id]}")

    report_lines.extend(
        [
            "",
            "## Split summary",
            "",
            "| split | images | labels | beam | column | wall | rebar | slab |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for split_name in ("train", "val"):
        split = split_stats.get(split_name, {})
        class_counts = split.get("class_counts", {})
        report_lines.append(
            f"| {split_name} | {split.get('images', 0)} | {split.get('labels', 0)} | "
            f"{class_counts.get('beam', 0)} | {class_counts.get('column', 0)} | "
            f"{class_counts.get('wall', 0)} | {class_counts.get('rebar', 0)} | "
            f"{class_counts.get('slab', 0)} |"
        )

    report_lines.extend(["", "## Source summary", ""])
    for source_name, source in source_stats["sources"].items():
        report_lines.extend(
            [
                f"### {source.get('display_name', source_name)}",
                "",
                f"- Images seen: {source.get('images_seen', 0)}",
                f"- Images kept: {source.get('images_kept', 0)}",
                f"- Labels seen: {source.get('labels_seen', 0)}",
                f"- Labels kept: {source.get('labels_kept', 0)}",
                f"- Removed by reason: {source.get('removed_by_reason', {})}",
                f"- Removed unmapped source classes: {source.get('removed_by_source_class', {})}",
                "",
            ]
        )

    report_lines.extend(
        [
            "## Validation",
            "",
            f"- Pre-merge validation: {source_stats['validation']}",
            f"- Final validation: {final_validation}",
            "",
            "## Outputs",
            "",
            f"- data.yaml: {output_dir / 'data.yaml'}",
            f"- stats JSON: {output_dir / 'dataset_stats.json'}",
        ]
    )
    (output_dir / "dataset_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def prepare_dataset(args: argparse.Namespace) -> None:
    root = repo_root()
    mapping_path = (root / args.mapping).resolve() if not Path(args.mapping).is_absolute() else Path(args.mapping)
    raw_dir = (root / args.raw_dir).resolve() if not Path(args.raw_dir).is_absolute() else Path(args.raw_dir)
    output_dir = (root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)

    mapping = load_mapping(mapping_path)
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_dirs = ensure_sources(
        mapping=mapping,
        raw_dir=raw_dir,
        skip_download=args.skip_download,
        force_download=args.force_download,
        api_key=args.roboflow_api_key or os.getenv("ROBOFLOW_API_KEY"),
    )
    items, source_stats = collect_source_items(
        mapping=mapping,
        source_dirs=source_dirs,
        keep_empty_images=args.keep_empty_images,
    )
    if not items:
        raise RuntimeError("No target-class images were available after remapping.")

    splits = split_items(items=items, train_ratio=args.train_ratio, seed=args.seed)
    split_stats = write_split_dataset(
        output_dir=output_dir,
        splits=splits,
        mapping=mapping,
        clean_output=not args.no_clean_output,
    )
    write_data_yaml(output_dir=output_dir, mapping=mapping, root=root)
    final_validation = validate_output_dataset(output_dir=output_dir, mapping=mapping)
    write_reports(
        output_dir=output_dir,
        mapping=mapping,
        split_stats=split_stats,
        source_stats=source_stats,
        final_validation=final_validation,
        train_ratio=args.train_ratio,
        seed=args.seed,
    )

    final_errors = sum(final_validation.values())
    print(f"Prepared SiteCheck YOLO dataset at {output_dir}")
    print(f"Train images: {split_stats['train']['images']}")
    print(f"Val images: {split_stats['val']['images']}")
    print(f"Final validation errors: {final_errors}")
    print(f"Report: {output_dir / 'dataset_report.md'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download, remap, merge, split, and validate SiteCheck YOLOv8 datasets."
    )
    parser.add_argument("--mapping", default="dataset_mapping.json")
    parser.add_argument("--raw-dir", default="data/raw_datasets")
    parser.add_argument("--output", default="data/yolo")
    parser.add_argument("--train-ratio", type=float, default=TARGET_TRAIN_RATIO)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--roboflow-api-key", default=None)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--keep-empty-images", action="store_true")
    parser.add_argument("--no-clean-output", action="store_true")
    args = parser.parse_args()

    if not 0 < args.train_ratio < 1:
        parser.error("--train-ratio must be between 0 and 1")
    return args


def main() -> None:
    try:
        prepare_dataset(parse_args())
    except (OSError, RuntimeError, ValueError, urllib.error.URLError) as error:
        raise SystemExit(f"Dataset preparation failed: {error}") from error


if __name__ == "__main__":
    main()
