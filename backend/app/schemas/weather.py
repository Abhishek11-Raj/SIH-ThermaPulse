"""Canonical weather observation schema.

An observation is a measured/reported value at a point in time. It is NOT a
forecast and is NOT a derived thermal-stress metric. Missing variables must be
left null and flagged — never set to zero.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.enums import QualityFlag
from .common import Provenance, QualityAssessment, SpatialReference, TemporalReference

# Physically plausible bounds (approximate, generous). Outside these → INVALID.
TEMPERATURE_C = (-90.0, 60.0)
RELATIVE_HUMIDITY = (0.0, 100.0)
WIND_SPEED_MS = (0.0, 150.0)
WIND_DIRECTION_DEG = (0.0, 360.0)
PRESSURE_HPA = (800.0, 1100.0)
RAINFALL_MM = (0.0, 1000.0)
CLOUD_COVER_PCT = (0.0, 100.0)
SOLAR_RADIATION_WM2 = (0.0, 1500.0)
VISIBILITY_KM = (0.0, 100.0)
UV_INDEX = (0.0, 20.0)

ALLOWED_TEMP_UNITS = {"C", "F", "K"}


class WeatherObservation(BaseModel):
    """Canonical weather observation (raw, provider-agnostic)."""

    observation_id: str
    source: str
    provider: str
    location_id: str
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)

    observed_at: datetime
    source_timestamp: Optional[datetime] = None
    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())

    temperature: Optional[float] = None
    temperature_unit: str = "C"
    relative_humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    pressure: Optional[float] = None
    rainfall: Optional[float] = None
    cloud_cover: Optional[float] = None
    solar_radiation: Optional[float] = None
    visibility: Optional[float] = None
    uv_index: Optional[float] = None

    quality_flag: QualityFlag = QualityFlag.VALID
    quality_assessment: Optional[QualityAssessment] = None

    spatial_resolution: SpatialReference = Field(default_factory=SpatialReference)
    temporal_resolution: TemporalReference = Field(default_factory=TemporalReference)
    provenance: Optional[Provenance] = None

    @field_validator("temperature_unit")
    @classmethod
    def _unit_must_be_known(cls, v: str) -> str:
        if v.upper() not in ALLOWED_TEMP_UNITS:
            raise ValueError(f"temperature_unit must be one of {ALLOWED_TEMP_UNITS}")
        return v.upper()

    @field_validator("relative_humidity", "cloud_cover")
    @classmethod
    def _pct_0_100(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("value outside 0-100")
        return v

    @field_validator("wind_direction")
    @classmethod
    def _wind_dir(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 360.0):
            raise ValueError("wind_direction outside 0-360")
        return v


class WeatherObservationList(BaseModel):
    observations: List[WeatherObservation]
    count: int = 0


# ThermalInput is used for risk calculation API
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