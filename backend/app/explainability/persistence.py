"""Persistence layer for KESHAV STEP 5 explanations, uncertainty, equity, and OOD records.

Database tables:
- risk_explanations: Local explanation records with provenance
- feature_importance: Global feature importance snapshots
- uncertainty_records: Uncertainty metadata per prediction
- ood_records: Out-of-distribution detection records
- calibration_diagnostics: Calibration quality diagnostics
- equity_audits: Equity audit records and results
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Boolean,
    Index,
    JSON,
)

from ..core.database import Base

logger = logging.getLogger(__name__)


class RiskExplanation(Base):
    """ORM model for local prediction explanations.

    Stores per-prediction explanations with SHAP/contributions,
    baseline comparison, and provenance tracking for auditing.
    """

    __tablename__ = "risk_explanations"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(String, unique=True, nullable=False, index=True)
    model_id = Column(String, nullable=False)
    model_version = Column(String, nullable=False, default="1.0")
    feature_version = Column(String, nullable=False, default="1.0")
    explanation_method = Column(String, nullable=False)
    explanation_version = Column(String, nullable=False, default="5.0.0")

    # Prediction metadata
    risk_probability = Column(Float, nullable=False, default=0.0)
    baseline_probability = Column(Float, nullable=False, default=0.0)
    risk_category = Column(String, nullable=True)

    # Feature contributions
    feature_contributions = Column(JSON, nullable=False, default=dict)
    top_positive_factors = Column(JSON, nullable=False, default=list)
    top_negative_factors = Column(JSON, nullable=False, default=list)
    feature_values = Column(JSON, nullable=False, default=dict)

    # Uncertainty and distribution
    in_distribution = Column(Boolean, nullable=False, default=True)
    ood = Column(Boolean, nullable=False, default=False)
    ood_score = Column(Float, nullable=True)

    # Provenance
    provenance_json = Column(JSON, nullable=False, default=dict)
    input_feature_hash = Column(String, length=32, nullable=True)
    dataset_version = Column(String, length=20, nullable=True, default="1.0")

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Quality assessment
    quality_valid = Column(Boolean, nullable=False, default=True)
    quality_errors = Column(JSON, nullable=True, default=list)
    quality_warnings = Column(JSON, nullable=True, default=list)

    __table_args__ = (
        Index("ix_risk_explanations_prediction_id", "prediction_id"),
        Index("ix_risk_explanions_model_version", "model_version"),
        Index("ix_risk_explanations_ood", "ood"),
    )


class FeatureImportanceSnapshot(Base):
    """ORM model for global feature importance snapshots.

    Stores ranked feature importance at different model versions
    for comparison and audit purposes.
    """

    __tablename__ = "feature_importance"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, nullable=False)
    model_version = Column(String, nullable=False, default="1.0")
    feature_version = Column(String, nullable=False, default="1.0")
    explanation_method = Column(String, nullable=False)
    explanation_version = Column(String, nullable=False, default="5.0.0")

    # Importance data
    feature_importance_json = Column(JSON, nullable=False, default=list)
    total_features = Column(Integer, nullable=False, default=0)

    # Ranked features (top K)
    top_k_features_json = Column(JSON, nullable=False, default=list)

    # Computation metadata
    computation_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_version = Column(String, length=20, nullable=True, default="1.0")
    dataset_size = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_feature_importance_model_version", "model_version", "explanation_method"),
        Index("ix_feature_importance_total", "total_features"),
    )


class UncertaintyRecordDB(Base):
    """ORM model for uncertainty metadata per prediction.

    Stores separate uncertainty metrics from risk probability.
    Implements: risk_probability ≠ prediction certainty.
    """

    __tablename__ = "uncertainty_records"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(String, unique=True, nullable=False, index=True)
    data_quality = Column(String, nullable=False, default="GOOD")
    data_completeness = Column(Float, nullable=False, default=1.0)
    missing_feature_count = Column(Integer, nullable=False, default=0)
    stale_feature_count = Column(Integer, nullable=False, default=0)
    forecast_uncertainty = Column(Float, nullable=True)
    model_uncertainty = Column(String, length=10, nullable=True)  # HIGH/MODERATE/LOW
    confidence_category = Column(String, length=10, nullable=False, default="MODERATE")

    # OOD status
    ood = Column(Boolean, nullable=False, default=False)
    ood_score = Column(Float, nullable=True)

    # Timestamps
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_uncertainty_prediction_id", "prediction_id"),
        Index("ix_uncertainty_data_quality", "data_quality"),
    )


class OODRecordDB(Base):
    """ORM model for out-of-distribution detection records.

    Stores OOD analysis per prediction including which features
    are outside training range.
    """

    __tablename__ = "ood_records"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(String, unique=True, nullable=False, index=True)
    in_distribution = Column(Boolean, nullable=False, default=True)
    ood = Column(Boolean, nullable=False, default=False)
    ood_score = Column(Float, nullable=True)

    # Warning features outside training range
    warning_features_json = Column(JSON, nullable=False, default=list)
    training_ranges_json = Column(JSON, nullable=False, default=dict)

    # Generated message
    message = Column(Text, nullable=True)

    # Timestamps
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ood_prediction_id", "prediction_id"),
        Index("ix_ood_in_distribution", "in_distribution"),
    )


class CalibrationDiagnosticsDB(Base):
    """ORM model for calibration diagnostics.

    Stores calibration quality metrics (Brier, ECE, reliability)
    for comparing raw vs calibrated probabilities.
    """

    __tablename__ = "calibration_diagnostics"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, nullable=False)
    model_version = Column(String, nullable=False, default="1.0")
    calibration_id = Column(String, unique=True, nullable=True)

    # Calibration metrics
    brier_score_raw = Column(Float, nullable=True)
    brier_score_calibrated = Column(Float, nullable=True)
    ece = Column(Float, nullable=True)  # Expected Calibration Error

    # Reliability diagram points
    reliability_image_json = Column(JSON, nullable=True, default=list)

    # Comparison: raw vs calibrated
    comparison_json = Column(JSON, nullable=True, default=dict)

    # Validation data
    validation_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    validation_end = Column(DateTime, nullable=False, default=datetime.utcnow)
    n_validation_samples = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_calibration_model_version", "model_version"),
        Index("ix_calibration_built_at", "created_at"),
    )


class EquityAuditDB(Base):
    """ORM model for equity/fairness audit records.

    Stores subgroup performance metrics and data coverage
    for equity auditing.
    """

    __tablename__ = "equity_audits"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, nullable=False)
    model_version = Column(String, nullable=False, default="1.0")

    # Subgroup identification
    subgroup = Column(String, nullable=False)  # e.g., "elderly_heavy", "data_poor"

    # Sample metrics
    sample_count = Column(Integer, nullable=False, default=0)
    prevalence = Column(Float, nullable=False, default=0.0)

    # Performance metrics
    recall = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    false_positive_rate = Column(Float, nullable=True)
    false_negative_rate = Column(Float, nullable=True)
    specificity = Column(Float, nullable=True)
    brier_score = Column(Float, nullable=True)
    pr_auc = Column(Float, nullable=True)

    # Confidence intervals
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)

    # Sample sufficiency
    sufficient_sample = Column(Boolean, nullable=False, default=False)

    # Data coverage metrics
    data_coverage = Column(Float, nullable=False, default=0.0)  # % features available

    # Computation metadata
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_equity_model_version", "model_version", "subgroup"),
        Index("ix_equity_sufficient_sample", "sufficient_sample"),
    )