"""Risk prediction ORM models — STEP 4 and STEP 5.

Tables created in Step 4:
    risk_predictions, risk_training_runs,
    risk_model_registry, risk_evaluation_metrics,
    risk_feature_manifest, risk_calibration

Tables created in Step 5:
    risk_explanations, feature_importance,
    uncertainty_records, ood_records,
    calibration_diagnostics, equity_audits
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Integer, String, Index, ForeignKey, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class RiskPrediction(Base):
    """Health risk prediction result for a location/time."""

    __tablename__ = "risk_predictions"
    __table_args__ = (
        Index("ix_risk_pred_location_time", "location_id", "target_date"),
        Index("ix_risk_pred_model_version", "model_version"),
        Index("ix_risk_pred_horizon", "horizon_days"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    location_id: Mapped[str] = mapped_column(String(64), index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    prediction_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    target_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, default=0)

    risk_probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_category: Mapped[str] = mapped_column(String(16), index=True)

    model_id: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(32))
    feature_version: Mapped[str] = mapped_column(String(32))
    threshold_version: Mapped[str] = mapped_column(String(32))

    data_completeness: Mapped[float] = mapped_column(Float, default=1.0)
    input_quality: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    missing_features: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    forecast_uncertainty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    source_type: Mapped[str] = mapped_column(String(16))
    prediction_status: Mapped[str] = mapped_column(String(16), default="SUCCESS")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    in_distribution: Mapped[bool] = mapped_column(default=True)
    ood_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RiskTrainingRun(Base):
    __tablename__ = "risk_training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="STARTED", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    training_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    training_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    test_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    test_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    algorithm: Mapped[str] = mapped_column(String(32))
    hyperparameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)
    feature_version: Mapped[str] = mapped_column(String(32))
    target_definition: Mapped[str] = mapped_column(String(64))
    dataset_version: Mapped[str] = mapped_column(String(32))

    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    calibration_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    model_artifact_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class RiskModelRegistry(Base):
    __tablename__ = "risk_model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    model_version: Mapped[str] = mapped_column(String(32), index=True)

    algorithm: Mapped[str] = mapped_column(String(32))
    hyperparameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)
    feature_version: Mapped[str] = mapped_column(String(32))
    target_definition: Mapped[str] = mapped_column(String(64))
    dataset_version: Mapped[str] = mapped_column(String(32))
    training_run_id: Mapped[str] = mapped_column(String(64), index=True)

    status: Mapped[str] = mapped_column(String(16), default="EXPERIMENTAL", index=True)

    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)
    calibration_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    artifact_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RiskExplanation(Base):
    __tablename__ = "risk_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prediction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    explanation_method: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation_version: Mapped[str] = mapped_column(String(32), nullable=False, default="5.0.0")

    risk_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    baseline_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_category: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    feature_contributions: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    top_positive_factors: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    top_negative_factors: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    feature_values: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    in_distribution: Mapped[bool] = mapped_column(default=True)
    ood: Mapped[bool] = mapped_column(default=False)
    ood_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    provenance_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    input_feature_hash: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    dataset_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    quality_valid: Mapped[bool] = mapped_column(default=True)
    quality_errors: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    quality_warnings: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)

    __table_args__ = (
        Index("ix_risk_explanations_prediction_id", "prediction_id"),
        Index("ix_risk_explanations_model_version", "model_version"),
        Index("ix_risk_explanations_ood", "ood"),
    )


class FeatureImportanceSnapshot(Base):
    __tablename__ = "feature_importance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    explanation_method: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation_version: Mapped[str] = mapped_column(String(32), nullable=False, default="5.0.0")

    feature_importance_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    total_features: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_k_features_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    computation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    data_version: Mapped[str] = mapped_column(String(20), nullable=True, default="1.0")
    dataset_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_feature_importance_model_version", "model_version", "explanation_method"),
        Index("ix_feature_importance_total", "total_features"),
    )


class UncertaintyRecordDB(Base):
    __tablename__ = "uncertainty_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prediction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    data_quality: Mapped[str] = mapped_column(String(16), nullable=False, default="GOOD")
    data_completeness: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    missing_feature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stale_feature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    forecast_uncertainty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_uncertainty: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # HIGH/MODERATE/LOW
    confidence_category: Mapped[str] = mapped_column(String(10), nullable=False, default="MODERATE")

    ood: Mapped[bool] = mapped_column(default=False)
    ood_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_uncertainty_prediction_id", "prediction_id"),
        Index("ix_uncertainty_data_quality", "data_quality"),
    )


class OODRecordDB(Base):
    __tablename__ = "ood_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prediction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    in_distribution: Mapped[bool] = mapped_column(default=True)
    ood: Mapped[bool] = mapped_column(default=False)
    ood_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    warning_features_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    training_ranges_json: Mapped[Dict[str, Dict[str, float]]] = mapped_column(JSON, nullable=False, default=dict)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_ood_prediction_id", "prediction_id"),
        Index("ix_ood_in_distribution", "in_distribution"),
    )


class CalibrationDiagnosticsDB(Base):
    __tablename__ = "calibration_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    calibration_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)

    brier_score_raw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brier_score_calibrated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ece: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    reliability_image_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)
    comparison_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, default=dict)

    validation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    validation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    n_validation_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_calibration_model_version", "model_version"),
        Index("ix_calibration_created_at", "created_at"),
    )


class EquityAuditDB(Base):
    __tablename__ = "equity_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")

    subgroup: Mapped[str] = mapped_column(String, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prevalence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    false_positive_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    false_negative_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    specificity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brier_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pr_auc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    confidence_interval_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_interval_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sufficient_sample: Mapped[bool] = mapped_column(default=False)

    data_coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_equity_model_version", "model_version", "subgroup"),
        Index("ix_equity_sufficient_sample", "sufficient_sample"),
    )


class RiskEvaluationMetrics(Base):
    __tablename__ = "risk_evaluation_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(32))

    split_name: Mapped[str] = mapped_column(String(16))
    evaluation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    roc_auc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pr_auc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    f1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    specificity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sensitivity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision_at_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall_at_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    pod: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    far: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    csi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    brier_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calibration_error: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ece: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    slice_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    confusion_matrix: Mapped[Optional[Dict[str, int]]] = mapped_column(JSON, nullable=True)

    dataset_size: Mapped[int] = mapped_column(Integer, default=0)
    positive_rate: Mapped[float] = mapped_column(Float, default=0.0)

    configuration: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class RiskFeatureManifest(Base):
    __tablename__ = "risk_feature_manifest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feature_version: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    features: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RiskCalibration(Base):
    __tablename__ = "risk_calibration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calibration_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    model_id: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(32))

    method: Mapped[str] = mapped_column(String(16))
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)

    validation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    n_samples: Mapped[int] = mapped_column(Integer, default=0)

    brier_score_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brier_score_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calibration_error_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calibration_error_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")

    artifact_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)