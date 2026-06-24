"""Pydantic models for inspection API requests and responses."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class UnitSystem(str, Enum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class Ruleset(str, Enum):
    IS456 = "IS456"
    NBC2016 = "NBC2016"
    CUSTOM = "custom"


class ElementStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: list[int] = Field(..., min_length=4, max_length=4)  # x1, y1, x2, y2
    trust_score: float = 100.0  # 0–100; < 50 means ignored


class Measurement(BaseModel):
    name: str
    value: float
    unit: str
    estimated: bool = False
    confidence: float = 1.0
    evidence: list[str] = Field(default_factory=list)
    details: Optional[dict[str, Any]] = None


class ElementResult(BaseModel):
    element_id: str
    label: str
    location: str
    status: ElementStatus
    deviation: Optional[float] = None
    expected: Optional[str] = None
    unit: str = "cm"
    reason: Optional[str] = None
    measurements: list[Measurement] = Field(default_factory=list)
    message: str = ""
    bbox: list[int] = Field(default_factory=list)
    allowed_value: Optional[str] = None
    deviation_pct: Optional[float] = None
    severity: str = "NONE"
    engineering_interpretation: Optional[str] = None
    recommendation: Optional[str] = None
    confidence_score: float = 0.0


class ComplianceReport(BaseModel):
    score: float
    elements: list[ElementResult]
    critical_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    pass_count: int = 0
    warning_count: int = 0
    fail_count: int = 0
    inconclusive_count: int = 0
    sqi: float = 0.0
    confidence_score: float = 0.0


class PhotoResult(BaseModel):
    photo_id: str
    file_name: str
    annotated_image_url: str
    elements: list[ElementResult]
    quality_flags: list[str] = Field(default_factory=list)


class InspectionSession(BaseModel):
    session_id: str
    status: str
    unit_system: UnitSystem
    ruleset: Ruleset
    compliance_score: float = 0.0
    photos: list[PhotoResult] = Field(default_factory=list)
    report_path: Optional[str] = None
    plan_provided: bool = False
    detection_mode: str = "heuristic"
    project_name: str = "Untitled Project"
    inspection_date: str = ""
    low_confidence: bool = False
    validation_log: Optional[ValidationLog] = None


class InspectResponse(BaseModel):
    session_id: str
    status: str
    preview_url: str


class CriticalFinding(BaseModel):
    element_id: str
    label: str
    status: ElementStatus
    deviation: Optional[float] = None
    deviation_pct: Optional[float] = None
    unit: str = ""
    summary: str = ""
    severity: str = "NONE"
    confidence_score: float = 0.0


class CoverageStats(BaseModel):
    total_detected: int = 0
    successfully_measured: int = 0
    coverage_pct: float = 0.0
    measurement_confidence_pct: float = 0.0


class RecommendationGroup(BaseModel):
    level: str  # "immediate", "monitor", "acceptable"
    items: list[str] = Field(default_factory=list)


class InspectionSummary(BaseModel):
    text: str = ""
    critical_count: int = 0
    warning_count: int = 0
    pass_count: int = 0
    most_severe_element: Optional[str] = None
    most_severe_deviation_pct: Optional[float] = None


class ResultsResponse(BaseModel):
    session_id: str
    compliance_score: float
    pass_count: int
    warning_count: int
    fail_count: int
    elements: list[ElementResult]
    annotated_images: list[str]
    report_url: str
    photos: list[PhotoResult]
    detection_mode: str = "heuristic"
    detection_classes: list[str] = Field(default_factory=list)
    critical_findings: list[CriticalFinding] = Field(default_factory=list)
    coverage: CoverageStats = Field(default_factory=CoverageStats)
    ai_inspection_summary: Optional[InspectionSummary] = None
    recommendation_groups: list[RecommendationGroup] = Field(default_factory=list)
    validation_log: Optional[ValidationLog] = None


class ValidationLog(BaseModel):
    scene_type: str = "unknown"
    scene_confidence: float = 0.0
    raw_detection_count: int = 0
    filtered_detection_count: int = 0
    ignored_low_trust_count: int = 0
    ignored_non_structural_count: int = 0
    final_detection_count: int = 0
    raw_counts: dict[str, int] = Field(default_factory=dict)
    filtered_counts: dict[str, int] = Field(default_factory=dict)
    removed_low_confidence: int = 0
    removed_duplicates: int = 0
    final_counts: dict[str, int] = Field(default_factory=dict)
    scene_overloaded: bool = False


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    detection_mode: str = "heuristic"
    weights_path: Optional[str] = None
    class_names: list[str] = Field(default_factory=list)


class ComparisonItem(BaseModel):
    element: str
    expected: float
    actual: float
    deviation_mm: float
    deviation_pct: float
    unit: str = "mm"
    status: str


class ComparisonSummary(BaseModel):
    total: int
    passed: int = 0
    warning: int = 0
    fail: int = 0
    compliance_pct: float = 0.0


class ComparePlanRequest(BaseModel):
    px_per_mm: Optional[float] = None


class ComparePlanResponse(BaseModel):
    drawing: dict[str, Any] = Field(default_factory=dict)
    comparisons: list[ComparisonItem] = Field(default_factory=list)
    summary: ComparisonSummary
    by_category: dict[str, dict[str, int]] = Field(default_factory=dict)
