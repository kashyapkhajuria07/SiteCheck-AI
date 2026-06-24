# SiteCheck AI — Report V3 Mockup

> **Target audience**: Civil engineering faculty, construction companies, hackathon judges
> **Tone**: Professional engineering inspection document, not a debug log

---

## Page 1 — Cover Page

```
╔══════════════════════════════════════════════════════════════╗
║  ██████████████████████████████████████████████████████████  ║  ← accent bar (deep blue #1a237e)
║                                                              ║
║                    SiteCheck AI                               ║  ← title (28pt, bold)
║         Structural Compliance Inspection Report               ║  ← subtitle (14pt, accent)
║                                                              ║
║                     ┌──────────┐                             ║
║                     │   72     │                             ║  ← SQI gauge (large number + colored bar)
║                     │   SQI    │                             ║
║                     └──────────┘                             ║
║                                                              ║
║  ┌──────────────────────────────────────────────────────┐    ║
║  │ Report ID           │ SITECHECK-2025-001             │    ║
║  │ Inspection Date     │ 15 June 2025                   │    ║
║  │ Project Name        │ Green Valley Tower — Phase 2   │    ║
║  │ Inspection Type     │ Structural Compliance Check    │    ║
║  │ Applicable Standard │ IS:456:2000                    │    ║
║  │ Images Analysed     │ 3                              │    ║
║  │ Elements Analysed   │ 12                             │    ║
║  │ SQI Classification  │ PASS — Compliant               │    ║
║  └──────────────────────────────────────────────────────┘    ║
║                                                              ║
║  ─────────────────────────────────────────  ← thin accent    ║
║  Generated: 2025-06-15 14:30 | Confidential                  ║
╚══════════════════════════════════════════════════════════════╝
```

**Layout notes:**
- Deep blue (#1a237e) header bar across top
- Large SQI score in center (48pt), colored by result (green ≥85, amber ≥70, red <70)
- SQI gauge bar below the number showing fill percentage
- Metadata table with alternating row backgrounds
- Footer with generation timestamp and confidentiality notice

---

## Page 2 — Executive Dashboard

```
╔══════════════════════════════════════════════════════════════╗
║  Executive Dashboard                                         ║  ← section header
║  ───────────────────────────────────────────                 ║
║                                                              ║
║  ┌──────────────────────────────────────────────────────┐    ║
║  │  SQI                    ████████████░░░░  72/100    │    ║  ← horizontal gauge bar
║  │  Confidence Score       ██████████░░░░░░  65%       │    ║
║  └──────────────────────────────────────────────────────┘    ║
║                                                              ║
║  ┌──────────────┬──────────┬──────────────┐                 ║
║  │ Metric       │ Count    │ % of Total   │                 ║
║  ├──────────────┼──────────┼──────────────┤                 ║
║  │ ✅ Pass      │ 8        │ 67%          │                 ║
║  │ ⚠ Warning    │ 2        │ 17%          │                 ║
║  │ ❌ Fail       │ 1        │ 8%           │                 ║
║  │ ➖ Inconcl.   │ 1        │ 8%           │                 ║
║  ├──────────────┼──────────┼──────────────┤                 ║
║  │ Total        │ 12       │ 100%         │                 ║
║  └──────────────┴──────────┴──────────────┘                 ║
║                                                              ║
║  Critical Issues (1):                                        ║
║  ┌──────────────────────────────────────────────────────┐    ║
║  │ ❌ E003 — Door - Main Entrance                        │    ║
║  │    Gap asymmetry 18.2mm exceeds 15mm limit            │    ║
║  │    Severity: HIGH — Immediate structural review req.  │    ║
║  └──────────────────────────────────────────────────────┘    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

**Dashboard metrics:**
| Metric | Source | Notes |
|--------|--------|-------|
| **SQI** | Weighted score from element statuses | 100 per PASS, 60 per WARNING, 0 per FAIL, 40 per INCONCLUSIVE |
| **Confidence Score** | Mean of all element confidence scores | Scaled to 0–100% |
| **Critical Issues** | Elements with FAIL status | Shown with severity label |
| **Warning Issues** | Elements with WARNING status | Count only, details on findings page |

---

## Page 3 — Project Metadata (condensed header card)

```
╔══════════════════════════════════════════════════════════════╗
║  Project Information                                         ║
║  ───────────────────────────────────────────                 ║
║                                                              ║
║  Project Name:     Green Valley Tower — Phase 2              ║
║  Inspection Date:  15 June 2025                              ║
║  Location:         Site 42, Sector 18, Gurgaon               ║
║  Client:           Green Valley Developers Pvt. Ltd.         ║
║  Inspector:        SiteCheck AI v2.1 / Auto-generated        ║
║  Standard:         IS:456:2000 (Indian Standard)             ║
║  Unit System:      Metric                                    ║
║  Images Analysed:  3                                         ║
║  Elements Found:   12 (8 walls, 2 beams, 1 door, 1 rebar)   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Pages 4–6 — Element Findings

Each finding shown as a card block:

```
╔══════════════════════════════════════════════════════════════╗
║  E001  │  Wall — North Face                        │ ⚠ WARNING ║
║  ───────────────────────────────────────────────────────────  ║
║                                                              ║
║  Measured Value:    2.10 cm/m                                ║
║  Allowed Value:     1.50 cm/m (warning) / 3.00 cm/m (fail)  ║
║  Deviation %:       40% above warning threshold              ║
║  Severity:          MODERATE                                 ║
║  Confidence:        87%                                      ║
║                                                              ║
║  Engineering Interpretation:                                 ║
║  The wall plumbness measurement of 2.10 cm/m exceeds the     ║
║  IS:456 warning threshold of 1.50 cm/m by 40%. This tilt    ║
║  is within the fail limit of 3.00 cm/m but requires         ║
║  rectification during finishing stages.                     ║
║                                                              ║
║  Recommendation:                                             ║
║  Monitor during concreting. Apply corrective measures if     ║
║  deviation exceeds 2.5 cm/m. Consider formwork adjustment.  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

**Severity matrix:**
| Status | Severity Label | Color |
|--------|---------------|-------|
| PASS | NONE | Green |
| WARNING | MODERATE | Amber |
| FAIL | HIGH | Red |
| INCONCLUSIVE | INDETERMINATE | Gray |

**Engineering interpretation** is generated per check-type:
- **Wall plumb**: "The wall plumbness deviation of {X} cm/m {description}. IS:456 allows up to {warn} cm/m (warning) and {fail} cm/m (fail)."
- **Beam level**: "The beam levelness deviation of {X} mm/m {description}. IS:456 allows up to {warn} mm/m (warning) and {fail} mm/m (fail)."
- **Door alignment**: "The door frame gap asymmetry of {X} mm {description}. Frame rectangularity is {Y}. Maximum allowed asymmetry is {max} mm."
- **Rebar spacing**: "The rebar spacing of {X} mm {description}. Design specification is {spec} mm ± {tol}%."

---

## Pages 7–9 — Visual Evidence

For each photo:

```
╔══════════════════════════════════════════════════════════════╗
║  Image 1: north_wall_view.jpg  (4 elements)                  ║
║  ───────────────────────────────────────────                 ║
║                                                              ║
║  ┌──────────────────────────────────────────────────────┐    ║
║  │              ANNOTATED OVERVIEW IMAGE                  │    ║
║  │     (full annotated scene with bounding boxes)        │    ║
║  │     Legend: PASS ■ WARNING ■ FAIL ■ INCONCLUSIVE ■   │    ║
║  └──────────────────────────────────────────────────────┘    ║
║                                                              ║
║  Element detail per photo:                                   ║
║  ┌─────────┬──────────┬───────────┬──────────┬──────────┐   ║
║  │ ID      │ Element  │ Measured  │ Status   │ Severity │   ║
║  ├─────────┼──────────┼───────────┼──────────┼──────────┤   ║
║  │ E001    │ Wall     │ 2.10 cm/m │ ⚠ WARN  │ MODERATE │   ║
║  │ E002    │ Wall     │ 0.80 cm/m │ ✅ PASS  │ NONE     │   ║
║  │ E004    │ Beam     │ 6.50 mm/m │ ⚠ WARN  │ MODERATE │   ║
║  │ E007    │ Door     │ 18.2 mm   │ ❌ FAIL  │ HIGH     │   ║
║  └─────────┴──────────┴───────────┴──────────┴──────────┘   ║
║                                                              ║
║  ┌──────────┐  ┌──────────┐  ┌──────────┐                  ║
║  │ Original │  │ Annotated│  │ Cropped  │                  ║
║  │ Crop     │  │ Crop     │  │ Evidence │                  ║
║  └──────────┘  └──────────┘  └──────────┘                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

**For each element with FAIL/WARNING status**, show three crop views:
1. **Original crop**: Raw image region from the bounding box
2. **Annotated crop**: Same region with detected lines overlaid
3. **Measurement overlay**: Gradient/Hough line visualization with deviation labeled

---

## Page 10 — Compliance Matrix

```
╔══════════════════════════════════════════════════════════════╗
║  Compliance Matrix — IS:456:2000                             ║
║  ───────────────────────────────────────────                 ║
║                                                              ║
║  ┌──────────────┬──────────┬──────────┬──────────┬─────────┐ ║
║  │ Check Type   │ Elements │ Pass     │ Warning  │ Fail    │ ║
║  ├──────────────┼──────────┼──────────┼──────────┼─────────┤ ║
║  │ Wall Plumb   │ 8        │ 6        │ 2        │ 0       │ ║
║  │ Beam Level   │ 2        │ 1        │ 0        │ 1       │ ║
║  │ Door Align.  │ 1        │ 0        │ 0        │ 1       │ ║
║  │ Rebar Spacing│ 1        │ 1        │ 0        │ 0       │ ║
║  ├──────────────┼──────────┼──────────┼──────────┼─────────┤ ║
║  │ Total        │ 12       │ 8        │ 2        │ 2       │ ║
║  └──────────────┴──────────┴──────────┴──────────┴─────────┘ ║
║                                                              ║
║  Compliance Rate by Category:                                ║
║  ┌──────────────────────────────────────────────────────┐    ║
║  │ Wall Plumb    ████████████████████░░░░░░  75%        │    ║
║  │ Beam Level    ██████████████████████████░  50%       │    ║
║  │ Door Align    ██████████████████████████░   0%       │    ║
║  │ Rebar Spacing ████████████████████████████ 100%      │    ║
║  └──────────────────────────────────────────────────────┘    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Page 11 — Recommendations

```
╔══════════════════════════════════════════════════════════════╗
║  Recommendations & Remedial Actions                          ║
║  ───────────────────────────────────────────                 ║
║                                                              ║
║  ┌─ Immediate Action ─────────────────────────────────────┐  ║
║  │  ❌ E003 — Door - Main Entrance                        │  ║
║  │     Gap asymmetry of 18.2 mm exceeds IS:456 limit of   │  ║
║  │     15 mm. Requires immediate realignment of door      │  ║
║  │     frame. Check hinge alignment and frame fixing.     │  ║
║  │                                                        │  ║
║  │  ❌ E009 — Beam - Roof Section B                       │  ║
║  │     Level deviation of 11.2 mm/m exceeds IS:456 fail   │  ║
║  │     threshold of 10 mm/m. Structural review needed.    │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                              ║
║  ┌─ Monitor ─────────────────────────────────────────────┐  ║
║  │  ⚠ E001 — Wall - North Face                          │  ║
║  │     Plumb deviation 2.10 cm/m (40% over warning).    │  ║
║  │     Monitor during subsequent pours.                  │  ║
║  │                                                        │  ║
║  │  ⚠ E005 — Wall - East Elevation                      │  ║
║  │     Plumb deviation 1.80 cm/m (20% over warning).    │  ║
║  │     Acceptable for now. Track on next inspection.     │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                              ║
║  ┌─ Acceptable ──────────────────────────────────────────┐  ║
║  │  ✅ 8 elements passed all checks with no issues.       │  ║
║  │  No action required.                                   │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                              ║
║  ─────────────────────────────────────────  ───────────────  ║
║  Disclaimer:                                                ║
║  This report is generated by SiteCheck AI for preliminary   ║
║  assessment. Measurements are computed from pixel-level     ║
║  geometry. This does not substitute for a professional      ║
║  structural engineer's evaluation.                          ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Page 12 — Appendix: Methodology

```
╔══════════════════════════════════════════════════════════════╗
║  Methodology & Measurement Notes                             ║
║  ───────────────────────────────────────────                 ║
║                                                              ║
║  Detection Method:    YOLOv8n (heuristic fallback active)    ║
║  Geometric Analysis:  HoughLinesP + Sobel gradient tracking  ║
║  Scale Calibration:   Reference door width (900 mm)          ║
║  Confidence Scoring:  Edge count, inlier ratio, std dev      ║
║                                                              ║
║  Measurement Uncertainty:                                    ║
║  • HoughLinesP quantization: ~1°                             ║
║  • Sub-pixel refinement via parabolic interpolation          ║
║  • Outlier rejection via robust regression (3 iterations)    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Data Model Changes Required

### New/enhanced fields on `ElementResult`:
```python
class ElementResult(BaseModel):
    # ... existing fields ...
    allowed_value: Optional[str] = None       # "1.50 cm/m (warn) / 3.00 cm/m (fail)"
    deviation_pct: Optional[float] = None     # % over threshold
    severity: str = "NONE"                    # NONE, MODERATE, HIGH, INDETERMINATE
    engineering_interpretation: Optional[str] = None
    recommendation: Optional[str] = None
    confidence_score: float = 0.0             # 0-100 scale
```

### New fields on `ComplianceReport`:
```python
class ComplianceReport(BaseModel):
    # ... existing fields ...
    sqi: float = 0.0                    # Structural Quality Index (alias for score)
    confidence_score: float = 0.0       # Mean of element confidences
    project_metadata: Optional[dict] = None
```

### New fields on `InspectionSession`:
```python
class InspectionSession(BaseModel):
    # ... existing fields ...
    project_name: str = "Untitled Project"
    inspection_date: str = ""
```

---

## Implementation Plan

1. Update `schemas/inspection.py` — add new fields to `ElementResult`, `ComplianceReport`, `InspectionSession`
2. Update `compliance_engine.py` — populate new fields in `evaluate_element()` and `build_compliance_report()`
3. Update `pipeline.py` — accept project metadata, pass to report generator
4. Rewrite `report_generator.py` — V3 layout with all new sections
5. Minor update to `overlay_renderer.py` — add confidence label
6. Update API routes if needed (inspect endpoint for project_name)
7. Generate test PDF and verify

---

*End of mockup — ready for implementation.*
