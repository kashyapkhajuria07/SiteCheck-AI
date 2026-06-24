# Dataset Structure and Collection Guide

## Dataset Objective

The dataset should help the system learn or test how beams and columns look when fabrication is correct
or incorrect. For the MVP, even a small but well-organized dataset is enough.

## Recommended Folder Layout

```text
data/
|- raw/
|  |- beams/
|  |- columns/
|  `- mixed/
|- annotations/
`- processed/
```

### Folder Meaning

- `raw/beams/`: beam fabrication images
- `raw/columns/`: column fabrication images
- `raw/mixed/`: uncategorized or mixed samples
- `annotations/`: labels, CSV files, bounding boxes, or notes
- `processed/`: resized, cleaned, or derived images

## Recommended Naming Convention

Use file names that are easy to understand:

- `BEAM_OK_001.jpg`
- `BEAM_DEFECT_002.jpg`
- `COLUMN_OK_003.jpg`
- `COLUMN_DEFECT_004.jpg`

This will make labeling and demo preparation much easier.

## What Images to Collect

Collect images showing:

- beam reinforcement cages
- column reinforcement cages
- different angles
- different distances
- different lighting conditions
- clean cases
- cluttered site cases
- correct fabrication
- faulty fabrication

## First Dataset Target

For the first working prototype, aim for:

- 50 beam images
- 50 column images
- at least 20 visibly faulty examples

If you can collect more, even better.

## Defect Types to Tag

Keep defect tags simple in the beginning:

- bent_bar
- irregular_spacing
- misalignment
- missing_visible_tie
- unclear_image

You can expand later after the MVP is stable.

## Annotation Strategy

Start with simple annotations first.

### Level 1: Image-Level Labels

For every image, record:

- image name
- element type
- compliant / non-compliant
- defect tag
- notes

This can be stored in a CSV file.

### Level 2: Region-Level Labels

If time allows, mark:

- bounding box for beam or column region
- rough defect location

### Level 3: Detailed Labels

Later, if needed, label:

- bar lines
- stirrup locations
- multiple defect instances

## Recommended Metadata CSV Columns

Use a sheet or CSV with columns like:

- `image_name`
- `element_type`
- `status`
- `defect_tag`
- `source`
- `view_angle`
- `lighting`
- `notes`

## Data Collection Sources

Possible sources:

- your own site photographs
- lab or model images
- faculty-approved academic samples
- manually created mock examples
- open images only if usage is allowed

Only use images you are allowed to use.

## Data Quality Rules

Prefer images where:

- the structural element is mostly visible
- reinforcement is not fully hidden
- the image is not too blurry
- the image is not extremely dark

Still keep some difficult images for testing robustness.

## Train / Validation / Test Split

Once enough images are collected, split them like this:

- train: 70 percent
- validation: 15 percent
- test: 15 percent

If the dataset is very small, keep a simple manual test set for demo images.

## Important Practical Advice

- Do not wait for a perfect dataset before starting the MVP.
- Start with a small dataset and improve it continuously.
- For the first review, a small well-labeled dataset is better than a large messy dataset.

## Plain Language Summary

Your dataset is the foundation of the whole project. Keep it small, clean, labeled, and easy to
understand. That will help both model development and final presentation.

