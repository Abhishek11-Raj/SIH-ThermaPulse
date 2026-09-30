"""Explanation schemas for KESHAV STEP 5."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LocalExplanationInput(BaseModel):
    """Input to a local explanation request."""

    prediction_id: str
    model_id: str
    model_version: str
    feature_version: str
    input_features: Dict[str, Any]
    feature_names: List[str]


class LocalExplanationOutput(BaseModel):
    """Local explanation output for a single prediction."""

    prediction_id: str
    risk_probability: float
    baseline_probability: float
    top_positive_factors: List[Dict[str, Any]]
    top_negative_factors: List[Dict[str, Any]]
    feature_values: Dict[str, Any]
    feature_contributions: Dict[str, float]
    model_version: str
    feature_version: str
    explanation_method: str
    explanation_version: str
    timestamp: datetime
    in_distribution: bool
    ood: bool = False
    ood_score: Optional[float] = None


class GlobalExplanationOutput(BaseModel):
    """Global model feature importance."""

    model_id: str
    model_version: str
    feature_version: str
    explanation_method: str
    explanation_version: str
    feature_importance: List[Dict[str, Any]]
    top_k: int = 10
    total_features: int


class FeatureImportanceEntry(BaseModel):
    """Single feature importance entry."""

    feature: str
    importance: float
    description: Optional[str] = None


class ExplanationQualityCheck(BaseModel):
    """Validation result for an explanation."""

    explanation_id: str
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ExplanationProvenance(BaseModel):
    """Provenance tracking for an explanation."""

    prediction_id: str
    model_id: str
    model_version: str
    feature_version: str
    explanation_method: str
    explainer_version: str
    input_feature_hash: Optional[str] = None
    dataset_version: Optional[str] = None
    created_at: datetime


class UncertaintyRecord(BaseModel):
    """Uncertainty metadata for a prediction."""

    prediction_id: str
    data_quality: Literal["BEST", "GOOD", "FAIR", "POOR"]
    data_completeness: float
    missing_feature_count: int
    stale_feature_count: int
    forecast_uncertainty: Optional[float] = None
    model_uncertainty: Optional[float] = None
    ood: bool = False
    ood_score: Optional[float] = None
    confidence_category: Literal["HIGH", "MODERATE", "LOW"] = "MODERATE"


class EquityAuditRecord(BaseModel):
    """Equity audit record for a subgroup."""

    subgroup: str
    sample_count: int
    prevalence: float
    recall: Optional[float] = None
    precision: Optional[float] = None
    false_positive_rate: Optional[float] = None
    false_negative_rate: Optional[float] = None
    specificity: Optional[float] = None
    brier_score: Optional[float] = None
    pr_auc: Optional[float] = None
    confidence_interval_lower: Optional[float] = None
    confidence_interval_upper: Optional[float] = None
    sufficient_sample: bool


class OODRecord(BaseModel):
    """Out-of-distribution record for a prediction."""

    prediction_id: str
    in_distribution: bool
    ood: bool = False
    ood_score: Optional[float] = None
    warning_features: List[Dict[str, Any]]
    training_ranges: Dict[str, Dict[str, float]]
    message: Optional[str] = None


class CalibrationDiagnostics(BaseModel):
    """Calibration diagnostics for a model."""

    model_id: str
    model_version: str
    brier_score_raw: Optional[float] = None
    brier_score_calibrated: Optional[float] = None
    ece: Optional[float] = None
    reliability_image_points: Optional[List[Dict[str, Any]]] = None
    comparison: Optional[Dict[str, Any]] = None  # raw vs calibrated