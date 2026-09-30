"""Risk prediction schemas — STEP 4.

Pydantic schemas for health risk predictions, model registry,
evaluation, calibration, and API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.enums import QualityFlag
from ..schemas.common import Provenance, QualityAssessment, SpatialReference, TemporalReference


# --- Target Definition -------------------------------------------------------

class RiskTargetConfig(BaseModel):
    """Configuration for the health risk prediction target."""

    target_type: Literal["binary", "count", "rate"] = "binary"
    # binary: heat event occurred (yes/no)
    # count: number of heat-related health events
    # rate: events per population

    # For binary target
    threshold_config: Optional[Dict[str, Any]] = None

    # For count/rate targets
    population_field: Optional[str] = None

    class Config:
        extra = "forbid"


# --- Feature Schemas ---------------------------------------------------------

class RiskFeatureConfig(BaseModel):
    """Configuration for feature engineering."""

    # Thermal features to include
    thermal_indices: List[str] = [
        "temperature_c", "heat_index_c", "wet_bulb_c",
        "wbgt_c", "utci_c", "mrt_c",
        "daily_stress", "exposure_memory"
    ]

    # Nighttime features
    nighttime_features: List[str] = [
        "nighttime_temperature_c", "nighttime_anomaly_c",
        "hot_night", "consecutive_hot_nights",
        "recovery_deficit", "recovery_hours"
    ]

    # Exposure features
    exposure_windows_hours: List[int] = [24, 72, 168]
    exposure_features: List[str] = [
        "cumulative_exposure_24h", "cumulative_exposure_72h",
        "cumulative_exposure_168h", "exposure_memory"
    ]

    # Vulnerability features
    vulnerability_features: List[str] = [
        "elderly_population_share", "children_population_share",
        "outdoor_worker_share", "population_density_per_km2",
        "housing_vulnerability_index", "cooling_access_share",
        "electricity_reliability_index", "water_access_share",
        "healthcare_accessibility_index", "socioeconomic_vulnerability_index",
        "informal_settlement_share"
    ]

    # Air quality features
    air_quality_features: List[str] = [
        "pm25_ugm3", "pm10_ugm3", "o3_ugm3", "no2_ugm3",
        "so2_ugm3", "co_mgm3", "aqi_index"
    ]

    # Lag features
    lag_hours: List[int] = [1, 2, 3, 6, 12, 24, 48, 72]
    lag_features: List[str] = [
        "utci_c", "wbgt_c", "exposure_memory", "hot_night"
    ]

    # Rolling window features
    rolling_windows_hours: List[int] = [3, 6, 12, 24, 48, 72, 168]
    rolling_features: List[str] = [
        "utci_c", "wbgt_c", "temperature_c", "exposure_memory"
    ]

    # Imputation policies
    imputation_policy: Literal["forward_fill", "interpolate", "historical_mean", "none"] = "forward_fill"
    max_gap_hours: int = 6

    class Config:
        extra = "forbid"


class FeatureManifestEntry(BaseModel):
    """Single entry in the feature manifest."""

    name: str
    source: str  # e.g., "thermal", "vulnerability", "health", "derived"
    unit: Optional[str] = None
    time_window: Optional[str] = None  # e.g., "24h", "7d"
    lag: Optional[int] = None  # hours
    allowed_at_prediction_time: bool = True
    missing_policy: Literal["drop", "impute", "flag", "error"] = "impute"
    imputation_policy: Optional[str] = None
    version: str = "1.0"
    description: Optional[str] = None
    derivation: Optional[str] = None  # e.g., "lag_24h(utci_c)", "rolling_7d_mean(temperature_c)"


# --- Target Definition -------------------------------------------------------

class HealthRiskTarget(BaseModel):
    """Health risk prediction target definition."""

    target_name: str
    target_type: Literal["binary", "count", "rate"] = "binary"
    description: str

    # For binary: what constitutes a positive case
    positive_threshold: Optional[float] = None
    positive_definition: Optional[str] = None  # e.g., "heat_illness_cases > 0"

    # For count/rate
    population_normalization: Optional[str] = None

    # Outcome window
    outcome_window_days: int = 1  # predict for next N days

    class Config:
        extra = "forbid"


# --- Configuration -----------------------------------------------------------

class RiskModelConfig(BaseModel):
    """Configuration for risk model training."""

    # Target
    target: Any  # HealthRiskTarget

    # Features
    features: Any = Field(default_factory=dict)  # RiskFeatureConfig

    # Data splits
    train_end_date: datetime
    validation_start_date: datetime
    validation_end_date: datetime
    test_start_date: datetime
    test_end_date: datetime

    # Spatial splits (optional)
    spatial_holdout_locations: Optional[List[str]] = None

    # Model type
    algorithm: Literal["logistic_regression", "hist_gradient_boosting", "xgboost"] = "hist_gradient_boosting"

    # Hyperparameters
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)

    # Class imbalance
    class_weight: Literal["balanced", "auto", "none"] = "balanced"
    oversample: bool = False
    oversample_ratio: Optional[float] = None

    # Calibration
    calibration_method: Literal["platt", "isotonic", "none"] = "isotonic"
    calibration_fraction: float = 0.2

    # Thresholds
    risk_thresholds: List[float] = [0.25, 0.5, 0.75]
    risk_labels: List[str] = ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]

    # Feature selection
    max_features: Optional[int] = None
    min_feature_importance: float = 0.0

    # Reproducibility
    random_seed: int = 42

    class Config:
        extra = "forbid"


# --- Output/Result Schemas ---------------------------------------------------

class RiskPredictionOutput(BaseModel):
    """Health risk prediction output."""

    prediction_id: str
    location_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    prediction_time: datetime
    target_date: datetime
    horizon_days: int = Field(default=0, ge=0, le=5)

    risk_probability: float = Field(ge=0.0, le=1.0)
    risk_category: Literal["LOW", "MODERATE", "HIGH", "VERY_HIGH"]

    # Model metadata
    model_id: str
    model_version: str
    feature_version: str
    threshold_version: str

    # Data quality
    data_completeness: float = Field(ge=0.0, le=1.0, default=1.0)
    input_quality: Optional[Literal["BEST", "GOOD", "FAIR", "POOR"]] = None
    missing_features: List[str] = Field(default_factory=list)
    forecast_uncertainty: Optional[float] = None

    # Source
    source_type: Literal["NOWCAST", "FORECAST"]

    # Uncertainty
    in_distribution: bool = True
    ood_score: Optional[float] = None

    # Status
    prediction_status: Literal["SUCCESS", "PARTIAL", "FAILED"] = "SUCCESS"
    error_message: Optional[str] = None

    # Provenance
    provenance: Optional[Dict[str, Any]] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class RiskPredictionList(BaseModel):
    predictions: List[Any]  # RiskPredictionOutput
    count: int = 0


class RiskPredictionRequest(BaseModel):
    """Request for health risk prediction."""

    location_id: str
    target_date: Optional[datetime] = None
    horizon_days: int = Field(default=0, ge=0, le=5)
    model_id: Optional[str] = None
    include_feature_vector: bool = False


class RiskTrainingRequest(BaseModel):
    """Request to train a new risk model."""

    config: Any  # RiskModelConfig
    run_id: Optional[str] = None


class RiskTrainingResponse(BaseModel):
    """Response from training request."""

    run_id: str
    status: Literal["STARTED", "SUCCESS", "FAILED", "PARTIAL"]
    model_id: Optional[str] = None
    model_version: Optional[str] = None


class RiskTrainingRunOutput(BaseModel):
    """Training run output."""

    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: Literal["STARTED", "SUCCESS", "FAILED", "PARTIAL"]
    error_message: Optional[str] = None

    training_start: datetime
    training_end: datetime
    validation_start: datetime
    validation_end: datetime
    test_start: datetime
    test_end: datetime

    algorithm: str
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    feature_version: str
    target_definition: str
    dataset_version: str

    metrics: Optional[Dict[str, Any]] = None
    calibration_metrics: Optional[Dict[str, Any]] = None

    model_artifact_path: Optional[str] = None
    duration_ms: Optional[int] = None


class RiskModelRegistryOutput(BaseModel):
    """Model registry entry output."""

    model_id: str
    model_version: str
    algorithm: str
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    feature_version: str
    target_definition: str
    dataset_version: str
    training_run_id: str
    status: Literal["EXPERIMENTAL", "VALIDATED", "PRODUCTION", "RETIRED"]
    metrics: Dict[str, Any] = Field(default_factory=dict)
    calibration_version: Optional[str] = None
    artifact_path: Optional[str] = None
    created_at: datetime
    promoted_at: Optional[datetime] = None
    promoted_by: Optional[str] = None
    notes: Optional[str] = None


class RiskEvaluationOutput(BaseModel):
    """Model evaluation output."""

    model_id: str
    model_version: str
    split_name: Literal["TRAIN", "VALIDATION", "TEST"]
    evaluation_date: datetime

    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    specificity: Optional[float] = None
    sensitivity: Optional[float] = None

    threshold: Optional[float] = None
    precision_at_threshold: Optional[float] = None
    recall_at_threshold: Optional[float] = None

    pod: Optional[float] = None
    far: Optional[float] = None
    csi: Optional[float] = None

    brier_score: Optional[float] = None
    calibration_error: Optional[float] = None
    ece: Optional[float] = None

    slice_metrics: Optional[Dict[str, Any]] = None
    confusion_matrix: Optional[Dict[str, int]] = None

    dataset_size: int = 0
    positive_rate: float = 0.0
    configuration: Optional[Dict[str, Any]] = None


class RiskFeatureManifestOutput(BaseModel):
    """Feature manifest output."""

    feature_version: str
    features: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    description: Optional[str] = None


class RiskCalibrationOutput(BaseModel):
    """Calibration output."""

    calibration_id: str
    model_id: str
    model_version: str
    method: Literal["PLATT", "ISOTONIC", "NONE"]
    parameters: Dict[str, Any] = Field(default_factory=dict)
    validation_start: datetime
    validation_end: datetime
    n_samples: int = 0
    brier_score_before: Optional[float] = None
    brier_score_after: Optional[float] = None
    calibration_error_before: Optional[float] = None
    calibration_error_after: Optional[float] = None
    created_at: datetime
    status: Literal["ACTIVE", "ARCHIVED"] = "ACTIVE"
    artifact_path: Optional[str] = None


class RiskMethodsResponse(BaseModel):
    """Available risk calculation methods."""

    algorithms: List[Dict[str, Any]]
    default_config: Any  # RiskModelConfig


class RiskHealthOutput(BaseModel):
    """Health check for risk service."""

    status: Literal["healthy", "degraded", "unhealthy"]
    model_registry_status: str
    available_models: int
    production_model: Optional[str] = None
    last_training: Optional[datetime] = None
    data_freshness: Optional[str] = None


class RiskForecastOutput(BaseModel):
    """Forecast risk output for multiple days."""

    location_id: str
    prediction_time: datetime
    forecasts: List[Any]  # RiskPredictionOutput
    model_id: str
    model_version: str
    feature_version: str


class RiskCalculateRequest(BaseModel):
    """Request body for POST /api/v1/risk/calculate."""

    location_id: str
    timestamps: List[datetime]
    inputs: List[Any]  # ThermalInput
    source_type: Literal["OBSERVATION", "FORECAST", "ESTIMATED"] = "OBSERVATION"
    config: Optional[Any] = None  # ThermalCalculationConfig


# ThermalInput for risk calculation requests (simplified, not full WeatherObservation)
class ThermalInput(BaseModel):
    """Simple thermal input for risk calculation requests."""

    air_temperature_c: Optional[float] = None
    relative_humidity: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    pressure_hpa: Optional[float] = None
    solar_radiation_wm2: Optional[float] = None
    cloud_cover_pct: Optional[float] = None

    @field_validator("relative_humidity", "cloud_cover_pct")
    @classmethod
    def _pct_0_100(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("percentage value outside 0-100")
        return v

    @field_validator("wind_direction_deg")
    @classmethod
    def _wind_dir(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 360.0):
            raise ValueError("wind_direction outside 0-360")
        return v