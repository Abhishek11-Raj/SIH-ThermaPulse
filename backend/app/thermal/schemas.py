"""Thermal stress schemas — STEP 3.

Pydantic schemas for thermal stress calculations, exposure memory,
nighttime heat, and API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from ..core.enums import QualityFlag
from ..schemas.common import Provenance, QualityAssessment, SpatialReference, TemporalReference


# --- Input/Configuration Schemas --------------------------------------------

class ThermalInput(BaseModel):
    """Meteorological input for thermal stress calculations."""

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


class ThermalCalculationConfig(BaseModel):
    """Configuration for thermal stress calculations."""

    # Heat Index
    heat_index_method: Literal["rothfusz", "steveg"] = "rothfusz"

    # Wet-bulb
    wet_bulb_method: Literal["stull", "davies_jones", "iterative"] = "stull"

    # WBGT
    wbgt_indoor: bool = False
    wbgt_estimate_globe: bool = True
    wbgt_method: Literal["liljegren", "bernard"] = "liljegren"

    # UTCI
    utci_method: Literal["brute_force", "lookup", "approximation"] = "approximation"

    # MRT
    mrt_method: Literal["solar_only", "full_radiative", "unavailable"] = "solar_only"

    # Nighttime
    nighttime_start_hour: int = 20
    nighttime_end_hour: int = 8
    nighttime_percentile: float = 90.0  # percentile for hot night threshold
    nighttime_baseline_days: int = 30
    recovery_threshold_c: float = 25.0

    # Cumulative exposure
    exposure_windows_hours: List[int] = [24, 72, 168]  # 24h, 72h, 7d
    daily_stress_method: Literal["simple_max", "time_weighted"] = "time_weighted"

    # Exposure memory
    memory_decay_factor: float = 0.95  # per hour
    memory_window_hours: int = 168  # 7 days

    # Classification thresholds
    hi_thresholds: List[float] = [27.0, 32.0, 41.0, 54.0]  # Caution, Extreme Caution, Danger, Extreme Danger
    wbgt_thresholds: List[float] = [25.0, 28.0, 30.0, 32.0]  # Low, Moderate, High, Very High
    utci_thresholds: List[float] = [9.0, 26.0, 32.0, 38.0, 46.0]  # No stress, Moderate, Strong, Very Strong, Extreme
    wb_thresholds: List[float] = [25.0, 28.0, 31.0, 35.0]  # WB thresholds

    class Config:
        extra = "forbid"


# --- Output/Result Schemas --------------------------------------------------

class ThermalIndices(BaseModel):
    """Computed thermal stress indices."""

    heat_index_c: Optional[float] = None
    heat_index_f: Optional[float] = None
    wet_bulb_c: Optional[float] = None
    wbgt_c: Optional[float] = None
    wbgt_indoor_c: Optional[float] = None
    utci_c: Optional[float] = None
    mrt_c: Optional[float] = None

    # Method metadata
    heat_index_method: Optional[str] = None
    wet_bulb_method: Optional[str] = None
    wbgt_method: Optional[str] = None
    wbgt_estimated_components: Optional[Dict[str, bool]] = None
    utci_method: Optional[str] = None
    mrt_method: Optional[str] = None


class NighttimeMetrics(BaseModel):
    """Nighttime heat analysis metrics."""

    nighttime_temperature_c: Optional[float] = None
    nighttime_mean_temperature_c: Optional[float] = None
    nighttime_max_temperature_c: Optional[float] = None
    nighttime_anomaly_c: Optional[float] = None
    nighttime_percentile: Optional[float] = None

    hot_night: Optional[bool] = None
    consecutive_hot_nights: Optional[int] = None
    hot_night_threshold_c: Optional[float] = None

    recovery_deficit: Optional[float] = None
    recovery_status: Optional[str] = None
    recovery_hours: Optional[float] = None


class ExposureMetrics(BaseModel):
    """Cumulative exposure and memory metrics."""

    daily_stress: Optional[float] = None
    cumulative_exposure_24h: Optional[float] = None
    cumulative_exposure_72h: Optional[float] = None
    cumulative_exposure_7d: Optional[float] = None
    exposure_memory: Optional[float] = None

    memory_decay_factor: Optional[float] = None
    memory_window_hours: Optional[int] = None


class ThermalClassification(BaseModel):
    """Thermal stress classification results."""

    thermal_stress_category: Optional[str] = None
    occupational_heat_category: Optional[str] = None
    nighttime_recovery_category: Optional[str] = None


class ThermalQualityUncertainty(BaseModel):
    """Quality and uncertainty propagation results."""

    quality_summary: Dict[str, Any] = Field(default_factory=dict)
    uncertainty_summary: Dict[str, Any] = Field(default_factory=dict)

    # Per-index quality flags
    heat_index_quality: Optional[QualityFlag] = None
    wet_bulb_quality: Optional[QualityFlag] = None
    wbgt_quality: Optional[QualityFlag] = None
    utci_quality: Optional[QualityFlag] = None
    mrt_quality: Optional[QualityFlag] = None
    nighttime_quality: Optional[QualityFlag] = None
    exposure_quality: Optional[QualityFlag] = None
    memory_quality: Optional[QualityFlag] = None


class ThermalProvenance(BaseModel):
    """Provenance metadata for thermal calculations."""

    method_versions: Dict[str, str] = Field(default_factory=dict)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Provenance] = None
    source_observation_ids: List[str] = Field(default_factory=list)
    source_forecast_ids: List[str] = Field(default_factory=list)


class ThermalStressResult(BaseModel):
    """Complete thermal stress calculation result for a single timestamp."""

    calculation_id: str
    location_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: datetime
    source_type: Literal["OBSERVATION", "FORECAST", "ESTIMATED"]

    # Inputs
    inputs: ThermalInput

    # Outputs
    indices: ThermalIndices = Field(default_factory=ThermalIndices)
    nighttime: Optional[NighttimeMetrics] = None
    exposure: Optional[ExposureMetrics] = None
    classification: Optional[ThermalClassification] = None
    quality: ThermalQualityUncertainty = Field(default_factory=ThermalQualityUncertainty)
    provenance: ThermalProvenance = Field(default_factory=ThermalProvenance)

    # Explanation
    explanation: Optional[str] = None


class ThermalStressResultList(BaseModel):
    results: List[ThermalStressResult]
    count: int = 0


class ThermalDailySummary(BaseModel):
    """Daily aggregate thermal stress summary."""

    location_id: str
    date: datetime

    max_temperature_c: Optional[float] = None
    min_temperature_c: Optional[float] = None
    mean_temperature_c: Optional[float] = None

    max_heat_index_c: Optional[float] = None
    max_wbgt_c: Optional[float] = None
    max_utci_c: Optional[float] = None

    max_thermal_stress_category: Optional[str] = None
    hot_day: bool = False
    extreme_day: bool = False

    nighttime_min_temperature_c: Optional[float] = None
    nighttime_mean_temperature_c: Optional[float] = None
    nighttime_max_temperature_c: Optional[float] = None
    hot_night: bool = False
    consecutive_hot_nights: int = 0

    recovery_deficit: Optional[float] = None
    recovery_status: Optional[str] = None
    recovery_hours: Optional[float] = None

    cumulative_exposure_24h: Optional[float] = None
    cumulative_exposure_72h: Optional[float] = None
    cumulative_exposure_7d: Optional[float] = None
    exposure_memory: Optional[float] = None

    quality_summary: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Provenance] = None


class NighttimeHeatMetric(BaseModel):
    """Nighttime heat analysis for a specific night."""

    location_id: str
    night_start: datetime
    night_end: datetime

    min_temperature_c: Optional[float] = None
    mean_temperature_c: Optional[float] = None
    max_temperature_c: Optional[float] = None
    anomaly_c: Optional[float] = None
    percentile: Optional[float] = None

    hot_night: bool = False
    consecutive_hot_nights: int = 0
    duration_hours_above_threshold: Optional[float] = None

    recovery_deficit: Optional[float] = None
    recovery_status: Optional[str] = None
    recovery_hours: Optional[float] = None

    baseline_percentile: Optional[float] = None
    threshold_used_c: Optional[float] = None
    method: Optional[str] = None

    quality_summary: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Provenance] = None


class ExposureMemoryState(BaseModel):
    """Stateful heat exposure memory for a location."""

    location_id: str
    timestamp: datetime

    previous_exposure_memory: Optional[float] = None
    current_stress_contribution: Optional[float] = None
    recovery_contribution: Optional[float] = None
    decay_factor: Optional[float] = None
    exposure_memory: Optional[float] = None

    window_hours: int = 168
    method: Optional[str] = None
    configuration_version: Optional[str] = None

    quality_summary: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Provenance] = None


class ThermalCalculationRun(BaseModel):
    """Audit log for thermal calculation runs."""

    run_id: str
    location_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None

    status: Literal["STARTED", "SUCCESS", "PARTIAL", "FAILED"] = "STARTED"
    timestamps_processed: int = 0
    timestamps_succeeded: int = 0
    timestamps_failed: int = 0

    source_type: Optional[str] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None

    error_message: Optional[str] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)

    duration_ms: Optional[int] = None


class ThermalCalculateRequest(BaseModel):
    """Request body for POST /api/v1/thermal/calculate."""

    location_id: str
    timestamps: List[datetime]
    inputs: List[ThermalInput]
    source_type: Literal["OBSERVATION", "FORECAST", "ESTIMATED"] = "OBSERVATION"
    config: Optional[ThermalCalculationConfig] = None


class ThermalMethodsResponse(BaseModel):
    """Available thermal calculation methods and versions."""

    methods: Dict[str, Dict[str, Any]]
    default_config: ThermalCalculationConfig