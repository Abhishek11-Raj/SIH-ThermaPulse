"""Data ingestion orchestration: provider â†’ adapter â†’ canonical â†’ persist â†’ log.

Central plumbing used by API routes (and later by scheduled ingestors). Every
flow records data-quality findings and an ingestion log entry, and updates
provider health â€” without exposing provider internals to the API layer.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ..adapters.air_quality import AirQualityAdapter
from ..adapters.forecast import WeatherForecastAdapter
from ..adapters.health import HealthOutcomeAdapter
from ..adapters.vulnerability import VulnerabilityAdapter
from ..adapters.weather import WeatherAdapter
from ..core.enums import DataDomain, QualityFlag
from ..models.location import Location as LocationModel
from ..models.operations import (
    DataQualityRecord,
    ProviderStatus as ProviderStatusModel,
)
from ..models.weather import (
    AirQualityObservation as AQModel,
    WeatherForecast as ForecastModel,
    WeatherObservation as WeatherModel,
)
from ..models.vulnerability import (
    HealthOutcome as HealthModel,
    VulnerabilityData as VulnerabilityModel,
)
from ..providers import ProviderRegistry, registry
from ..schemas.air_quality import AirQualityObservation
from ..schemas.common import QualityAssessment
from ..schemas.forecast import WeatherForecast
from ..schemas.health import HealthOutcome
from ..schemas.weather import WeatherObservation
from ..schemas.vulnerability import VulnerabilityRecord
from ..utils.time import to_utc
from .fallback import FallbackResult, fetch_with_fallback
from .ingestion import IngestionTracker


def _utc_naive(value: datetime) -> datetime:
    """Normalize to UTC and drop tzinfo (SQLite-compatible, all-UTC internal)."""
    return to_utc(value).replace(tzinfo=None)


def _tracker_source(result: FallbackResult) -> str:
    """Human source label for ingestion logs (mock path keeps ``mock``)."""
    if result.provider_name.startswith("mock"):
        return "mock"
    return result.provider_name.split("_")[0] if "_" in result.provider_name else result.provider_name


def _coords(db: Session, location_id: str) -> Tuple[Optional[float], Optional[float]]:
    row = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
    if row is None:
        return None, None
    return row.latitude, row.longitude


def _record_quality(db: Session, domain: str, source: str, provider: str,
                    record_ref: str, assessment: Optional[QualityAssessment]) -> None:
    if assessment is None or assessment.flag == QualityFlag.VALID:
        return
    db.add(
        DataQualityRecord(
            source=source,
            provider=provider,
            domain=domain,
            record_reference=record_ref,
            quality_flag=assessment.flag.value,
            missing_variables=assessment.missing_variables,
            issues=[i.model_dump() for i in assessment.issues],
        )
    )


def _persist_or_skip(model_cls, canonical_list, key_getter, mapper, db: Session) -> int:
    inserted = 0
    for item in canonical_list:
        key = key_getter(item)
        exists = _lookup_existing(db, model_cls, key)
        if exists:
            continue
        db.add(mapper(item))
        inserted += 1
    db.commit()
    return inserted


def _dq_json(value) -> dict | None:
    return value.model_dump(mode="json") if value is not None else None


def _weather_orm(o: WeatherObservation) -> WeatherModel:
    return WeatherModel(
        observation_id=o.observation_id,
        source=o.source,
        provider=o.provider,
        location_id=o.location_id,
        latitude=o.latitude,
        longitude=o.longitude,
        observed_at=_utc_naive(o.observed_at),
        source_timestamp=_utc_naive(o.source_timestamp) if o.source_timestamp else None,
        temperature=o.temperature,
        temperature_unit=o.temperature_unit,
        relative_humidity=o.relative_humidity,
        wind_speed=o.wind_speed,
        wind_direction=o.wind_direction,
        pressure=o.pressure,
        rainfall=o.rainfall,
        cloud_cover=o.cloud_cover,
        solar_radiation=o.solar_radiation,
        visibility=o.visibility,
        uv_index=o.uv_index,
        quality_flag=o.quality_flag.value,
        quality_assessment=_dq_json(o.quality_assessment),
        spatial_resolution=_dq_json(o.spatial_resolution),
        temporal_resolution=_dq_json(o.temporal_resolution),
        provenance=_dq_json(o.provenance),
    )


def _forecast_orm(f: WeatherForecast) -> ForecastModel:
    return ForecastModel(
        forecast_id=f.forecast_id,
        source=f.source,
        provider=f.provider,
        location_id=f.location_id,
        latitude=f.latitude,
        longitude=f.longitude,
        issued_at=_utc_naive(f.issued_at),
        valid_from=_utc_naive(f.valid_from),
        valid_to=_utc_naive(f.valid_to),
        forecast_horizon_hours=f.forecast_horizon_hours,
        temperature=f.temperature,
        temperature_unit=f.temperature_unit,
        relative_humidity=f.relative_humidity,
        wind_speed=f.wind_speed,
        pressure=f.pressure,
        rainfall=f.rainfall,
        cloud_cover=f.cloud_cover,
        solar_radiation=f.solar_radiation,
        model_name=f.model_name,
        model_version=f.model_version,
        quality_flag=f.quality_flag.value,
        quality_assessment=_dq_json(f.quality_assessment),
        spatial_resolution=_dq_json(f.spatial_resolution),
        temporal_resolution=_dq_json(f.temporal_resolution),
        provenance=_dq_json(f.provenance),
    )


def _aq_orm(o: AirQualityObservation) -> AQModel:
    return AQModel(
        observation_id=o.observation_id,
        source=o.source,
        provider=o.provider,
        location_id=o.location_id,
        latitude=o.latitude,
        longitude=o.longitude,
        observed_at=_utc_naive(o.observed_at),
        source_timestamp=_utc_naive(o.source_timestamp) if o.source_timestamp else None,
        pm25=o.pm25,
        pm10=o.pm10,
        o3=o.o3,
        no2=o.no2,
        so2=o.so2,
        co=o.co,
        aqi=o.aqi,
        quality_flag=o.quality_flag.value,
        quality_assessment=_dq_json(o.quality_assessment),
        spatial_resolution=_dq_json(o.spatial_resolution),
        temporal_resolution=_dq_json(o.temporal_resolution),
        provenance=_dq_json(o.provenance),
    )


def _lookup_existing(db: Session, model_cls, key: Tuple[str, str, str]):
    source, provider, marker = key
    filters = [model_cls.source == source, model_cls.provider == provider]
    if isinstance(model_cls, type) and model_cls is WeatherModel:
        row = (db.query(model_cls)
               .filter(*filters, model_cls.observed_at == marker).first())
        return row
    if model_cls is ForecastModel:
        row = (db.query(model_cls)
               .filter(*filters, model_cls.valid_from == marker).first())
        return row
    if model_cls is AQModel:
        return db.query(model_cls).filter(*filters, model_cls.observed_at == marker).first()
    if model_cls is HealthModel:
        return db.query(model_cls).filter(*filters, model_cls.period_start == marker).first()
    if model_cls is VulnerabilityModel:
        return db.query(model_cls).filter(*filters, model_cls.reference_date == marker).first()
    return None


def _update_provider_health(db: Session, name: str, ok: bool = True,
                            latency_ms: int = 4) -> None:
    row = db.query(ProviderStatusModel).filter(ProviderStatusModel.name == name).first()
    if row is None:
        row = ProviderStatusModel(name=name, domain="unknown")
        db.add(row)
    from ..core.enums import FreshnessStatus, ProviderStatus
    from ..utils.time import utcnow

    now = utcnow()
    if ok:
        row.status = ProviderStatus.ONLINE.value
        row.last_successful_request_at = now
        row.last_latency_ms = latency_ms
        row.success_count = (row.success_count or 0) + 1
        row.freshness = FreshnessStatus.FRESH.value
    else:
        row.status = ProviderStatus.OFFLINE.value
        row.last_failure_at = now
        row.failure_count = (row.failure_count or 0) + 1
    row.last_check = now
    db.commit()


# ---------------------------------------------------------------------------
# Domain ingestors
# ---------------------------------------------------------------------------

def ingest_weather(
    db: Session,
    location_id: str,
    start: datetime,
    end: datetime,
    seed: int = 2026,
    reg: Optional[ProviderRegistry] = None,
) -> Tuple[List[WeatherObservation], IngestionTracker]:
    _reg = reg or registry
    lat, lon = _coords(db, location_id)
    result = fetch_with_fallback(
        db, _reg, DataDomain.WEATHER.value, location_id,
        fetch=lambda provider: provider.fetch_observations(
            location_id, start, end, seed=seed, latitude=lat, longitude=lon
        ),
    )
    adapter = WeatherAdapter()
    canonical = adapter.adapt_many(result.raws, lat, lon)

    tracker = IngestionTracker(db, source=_tracker_source(result),
                               provider=result.provider_name,
                               domain=DataDomain.WEATHER.value)
    if result.fallback_used:
        tracker.mark_fallback(result.fallback_source or "unknown")
    for obs in canonical:
        tracker.add_assessment(obs.quality_assessment)
    inserted = _persist_or_skip(
        WeatherModel, canonical,
        lambda o: (o.source, o.provider, _utc_naive(o.observed_at)),
        _weather_orm,
        db,
    )
    for obs in canonical:
        _record_quality(db, "weather", obs.source, obs.provider, obs.observation_id,
                        obs.quality_assessment)
    db.commit()
    tracker.complete(accepted=inserted, duplicate=len(canonical) - inserted,
                     extra=result.tracker_extra())
    _update_provider_health(db, result.provider_name, latency_ms=result.latency_ms)
    return canonical, tracker


def ingest_forecast(
    db: Session,
    location_id: str,
    issued_at: datetime,
    horizon_hours: int = 120,
    seed: int = 2026,
    reg: Optional[ProviderRegistry] = None,
) -> Tuple[List[WeatherForecast], IngestionTracker]:
    _reg = reg or registry
    lat, lon = _coords(db, location_id)
    result = fetch_with_fallback(
        db, _reg, DataDomain.WEATHER_FORECAST.value, location_id,
        fetch=lambda provider: provider.fetch_forecast(
            location_id, issued_at, horizon_hours, seed=seed, latitude=lat, longitude=lon
        ),
    )
    adapter = WeatherForecastAdapter()
    canonical = adapter.adapt_many(result.raws, lat, lon)

    tracker = IngestionTracker(db, source=_tracker_source(result),
                               provider=result.provider_name,
                               domain=DataDomain.WEATHER_FORECAST.value)
    if result.fallback_used:
        tracker.mark_fallback(result.fallback_source or "unknown")
    for f in canonical:
        tracker.add_assessment(f.quality_assessment)
    inserted = _persist_or_skip(
        ForecastModel, canonical,
        lambda f: (f.source, f.provider, _utc_naive(f.valid_from)),
        _forecast_orm,
        db,
    )
    for f in canonical:
        _record_quality(db, "weather_forecast", f.source, f.provider, f.forecast_id,
                        f.quality_assessment)
    db.commit()
    tracker.complete(accepted=inserted, duplicate=len(canonical) - inserted,
                     extra=result.tracker_extra())
    _update_provider_health(db, result.provider_name, latency_ms=result.latency_ms)
    return canonical, tracker


def ingest_air_quality(
    db: Session,
    location_id: str,
    start: datetime,
    end: datetime,
    seed: int = 2026,
    reg: Optional[ProviderRegistry] = None,
) -> Tuple[List[AirQualityObservation], IngestionTracker]:
    _reg = reg or registry
    lat, lon = _coords(db, location_id)
    result = fetch_with_fallback(
        db, _reg, DataDomain.AIR_QUALITY.value, location_id,
        fetch=lambda provider: provider.fetch_observations(
            location_id, start, end, seed=seed, latitude=lat, longitude=lon
        ),
    )
    adapter = AirQualityAdapter()
    canonical = adapter.adapt_many(result.raws, lat, lon)

    tracker = IngestionTracker(db, source=_tracker_source(result),
                               provider=result.provider_name,
                               domain=DataDomain.AIR_QUALITY.value)
    if result.fallback_used:
        tracker.mark_fallback(result.fallback_source or "unknown")
    for o in canonical:
        tracker.add_assessment(o.quality_assessment)
    inserted = _persist_or_skip(
        AQModel, canonical,
        lambda o: (o.source, o.provider, _utc_naive(o.observed_at)),
        _aq_orm,
        db,
    )
    for o in canonical:
        _record_quality(db, "air_quality", o.source, o.provider, o.observation_id,
                        o.quality_assessment)
    db.commit()
    tracker.complete(accepted=inserted, duplicate=len(canonical) - inserted,
                     extra=result.tracker_extra())
    _update_provider_health(db, result.provider_name, latency_ms=result.latency_ms)
    return canonical, tracker


def _vulnerability_orm(o: VulnerabilityRecord) -> VulnerabilityModel:
    return VulnerabilityModel(
        vulnerability_id=o.vulnerability_id,
        location_id=o.location_id,
        reference_date=_utc_naive(o.reference_date),
        factors=o.factors.model_dump(mode="json"),
        source=o.source,
        provider=o.provider,
        quality_flag=o.quality_flag.value,
        quality_assessment=_dq_json(o.quality_assessment),
        provenance=_dq_json(o.provenance),
    )


def ingest_vulnerability(
    db: Session,
    location_id: str,
    reference_date: datetime,
    seed: int = 2026,
    reg: Optional[ProviderRegistry] = None,
) -> Tuple[Optional[VulnerabilityRecord], Optional[IngestionTracker]]:
    _reg = reg or registry
    provider = _reg.get("mock_vulnerability")
    raw = provider.fetch_vulnerability(location_id, reference_date, seed=seed)
    adapter = VulnerabilityAdapter()
    canonical = adapter.to_record(raw, reference_date)

    tracker = IngestionTracker(db, source="mock", provider=provider.name,
                               domain=DataDomain.VULNERABILITY.value)
    tracker.add_assessment(canonical.quality_assessment)
    inserted = _persist_or_skip(
        VulnerabilityModel, [canonical],
        lambda o: (o.source, o.provider, _utc_naive(o.reference_date)),
        _vulnerability_orm,
        db,
    )
    _record_quality(db, "vulnerability", canonical.source, canonical.provider,
                    canonical.vulnerability_id, canonical.quality_assessment)
    db.commit()
    tracker.complete(accepted=inserted, duplicate=0)
    _update_provider_health(db, provider.name)
    return canonical, tracker


def ingest_health_outcomes(
    db: Session,
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    seed: int = 2026,
    reg: Optional[ProviderRegistry] = None,
) -> Tuple[List[HealthOutcome], IngestionTracker]:
    _reg = reg or registry
    provider = _reg.get("mock_health")
    raws = provider.fetch_outcomes(location_id, period_start, period_end, seed=seed)
    adapter = HealthOutcomeAdapter()
    canonical = [adapter.to_record(r) for r in raws]

    tracker = IngestionTracker(db, source="mock", provider=provider.name,
                               domain=DataDomain.HEALTH.value)
    for o in canonical:
        tracker.add_assessment(o.quality_assessment)
    inserted = _persist_or_skip(
        HealthModel, canonical,
        lambda o: (o.source, o.provider, _utc_naive(o.time_period.start)),
        lambda o: HealthModel(
            outcome_id=o.outcome_id,
            location_id=o.location_id,
            period_start=_utc_naive(o.time_period.start),
            period_end=_utc_naive(o.time_period.end),
            aggregation_level=o.aggregation_level.value,
            heat_illness_cases=o.heat_illness_cases,
            emergency_visits=o.emergency_visits,
            hospital_admissions=o.hospital_admissions,
            respiratory_admissions=o.respiratory_admissions,
            cardiovascular_admissions=o.cardiovascular_admissions,
            mortality_count=o.mortality_count,
            surveillance_indicators=o.surveillance_indicators,
            source=o.source,
            provider=o.provider,
            quality_flag=o.quality_flag.value,
            provenance=o.provenance.model_dump(mode="json") if o.provenance else None,
            quality_assessment=o.quality_assessment.model_dump(mode="json")
            if o.quality_assessment else None,
        ),
        db,
    )
    for o in canonical:
        _record_quality(db, "health", o.source, o.provider, o.outcome_id, o.quality_assessment)
    db.commit()
    tracker.complete(accepted=inserted, duplicate=len(canonical) - inserted)
    _update_provider_health(db, provider.name)
    return canonical, tracker


def default_window(hours: int = 48) -> Tuple[datetime, datetime]:
    from ..utils.time import utcnow

    end = utcnow().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours)
    return start, end
