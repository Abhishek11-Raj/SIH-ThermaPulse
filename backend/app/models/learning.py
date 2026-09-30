"""SQLAlchemy ORM models for KESHAV STEP 8:
Outcome Verification, Forecast Track Record, Alert Performance, Drift Monitoring, and Model Governance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class OutcomeRecordDB(Base):
    """Aggregated, privacy-preserving health outcome record for an area and time window."""

    __tablename__ = "outcome_records"
    __table_args__ = (
        Index("ix_outcome_loc_date", "location_id", "outcome_date"),
        Index("ix_outcome_type", "outcome_type"),
        Index("ix_outcome_quality", "quality_status"),
    )

    outcome_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    outcome_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    outcome_type: Mapped[str] = mapped_column(String(64), default="heat_hospital_admissions")
    
    observed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    heat_illness_cases: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    emergency_visits: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hospital_admissions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mortality_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    aggregation_level: Mapped[str] = mapped_column(String(32), default="WARD_DAY")
    source: Mapped[str] = mapped_column(String(64), default="synthetic_health_surveillance")
    provider: Mapped[str] = mapped_column(String(64), default="mock_health_provider")
    quality_status: Mapped[str] = mapped_column(String(32), default="VALID")
    revision_status: Mapped[str] = mapped_column(String(32), default="FINAL")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutcomeVerificationDB(Base):
    """Historical verification comparing a prediction with actual observed outcome."""

    __tablename__ = "outcome_verifications"
    __table_args__ = (
        Index("ix_verif_pred_id", "prediction_id"),
        Index("ix_verif_loc_time", "location_id", "forecast_valid_from"),
        Index("ix_verif_match_status", "match_status"),
        Index("ix_verif_model_ver", "model_id", "model_version"),
    )

    verification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prediction_id: Mapped[str] = mapped_column(String(64), index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    
    model_id: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(32), default="1.0")
    
    forecast_issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forecast_valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forecast_valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forecast_horizon_hours: Mapped[int] = mapped_column(Integer, default=24)
    
    predicted_risk_probability: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_risk_category: Mapped[str] = mapped_column(String(16))
    
    observed_outcome_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    observed_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verification_window: Mapped[str] = mapped_column(String(32), default="24H")
    
    error_residual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brier_contribution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    match_status: Mapped[str] = mapped_column(String(32), default="MATCHED")
    event_ground_truth: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    event_prediction: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    classification_outcome: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # TP, FP, TN, FN, UNVERIFIED
    
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutcomeRevisionDB(Base):
    """Audit log of revisions made to health outcome records."""

    __tablename__ = "outcome_revisions"
    __table_args__ = (
        Index("ix_rev_outcome_id", "outcome_id"),
        Index("ix_rev_at", "revised_at"),
    )

    revision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    outcome_id: Mapped[str] = mapped_column(String(64), index=True)
    
    previous_count: Mapped[int] = mapped_column(Integer, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_status: Mapped[str] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32))
    
    reason: Mapped[str] = mapped_column(Text)
    revised_by: Mapped[str] = mapped_column(String(64))
    revised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertPerformanceDB(Base):
    """Operational and event-level performance tracking for issued alerts."""

    __tablename__ = "alert_performance_records"
    __table_args__ = (
        Index("ix_alert_perf_alert_id", "alert_id"),
        Index("ix_alert_perf_loc_time", "location_id", "issued_at"),
    )

    performance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), index=True)
    prediction_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    alert_level: Mapped[str] = mapped_column(String(16))
    
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lead_time_hours: Mapped[float] = mapped_column(Float, default=24.0)
    timeliness: Mapped[str] = mapped_column(String(32), default="ON_TIME")  # EARLY, ON_TIME, LATE, MISSED
    
    outcome_event_occurred: Mapped[bool] = mapped_column(Boolean, default=False)
    confusion_status: Mapped[str] = mapped_column(String(16), default="TP")  # TP, FP, TN, FN
    
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    mocked_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledgement_delay_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DriftRecordDB(Base):
    """Recorded data drift, concept drift, calibration, or equity shift findings."""

    __tablename__ = "drift_records"
    __table_args__ = (
        Index("ix_drift_type", "drift_type"),
        Index("ix_drift_detected_at", "detected_at"),
    )

    drift_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    drift_type: Mapped[str] = mapped_column(String(64))  # FEATURE_DATA_DRIFT, CONCEPT_DRIFT, CALIBRATION_DRIFT, OOD_TREND, EQUITY_DISPARITY
    feature_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    baseline_period: Mapped[str] = mapped_column(String(64))
    current_period: Mapped[str] = mapped_column(String(64))
    
    test_statistic: Mapped[float] = mapped_column(Float, default=0.0)
    threshold: Mapped[float] = mapped_column(Float, default=0.2)
    drift_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(16), default="NONE")  # NONE, LOW, MODERATE, SEVERE
    
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelCandidateDB(Base):
    """Candidate challenger model evaluated for controlled promotion into production."""

    __tablename__ = "model_candidates"
    __table_args__ = (
        Index("ix_cand_model_ver", "model_id", "model_version"),
        Index("ix_cand_status", "status"),
    )

    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(32), index=True)
    training_run_id: Mapped[str] = mapped_column(String(64))
    
    algorithm: Mapped[str] = mapped_column(String(32), default="LightGBM")
    dataset_version: Mapped[str] = mapped_column(String(32), default="1.0")
    feature_manifest_version: Mapped[str] = mapped_column(String(32), default="1.0")
    
    status: Mapped[str] = mapped_column(String(32), default="TRAINED", index=True)  # TRAINED, VALIDATED, CHALLENGER, APPROVED, REJECTED, DEPLOYED, RETIRED
    artifact_hash: Mapped[str] = mapped_column(String(64), default="")
    
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    safety_gates_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_gate_details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    comparison_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(64), default="admin")
    
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ModelDeploymentDB(Base):
    """Audit record of production model deployments."""

    __tablename__ = "model_deployments"
    __table_args__ = (
        Index("ix_dep_deployed_at", "deployed_at"),
        Index("ix_dep_status", "status"),
    )

    deployment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    
    previous_champion_id: Mapped[str] = mapped_column(String(64))
    previous_champion_version: Mapped[str] = mapped_column(String(32))
    
    new_champion_id: Mapped[str] = mapped_column(String(64))
    new_champion_version: Mapped[str] = mapped_column(String(32))
    
    deployed_by: Mapped[str] = mapped_column(String(64))
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")  # ACTIVE, ROLLED_BACK, SUPERSEDED


class ModelRollbackDB(Base):
    """Audit log of model rollbacks to previous stable champion versions."""

    __tablename__ = "model_rollbacks"
    __table_args__ = (
        Index("ix_roll_executed_at", "executed_at"),
    )

    rollback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    deployment_id: Mapped[str] = mapped_column(String(64), index=True)
    
    rolled_back_model_id: Mapped[str] = mapped_column(String(64))
    rolled_back_model_version: Mapped[str] = mapped_column(String(32))
    
    restored_model_id: Mapped[str] = mapped_column(String(64))
    restored_model_version: Mapped[str] = mapped_column(String(32))
    
    reason: Mapped[str] = mapped_column(Text)
    executed_by: Mapped[str] = mapped_column(String(64))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
