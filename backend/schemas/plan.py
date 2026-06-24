"""Schema for parsed architectural plans (Phase 3)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RoomSpec(BaseModel):
    id: str
    width_mm: float
    depth_mm: float
    label: Optional[str] = None


class DoorSpec(BaseModel):
    id: str
    width_mm: float
    height_mm: float
    label: Optional[str] = None


class ColumnSpec(BaseModel):
    id: str
    section: str
    label: Optional[str] = None


class BeamSpec(BaseModel):
    id: str
    width_mm: float
    depth_mm: float
    label: Optional[str] = None


class PlanSchema(BaseModel):
    """Structured dimensions extracted from an architectural plan."""

    rooms: list[RoomSpec] = Field(default_factory=list)
    doors: list[DoorSpec] = Field(default_factory=list)
    columns: list[ColumnSpec] = Field(default_factory=list)
    beams: list[BeamSpec] = Field(default_factory=list)
    raw_text_blocks: list[str] = Field(default_factory=list)
