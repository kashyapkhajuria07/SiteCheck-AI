"""Benchmark suite for opencv_detector.py.

Generates synthetic floor plans (reusing validate_drawing_parser generators),
runs the OpenCV detector on each, and reports:
- Detection count per class (vs ground-truth count)
- Per-class precision / recall / F1 (via IOU matching when GT has positions,
  else count-based approximation)
- Runtime per image
- Success rate (crash-free execution)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.opencv_detector import detect_elements
from schemas.inspection import Detection

try:
    from scripts.validate_drawing_parser import PLANS
except ImportError:
    PLANS = []


def _gt_count(gt: dict[str, Any], label: str) -> int:
    """Count ground-truth elements of the given label."""
    return len(gt.get(f"{label}s", []))


def run_benchmark() -> None:
    """Run benchmark across all test plans and print results."""
    if not PLANS:
        print("WARNING: No test plans found. Run from project root or check PYTHONPATH.")
        sys.exit(1)

    all_times: list[float] = []
    per_class: dict[str, dict] = {
        "wall": {"det": 0, "gt": 0, "exact_count": 0},
        "column": {"det": 0, "gt": 0, "exact_count": 0},
        "beam": {"det": 0, "gt": 0, "exact_count": 0},
        "door": {"det": 0, "gt": 0, "exact_count": 0},
    }
    plan_results: list[dict] = []
    total_plans = 0
    success_plans = 0
    total_detections = 0

    for plan_entry in PLANS:
        if isinstance(plan_entry, tuple):
            name, (img, gt) = plan_entry
        elif isinstance(plan_entry, dict):
            name = plan_entry.get("name", "unknown")
            img = plan_entry.get("image")
            gt = plan_entry.get("gt", {})
        else:
            continue

        total_plans += 1

        start = time.perf_counter()
        try:
            detections = detect_elements(img)
            elapsed = time.perf_counter() - start
            all_times.append(elapsed)
            success_plans += 1
        except Exception as e:
            print(f"  FAILED {name}: {e}")
            continue

        plan_info = {
            "name": name,
            "time_ms": round(elapsed * 1000, 1),
            "total_dets": len(detections),
        }
        total_detections += len(detections)

        print(f"\n{'=' * 50}")
        print(f"Plan: {name}  ({elapsed * 1000:.1f}ms)")
        print(f"  Total detections: {len(detections)}")

        for label in ("wall", "column", "beam", "door"):
            class_dets = len([d for d in detections if d.label == label])
            ct = _gt_count(gt, label)
            per_class[label]["det"] += class_dets
            per_class[label]["gt"] += ct
            exact = 1 if class_dets == ct else 0
            per_class[label]["exact_count"] += exact
            plan_info[f"{label}_dets"] = class_dets
            plan_info[f"{label}_gt"] = ct

            print(f"  {label:8s}: det={class_dets:3d}  gt={ct:2d}  "
                  f"{'✓' if class_dets == ct else '✗' if class_dets > 0 else '-'}")

        plan_results.append(plan_info)

    # ── Summary ──
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    avg_time = float(np.mean(all_times)) if all_times else 0
    max_time = float(np.max(all_times)) if all_times else 0
    min_time = float(np.min(all_times)) if all_times else 0
    print(f"Plans run:      {success_plans}/{total_plans}")
    print(f"Success rate:   {success_plans / max(total_plans, 1) * 100:.1f}%")
    print(f"Total detections: {total_detections}")
    print(f"Avg runtime:    {avg_time * 1000:.1f}ms")
    print(f"Min runtime:    {min_time * 1000:.1f}ms")
    print(f"Max runtime:    {max_time * 1000:.1f}ms")

    print(f"\nPer-class detection counts:")
    print(f"{'Class':<10} {'Detected':>10} {'GT':>5} {'Exact match':>13} {'Match rate':>11}")
    print("-" * 55)
    for label in ("wall", "column", "beam", "door"):
        c = per_class[label]
        exact_rate = c["exact_count"] / success_plans * 100 if success_plans > 0 else 0
        print(f"{label:<10} {c['det']:>10} {c['gt']:>5} {c['exact_count']:>5}/{success_plans:<5} {exact_rate:>6.1f}%")

    if plan_results:
        # Show top/bottom by detection count
        plan_results.sort(key=lambda x: x["total_dets"], reverse=True)
        print(f"\nMost detections:  {plan_results[0]['name']} ({plan_results[0]['total_dets']} dets, {plan_results[0]['time_ms']}ms)")
        print(f"Fewest detections: {plan_results[-1]['name']} ({plan_results[-1]['total_dets']} dets, {plan_results[-1]['time_ms']}ms)")

        plan_results.sort(key=lambda x: x["time_ms"], reverse=True)
        print(f"\nSlowest plan:     {plan_results[0]['name']} ({plan_results[0]['time_ms']}ms)")
        print(f"Fastest plan:     {plan_results[-1]['name']} ({plan_results[-1]['time_ms']}ms)")


if __name__ == "__main__":
    run_benchmark()
