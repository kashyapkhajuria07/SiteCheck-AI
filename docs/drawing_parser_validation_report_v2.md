# Drawing Parser Validation Report v2

**Date:** 2026-06-16 21:29
**Plans tested:** 50
**Plan scale:** 0.5 px/mm

---

## Dataset Breakdown

| Category | Count |
|----------|-------|
| Architectural | 10 |
| Basic | 5 |
| Complex | 5 |
| Edge | 5 |
| Low-Quality Scan | 5 |
| Medium | 5 |
| Rotated | 5 |
| Structural | 10 |

**Total elements across all plans:** 447 ground truth, 607 extracted

---

## Overall Accuracy Summary

| Category | Precision | Recall | F1-Score | Target | Met? |
|----------|-----------|--------|----------|--------|------|
| Doors | 59.4% | 59.4% | 59.4% | 90% | ❌ |
| Columns | 88.9% | 92.3% | 90.6% | 85% | ✅ |
| Beams | 28.9% | 41.2% | 34.0% | 85% | ❌ |
| Walls | 30.1% | 91.4% | 45.3% | 85% | ❌ |
| **Overall** | **55.7%** | **75.6%** | **64.1%** | **85%** | ❌ |

---

## Confusion Matrices

### Doors

| | Predicted Yes | Predicted No |
|--------------|--------------|--------------|
| Actual Yes | **60** (TP) | **41** (FN) |
| Actual No | **41** (FP) | — |

### Columns

| | Predicted Yes | Predicted No |
|--------------|--------------|--------------|
| Actual Yes | **192** (TP) | **16** (FN) |
| Actual No | **24** (FP) | — |

### Beams

| | Predicted Yes | Predicted No |
|--------------|--------------|--------------|
| Actual Yes | **33** (TP) | **47** (FN) |
| Actual No | **81** (FP) | — |

### Walls

| | Predicted Yes | Predicted No |
|--------------|--------------|--------------|
| Actual Yes | **53** (TP) | **5** (FN) |
| Actual No | **123** (FP) | — |

---

## Per-Plan Detailed Results

| # | Plan | GT | Extracted | Doors (P/R/F1) | Walls (P/R/F1) | Columns (P/R/F1) | Beams (P/R/F1) |
|---|------|----|-----------|----------------|----------------|------------------|----------------|
| 01 | basic_1door | 2 | 2 | 0/0/0 | 0/0/0 | 0/0/0 | 50/100/67 |
| 02 | basic_2doors_1col | 4 | 7 | 33/50/40 | 100/100/100 | 0/0/0 | 33/100/50 |
| 03 | basic_1door_1beam_1col | 4 | 5 | 100/100/100 | 100/100/100 | 0/0/0 | 33/100/50 |
| 04 | basic_2doors_2beams_1col | 6 | 6 | 100/100/100 | 100/100/100 | 0/0/0 | 33/100/50 |
| 05 | basic_3doors_2cols_1beam | 7 | 8 | 100/67/80 | 100/100/100 | 0/0/0 | 25/100/40 |
| 06 | medium_Lshape | 6 | 8 | 50/50/50 | 100/100/100 | 0/0/0 | 50/100/67 |
| 07 | medium_Tshape | 7 | 11 | 67/67/67 | 100/100/100 | 0/0/0 | 20/100/33 |
| 08 | medium_Ushape | 5 | 3 | 100/100/100 | 0/0/0 | 0/0/0 | 100/100/100 |
| 09 | medium_cross | 9 | 10 | 100/50/67 | 100/100/100 | 0/0/0 | 25/100/40 |
| 10 | medium_multroom | 11 | 16 | 75/60/67 | 67/67/67 | 0/0/0 | 20/100/33 |
| 11 | complex_industrial | 15 | 17 | 0/0/0 | 100/100/100 | 0/0/0 | 20/100/33 |
| 12 | complex_stairwell | 3 | 3 | 100/50/67 | 0/0/0 | 0/0/0 | 50/100/67 |
| 13 | complex_commercial | 23 | 35 | 50/100/67 | 100/100/100 | 0/0/0 | 14/100/25 |
| 14 | complex_grid | 16 | 11 | 0/0/0 | 100/25/40 | 25/17/20 | 20/100/33 |
| 15 | complex_residential | 10 | 9 | 100/40/57 | 100/100/100 | 0/0/0 | 25/100/40 |
| 16 | edge_smalldoors | 4 | 2 | 0/0/0 | 0/0/0 | 0/0/0 | 50/100/67 |
| 17 | edge_thickwalls | 2 | 0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| 18 | edge_irregular_cols | 5 | 3 | 100/100/100 | 0/0/0 | 0/0/0 | 50/100/67 |
| 19 | edge_overlap | 3 | 6 | 50/100/67 | 100/100/100 | 0/0/0 | 33/100/50 |
| 20 | edge_dense_text | 6 | 10 | 0/0/0 | 100/100/100 | 0/0/0 | 20/100/33 |
| 21 | arch_2room | 6 | 7 | 100/100/100 | 100/100/100 | 0/0/0 | 67/100/80 |
| 22 | arch_3room | 7 | 8 | 100/67/80 | 100/100/100 | 0/0/0 | 50/100/67 |
| 23 | arch_openplan | 5 | 8 | 50/50/50 | 100/100/100 | 0/0/0 | 25/100/40 |
| 24 | arch_hotelcorridor | 12 | 13 | 80/67/73 | 100/100/100 | 0/0/0 | 50/100/67 |
| 25 | arch_Lapartment | 6 | 10 | 33/50/40 | 100/100/100 | 0/0/0 | 40/100/57 |
| 26 | arch_office | 17 | 20 | 100/100/100 | 100/100/100 | 0/0/0 | 25/100/40 |
| 27 | arch_classroom | 9 | 12 | 67/67/67 | 50/50/50 | 33/50/40 | 50/100/67 |
| 28 | arch_hospital | 13 | 14 | 60/50/54 | 100/100/100 | 0/0/0 | 33/100/50 |
| 29 | arch_library | 11 | 14 | 100/100/100 | 100/100/100 | 0/0/0 | 33/100/50 |
| 30 | arch_mall | 25 | 31 | 17/25/20 | 100/100/100 | 0/0/0 | 20/100/33 |
| 31 | struct_grid3x3 | 17 | 26 | 50/100/67 | 75/100/86 | 86/100/92 | 20/100/33 |
| 32 | struct_grid4x3 | 22 | 35 | 0/0/0 | 67/100/80 | 90/100/95 | 20/100/33 |
| 33 | struct_foundation | 8 | 13 | 33/100/50 | 100/100/100 | 0/0/0 | 25/100/40 |
| 34 | struct_transferbeams | 12 | 12 | 50/100/67 | 100/100/100 | 0/0/0 | 25/100/40 |
| 35 | struct_parking | 22 | 41 | 0/0/0 | 80/100/89 | 35/67/46 | 20/100/33 |
| 36 | struct_retaining | 11 | 13 | 100/100/100 | 100/100/100 | 0/0/0 | 33/100/50 |
| 37 | struct_watertank | 8 | 9 | 50/100/67 | 100/100/100 | 0/0/0 | 33/100/50 |
| 38 | struct_steel | 22 | 46 | 0/0/0 | 67/100/80 | 39/100/56 | 20/100/33 |
| 39 | struct_bridge | 9 | 12 | 0/0/0 | 100/80/89 | 0/0/0 | 33/100/50 |
| 40 | struct_shearwall | 7 | 13 | 33/100/50 | 100/100/100 | 0/0/0 | 33/100/50 |
| 41 | lowq_blur | 4 | 35 | 100/100/100 | 100/100/100 | 3/100/6 | 33/100/50 |
| 42 | lowq_noise | 4 | 9 | 100/100/100 | 100/100/100 | 0/0/0 | 25/100/40 |
| 43 | lowq_lowcontrast | 4 | 5 | 100/100/100 | 100/100/100 | 0/0/0 | 33/100/50 |
| 44 | lowq_skew | 4 | 14 | 50/100/67 | 100/100/100 | 0/0/0 | 17/100/29 |
| 45 | lowq_crop | 4 | 3 | 100/100/100 | 100/100/100 | 0/0/0 | 100/100/100 |
| 46 | rot_30deg | 6 | 1 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| 47 | rot_45deg | 6 | 1 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| 48 | rot_60deg | 6 | 1 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| 49 | rot_90deg | 6 | 3 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| 50 | rot_180deg | 6 | 6 | 100/100/100 | 100/100/100 | 0/0/0 | 33/100/50 |

---

## Failure Analysis

### Doors — Below Target (59.4% vs 90%)

- **False Positives:** 41
- **False Negatives:** 41

| Plan | FN | FP | Details |
|------|----|----|---------|
| basic_1door | 1 | 0 | FN: D1 |
| basic_2doors_1col | 1 | 2 | FN: D2; FP: D3, D4 |
| basic_3doors_2cols_1beam | 1 | 0 | FN: D3 |
| medium_Lshape | 1 | 1 | FN: D2; FP: D3 |
| medium_Tshape | 1 | 1 | FN: D3; FP: D3 |
| medium_cross | 2 | 0 | FN: D3, D4 |
| medium_multroom | 2 | 1 | FN: D4, D5; FP: D6 |
| complex_industrial | 2 | 0 | FN: D1, D2 |
| complex_stairwell | 1 | 0 | FN: D2 |
| complex_commercial | 0 | 2 | FP: D2, D11 |
| complex_grid | 1 | 0 | FN: D1 |
| complex_residential | 3 | 0 | FN: D2, D3, D5 |
| edge_smalldoors | 3 | 0 | FN: D1, D2, D3 |
| edge_thickwalls | 1 | 0 | FN: D1 |
| edge_overlap | 0 | 1 | FP: D2 |
| edge_dense_text | 1 | 2 | FN: D1; FP: D1, D3 |
| arch_3room | 1 | 0 | FN: D3 |
| arch_openplan | 1 | 1 | FN: D2; FP: D3 |
| arch_hotelcorridor | 2 | 1 | FN: D5, D6; FP: D9 |
| arch_Lapartment | 1 | 2 | FN: D2; FP: D5, D1 |
| arch_classroom | 1 | 1 | FN: D2; FP: D6 |
| arch_hospital | 3 | 2 | FN: D4, D5, D6; FP: D9, D10 |
| arch_mall | 3 | 5 | FN: D1, D2, D4; FP: D1, D2, D3, D4, D5 |
| struct_grid3x3 | 0 | 1 | FP: D3 |
| struct_grid4x3 | 0 | 2 | FP: D7, D1 |
| struct_foundation | 0 | 2 | FP: D1, D2 |
| struct_transferbeams | 0 | 1 | FP: D2 |
| struct_parking | 0 | 4 | FP: D9, D10, D11, D12 |
| struct_watertank | 0 | 1 | FP: D1 |
| struct_bridge | 0 | 5 | FP: D5, D1, D2, D3, D4 |
| struct_shearwall | 0 | 2 | FP: D8, D1 |
| lowq_skew | 0 | 1 | FP: D4 |
| rot_30deg | 2 | 0 | FN: D1, D2 |
| rot_45deg | 2 | 0 | FN: D1, D2 |
| rot_60deg | 2 | 0 | FN: D1, D2 |
| rot_90deg | 2 | 0 | FN: D1, D2 |

Failure gallery images saved to `/tmp/drawing_parser_validation/validation_failures/`

### Columns — Target Met ✅ (90.6% ≥ 85%)

### Beams — Below Target (34.0% vs 85%)

- **False Positives:** 81
- **False Negatives:** 47

| Plan | FN | FP | Details |
|------|----|----|---------|
| basic_1door_1beam_1col | 1 | 0 | FN: B1 |
| basic_2doors_2beams_1col | 2 | 0 | FN: B1, B2 |
| basic_3doors_2cols_1beam | 1 | 0 | FN: B1 |
| medium_Ushape | 2 | 0 | FN: B1, B2 |
| medium_multroom | 2 | 4 | FN: B1, B2; FP: B1, B2, B3, B4 |
| complex_commercial | 0 | 4 | FP: B1, B2, B3, B4 |
| complex_grid | 5 | 3 | FN: B2, B3, B4, B5, B6; FP: B1, B2, B3 |
| complex_residential | 1 | 0 | FN: B1 |
| edge_dense_text | 1 | 0 | FN: B1 |
| arch_classroom | 1 | 2 | FN: B1; FP: B1, B3 |
| arch_library | 1 | 0 | FN: B1 |
| struct_grid3x3 | 0 | 1 | FP: B6 |
| struct_grid4x3 | 0 | 1 | FP: B6 |
| struct_transferbeams | 4 | 0 | FN: B1, B2, B3, B4 |
| struct_parking | 3 | 11 | FN: B7, B8, B9; FP: B3, B4, B5, B7, B8, B9, B10, B11, B12, B13, B14 |
| struct_retaining | 4 | 4 | FN: B1, B2, B3, B4; FP: B1, B2, B3, B4 |
| struct_watertank | 2 | 0 | FN: B1, B2 |
| struct_steel | 0 | 14 | FP: B2, B3, B8, B10, B11, B12, B13, B14, B16, B17, B18, B19, B20, B23 |
| struct_bridge | 3 | 0 | FN: B1, B2, B3 |
| lowq_blur | 0 | 29 | FP: B1, B2, B3, B4, B5, B6, B7, B8, B9, B10, B11, B12, B13, B14, B15, B16, B17, B18, B19, B20, B21, B22, B23, B24, B25, B26, B28, B29, B30 |
| lowq_noise | 1 | 3 | FN: B1; FP: B1, B2, B3 |
| lowq_lowcontrast | 1 | 0 | FN: B1 |
| lowq_skew | 1 | 5 | FN: B1; FP: B1, B2, B3, B4, B5 |
| lowq_crop | 1 | 0 | FN: B1 |
| rot_30deg | 2 | 0 | FN: B1, B2 |
| rot_45deg | 2 | 0 | FN: B1, B2 |
| rot_60deg | 2 | 0 | FN: B1, B2 |
| rot_90deg | 2 | 0 | FN: B1, B2 |
| rot_180deg | 2 | 0 | FN: B1, B2 |

Failure gallery images saved to `/tmp/drawing_parser_validation/validation_failures/`

### Walls — Below Target (45.3% vs 85%)

- **False Positives:** 123
- **False Negatives:** 5

| Plan | FN | FP | Details |
|------|----|----|---------|
| basic_1door | 0 | 1 | FP: W1 |
| basic_2doors_1col | 0 | 2 | FP: W2, W3 |
| basic_1door_1beam_1col | 0 | 2 | FP: W1, W2 |
| basic_2doors_2beams_1col | 0 | 2 | FP: W2, W3 |
| basic_3doors_2cols_1beam | 0 | 3 | FP: W2, W3, W4 |
| medium_Lshape | 0 | 2 | FP: W2, W3 |
| medium_Tshape | 0 | 4 | FP: W2, W3, W4, W5 |
| medium_cross | 0 | 3 | FP: W2, W3, W4 |
| medium_multroom | 0 | 4 | FP: W2, W3, W4, W5 |
| complex_industrial | 0 | 4 | FP: W2, W3, W5, W6 |
| complex_stairwell | 0 | 1 | FP: W2 |
| complex_commercial | 0 | 6 | FP: W3, W4, W5, W7, W8, W9 |
| complex_grid | 0 | 4 | FP: W2, W3, W5, W7 |
| complex_residential | 0 | 3 | FP: W2, W3, W4 |
| edge_smalldoors | 0 | 1 | FP: W2 |
| edge_thickwalls | 1 | 0 | FN: W1 |
| edge_irregular_cols | 0 | 1 | FP: W1 |
| edge_overlap | 0 | 2 | FP: W2, W3 |
| edge_dense_text | 0 | 4 | FP: W2, W3, W4, W5 |
| arch_2room | 0 | 1 | FP: W3 |
| arch_3room | 0 | 2 | FP: W2, W3 |
| arch_openplan | 0 | 3 | FP: W2, W3, W4 |
| arch_hotelcorridor | 0 | 2 | FP: W2, W4 |
| arch_Lapartment | 0 | 3 | FP: W3, W4, W5 |
| arch_office | 0 | 3 | FP: W1, W2, W3 |
| arch_classroom | 0 | 2 | FP: W2, W3 |
| arch_hospital | 0 | 2 | FP: W1, W2 |
| arch_library | 0 | 4 | FP: W2, W3, W4, W5 |
| arch_mall | 0 | 4 | FP: W1, W4, W5, W6 |
| struct_grid3x3 | 0 | 4 | FP: W2, W3, W5, W6 |
| struct_grid4x3 | 0 | 4 | FP: W1, W3, W4, W5 |
| struct_foundation | 0 | 3 | FP: W2, W3, W4 |
| struct_transferbeams | 0 | 3 | FP: W2, W3, W4 |
| struct_parking | 0 | 4 | FP: W1, W2, W3, W5 |
| struct_retaining | 0 | 2 | FP: W2, W3 |
| struct_watertank | 0 | 2 | FP: W1, W3 |
| struct_steel | 0 | 4 | FP: W1, W2, W3, W4 |
| struct_bridge | 0 | 2 | FP: W1, W2 |
| struct_shearwall | 0 | 4 | FP: W2, W5, W6, W8 |
| lowq_blur | 0 | 2 | FP: W4, W6 |
| lowq_noise | 0 | 3 | FP: W2, W3, W4 |
| lowq_lowcontrast | 0 | 2 | FP: W1, W2 |
| lowq_skew | 0 | 5 | FP: W1, W4, W5, W7, W10 |
| rot_30deg | 1 | 0 | FN: W1 |
| rot_45deg | 1 | 0 | FN: W1 |
| rot_60deg | 1 | 0 | FN: W1 |
| rot_90deg | 1 | 2 | FN: W1; FP: W1, W3 |
| rot_180deg | 0 | 2 | FP: W2, W3 |

Failure gallery images saved to `/tmp/drawing_parser_validation/validation_failures/`

---

## Dimension Extraction Accuracy

Average dimension deviation across all true-positive matches:

| Category | Mean Error % | Within 5% | Within 10% | Within 15% |
|----------|-------------|-----------|------------|------------|
| Doors | 6.0% | 61.7% | 73.3% | 95.0% |
| Columns | 2.3% | 99.0% | 100.0% | 100.0% |
| Beams | 2.0% | 90.9% | 90.9% | 97.0% |
| Walls | 0.2% | 98.1% | 100.0% | 100.0% |

---

## Recommendations

Based on the validation results:

**Doors** (31% below target):

**Columns** — Target met ✅

**Beams** (51% below target):
- Increase precision: 81 false positives suggest over-detection
- Tighten geometric constraints and add verification checks

**Walls** (40% below target):
- Increase precision: 123 false positives suggest over-detection
- Tighten geometric constraints and add verification checks

---

*Report generated automatically by `validate_drawing_parser.py` at 2026-06-16 21:29*
*Failure gallery: `/tmp/drawing_parser_validation/validation_failures/`*