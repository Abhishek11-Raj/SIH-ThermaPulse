"""Thermal Stress API Routes — STEP 3.

Endpoints:
- GET /api/v1/thermal/current/{location_id}
- GET /api/v1/thermal/history/{location_id}
- GET /api/v1/thermal/nighttime/{location_id}
- GET /api/v1/thermal/exposure/{location_id}
- GET /api/v1/thermal/forecast/{location_id}
- POST /api/v1/thermal/calculate
- GET /api/v1/thermal/methods
- GET /api/v1/thermal/provenance/{calculation_id}
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.weather import WeatherObservationList, WeatherObservation
from ...schemas.forecast import WeatherForecastList
from ...services.ingest import (
    ingest_weather,
    ingest_forecast,
    default_window,
)
from app.models.thermal import (
    ThermalStressResult as ThermalStressResultModel,
    ThermalDailySummary as ThermalDailySummaryModel,
    NighttimeHeatMetric as NighttimeHeatMetricModel,
    ExposureMemoryState as ExposureMemoryStateModel,
    ThermalCalculationRun as ThermalCalculationRunModel,
)
from ...thermal.schemas import (
    ThermalStressResult,
    ThermalStressResultList,
    ThermalDailySummary,
    NighttimeHeatMetric,
    ExposureMemoryState,
    ThermalCalculationRun,
    ThermalCalculateRequest,
    ThermalMethodsResponse,
    ThermalCalculationConfig,
)
from ...api.dependencies import get_thermal_service, get_db as _get_db, resolve_location, parse_window

router = APIRouter(prefix="/api/v1/thermal", tags=["thermal"])


@router.get("/methods", response_model=ThermalMethodsResponse)
def get_thermal_methods() -> ThermalMethodsResponse:
    """Get available thermal calculation methods and default configuration."""
    config = ThermalCalculationConfig()
    methods = {
        "heat_index": {
            "default": "rothfusz",
            "available": ["rothfusz"],
            "description": "NOAA/NWS Rothfusz regression equation",
        },
        "wet_bulb": {
            "default": "stull",
            "available": ["stull", "davies_jones", "iterative"],
            "description": "Wet-bulb temperature approximation methods",
        },
        "wbgt": {
            "default": "liljegren",
            "available": ["liljegren", "bernard"],
            "description": "Wet Bulb Globe Temperature methods",
        },
        "utci": {
            "default": "approximation",
            "available": ["approximation", "lookup"],
            "description": "Universal Thermal Climate Index methods",
        },
        "mrt": {
            "default": "solar_only",
            "available": ["solar_only", "full_radiative", "unavailable"],
            "description": "Mean Radiant Temperature estimation methods",
        },
        "classification": {
            "default": "multi_index",
            "available": ["multi_index"],
            "description": "Multi-index thermal stress classification",
        },
    }
    return ThermalMethodsResponse(methods=methods, default_config=config)


@router.get("/current/{location_id}", response_model=ThermalStressResultList)
def get_current_thermal(
    location_id: str,
    seed: int = Query(default=2026, ge=0),
    config_override: Optional[str] = Query(default=None),
    db: Session = Depends(_get_db),
    service: ThermalCalculationService = Depends(get_thermal_service),
) -> ThermalStressResultList:
    """
    Get current thermal stress for a location.

    Calculates thermal indices from the most recent weather observation.
    """
    # Ingest current weather
    start, end = default_window(24)  # Last 24 hours
    observations, _ = ingest_weather(db, location_id, start, end, seed=seed)

    if not observations:
        raise HTTPException(status_code=404, detail="No weather data available for location")

    # Get location info
    from app.models.location import Location as LocationModel
    loc = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    # Calculate thermal stress
    service.config = service.config or ThermalCalculationConfig()
    results = service.calculate_batch(
        observations, "OBSERVATION", location_id, loc.latitude, loc.longitude
    )

    return ThermalStressResultList(results=results, count=len(results))


@router.get("/history/{location_id}", response_model=ThermalStressResultList)
def get_thermal_history(
    location_id: str,
    start: Optional[str] = Query(default=None, description="ISO-8601 start (UTC)"),
    end: Optional[str] = Query(default=None, description="ISO-8601 end (UTC)"),
    seed: int = Query(default=2026, ge=0),
    db: Session = Depends(_get_db),
    service: ThermalCalculationService = Depends(get_thermal_service),
) -> ThermalStressResultList:
    """
    Get historical thermal stress for a location over a time window.
    """
    start_dt, end_dt = parse_window(start, end, hours=168)  # Default 7 days

    observations, _ = ingest_weather(db, location_id, start_dt, end_dt, seed=seed)

    if not observations:
        raise HTTPException(status_code=404, detail="No weather data available for location")

    from app.models.location import Location as LocationModel
    loc = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    service.config = service.config or ThermalCalculationConfig()
    results = service.calculate_batch(
        observations, "OBSERVATION", location_id, loc.latitude, loc.longitude
    )

    return ThermalStressResultList(results=results, count=len(results))


@router.get("/forecast/{location_id}", response_model=ThermalStressResultList)
def get_thermal_forecast(
    location_id: str,
    horizon_hours: int = Query(default=48, ge=1, le=120),
    seed: int = Query(default=2026, ge=0),
    db: Session = Depends(_get_db),
    service: ThermalCalculationService = Depends(get_thermal_service),
) -> ThermalStressResultList:
    """
    Get thermal stress forecast for a location.
    """
    from app.models.location import Location as LocationModel
    loc = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    issued_at = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    forecasts, _ = ingest_forecast(db, location_id, issued_at, horizon_hours, seed=seed)

    if not forecasts:
        raise HTTPException(status_code=404, detail="No forecast data available for location")

    service.config = service.config or ThermalCalculationConfig()
    results = service.calculate_batch(
        forecasts, "FORECAST", location_id, loc.latitude, loc.longitude
    )

    return ThermalStressResultList(results=results, count=len(results))


@router.get("/nighttime/{location_id}", response_model=List[NighttimeHeatMetric])
def get_nighttime_heat(
    location_id: str,
    days: int = Query(default=7, ge=1, le=30),
    seed: int = Query(default=2026, ge=0),
    db: Session = Depends(get_db),
) -> List[NighttimeHeatMetric]:
    """
    Get nighttime heat analysis for recent nights.
    """
    from app.models.thermal import NighttimeHeatMetric as NightModel
    from app.models.location import Location as LocationModel

    loc = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    # Query persisted nighttime metrics
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    metrics = db.query(NightModel).filter(
        NightModel.location_id == location_id,
        NightModel.night_start >= start,
        NightModel.night_start <= end,
    ).order_by(NightModel.night_start.desc()).all()

    return [
        NighttimeHeatMetric(
            location_id=m.location_id,
            night_start=m.night_start,
            night_end=m.night_end,
            min_temperature_c=m.min_temperature_c,
            mean_temperature_c=m.mean_temperature_c,
            max_temperature_c=m.max_temperature_c,
            anomaly_c=m.anomaly_c,
            percentile=m.percentile,
            hot_night=m.hot_night,
            consecutive_hot_nights=m.consecutive_hot_nights,
            duration_hours_above_threshold=m.duration_hours_above_threshold,
            recovery_deficit=m.recovery_deficit,
            recovery_status=m.recovery_status,
            recovery_hours=m.recovery_hours,
            baseline_percentile=m.baseline_percentile,
            threshold_used_c=m.threshold_used_c,
            method=m.method,
            quality_summary=m.quality_summary or {},
            provenance=m.provenance,
        )
        for m in metrics
    ]


@router.get("/exposure/{location_id}", response_model=List[ExposureMemoryState])
def get_exposure_memory(
    location_id: str,
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
) -> List[ExposureMemoryState]:
    """
    Get heat exposure memory states for a location.
    """
    from app.models.thermal import ExposureMemoryState as MemoryModel
    from app.models.location import Location as LocationModel

    loc = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    end = datetime.utcnow()
    start = end - timedelta(days=days)

    states = db.query(MemoryModel).filter(
        MemoryModel.location_id == location_id,
        MemoryModel.timestamp >= start,
        MemoryModel.timestamp <= end,
    ).order_by(MemoryModel.timestamp.desc()).all()

    return [
        ExposureMemoryState(
            location_id=s.location_id,
            timestamp=s.timestamp,
            previous_exposure_memory=s.previous_exposure_memory,
            current_stress_contribution=s.current_stress_contribution,
            recovery_contribution=s.recovery_contribution,
            decay_factor=s.decay_factor,
            exposure_memory=s.exposure_memory,
            window_hours=s.window_hours,
            method=s.method,
            configuration_version=s.configuration_version,
            quality_summary=s.quality_summary or {},
            provenance=s.provenance,
        )
        for s in states
    ]


@router.get("/daily-summary/{location_id}", response_model=List[ThermalDailySummary])
def get_thermal_daily_summary(
    location_id: str,
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
) -> List[ThermalDailySummary]:
    """
    Get daily thermal stress summaries for a location.
    """
    from app.models.thermal import ThermalDailySummary as DailyModel
    from app.models.location import Location as LocationModel

    loc = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    end = datetime.utcnow()
    start = end - timedelta(days=days)

    summaries = db.query(DailyModel).filter(
        DailyModel.location_id == location_id,
        DailyModel.date >= start,
        DailyModel.date <= end,
    ).order_by(DailyModel.date.desc()).all()

    return [
        ThermalDailySummary(
            location_id=s.location_id,
            date=s.date,
            max_temperature_c=s.max_temperature_c,
            min_temperature_c=s.min_temperature_c,
            mean_temperature_c=s.mean_temperature_c,
            max_heat_index_c=s.max_heat_index_c,
            max_wbgt_c=s.max_wbgt_c,
            max_utci_c=s.max_utci_c,
            max_thermal_stress_category=s.max_thermal_stress_category,
            hot_day=s.hot_day,
            extreme_day=s.extreme_day,
            nighttime_min_temperature_c=s.nighttime_min_temperature_c,
            nighttime_mean_temperature_c=s.nighttime_mean_temperature_c,
            nighttime_max_temperature_c=s.nighttime_max_temperature_c,
            hot_night=s.hot_night,
            consecutive_hot_nights=s.consecutive_hot_nights,
            recovery_deficit=s.recovery_deficit,
            recovery_status=s.recovery_status,
            recovery_hours=s.recovery_hours,
            cumulative_exposure_24h=s.cumulative_exposure_24h,
            cumulative_exposure_72h=s.cumulative_exposure_72h,
            cumulative_exposure_7d=s.cumulative_exposure_7d,
            exposure_memory=s.exposure_memory,
            quality_summary=s.quality_summary or {},
            provenance=s.provenance,
        )
        for s in summaries
    ]


@router.post("/calculate", response_model=ThermalStressResultList)
def calculate_thermal(
    request: ThermalCalculateRequest,
    db: Session = Depends(_get_db),
    service: ThermalCalculationService = Depends(get_thermal_service),
) -> ThermalStressResultList:
    """
    Calculate thermal stress from provided meteorological inputs.

    This endpoint allows calculation of thermal indices from arbitrary
    temperature, humidity, wind, radiation, etc. values without requiring
    existing weather observations in the database.
    """
    from app.models.location import Location as LocationModel

    loc = db.query(LocationModel).filter(LocationModel.location_id == request.location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    # Use provided config or default
    if request.config:
        service.config = request.config

    # Create mock observation objects from inputs
    from ...schemas.weather import WeatherObservation
    from ...core.enums import QualityFlag

    observations = []
    for i, inp in enumerate(request.inputs):
        obs = WeatherObservation(
            observation_id=f"manual_{request.location_id}_{i}",
            source=request.source_type.lower(),
            provider="manual",
            location_id=request.location_id,
            latitude=loc.latitude,
            longitude=loc.longitude,
            observed_at=request.timestamps[i] if i < len(request.timestamps) else datetime.utcnow(),
            temperature=inp.air_temperature_c,
            temperature_unit="C",
            relative_humidity=inp.relative_humidity,
            wind_speed=inp.wind_speed_ms,
            wind_direction=inp.wind_direction_deg,
            pressure=inp.pressure_hpa,
            solar_radiation=inp.solar_radiation_wm2,
            cloud_cover=inp.cloud_cover_pct,
            quality_flag=QualityFlag.VALID,
        )
        observations.append(obs)

    results = service.calculate_batch(
        observations, request.source_type, request.location_id, loc.latitude, loc.longitude
    )

    return ThermalStressResultList(results=results, count=len(results))


@router.get("/provenance/{calculation_id}", response_model=Dict[str, Any])
def get_calculation_provenance(
    calculation_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed provenance for a specific thermal calculation."""
    from app.models.thermal import ThermalStressResult as ResultModel

    result = db.query(ResultModel).filter(
        ResultModel.calculation_id == calculation_id
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Calculation not found")

    return {
        "calculation_id": result.calculation_id,
        "location_id": result.location_id,
        "timestamp": result.timestamp.isoformat() if result.timestamp else None,
        "source_type": result.source_type,
        "method_versions": result.method_versions,
        "configuration": result.configuration,
        "provenance": result.provenance,
        "quality_summary": result.quality_summary,
        "uncertainty_summary": result.uncertainty_summary,
    }


@router.get("/run/{run_id}", response_model=ThermalCalculationRun)
def get_calculation_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> ThermalCalculationRun:
    """Get thermal calculation run audit log."""
    run = db.query(ThermalCalculationRunModel).filter(
        ThermalCalculationRunModel.run_id == run_id
    ).first()

    if not run:
        raise HTTPException(status_code=404, detail="Calculation run not found")

    return ThermalCalculationRun(
        run_id=run.run_id,
        location_id=run.location_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        timestamps_processed=run.timestamps_processed,
        timestamps_succeeded=run.timestamps_succeeded,
        timestamps_failed=run.timestamps_failed,
        source_type=run.source_type,
        date_range_start=run.date_range_start,
        date_range_end=run.date_range_end,
        error_message=run.error_message,
        configuration=run.configuration or {},
        duration_ms=run.duration_ms,
    )