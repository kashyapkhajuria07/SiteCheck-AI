# SiteCheck AI

AI-assisted construction site inspection platform. Upload site photographs (and optionally an architectural plan) to detect structural elements, measure alignment deviations, and generate downloadable PDF inspection reports.

## Project structure

```
SiteCheck-AI/
├── app.py                  # Streamlit MVP (Days 1–4 demo)
├── src/                    # Streamlit MVP modules
├── backend/                # FastAPI REST API (full-stack Phase 1)
├── frontend/               # Next.js 14 dashboard
└── data/                   # Dataset placeholders
```

The **Streamlit MVP** (`app.py`) remains for quick demos. The **full-stack** path uses `backend/` + `frontend/`.

## Quick start — Full stack (Phase 1)

### Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local` if the API runs elsewhere.

## Quick start — Streamlit MVP

```bash
pip install -r requirements.txt
python3 -m streamlit run app.py
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check + YOLO load status |
| POST | `/api/inspect` | Upload photos (+ optional plan), run inspection |
| GET | `/api/results/{session_id}` | JSON results |
| GET | `/api/report/{session_id}` | Download PDF report |
| GET | `/api/files/{session_id}/{filename}` | Annotated image |

## Phase 1 capabilities

- OpenCV preprocessing (resize, CLAHE, blur, quality flags)
- Heuristic + optional YOLOv8 element detection
- HoughLines wall plumb / beam level / rebar spacing checks
- IS:456 and NBC 2016 JSON rulesets
- Colour-coded overlay images
- PDF report generation
- Next.js upload UI + results dashboard

## Phase 2 — YOLO training (current)

Custom YOLOv8 fine-tuning pipeline for construction classes:

```bash
# 1. Add images to data/raw/beams/, data/raw/columns/, etc.
python backend/scripts/prepare_yolo_dataset.py
python backend/scripts/train_yolo.py --epochs 50
# Restart backend — loads backend/models/weights/sitecheck_yolov8n.pt
```

See **[07_phase2_yolo_guide.md](07_phase2_yolo_guide.md)** for Roboflow export, class list, and detection modes.

API health now reports `detection_mode`: `custom_yolo` | `coco_yolo` | `heuristic`.

## Development phases

1. **Phase 1** — FastAPI + OpenCV heuristics + Next.js UI ✓
2. **Phase 2 (current)** — Custom YOLOv8 training + detector integration ✓
3. **Phase 3** — Plan OCR + plan-vs-reality comparison
4. **Phase 4** — Report polish, imperial units, deployment

## Notes

- All deviation values are computed from pixel-level geometry; uncalibrated measurements are flagged as estimated.
- Scale calibration uses plan door width or IS standard door (900 mm) when no plan is provided.
- YOLO loads optionally; contour heuristics run when the model is unavailable.
