# Dataset Class Mapping

This document defines the unified class mapping strategy for the SiteCheck AI MVP. We are combining smaller, real-photo datasets (Elements Dataset, Rebar Dataset, Slab Dataset) into a single YOLO format to boost data volume without adding unnecessary noise.

| Source Class       | SiteCheck Target | ID  |
| :----------------- | :--------------- | :-- |
| `beam-concrete`    | `beam`           | 0   |
| `beam-rebar`       | `beam`           | 0   |
| `columns-concrete` | `column`         | 1   |
| `columns-rebar`    | `column`         | 1   |
| `wall-concrete`    | `wall`           | 2   |
| `wall-rebar`       | `wall`           | 2   |
| `rebar-mesh`       | `rebar`          | 3   |
| `concrete-floor`   | `slab`           | 4   |
| `formwork`         | `slab`           | 4   |

## Strategy Notes
* **Model:** Stick to `YOLOv8n` (nano).
* **Target Volume:** 1500–2500 total images.
* **Format:** Images must be **REAL construction site photographs** (no CAD, no blueprints).
* **Merging Process:** Download these small, targeted datasets, run a Python script to remap their IDs according to the table above, prefix the filenames to prevent overwrites, and combine them into a single `images/` and `labels/` directory.
