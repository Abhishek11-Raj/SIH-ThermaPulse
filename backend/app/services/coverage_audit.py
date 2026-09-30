"""Coverage and quality audit service (Step 2).

Expands the Step 1 per-location coverage reports into a cross-cutting audit:
    - location coverage (sensor-rich vs sensor-poor wards compared explicitly)
    - variable coverage and missingness (missing ≠ zero)
    - temporal coverage (cadence, coverage hours, freshness by domain)
    - spatial coverage and resolution
    - provider coverage (which providers contributed records)
    - equity audit with the hard rule: NO DATA ≠ LOW RISK

All counts are computed from stored rows; nothing is fabricated.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..core.enums import FreshnessStatus
from ..models.location import Location as LocationModel
from ..models.operations import IngestionLog as IngestionLogModel
from ..models.weather import (
    AirQualityObservation as AQModel,
    WeatherForecast as ForecastModel,
    WeatherObservation as WeatherModel,
)
from ..models.vulnerability import (
    HealthOutcome as HealthModel,
    VulnerabilityData as VulnerabilityModel,
)
from ..schemas.common import TimeWindow
from ..utils.time import utcnow
from .coverage import aggregate_by_location, coverage_reports_from_db

FRESHNESS_CADENCE: Dict[str, timedelta] = {
    "weather": timedelta(hours=3),
    "air_quality": timedelta(hours=3),
    "weather_forecast": timedelta(hours=24),
    "vulnerability": timedelta(days=30),
    "health": timedelta(days=7),
}


def _domain_freshness(rows_by_domain: Dict[str, List[Any]]) -> Dict[str, str]:
    now = utcnow()
    out: Dict[str, str] = {}
    for domain, rows in rows_by_domain.items():
        cadence = FRESHNESS_CADENCE.get(domain)
        latest = None
        for row in rows:
            ts = getattr(row, "observed_at", None) or getattr(row, "valid_from", None) \
                or getattr(row, "checked_at", None)
            if ts is not None:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                latest = ts if latest is None else max(latest, ts)
        if latest is None:
            out[domain] = FreshnessStatus.UNAVAILABLE.value
            continue
        age = now - latest
        if cadence is None or age <= cadence:
            out[domain] = FreshnessStatus.FRESH.value
        elif age <= cadence * 2:
            out[domain] = FreshnessStatus.AGING.value
        else:
            out[domain] = FreshnessStatus.STALE.value
    return out


def _provider_coverage(db: Session, window: TimeWindow) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    models = [
        (WeatherModel, WeatherModel.observed_at, "weather"),
        (AQModel, AQModel.observed_at, "air_quality"),
        (ForecastModel, ForecastModel.valid_from, "weather_forecast"),
    ]
    for model, col, domain in models:
        rows = db.query(model.provider, model.location_id).filter(
            col >= window.start, col <= window.end
        ).all()
        for provider, location_id in rows:
            out[provider][domain] = out[provider][domain] + 1
    return {k: dict(v) for k, v in out.items()}


def _spatial_summary(db: Session, window: TimeWindow) -> Dict[str, Any]:
    """Count how many locations received data per domain in the window."""
    summary: Dict[str, int] = {}
    locations_with_weather = db.query(WeatherModel.location_id).filter(
        WeatherModel.observed_at >= window.start, WeatherModel.observed_at <= window.end
    ).distinct().count()
    summary["weather"] = locations_with_weather
    summary["air_quality"] = db.query(AQModel.location_id).filter(
        AQModel.observed_at >= window.start, AQModel.observed_at <= window.end
    ).distinct().count()
    summary["forecast"] = db.query(ForecastModel.location_id).filter(
        ForecastModel.valid_from >= window.start, ForecastModel.valid_from <= window.end
    ).distinct().count()
    summary["total_locations"] = db.query(LocationModel).count() or 0
    return summary


def _missingness_summary(db: Session, window: TimeWindow) -> Dict[str, Any]:
    total_missing_cells = 0
    examined = 0
    domain_missing: Dict[str, int] = defaultdict(int)
    specs = [
        (WeatherModel, WeatherModel.observed_at,
         ["temperature", "relative_humidity", "wind_speed", "pressure",
          "rainfall", "cloud_cover", "solar_radiation", "visibility"]),
        (AQModel, AQModel.observed_at, ["pm25", "pm10", "o3", "no2", "so2", "co", "aqi"]),
    ]
    for model, col, variables in specs:
        rows = db.query(model).filter(col >= window.start, col <= window.end).all()
        for row in rows:
            for var in variables:
                examined += 1
                if getattr(row, var, None) is None:
                    total_missing_cells += 1
                    domain_missing[model.__tablename__] = domain_missing[model.__tablename__] + 1
    return {
        "examined_cells": examined,
        "missing_cells": total_missing_cells,
        "missingness_rate": round(total_missing_cells / examined, 4) if examined else None,
        "by_domain": dict(domain_missing),
        "note": "Missing cells stay None and are counted as missing — never zeroed.",
    }


def _equity_audit(db: Session) -> Dict[str, Any]:
    """Compare coverage across data-rich vs data-poor wards and by vulnerability.

    Explicitly avoids equating absence with safety: a ward with no data is
    reported with higher uncertainty, never as low risk.
    """
    wards = (
        db.query(LocationModel)
        .filter(LocationModel.type == "ward")
        .all()
    )
    rows = []
    for ward in wards:
        w_records = db.query(WeatherModel).filter(WeatherModel.location_id == ward.location_id).count()
        aq_records = db.query(AQModel).filter(AQModel.location_id == ward.location_id).count()
        vuln = (
            db.query(VulnerabilityModel)
            .filter(VulnerabilityModel.location_id == ward.location_id)
            .first()
        )
        vindex = vuln.factors.get("housing_vulnerability_index") if vuln and vuln.factors else None
        combined = w_records + aq_records
        if combined == 0:
            coverage_label = "DATA_POOR"
        elif combined <= 50:
            coverage_label = "ADEQUATE"
        else:
            coverage_label = "DATA_RICH"
        rows.append(
            {
                "location_id": ward.location_id,
                "weather_observation_count": w_records,
                "air_quality_observation_count": aq_records,
                "coverage_label": coverage_label,
                "housing_vulnerability_index": vindex,
            }
        )
    data_poor_high_vuln = [
        r for r in rows
        if r["coverage_label"] == "DATA_POOR"
        and isinstance(r["housing_vulnerability_index"], (int, float))
        and r["housing_vulnerability_index"] >= 0.5
    ]
    return {
        "wards": rows,
        "data_poor_with_high_vulnerability": len(data_poor_high_vuln),
        "equity_rule": (
            "Ungauged locations are reported as higher-uncertainty, never as "
            "low risk; sensor-poor + high-vulnerability locations are flagged."
        ),
    }


def coverage_audit(
    db: Session,
    location_id: Optional[str] = None,
    window_hours: int = 48,
) -> Dict[str, Any]:
    """Produce the cross-cutting coverage audit for one or all locations."""
    end = utcnow()
    start = end - timedelta(hours=window_hours)
    window = TimeWindow(start=start, end=end)

    reports = []
    targets = (
        [location_id]
        if location_id
        else [r[0] for r in db.query(LocationModel.location_id).all()]
    )
    for loc_id in targets:
        reports.extend(coverage_reports_from_db(db, loc_id, window))
    per_location = aggregate_by_location(reports)

    rows_by_domain: Dict[str, List[Any]] = {
        "weather": db.query(WeatherModel).filter(
            WeatherModel.observed_at >= window.start, WeatherModel.observed_at <= window.end
        ).all(),
        "air_quality": db.query(AQModel).filter(
            AQModel.observed_at >= window.start, AQModel.observed_at <= window.end
        ).all(),
        "weather_forecast": db.query(ForecastModel).filter(
            ForecastModel.valid_from >= window.start, ForecastModel.valid_from <= window.end
        ).all(),
    }

    return {
        "window": {"start": window.start, "end": window.end, "hours": window_hours},
        "locations_covered": len([r for r in reports if r.overall_missingness_rate < 1.0]),
        "per_location": per_location,
        "provider_coverage": _provider_coverage(db, window),
        "spatial": _spatial_summary(db, window),
        "variable_missingness": _missingness_summary(db, window),
        "temporal": {
            "freshness_by_domain": _domain_freshness(rows_by_domain),
            "granularity_expected": {
                "weather": "hourly",
                "air_quality": "hourly",
                "weather_forecast": "hourly",
                "vulnerability": "periodic",
                "health": "daily",
            },
        },
        "equity": _equity_audit(db),
        "note": (
            "Coverage audit computed from stored records. Missingness counts "
            "null cells as missing. No data is never treated as low risk."
        ),
    }


def ingest_status_summary(db: Session, limit: int = 25) -> Dict[str, Any]:
    """Short summary of ingestion health for the audit endpoint."""
    from collections import Counter

    rows = (
        db.query(IngestionLogModel)
        .order_by(IngestionLogModel.started_at.desc())
        .limit(limit)
        .all()
    )
    statuses = Counter(r.status for r in rows)
    return {
        "recent_runs": len(rows),
        "by_status": dict(statuses),
        "fallback_runs": sum(1 for r in rows if r.fallback_used),
        "latest_error": next(
            (r.error_message for r in rows if r.error_message), None
        ),
    }