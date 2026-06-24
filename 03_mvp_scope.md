# MVP Scope Definition

## MVP Goal

Build a minimum usable demo that proves the idea:

The user uploads a beam or column fabrication image, the system analyzes visible features, highlights
possible issues, and produces a basic compliance result.

## What the MVP Will Include

### Input

- single uploaded image
- jpg, jpeg, or png input

### Supported Structural Elements

- reinforced concrete columns
- reinforced concrete beams

### Analysis Included

- element type recognition
- image preprocessing
- visible structural region identification
- alignment analysis
- spacing consistency analysis
- simple anomaly flagging

### Output Included

- original image preview
- processed image preview
- annotated inspection image
- issue list
- compliance score
- short inspection report

## Recommended MVP Checks

The MVP should not try to check everything. It should only check things that are visible and practical.

### Check 1: Beam vs Column Identification

The system should identify whether the uploaded image mainly contains a beam or a column.

### Check 2: Orientation / Alignment

The system should estimate whether the visible reinforcement pattern looks properly aligned.

### Check 3: Spacing Consistency

The system should estimate whether reinforcement spacing appears regular or irregular.

### Check 4: Obvious Visual Anomaly Detection

The system should flag possible bent bars, gaps, missing visible members, or major distortions.

## What the MVP Will Not Include

- full structural drawing interpretation
- exact bar diameter estimation
- exact real-world dimension estimation from any image
- complete code compliance certification
- automatic detection of every possible site defect
- support for slabs, footings, walls, or steel structures

## Suggested MVP Scoring Logic

Use a simple score out of 100.

Suggested weights:

- element detection confidence: 20
- alignment quality: 25
- spacing consistency: 25
- anomaly severity: 30

Example:

- no major issue: 85 to 100
- minor review needed: 70 to 84
- several concerns: 50 to 69
- high concern: below 50

## Recommended MVP Architecture

Use a lightweight pipeline:

1. upload image
2. preprocess image
3. detect lines / edges / region
4. extract visual cues
5. apply rule checks
6. draw overlays
7. generate report

## MVP Demo Story

During the review, the demo should show:

1. user uploads a beam or column image
2. system displays the original image
3. system displays processed or detected line output
4. system highlights suspicious regions
5. system prints score and inspection summary

## MVP Success Criteria

The MVP is good enough if it can:

- run reliably on a small test set
- produce understandable visual results
- explain findings clearly
- support the project objective in a believable way

## Plain Language Summary

The MVP is not a perfect engineering checker. It is a strong proof of concept that shows how computer
vision can support beam and column fabrication inspection from images.

