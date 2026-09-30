"""Canonical weather forecast schema.

A forecast is fundamentally different from an observation: it was issued at
``issued_at`` for a future window ``valid_from``..``valid_to``. Preserving both
is required for the future forecast track record (verifying forecasts against
later observations) and the 3–5 day health-risk forecast.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.enums import QualityFlag
from .common import Provenance, QualityAssessment, SpatialReference, TemporalReference
from .weather import ALLOWED_TEMP_UNITS


class WeatherForecast(BaseModel):
    """Canonical weather forecast for one location and validity window."""

    forecast_id: str
    source: str
    provider: str
    location_id: str
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)

    issued_at: datetime
    valid_from: datetime
    valid_to: datetime
    forecast_horizon_hours: int = Field(..., ge=0, le=240)

    temperature: Optional[float] = None
    temperature_unit: str = "C"
    relative_humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    pressure: Optional[float] = None
    rainfall: Optional[float] = None
    cloud_cover: Optional[float] = None
    solar_radiation: Optional[float] = None

    model_name: Optional[str] = Field(default=None, description="e.g. 'mock-forecast-v1'")
    model_version: Optional[str] = None
    quality_flag: QualityFlag = QualityFlag.VALID
    quality_assessment: Optional[QualityAssessment] = None

    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    spatial_resolution: SpatialReference = Field(default_factory=SpatialReference)
    temporal_resolution: TemporalReference = Field(default_factory=TemporalReference)
    provenance: Optional[Provenance] = None

    @field_validator("temperature_unit")
    @classmethod
    def _unit_must_be_known(cls, v: str) -> str:
        if v.upper() not in ALLOWED_TEMP_UNITS:
            raise ValueError(f"temperature_unit must be one of {ALLOWED_TEMP_UNITS}")
        return v.upper()

    @field_validator("valid_to")
    @classmethod
    def _window_ordered(cls, v: datetime, info) -> datetime:
        valid_from = info.data.get("valid_from")
        if valid_from is not None and v < valid_from:
            raise ValueError("valid_to must be >= valid_from")
        return v


class WeatherForecastList(BaseModel):
    forecasts: List[WeatherForecast]
    count: int = 0