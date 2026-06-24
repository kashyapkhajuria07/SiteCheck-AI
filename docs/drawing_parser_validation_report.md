# Drawing Parser Validation Report

**Date:** 2026-06-15 21:51
**Plans tested:** 20
**Plan scale:** 0.5 px/mm

---

## Overall Accuracy Summary

| Category | Precision | Recall | F1-Score | Target | Met? |
|----------|-----------|--------|----------|--------|------|
| Doors | 54.8% | 90.9% | 68.4% | 90% | ❌ |
| Columns | 100.0% | 56.7% | 72.4% | 85% | ❌ |
| Beams | 5.6% | 100.0% | 10.6% | 85% | ❌ |
| Walls | 15.6% | 100.0% | 26.9% | 85% | ❌ |
| **Overall** | **21.7%** | **77.7%** | **33.9%** | **85%** | ❌ |

---

## Dimension Extraction Accuracy

Average dimension deviation across all true-positive matches:

| Category | Mean Error % | Within 5% | Within 10% | Within 15% |
|----------|-------------|-----------|------------|------------|
| Doors | 2.7% | 85.0% | 92.5% | 92.5% |
| Columns | 4.2% | 94.7% | 94.7% | 100.0% |
| Beams | 0.2% | 100.0% | 100.0% | 100.0% |
| Walls | 1.3% | 100.0% | 100.0% | 100.0% |

---

## Confusion Matrices

### Doors

| | Predicted Yes | Predicted No |
|--------------|--------------|--------------|
| Actual Yes | 40 | 4 |
| Actual No | 33 | — |

### Columns

| | Predicted Yes | Predicted No |
|--------------|--------------|--------------|
| Actual Yes | 38 | 29 |
| Actual No | 0 | — |

### Beams

| | Predicted Yes | Predicted No |
|--------------|--------------|--------------|
| Actual Yes | 16 | 0 |
| Actual No | 269 | — |

### Walls

| | Predicted Yes | Predicted No |
|--------------|--------------|--------------|
| Actual Yes | 21 | 0 |
| Actual No | 114 | — |

---

## Per-Plan Detailed Results

| # | Plan | GT | Extracted | Doors (P/R/F1) | Walls (P/R/F1) | Columns (P/R/F1) | Beams (P/R/F1) |
|---|------|----|-----------|----------------|----------------|------------------|----------------|
| 01 | basic_1door | 2 | 6 | 50/100/67 | 0/0/0 | 0/0/0 | 25/100/40 |
| 02 | basic_2doors_1col | 4 | 14 | 40/100/57 | 100/100/100 | 0/0/0 | 20/100/33 |
| 03 | basic_1door_1beam_1col | 4 | 16 | 50/100/67 | 100/100/100 | 14/100/25 | 17/100/29 |
| 04 | basic_2doors_2beams_1col | 6 | 26 | 50/100/67 | 0/0/0 | 11/100/20 | 25/100/40 |
| 05 | basic_3doors_2cols_1beam | 7 | 19 | 100/100/100 | 100/50/67 | 9/100/17 | 25/100/40 |
| 06 | medium_Lshape | 6 | 14 | 50/100/67 | 0/0/0 | 0/0/0 | 29/100/44 |
| 07 | medium_Tshape | 7 | 15 | 75/100/86 | 100/33/50 | 0/0/0 | 17/100/29 |
| 08 | medium_Ushape | 5 | 15 | 67/100/80 | 0/0/0 | 20/100/33 | 50/100/67 |
| 09 | medium_cross | 9 | 22 | 100/50/67 | 100/25/40 | 0/0/0 | 10/100/18 |
| 10 | medium_multroom | 11 | 31 | 71/100/83 | 0/0/0 | 12/100/22 | 12/100/22 |
| 11 | complex_industrial | 15 | 70 | 0/0/0 | 100/92/96 | 0/0/0 | 7/100/13 |
| 12 | complex_stairwell | 3 | 6 | 50/100/67 | 0/0/0 | 0/0/0 | 50/100/67 |
| 13 | complex_commercial | 23 | 129 | 25/100/40 | 100/90/95 | 0/0/0 | 4/100/7 |
| 14 | complex_grid | 16 | 70 | 33/100/50 | 100/12/22 | 11/100/19 | 10/100/18 |
| 15 | complex_residential | 10 | 29 | 71/100/83 | 100/67/80 | 7/100/13 | 17/100/29 |
| 16 | edge_smalldoors | 4 | 6 | 75/100/86 | 0/0/0 | 0/0/0 | 50/100/67 |
| 17 | edge_thickwalls | 2 | 5 | 50/100/67 | 0/0/0 | 0/0/0 | 33/100/50 |
| 18 | edge_irregular_cols | 5 | 5 | 50/100/67 | 0/0/0 | 0/0/0 | 33/100/50 |
| 19 | edge_overlap | 3 | 9 | 50/100/67 | 100/100/100 | 0/0/0 | 33/100/50 |
| 20 | edge_dense_text | 6 | 24 | 50/100/67 | 0/0/0 | 7/100/13 | 12/100/22 |

---

## Failure Analysis

### Doors — Below Target (68.4% vs 90%)

- **False Positives:** 33 — extracted items not in ground truth
- **False Negatives:** 4 — ground truth items not extracted

  - **basic_1door**: FN=0, FP=1
  - **basic_2doors_1col**: FN=0, FP=3
  - **basic_1door_1beam_1col**: FN=0, FP=1
  - **basic_2doors_2beams_1col**: FN=0, FP=2
  - **medium_Lshape**: FN=0, FP=2
  - **medium_Tshape**: FN=0, FP=1
  - **medium_Ushape**: FN=0, FP=1
  - **medium_cross**: FN=2, FP=0
  - **medium_multroom**: FN=0, FP=2
  - **complex_industrial**: FN=2, FP=3
  - **complex_stairwell**: FN=0, FP=2
  - **complex_commercial**: FN=0, FP=6
  - **complex_grid**: FN=0, FP=2
  - **complex_residential**: FN=0, FP=2
  - **edge_smalldoors**: FN=0, FP=1
  - **edge_thickwalls**: FN=0, FP=1
  - **edge_irregular_cols**: FN=0, FP=1
  - **edge_overlap**: FN=0, FP=1
  - **edge_dense_text**: FN=0, FP=1

### Columns — Below Target (72.4% vs 85%)

- **False Positives:** 0 — extracted items not in ground truth
- **False Negatives:** 29 — ground truth items not extracted

  - **basic_2doors_2beams_1col**: FN=1, FP=0
  - **basic_3doors_2cols_1beam**: FN=1, FP=0
  - **medium_Lshape**: FN=2, FP=0
  - **medium_Tshape**: FN=2, FP=0
  - **medium_cross**: FN=3, FP=0
  - **medium_multroom**: FN=3, FP=0
  - **complex_industrial**: FN=1, FP=0
  - **complex_commercial**: FN=2, FP=0
  - **complex_grid**: FN=7, FP=0
  - **complex_residential**: FN=1, FP=0
  - **edge_irregular_cols**: FN=3, FP=0
  - **edge_dense_text**: FN=3, FP=0

### Beams — Below Target (10.6% vs 85%)

- **False Positives:** 269 — extracted items not in ground truth
- **False Negatives:** 0 — ground truth items not extracted

  - **basic_2doors_1col**: FN=0, FP=3
  - **basic_1door_1beam_1col**: FN=0, FP=6
  - **basic_2doors_2beams_1col**: FN=0, FP=16
  - **basic_3doors_2cols_1beam**: FN=0, FP=10
  - **medium_Lshape**: FN=0, FP=3
  - **medium_Tshape**: FN=0, FP=4
  - **medium_Ushape**: FN=0, FP=8
  - **medium_cross**: FN=0, FP=9
  - **medium_multroom**: FN=0, FP=14
  - **complex_industrial**: FN=0, FP=42
  - **complex_commercial**: FN=0, FP=75
  - **complex_grid**: FN=0, FP=50
  - **complex_residential**: FN=0, FP=13
  - **edge_overlap**: FN=0, FP=3
  - **edge_dense_text**: FN=0, FP=13

### Walls — Below Target (26.9% vs 85%)

- **False Positives:** 114 — extracted items not in ground truth
- **False Negatives:** 0 — ground truth items not extracted

  - **basic_1door**: FN=0, FP=3
  - **basic_2doors_1col**: FN=0, FP=4
  - **basic_1door_1beam_1col**: FN=0, FP=5
  - **basic_2doors_2beams_1col**: FN=0, FP=3
  - **basic_3doors_2cols_1beam**: FN=0, FP=3
  - **medium_Lshape**: FN=0, FP=5
  - **medium_Tshape**: FN=0, FP=5
  - **medium_Ushape**: FN=0, FP=1
  - **medium_cross**: FN=0, FP=9
  - **medium_multroom**: FN=0, FP=7
  - **complex_industrial**: FN=0, FP=13
  - **complex_stairwell**: FN=0, FP=1
  - **complex_commercial**: FN=0, FP=27
  - **complex_grid**: FN=0, FP=9
  - **complex_residential**: FN=0, FP=5
  - **edge_smalldoors**: FN=0, FP=1
  - **edge_thickwalls**: FN=0, FP=2
  - **edge_irregular_cols**: FN=0, FP=2
  - **edge_overlap**: FN=0, FP=2
  - **edge_dense_text**: FN=0, FP=7

---

## OCR Accuracy

OCR accuracy measures how many dimension text labels were successfully read from the plans.

| Plan | Texts on Plan | OCR Found | Accuracy |
|------|--------------|-----------|----------|
| basic_1door | — | — | — |
| basic_2doors_1col | — | — | — |
| basic_1door_1beam_1col | — | — | — |
| basic_2doors_2beams_1col | — | — | — |
| basic_3doors_2cols_1beam | — | — | — |
| medium_Lshape | — | — | — |
| medium_Tshape | — | — | — |
| medium_Ushape | — | — | — |
| medium_cross | — | — | — |
| medium_multroom | — | — | — |
| complex_industrial | — | — | — |
| complex_stairwell | — | — | — |
| complex_commercial | — | — | — |
| complex_grid | — | — | — |
| complex_residential | — | — | — |
| edge_smalldoors | — | — | — |
| edge_thickwalls | — | — | — |
| edge_irregular_cols | — | — | — |
| edge_overlap | — | — | — |
| edge_dense_text | — | — | — |

*Note: OCR accuracy depends on EasyOCR model download and image quality.*

---

## Recommendations

Based on the validation results:

1. **Improve doors detection** (22% below target):
   - Increase precision: tighten validation criteria, add shape verification
   - Consider alternative detection strategy for edge cases

1. **Improve columns detection** (13% below target):
   - Increase recall: adjust detection thresholds, add fallback logic
   - Consider alternative detection strategy for edge cases

1. **Improve beams detection** (74% below target):
   - Increase precision: tighten validation criteria, add shape verification
   - Consider alternative detection strategy for edge cases

1. **Improve walls detection** (58% below target):
   - Increase precision: tighten validation criteria, add shape verification
   - Consider alternative detection strategy for edge cases

---

*Report generated automatically by `validate_drawing_parser.py` at 2026-06-15 21:51*