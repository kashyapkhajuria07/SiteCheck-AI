# SiteCheck AI Test Assets

This directory contains sample images for regression testing the geometric analysis pipeline.

## Directory Structure
- `walls/`: Images of walls for plumbness testing.
- `beams/`: Images of beams for levelness testing.
- `columns/`: Images of columns for verticality testing.
- `doors/`: Images of doors for alignment testing.

## Usage
Add images to the respective folders. These images will be loaded by the unit tests in `backend/tests/` to verify that the geometric analysis modules return expected measurements, confidences, and statuses.
