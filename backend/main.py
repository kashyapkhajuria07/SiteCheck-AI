"""
SiteCheck AI — FastAPI backend entry point.

Run from the backend directory:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS, OUTPUTS_DIR, UPLOADS_DIR
from routers.inspect import router as inspect_router
from routers.compare import router as compare_router

# Ensure storage directories exist at startup
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="SiteCheck AI",
    description="Computer vision construction inspection API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inspect_router)
app.include_router(compare_router)


@app.get("/")
async def root():
    return {"service": "SiteCheck AI", "docs": "/docs", "health": "/api/health"}
