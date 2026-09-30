"""Pydantic V2 schemas for KESHAV STEP 8:
Outcome Verification, Forecast Track Record, Alert Performance, Drift Monitoring & Controlled Self-Learning.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from ..utils.time import utcnow


# ============================================================
# Enums
# ============================================================

class VerificationWindowType(str, Enum):
    SAME_DAY = "SAME_DAY"
    NEXT_DAY = "NEXT_DAY"
    WINDOW_24H = "24H"
    WINDOW_48H = "48H"
    WINDOW_72H = "72H"
    HORIZON = "HORIZON"


class OutcomeMatchStatus(str, Enum):
    MATCHED = "MATCHED"
    NO_OUTCOME_AVAILABLE = "NO_OUTCOME_AVAILABLE"
    DELAYED = "DELAYED"
    INCOMPATIBLE_WINDOW = "INCOMPATIBLE_WINDOW"
    REVISED = "REVISED"


class ModelHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    RETRAIN_RECOMMENDED = "RETRAIN_RECOMMENDED"
    RETIRE_RECOMMENDED = "RETIRE_RECOMMENDED"


class ModelCandidateStatus(str, Enum):
    TRAINED = "TRAINED"
    VALIDATED = "VALIDATED"
    CHALLENGER = "CHALLENGER"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEPLOYED = "DEPLOYED"
    RETIRED = "RETIRED"


class AlertTimeliness(str, Enum):
    EARLY = "EARLY"
    ON_TIME = "ON_TIME"
    LATE = "LATE"
    MISSED = "MISSED"


# ============================================================
# 1. Outcome Schemas
# ============================================================

class OutcomeRecordCreate(BaseModel):
    location_id: str
    outcome_date: datetime
    outcome_type: str = "heat_hospital_admissions"
    observed_count: int = Field(ge=0)
    heat_illness_cases: Optional[int] = Field(default=None, ge=0)
    emergency_visits: Optional[int] = Field(default=None, ge=0)
    hospital_admissions: Optional[int] = Field(default=None, ge=0)
    mortality_count: Optional[int] = Field(default=None, ge=0)
    aggregation_level: str = "WARD_DAY"
    source: str = "synthetic_health_surveillance"
    provider: str = "mock_health_provider"
    quality_status: str = "VALID"
    revision_status: str = "FINAL"
    is_synthetic: bool = True
    provenance: Optional[Dict[str, Any]] = None


class OutcomeRecordResponse(BaseModel):
    outcome_id: str
    location_id: str
    outcome_date: datetime
    outcome_type: str
    observed_count: int
    heat_illness_cases: Optional[int] = None
    emergency_visits: Optional[int] = None
    hospital_admissions: Optional[int] = None
    mortality_count: Optional[int] = None
    aggregation_level: str
    source: str
    provider: str
    quality_status: str
    revision_status: str
    is_synthetic: bool = True
    created_at: datetime
    updated_at: datetime


class OutcomeListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    outcomes: List[OutcomeRecordResponse]


class OutcomeRevisionRequest(BaseModel):
    new_count: int = Field(ge=0)
    new_status: str = "FINAL"
    reason: str
    revised_by: str = "health_admin"


class OutcomeRevisionResponse(BaseModel):
    revision_id: str
    outcome_id: str
    previous_count: int
    new_count: int
    previous_status: str
    new_status: str
    reason: str
    revised_by: str
    revised_at: datetime


# ============================================================
# 2. Outcome Verification & Track Record Schemas
# ============================================================

class OutcomeVerificationRequest(BaseModel):
    prediction_id: str
    verification_window: VerificationWindowType = VerificationWindowType.WINDOW_24H
    event_risk_threshold: float = 0.60
    outcome_event_threshold: int = 5


class OutcomeVerificationResponse(BaseModel):
    verification_id: str
    prediction_id: str
    location_id: str
    model_id: str
    model_version: str
    forecast_issued_at: datetime
    forecast_valid_from: datetime
    forecast_valid_to: datetime
    forecast_horizon_hours: int
    predicted_risk_probability: float
    predicted_risk_category: str
    observed_outcome_id: Optional[str] = None
    observed_value: Optional[float] = None
    verification_window: str
    error_residual: Optional[float] = None
    brier_contribution: Optional[float] = None
    match_status: str
    event_ground_truth: Optional[bool] = None
    event_prediction: Optional[bool] = None
    classification_outcome: Optional[str] = None
    is_synthetic: bool = True
    created_at: datetime


class TrackRecordItem(BaseModel):
    verification_id: str
    prediction_id: str
    location_id: str
    model_version: str
    forecast_issued_at: datetime
    forecast_valid_from: datetime
    forecast_valid_to: datetime
    forecast_horizon_hours: int
    predicted_risk_probability: float
    predicted_risk_category: str
    observed_value: Optional[float] = None
    error_residual: Optional[float] = None
    match_status: str
    classification_outcome: Optional[str] = None


class TrackRecordMetrics(BaseModel):
    sample_size: int
    mae: Optional[float] = None
    rmse: Optional[float] = None
    brier_score: Optional[float] = None
    calibration_error: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    specificity: Optional[float] = None
    pod: Optional[float] = None  # Probability of Detection
    far: Optional[float] = None  # False Alarm Ratio
    csi: Optional[float] = None  # Critical Success Index
    average_lead_time_hours: Optional[float] = None


class TrackRecordSummary(BaseModel):
    total_verifications: int
    matched_verifications: int
    missing_outcomes: int
    metrics: TrackRecordMetrics
    records: List[TrackRecordItem] = Field(default_factory=list)


# ============================================================
# 3. Alert Performance Schemas
# ============================================================

class AlertConfusionMatrix(BaseModel):
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    total_evaluated_events: int = 0


class AlertFatigueMetrics(BaseModel):
    alerts_per_ward_avg: float = 0.0
    alerts_per_day_avg: float = 0.0
    duplicate_suppressed_count: int = 0
    repeated_alert_sequences: int = 0
    acknowledgement_rate: float = 0.0
    average_ack_delay_minutes: float = 0.0


class ProviderPerformanceMetric(BaseModel):
    channel: str
    provider_name: str
    dispatched_count: int = 0
    delivered_count: int = 0
    mocked_count: int = 0
    failed_count: int = 0
    success_rate: float = 0.0
    is_mock: bool = False


class AlertPerformanceSummary(BaseModel):
    total_alerts: int
    delivered_count: int
    mocked_count: int
    failed_count: int
    acknowledged_count: int
    average_lead_time_hours: float
    confusion_matrix: AlertConfusionMatrix
    fatigue_metrics: AlertFatigueMetrics
    provider_breakdown: List[ProviderPerformanceMetric] = Field(default_factory=list)
    timeliness_distribution: Dict[str, int] = Field(default_factory=dict)


# ============================================================
# 4. Drift & Model Health Monitoring Schemas
# ============================================================

class FeatureDriftResult(BaseModel):
    feature_name: str
    drift_metric: str  # "PSI", "KS_STATISTIC", "WASSERSTEIN"
    statistic_value: float
    threshold: float
    drift_detected: bool
    severity: Literal["NONE", "LOW", "MODERATE", "SEVERE"]


class DataDriftReport(BaseModel):
    baseline_period: str
    current_period: str
    overall_drift_detected: bool
    drifted_feature_count: int
    total_features_evaluated: int
    features: List[FeatureDriftResult] = Field(default_factory=list)


class ConceptDriftReport(BaseModel):
    metric: str
    baseline_brier: float
    current_brier: float
    baseline_pr_auc: float
    current_pr_auc: float
    performance_drop: float
    concept_drift_detected: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class OODTrendReport(BaseModel):
    total_predictions: int
    ood_predictions: int
    ood_rate: float
    ood_rate_trend: Literal["STABLE", "INCREASING", "DECREASING"]
    high_ood_wards: List[str] = Field(default_factory=list)


class SubgroupEquityMetric(BaseModel):
    subgroup: str
    sample_size: int
    recall: Optional[float] = None
    false_positive_rate: Optional[float] = None
    brier_score: Optional[float] = None
    sufficient_sample: bool = True
    disparity_detected: bool = False


class EquityMonitoringReport(BaseModel):
    model_version: str
    evaluation_date: datetime = Field(default_factory=utcnow)
    subgroups: List[SubgroupEquityMetric] = Field(default_factory=list)
    max_recall_disparity: float = 0.0
    max_fpr_disparity: float = 0.0
    equity_warning: bool = False


class ModelHealthReport(BaseModel):
    model_id: str
    model_version: str
    status: ModelHealthStatus
    data_drift: DataDriftReport
    concept_drift: ConceptDriftReport
    ood_trend: OODTrendReport
    equity_status: EquityMonitoringReport
    retrain_recommended: bool
    reasons: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=utcnow)


# ============================================================
# 5. Candidate Training & Model Governance Schemas
# ============================================================

class CandidateTrainingRequest(BaseModel):
    algorithm: str = "LightGBM"
    dataset_version: str = "2.0"
    feature_manifest_version: str = "1.0"
    training_start_date: datetime
    training_end_date: datetime
    validation_start_date: datetime
    validation_end_date: datetime
    hyperparameters: Optional[Dict[str, Any]] = None
    random_seed: int = 2026
    notes: Optional[str] = None


class SafetyGateCheckResult(BaseModel):
    gate_name: str
    passed: bool
    criterion: str
    champion_value: Optional[float] = None
    challenger_value: Optional[float] = None
    message: str


class ModelComparisonReport(BaseModel):
    champion_version: str
    challenger_version: str
    champion_metrics: Dict[str, Any]
    challenger_metrics: Dict[str, Any]
    metric_deltas: Dict[str, float]
    safety_gates: List[SafetyGateCheckResult]
    all_safety_gates_passed: bool
    recommendation: Literal["APPROVE_CANDIDATE", "REJECT_CANDIDATE", "HUMAN_REVIEW_REQUIRED"]


class ModelCandidateResponse(BaseModel):
    candidate_id: str
    model_id: str
    model_version: str
    training_run_id: str
    algorithm: str
    dataset_version: str
    feature_manifest_version: str
    status: ModelCandidateStatus
    artifact_hash: str
    metrics: Dict[str, Any]
    safety_gates_passed: bool
    safety_gate_details: Dict[str, Any]
    comparison_summary: Optional[Dict[str, Any]] = None
    created_at: datetime
    created_by: str
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None


class ModelApprovalRequest(BaseModel):
    approved_by: str
    approval_notes: str


class ModelDeploymentRequest(BaseModel):
    deployed_by: str
    reason: str


class ModelRollbackRequest(BaseModel):
    target_model_version: Optional[str] = None
    reason: str
    executed_by: str


class ChampionChallengerStatus(BaseModel):
    champion: Optional[Dict[str, Any]] = None
    challenger: Optional[Dict[str, Any]] = None
    all_models_count: int = 0
    last_deployment: Optional[Dict[str, Any]] = None
    last_rollback: Optional[Dict[str, Any]] = None
