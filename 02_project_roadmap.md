# Project Roadmap

## Roadmap Goal

This roadmap is designed to help build a review-ready MVP quickly while keeping the project scalable
for future improvement.

## Phase 1: Requirement Finalization

### Goal

Freeze the MVP scope and avoid confusion later.

### Tasks

- finalize target element types: beam and column
- finalize target image stage: pre-concreting fabrication
- finalize first defect checks
- define what the score means
- define what the report should contain

### Deliverables

- requirement specification
- approved MVP checklist

## Phase 2: Dataset Collection and Organization

### Goal

Build a small but useful dataset for prototyping and testing.

### Tasks

- collect beam images
- collect column images
- separate correct and faulty samples
- store images in the planned folder layout
- create a metadata sheet for labels and notes

### Deliverables

- organized raw image dataset
- initial labeled sample set

## Phase 3: Baseline Computer Vision Pipeline

### Goal

Create a simple working analysis pipeline before training heavier models.

### Tasks

- image upload
- preprocessing
- edge and line extraction
- region of interest highlighting
- simple rule-based checks
- annotated image output

### Deliverables

- working local demo that accepts images
- first annotated inspection output

## Phase 4: Scoring and Reporting

### Goal

Turn raw analysis into something reviewers can understand quickly.

### Tasks

- define score weights
- map findings to report statements
- generate inspection summary
- export result as image + text or PDF

### Deliverables

- compliance score
- automated report

## Phase 5: Optional Model Improvement

### Goal

Improve element or defect detection if time allows.

### Tasks

- train a small detection model
- test on beam and column samples
- compare with rule-only baseline
- retain the simpler method if the model does not improve reliability

### Deliverables

- optional trained detector
- evaluation notes

## Short-Term Execution Plan for the Upcoming Review

### Day 1

- finalize requirements and folder structure
- collect first batch of images
- build simple image upload interface

### Day 2

- implement preprocessing
- implement line and alignment analysis
- produce first overlay output

### Day 3

- implement spacing checks
- add scoring logic
- generate text inspection summary

### Day 4

- improve UI
- test on multiple images
- prepare review screenshots and talking points

### Day 5

- polish demo
- reduce false alarms where possible
- rehearse the review flow

## Milestones

### Milestone 1

Project definition is frozen and dataset collection has started.

### Milestone 2

Image upload and preprocessing work on sample images.

### Milestone 3

The system produces annotated inspection results.

### Milestone 4

The system generates a score and report.

### Milestone 5

The MVP is demo-ready.

## Progress Update Format

Use this short update format daily:

- completed today
- current blocker
- next task
- sample output produced

This will help you stay review-ready and show regular progress clearly.

