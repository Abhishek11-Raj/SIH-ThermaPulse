"""Observational ORM models: weather observations, weather forecasts and air
quality observations. Stored in UTC; source vs ingestion timestamps preserved."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature_unit: Mapped[str] = mapped_column(String(8), default="C")
    relative_humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_direction: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rainfall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cloud_cover: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    solar_radiation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visibility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uv_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    quality_flag: Mapped[str] = mapped_column(String(16), default="VALID", index=True)
    quality_assessment: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    spatial_resolution: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    temporal_resolution: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    forecast_horizon_hours: Mapped[int] = mapped_column(Integer, default=0)

    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature_unit: Mapped[str] = mapped_column(String(8), default="C")
    relative_humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rainfall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cloud_cover: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    solar_radiation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quality_flag: Mapped[str] = mapped_column(String(16), default="VALID", index=True)
    quality_assessment: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    spatial_resolution: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    temporal_resolution: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class AirQualityObservation(Base):
    __tablename__ = "air_quality_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    pm25: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pm10: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    o3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    no2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    so2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    co: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    aqi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    quality_flag: Mapped[str] = mapped_column(String(16), default="VALID", index=True)
    quality_assessment: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    spatial_resolution: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    temporal_resolution: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)