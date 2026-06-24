# Cursor Implementation Guide

## Goal of This Guide

This guide is written for fast execution in Cursor over the next few days. The main aim is not to build
the most advanced system first. The aim is to build a believable, working MVP quickly.

## Best Stack for a Fast MVP

Use this stack because it is simple, fast to build, and easy to demo:

- Python 3.11
- Streamlit for the user interface
- OpenCV for image preprocessing and analysis
- NumPy and Pandas for data handling
- ReportLab for PDF report generation
- Ultralytics YOLO only if time allows

## Important Recommendation

For the first review, do not start with a heavy custom deep learning pipeline. Start with:

- image upload
- preprocessing
- line detection
- spacing analysis
- rule-based checks
- report generation

This is the fastest path to a working demo.

## Suggested Build Plan in 4 Days

## Day 1: Project Setup and UI Skeleton

### Objective

Create the basic app structure and make image upload work.

### What to Build

- Python virtual environment
- required package installation
- simple Streamlit app
- image upload widget
- original image preview

### Files You Should Create

- `app.py`
- `src/vision/preprocess.py`
- `src/logic/scoring.py`
- `src/reporting/report_generator.py`

### What to Ask Cursor to Do

Use prompts like:

- "Create a Streamlit app in `app.py` that uploads an image and displays it."
- "Create a preprocessing module in `src/vision/preprocess.py` using OpenCV."
- "Create clean project imports and helper functions."

### End of Day 1 Result

You should be able to upload an image and see it in the app.

## Day 2: Image Processing and Visual Analysis

### Objective

Make the system extract useful visual information from the image.

### What to Build

- grayscale conversion
- blur and edge detection
- line detection using Hough transform
- contour or region highlighting
- basic orientation estimation

### Suggested Processing Steps

1. read image
2. resize image
3. convert to grayscale
4. apply Gaussian blur
5. detect edges with Canny
6. detect lines with HoughLinesP
7. draw detected lines on overlay image

### What to Ask Cursor to Do

- "Implement OpenCV preprocessing with grayscale, blur, and Canny edge detection."
- "Add line detection and return an overlay image with the lines drawn."
- "Create a helper that estimates whether dominant lines are vertical or horizontal."

### End of Day 2 Result

You should be able to show:

- original image
- processed edge image
- overlay image with detected lines

## Day 3: Rule Engine, Scoring, and Report

### Objective

Convert visual analysis into inspection logic.

### What to Build

- simple beam/column classification rule
- alignment check
- spacing regularity check
- anomaly flagging
- score calculation
- short text report

### Simple Rule Examples

- if most lines are vertical, image may be a column
- if most long lines are horizontal, image may be a beam
- if spacing deviation is high, reduce score
- if line orientation is inconsistent, add warning

### Score Design

Start with a simple formula:

- start from 100
- subtract points for each issue
- cap the score between 0 and 100

Example deductions:

- minor spacing issue: -10
- major spacing issue: -20
- alignment issue: -15
- anomaly region detected: -20

### What to Ask Cursor to Do

- "Create a rule-based inspection function that returns findings, score, and status."
- "Generate a text report from findings in plain language."
- "Show the score, status, and warnings in Streamlit."

### End of Day 3 Result

You should have a complete end-to-end demo:

- upload image
- analyze image
- show highlighted output
- display score
- display report text

## Day 4: Polishing and Review Preparation

### Objective

Make the system stable enough for presentation.

### What to Improve

- cleaner UI layout
- clearer warning messages
- better overlays
- save output image
- generate downloadable report
- test on many images

### Optional Upgrade If Time Allows

If your heuristic pipeline already works, you may optionally add:

- YOLO-based element detector
- defect detection experiment

But only do this if the MVP is already stable.

### Review Checklist

- can upload multiple sample images one by one
- score changes based on image quality and issues
- overlay is easy to understand
- report text is readable
- demo runs without code editing during presentation

## Exact Manual Build Order

If you want the safest execution path, follow this order exactly:

1. Create the folder structure.
2. Set up Python environment.
3. Install dependencies.
4. Build `app.py` with image upload and display only.
5. Add preprocessing functions.
6. Add edge and line detection.
7. Add overlay drawing.
8. Add rule-based checks.
9. Add scoring.
10. Add report text generation.
11. Add output download.
12. Test with at least 10 images.
13. Prepare 3 best demo images and 2 faulty examples.

## Recommended File Responsibilities

- `app.py`: Streamlit UI and overall flow
- `src/vision/preprocess.py`: image cleaning and edge extraction
- `src/vision/feature_extract.py`: line detection and spacing calculations
- `src/logic/rules.py`: inspection rules
- `src/logic/scoring.py`: score calculation
- `src/reporting/report_generator.py`: report text and PDF output

## Recommended Cursor Workflow

Use Cursor as a coding assistant, not as a full autopilot.

Best practice:

1. create one file at a time
2. ask Cursor for one module at a time
3. run the code after each module
4. fix errors immediately
5. keep prompts specific

Good prompt style:

- "Implement only the preprocessing module with docstrings and simple helper functions."
- "Do not modify other files. Add a function that returns grayscale, edges, and resized image."
- "Now integrate this module into `app.py` and display all intermediate outputs."

## If You Want a Model Later

Only after the MVP works, you can try:

1. labeling beam and column images
2. training a small YOLO model
3. replacing manual element detection with learned detection
4. comparing results with the rule-based baseline

This should be a second step, not the first step.

## What to Avoid

- do not start with React + FastAPI unless required
- do not wait for a large dataset before building
- do not promise exact structural code compliance
- do not spend all time tuning a model before a demo exists

## Final Advice

If you have only a few days, the winning strategy is:

- build a simple but complete pipeline
- make the output visually convincing
- keep the rules understandable
- show clear progress with examples

That is the fastest path to a strong academic MVP.

