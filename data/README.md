# Data folder

Use this folder to store sample images and labels.

## Structure

- `raw/beams/`: beam reinforcement/fabrication images
- `raw/columns/`: column reinforcement/fabrication images
- `raw/mixed/`: uncategorized images
- `annotations/metadata.csv`: simple labels and source tracking
- `processed/`: derived outputs (edges, overlays, resized images)

## Labeling tips

- Keep `source_url` and `license` for every web image you download.
- Use `status=ok` or `status=defect` for MVP.
- Use simple `defect_tag` values like `bent_bar`, `irregular_spacing`, `misalignment`, `missing_tie`.

