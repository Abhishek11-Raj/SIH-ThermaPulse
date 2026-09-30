"""Canonical air-quality observation schema.

All pollutant concentrations are nullable. A missing value must remain null and
be flagged — it must NEVER be silently converted to zero ("0 µg/m³ air" is an
error, not a measurement).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.enums import QualityFlag
from .common import Provenance, QualityAssessment, SpatialReference, TemporalReference

# Plausible bounds; outside here → INVALID, never coerced.
PM25_RANGE = (0.0, 2000.0)     # µg/m³
PM10_RANGE = (0.0, 5000.0)     # µg/m³
O3_RANGE = (0.0, 1000.0)       # µg/m³
NO2_RANGE = (0.0, 2000.0)      # µg/m³
SO2_RANGE = (0.0, 2000.0)      # µg/m³
CO_RANGE = (0.0, 200.0)        # mg/m³
AQI_RANGE = (0.0, 1000.0)


class AirQualityObservation(BaseModel):
    """Canonical air-quality observation."""

    observation_id: str
    source: str
    provider: str
    location_id: str
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)

    observed_at: datetime
    source_timestamp: Optional[datetime] = None
    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())

    pm25: Optional[float] = None     # µg/m³
    pm10: Optional[float] = None     # µg/m³
    o3: Optional[float] = None       # µg/m³
    no2: Optional[float] = None      # µg/m³
    so2: Optional[float] = None      # µg/m³
    co: Optional[float] = None       # mg/m³
    aqi: Optional[float] = None

    quality_flag: QualityFlag = QualityFlag.VALID
    quality_assessment: Optional[QualityAssessment] = None

    spatial_resolution: SpatialReference = Field(default_factory=SpatialReference)
    temporal_resolution: TemporalReference = Field(default_factory=TemporalReference)
    provenance: Optional[Provenance] = None

    @field_validator("pm25")
    @classmethod
    def _pm25(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            _in(v, PM25_RANGE, "pm25")
        return v

    @field_validator("pm10")
    @classmethod
    def _pm10(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            _in(v, PM10_RANGE, "pm10")
        return v

    @field_validator("o3")
    @classmethod
    def _o3(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            _in(v, O3_RANGE, "o3")
        return v


def _in(value: float, bounds: tuple, name: str) -> None:
    if not (bounds[0] <= value <= bounds[1]):
        raise ValueError(f"{name}={value} outside plausible range {bounds}")