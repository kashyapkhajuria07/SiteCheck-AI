"""Real-world validation benchmark for SiteCheck AI.

Evaluates scene classification accuracy, detection precision/recall,
false positive/negative rates, and average trust score against
a labelled ground-truth dataset.

Usage:
    cd backend
    ../.venv/bin/python scripts/validate_real_world.py

Output:
    - Console summary
    - docs/real_world_validation_report.md
    - debug/validation_results.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.opencv_detector import detect_elements, compute_validation_log, _detect_all_raw
from modules.scene_classifier import SceneType, classify_scene, is_allowed_scene
from modules.roi_filter import filter_structural
from schemas.inspection import Detection


GROUND_TRUTH_PATH = PROJECT_ROOT.parent / "validation_ground_truth.json"
VALIDATION_ROOT = PROJECT_ROOT.parent / "validation_dataset"
OUTPUT_DIR = PROJECT_ROOT / "scripts" / "validation_output"


def load_ground_truth(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def compute_iou(a: list[int], b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def match_detections(
    detections: list[Detection],
    expected_elements: dict[str, int],
    iou_thresh: float = 0.3,
) -> dict:
    matched = set()
    true_positives = 0
    false_positives = 0

    gt_by_label: dict[str, int] = {}
    for label, count in expected_elements.items():
        singular = label.rstrip("s") if label.endswith("s") else label
        gt_by_label[singular] = count

    detected_by_label: dict[str, list[Detection]] = defaultdict(list)
    for d in detections:
        detected_by_label[d.label].append(d)

    per_label_results: dict[str, dict] = {}

    all_labels = set(list(gt_by_label.keys()) + list(detected_by_label.keys()))
    for label in sorted(all_labels):
        gt_count = gt_by_label.get(label, 0)
        det_count = len(detected_by_label.get(label, []))
        tp = min(gt_count, det_count)
        fp = max(0, det_count - gt_count)
        fn = max(0, gt_count - det_count)
        per_label_results[label] = {
            "ground_truth": gt_count,
            "detected": det_count,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
        }
        true_positives += tp
        false_positives += fp

    total_expected = sum(gt_by_label.values())
    false_negatives = total_expected - true_positives

    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "total_expected": total_expected,
        "total_detected": len(detections),
        "per_label": per_label_results,
    }


def run_validation() -> dict:
    gt = load_ground_truth(GROUND_TRUTH_PATH)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results: list[dict] = []
    scene_confusion = Counter()
    scene_correct = 0
    scene_total = 0

    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_expected_elements = 0
    total_detected_elements = 0
    trust_scores: list[float] = []
    detection_counts: list[int] = []

    for entry in gt:
        rel_path = entry["image"]
        img_path = VALIDATION_ROOT / rel_path

        if not img_path.exists():
            print(f"  SKIP  {rel_path}  (file not found)")
            continue

        bgr = cv2.imread(str(img_path))
        if bgr is None:
            print(f"  SKIP  {rel_path}  (unreadable)")
            continue

        gt_scene = entry["scene_type"]
        should_inspect = entry["should_inspect"]
        gt_elements = entry.get("expected_elements", {})

        # ── Scene classification ──
        pred_scene, scene_conf = classify_scene(bgr)
        scene_total += 1
        gt_scene_enum = SceneType(gt_scene) if gt_scene in {s.value for s in SceneType} else SceneType.UNKNOWN

        if pred_scene == gt_scene_enum:
            scene_correct += 1
        scene_confusion[f"{gt_scene}->{pred_scene.value}"] += 1

        scene_allowed = is_allowed_scene(pred_scene)
        gt_allowed = is_allowed_scene(gt_scene_enum)

        # ── Detection (only if scene should be inspected) ──
        detections: list[Detection] = []
        val_log: dict = {}

        if should_inspect and scene_allowed:
            raw = _detect_all_raw(bgr)
            detections = detect_elements(bgr)
            roied = filter_structural(bgr, detections, scene_type=pred_scene.value)
            val_log = compute_validation_log(bgr, raw, roied, roi_filtered=roied)
            detections = roied

            # Trust scores
            for d in detections:
                trust_scores.append(d.trust_score)
        elif should_inspect and not scene_allowed:
            pass  # Detection suppressed due to wrong scene classification

        detection_counts.append(len(detections))

        # ── Matching ──
        match = match_detections(detections, gt_elements)
        total_tp += match["true_positives"]
        total_fp += match["false_positives"]
        total_fn += match["false_negatives"]
        total_expected_elements += match["total_expected"]
        total_detected_elements += match["total_detected"]

        # Classify this result
        if should_inspect and scene_allowed:
            if match["true_positives"] >= match["total_expected"] and match["false_positives"] == 0:
                outcome = "PASS"
            elif match["true_positives"] > 0:
                outcome = "PARTIAL"
            else:
                outcome = "FAIL"
        elif should_inspect and not scene_allowed:
            outcome = "MISCLASSIFIED"
        else:
            outcome = "CORRECTLY_SKIPPED"

        results.append({
            "image": rel_path,
            "gt_scene": gt_scene,
            "pred_scene": pred_scene.value,
            "scene_confidence": round(scene_conf, 3),
            "scene_correct": pred_scene == gt_scene_enum,
            "should_inspect": should_inspect,
            "inspected": scene_allowed,
            "outcome": outcome,
            "gt_elements": gt_elements,
            "detections": {d.label: d.confidence for d in detections},
            "detection_counts": {
                "walls": sum(1 for d in detections if d.label == "wall"),
                "columns": sum(1 for d in detections if d.label == "column"),
                "doors": sum(1 for d in detections if d.label == "door"),
                "beams": sum(1 for d in detections if d.label == "beam"),
            },
            "match": match,
        })

    # ── Aggregate metrics ──
    scene_accuracy = scene_correct / scene_total if scene_total > 0 else 0.0
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_trust = np.mean(trust_scores) if trust_scores else 0.0
    avg_dets = np.mean(detection_counts) if detection_counts else 0.0

    outcomes = Counter(r["outcome"] for r in results)

    return {
        "num_images": len(results),
        "scene_classification": {
            "correct": scene_correct,
            "total": scene_total,
            "accuracy": round(scene_accuracy, 4),
            "confusion": dict(scene_confusion),
        },
        "detection_metrics": {
            "true_positives": total_tp,
            "false_positives": total_fp,
            "false_negatives": total_fn,
            "total_expected": total_expected_elements,
            "total_detected": total_detected_elements,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
        },
        "trust_metrics": {
            "average_trust_score": round(avg_trust, 1),
            "num_scored": len(trust_scores),
        },
        "detection_counts": {
            "average_per_image": round(avg_dets, 1),
        },
        "outcomes": dict(outcomes),
        "results": results,
    }


def generate_report(stats: dict):
    report_path = PROJECT_ROOT.parent / "docs" / "real_world_validation_report.md"
    os.makedirs(report_path.parent, exist_ok=True)

    lines = []
    lines.append("# Real-World Validation Report — SiteCheck AI")
    lines.append("")
    lines.append(f"**Run:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Images evaluated:** {stats['num_images']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Scene Classification ──
    sc = stats["scene_classification"]
    lines.append("## Scene Classification")
    lines.append("")
    lines.append(f"- **Accuracy:** {sc['accuracy'] * 100:.1f}% ({sc['correct']}/{sc['total']})")
    lines.append("")

    lines.append("### Confusion Matrix")
    lines.append("")
    lines.append("| Actual → Predicted | Count |")
    lines.append("|-------------------|-------|")
    for pair, count in sorted(sc["confusion"].items()):
        lines.append(f"| {pair} | {count} |")
    lines.append("")

    # ── Detection Metrics ──
    dm = stats["detection_metrics"]
    lines.append("## Detection Metrics")
    lines.append("")
    lines.append(f"- **Precision:** {dm['precision'] * 100:.1f}%")
    lines.append(f"- **Recall:** {dm['recall'] * 100:.1f}%")
    lines.append(f"- **F1 Score:** {dm['f1_score'] * 100:.1f}%")
    lines.append(f"- **True Positives:** {dm['true_positives']}")
    lines.append(f"- **False Positives:** {dm['false_positives']}")
    lines.append(f"- **False Negatives:** {dm['false_negatives']}")
    lines.append(f"- **Total Ground Truth Elements:** {dm['total_expected']}")
    lines.append(f"- **Total Detected Elements:** {dm['total_detected']}")
    lines.append("")

    # ── Per-label breakdown ──
    lines.append("### Per-Label Detection Breakdown")
    lines.append("")
    lines.append("| Label | GT | Detected | TP | FP | FN | Precision | Recall |")
    lines.append("|-------|----|----------|----|----|----|-----------|--------|")
    per_label_agg: dict[str, dict] = {}
    for r in stats["results"]:
        for label, m in r["match"].get("per_label", {}).items():
            if label not in per_label_agg:
                per_label_agg[label] = {"gt": 0, "det": 0, "tp": 0, "fp": 0, "fn": 0}
            per_label_agg[label]["gt"] += m["ground_truth"]
            per_label_agg[label]["det"] += m["detected"]
            per_label_agg[label]["tp"] += m["true_positives"]
            per_label_agg[label]["fp"] += m["false_positives"]
            per_label_agg[label]["fn"] += m["false_negatives"]

    for label in sorted(per_label_agg.keys()):
        m = per_label_agg[label]
        prec = m["tp"] / (m["tp"] + m["fp"]) * 100 if (m["tp"] + m["fp"]) > 0 else 0
        rec = m["tp"] / (m["tp"] + m["fn"]) * 100 if (m["tp"] + m["fn"]) > 0 else 0
        lines.append(f"| {label} | {m['gt']} | {m['det']} | {m['tp']} | {m['fp']} | {m['fn']} | {prec:.1f}% | {rec:.1f}% |")
    lines.append("")

    # ── Category-wise Accuracy ──
    lines.append("### Category-Wise Accuracy")
    lines.append("")
    by_category: dict[str, dict] = {}
    for r in stats["results"]:
        cat = r["gt_scene"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "correct": 0, "tp": 0, "fp": 0, "fn": 0}
        by_category[cat]["total"] += 1
        if r["scene_correct"]:
            by_category[cat]["correct"] += 1
        by_category[cat]["tp"] += r["match"]["true_positives"]
        by_category[cat]["fp"] += r["match"]["false_positives"]
        by_category[cat]["fn"] += r["match"]["false_negatives"]

    lines.append("| Category | Images | Scene Acc. | TP | FP | FN | Precision | Recall |")
    lines.append("|----------|--------|------------|----|----|----|-----------|--------|")
    for cat in sorted(by_category.keys()):
        c = by_category[cat]
        acc = c["correct"] / c["total"] * 100 if c["total"] > 0 else 0
        prec = c["tp"] / (c["tp"] + c["fp"]) * 100 if (c["tp"] + c["fp"]) > 0 else 0
        rec = c["tp"] / (c["tp"] + c["fn"]) * 100 if (c["tp"] + c["fn"]) > 0 else 0
        lines.append(f"| {cat} | {c['total']} | {acc:.1f}% | {c['tp']} | {c['fp']} | {c['fn']} | {prec:.1f}% | {rec:.1f}% |")
    lines.append("")

    # ── Trust Metrics ──
    tm = stats["trust_metrics"]
    lines.append("## Trust Score Metrics")
    lines.append("")
    lines.append(f"- **Average Trust Score:** {tm['average_trust_score']}/100")
    lines.append(f"- **Detections scored:** {tm['num_scored']}")
    lines.append("")

    # ── Outcome distribution ──
    lines.append("## Outcome Distribution")
    lines.append("")
    lines.append("| Outcome | Count |")
    lines.append("|---------|-------|")
    for outcome, count in sorted(stats["outcomes"].items()):
        lines.append(f"| {outcome} | {count} |")
    lines.append("")

    # ── Average detections ──
    lines.append("## Detection Volume")
    lines.append("")
    lines.append(f"- **Average detections per image:** {stats['detection_counts']['average_per_image']}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Report generated automatically by `validate_real_world.py`*")
    lines.append("")

    with open(report_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Report written to {report_path}")


def main():
    print("=" * 60)
    print("  SiteCheck AI — Real-World Validation Benchmark")
    print("=" * 60)
    print()

    stats = run_validation()

    print()
    print("─" * 50)
    print("SUMMARY")
    print("─" * 50)
    sc = stats["scene_classification"]
    print(f"  Scene Accuracy:        {sc['accuracy'] * 100:.1f}%  ({sc['correct']}/{sc['total']})")
    dm = stats["detection_metrics"]
    print(f"  Precision:             {dm['precision'] * 100:.1f}%")
    print(f"  Recall:                {dm['recall'] * 100:.1f}%")
    print(f"  F1 Score:             {dm['f1_score'] * 100:.1f}%")
    tm = stats["trust_metrics"]
    print(f"  Avg Trust Score:      {tm['average_trust_score']:.1f}/100")
    dc = stats["detection_counts"]
    print(f"  Avg Detections/Image: {dc['average_per_image']:.1f}")
    print(f"  Images:               {stats['num_images']}")
    print(f"  TP: {dm['true_positives']}  FP: {dm['false_positives']}  FN: {dm['false_negatives']}")
    print(f"  Outcome distribution: {json.dumps(stats['outcomes'])}")

    # Save detailed JSON
    json_path = OUTPUT_DIR / "validation_results.json"
    with open(json_path, "w") as f:
        json.dump(stats, f, indent=2, default=str)
    print(f"\n  Detailed results: {json_path}")

    generate_report(stats)


if __name__ == "__main__":
    main()
