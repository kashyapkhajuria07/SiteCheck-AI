# Requirement Specification

## 1. Project Title

A System and Computer Vision-Based Method for Verifying Column and Beam Fabrication at Construction Sites

## 2. Problem Statement

Construction quality inspection is still heavily manual. Site engineers often inspect beam and column
fabrication visually, which can be time-consuming, inconsistent, and difficult to document clearly.
This project aims to build a computer vision based system that helps inspect visible fabrication quality
from uploaded images.

In simple words, the system should act like a digital inspection assistant that looks at a site photo,
checks what is visible, and points out possible fabrication problems.

## 3. Main Objective

The main objective is to create an AI-assisted inspection tool that can:

- detect beams or columns in a site image
- analyze visible alignment and arrangement
- verify visible reinforcement placement at a basic level
- identify possible deviations from expected standards
- create visual overlays and an inspection summary

## 4. Users of the System

The primary users are expected to be:

- civil engineering students working on the project
- site engineers
- quality inspection teams
- project reviewers or faculty members evaluating the demo

## 5. Scope of the First Version

The first version should be intentionally limited so that it can be built and demonstrated successfully.

### In Scope

- uploaded images of beam and column fabrication
- pre-concreting stage images
- visible reinforcement-related checks
- simple geometric and visual verification
- annotated inspection result
- compliance score and short report

### Out of Scope for MVP

- exact structural code verification for all cases
- millimeter-accurate dimension estimation from a single image
- automatic reading of full structural drawings
- 3D reconstruction
- legal certification or final approval replacement

## 6. Inputs Required

The system will need the following inputs:

- one uploaded image at a time
- selected structural element type or auto-detection
- predefined inspection rules

Optional future inputs:

- multiple views of the same element
- drawing reference
- known scale reference in image
- bar schedule information

## 7. Outputs Required

The system should produce:

- detected structural element label
- annotated image with warnings or highlights
- detected issue list
- compliance score
- short automated inspection report

Example output:

- Element: Column
- Issues: Bent bar near top, irregular tie spacing
- Score: 81/100
- Status: Needs review

## 8. Functional Requirements

The system must be able to:

1. Upload and read image files.
2. Preprocess images for better analysis.
3. Detect whether the structural element is a beam or a column.
4. Identify the main region of interest in the image.
5. Analyze visible lines, bars, and spacing patterns.
6. Apply rule-based checks for fabrication quality.
7. Highlight suspected issues using visual overlays.
8. Generate a basic compliance score.
9. Produce a short report summarizing findings.

## 9. Non-Functional Requirements

The system should be:

- easy to use
- fast enough for demo use
- modular for future upgrades
- understandable to non-ML reviewers
- robust to normal image variation
- simple to operate on a laptop

## 10. Data Requirements

The system requires a curated image dataset containing:

- beam fabrication images
- column fabrication images
- correct examples
- incorrect examples
- different viewpoints
- different lighting conditions
- images with clutter typical of construction sites

Useful labels include:

- beam / column
- compliant / non-compliant
- defect type
- defect location
- reinforcement region

## 11. Core Checks for the MVP

The MVP should focus on a few checks that are realistic and visible:

- element type detection
- overall orientation check
- reinforcement line visibility
- spacing consistency check
- obvious anomaly detection

Examples of anomalies:

- bent bar
- missing visible tie segment
- irregular spacing
- severe misalignment

## 12. Assumptions

The first version will assume:

- the image shows one main structural element
- reinforcement is reasonably visible
- the image is not fully blocked by people or tools
- the user provides reasonably clear images
- the output is advisory, not final engineering approval

## 13. Constraints

The project may face the following constraints:

- limited time
- small dataset
- uncontrolled site image quality
- limited domain annotations
- difficulty of exact measurement without calibration

## 14. Risks

Main risks include:

- insufficient real construction images
- poor defect examples
- false alarms in cluttered scenes
- over-promising exact compliance verification
- spending too much time on model complexity instead of building the MVP

## 15. MVP Acceptance Criteria

The MVP will be considered successful if it can:

1. accept an uploaded image
2. identify beam or column in a useful way
3. run at least 2 to 4 simple inspection checks
4. show issue highlights on the image
5. generate a score and short report
6. complete a smooth demo for reviewers

## 16. Final Plain Language Summary

This project is building a smart visual inspection assistant for beam and column fabrication. It will
look at construction images, perform a few important visual checks, highlight suspicious areas, and
generate a simple inspection result that helps quality assurance work.

