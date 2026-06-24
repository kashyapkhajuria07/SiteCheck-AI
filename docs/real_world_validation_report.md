# Real-World Validation Report — SiteCheck AI

**Run:** 2026-06-17 15:37:22
**Images evaluated:** 105

---

## Scene Classification

- **Accuracy:** 51.4% (54/105)

### Confusion Matrix

| Actual → Predicted | Count |
|-------------------|-------|
| construction_site->construction_site | 44 |
| structural_frame->construction_site | 24 |
| structural_frame->floor_plan | 27 |
| structural_frame->structural_frame | 10 |

## Detection Metrics

- **Precision:** 1.6%
- **Recall:** 3.8%
- **F1 Score:** 2.2%
- **True Positives:** 4
- **False Positives:** 247
- **False Negatives:** 101
- **Total Ground Truth Elements:** 105
- **Total Detected Elements:** 251

### Per-Label Detection Breakdown

| Label | GT | Detected | TP | FP | FN | Precision | Recall |
|-------|----|----------|----|----|----|-----------|--------|
| beam | 45 | 4 | 1 | 3 | 44 | 25.0% | 2.2% |
| column | 0 | 0 | 0 | 0 | 0 | 0.0% | 0.0% |
| door | 30 | 12 | 1 | 11 | 29 | 8.3% | 3.3% |
| wall | 30 | 235 | 2 | 233 | 28 | 0.9% | 6.7% |

### Category-Wise Accuracy

| Category | Images | Scene Acc. | TP | FP | FN | Precision | Recall |
|----------|--------|------------|----|----|----|-----------|--------|
| construction_site | 44 | 100.0% | 0 | 42 | 44 | 0.0% | 0.0% |
| structural_frame | 61 | 16.4% | 4 | 205 | 57 | 1.9% | 6.6% |

## Trust Score Metrics

- **Average Trust Score:** 80.2/100
- **Detections scored:** 251

## Outcome Distribution

| Outcome | Count |
|---------|-------|
| FAIL | 74 |
| MISCLASSIFIED | 27 |
| PARTIAL | 4 |

## Detection Volume

- **Average detections per image:** 2.4

---

*Report generated automatically by `validate_real_world.py`*

