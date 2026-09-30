"""Thermal stress and exposure memory ORM models — STEP 3.

Tables created in Step 3:
    thermal_stress_results, thermal_daily_summary,
    nighttime_heat_metrics, exposure_memory_states,
    thermal_calculation_runs
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Float, Integer, String, Index, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from ..utils.time import utcnow


class ThermalStressResult(Base):
    """Thermal stress calculation result for a single timestamp/location."""

    __tablename__ = "thermal_stress_results"
    __table_args__ = (
        Index("ix_thermal_stress_location_time", "location_id", "timestamp"),
        Index("ix_thermal_stress_source_type", "source_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calculation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    location_id: Mapped[str] = mapped_column(String(64), index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_type: Mapped[str] = mapped_column(String(16), index=True)  # OBSERVATION / FORECAST / ESTIMATED

    # Input meteorological variables
    air_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relative_humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_direction_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pressure_hpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    solar_radiation_wm2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cloud_cover_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Thermal indices (output)
    heat_index_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heat_index_f: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wet_bulb_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wbgt_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wbgt_indoor_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    utci_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mrt_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Nighttime heat metrics
    nighttime_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nighttime_anomaly_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hot_night: Mapped[Optional[bool]] = mapped_column(nullable=True)
    consecutive_hot_nights: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Recovery deficit
    recovery_deficit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recovery_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Cumulative exposure & memory
    daily_stress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cumulative_exposure_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cumulative_exposure_72h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cumulative_exposure_7d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exposure_memory: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Classification
    thermal_stress_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    occupational_heat_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    nighttime_recovery_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Quality & uncertainty
    quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    uncertainty_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Provenance
    method_versions: Mapped[Optional[Dict[str, str]]] = mapped_column(JSON, nullable=True)
    configuration: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ThermalDailySummary(Base):
    """Daily aggregate thermal stress summary."""

    __tablename__ = "thermal_daily_summary"
    __table_args__ = (
        Index("ix_thermal_daily_location_date", "location_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    max_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    max_heat_index_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_wbgt_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_utci_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    max_thermal_stress_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    hot_day: Mapped[bool] = mapped_column(default=False)
    extreme_day: Mapped[bool] = mapped_column(default=False)

    nighttime_min_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nighttime_mean_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nighttime_max_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hot_night: Mapped[bool] = mapped_column(default=False)
    consecutive_hot_nights: Mapped[int] = mapped_column(Integer, default=0)

    recovery_deficit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recovery_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    recovery_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    cumulative_exposure_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cumulative_exposure_72h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cumulative_exposure_7d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exposure_memory: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NighttimeHeatMetric(Base):
    """Nighttime heat analysis for a specific night."""

    __tablename__ = "nighttime_heat_metrics"
    __table_args__ = (
        Index("ix_nighttime_location_date", "location_id", "night_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    night_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    night_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    min_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    anomaly_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    hot_night: Mapped[bool] = mapped_column(default=False)
    consecutive_hot_nights: Mapped[int] = mapped_column(Integer, default=0)
    duration_hours_above_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    recovery_deficit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recovery_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    recovery_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    baseline_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_used_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExposureMemoryState(Base):
    """Stateful heat exposure memory for a location."""

    __tablename__ = "exposure_memory_states"
    __table_args__ = (
        Index("ix_exposure_memory_location_time", "location_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    previous_exposure_memory: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_stress_contribution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recovery_contribution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decay_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exposure_memory: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    window_hours: Mapped[int] = mapped_column(Integer, default=168)  # 7 days default
    method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    configuration_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ThermalCalculationRun(Base):
    """Audit log for thermal calculation runs."""

    __tablename__ = "thermal_calculation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="STARTED", index=True)
    timestamps_processed: Mapped[int] = mapped_column(Integer, default=0)
    timestamps_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    timestamps_failed: Mapped[int] = mapped_column(Integer, default=0)

    source_type: Mapped[str] = mapped_column(String(16), nullable=True)
    date_range_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    date_range_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    configuration: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)