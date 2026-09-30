"""Startup/bootstrap services: seed locations, provider health and samples.

Step 2: also registers REAL providers when the app runs outside mock mode and
maintains the data-source registry (static provider metadata), keeping runtime
health (provider_status) and configuration (data_sources) as separate notions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from ..adapters.location import LocationAdapter
from ..adapters.health import HealthOutcomeAdapter
from ..adapters.vulnerability import VulnerabilityAdapter
from ..core.config import settings
from ..core.database import init_db
from ..core.enums import Scenario
from ..models.location import Location
from ..models.operations import ProviderStatus as ProviderStatusModel
from ..models.step2 import DataSource as DataSourceModel
from ..providers import (
    ProviderRegistry,
    register_all_mock_providers,
    registry,
    set_mock_seed,
    set_scenario,
)
from ..utils.time import utcnow

logger = logging.getLogger("keshav.bootstrap")


def bootstrap(
    mock_mode: bool = True,
    mock_seed: int = 2026,
    scenario: Scenario = Scenario.NORMAL_DAY,
    db: Session | None = None,
) -> None:
    """Initialize database tables, providers and seed data.

    Safe to call on every startup. Real providers replace/join the mock
    registry when ``mock_mode`` is False — without touching the rest of the app.
    """
    init_db()
    set_mock_seed(mock_seed)
    set_scenario(scenario)

    if mock_mode:
        register_all_mock_providers()
        if db is not None:
            seed_locations(db, registry)
            seed_provider_status(db, registry)
            seed_health_status(db, registry)
            seed_data_source_registry(db, registry)
    else:
        _register_real_providers()
        register_all_mock_providers()  # keep deterministic fallback available
        if db is not None:
            seed_locations(db, registry)
            seed_provider_status(db, registry)
            seed_health_status(db, registry)
            seed_data_source_registry(db, registry)


def _register_real_providers() -> None:
    from ..providers.base import register_provider
    from ..providers.real import (
        OpenMeteoAirQualityProvider,
        OpenMeteoForecastProvider,
        OpenMeteoWeatherProvider,
    )

    if settings.weather_provider == "openmeteo":
        register_provider(OpenMeteoWeatherProvider())
    if settings.forecast_provider == "openmeteo":
        register_provider(OpenMeteoForecastProvider())
    if settings.air_quality_provider == "openmeteo":
        register_provider(OpenMeteoAirQualityProvider())
    logger.info(
        "real provider registration (weather=%s forecast=%s aq=%s)",
        settings.weather_provider,
        settings.forecast_provider,
        settings.air_quality_provider,
    )


def seed_locations(db: Session, reg: ProviderRegistry) -> int:
    existing = {row.location_id for row in db.query(Location.location_id).all()}
    adapter = LocationAdapter()
    rows = reg.get("mock_gis").fetch_locations()  # type: ignore[union-attr]
    canonical = adapter.adapt_all(rows)  # type: ignore[arg-type]
    added = 0
    for loc in canonical:
        if loc.location_id in existing:
            continue
        db.add(
            Location(
                location_id=loc.location_id,
                parent_location_id=loc.parent_location_id,
                name=loc.name,
                type=loc.type.value if hasattr(loc.type, "value") else str(loc.type),
                latitude=loc.latitude,
                longitude=loc.longitude,
                population=loc.population,
                area_sq_km=loc.area_sq_km,
                source="mock_gis",
            )
        )
        added += 1
    db.commit()
    logger.info("seeded %d locations", added)
    return added


def seed_provider_status(db: Session, reg: ProviderRegistry) -> int:
    names = {row.name for row in db.query(ProviderStatusModel.name).all()}
    added = 0
    for provider in reg.providers():
        if provider.name in names:
            continue
        db.add(
            ProviderStatusModel(
                name=provider.name,
                domain=getattr(provider, "domain", "unknown"),
                status="UNKNOWN",
                auth_configured=False,
                freshness="UNAVAILABLE",
                last_check=utcnow(),
            )
        )
        added += 1
    db.commit()
    return added


def seed_data_source_registry(db: Session, reg: ProviderRegistry) -> int:
    """Upsert static metadata for every known data source (mock + real).

    The registry describes configuration (type, enabled, auth, fallback) —
    runtime health lives in ``provider_status``. The satellite foundation is
    listed but disabled by default (interface + optional mock exist only).
    """
    from ..providers.mock.satellite import MockSatelliteProvider

    rows = reg.providers()
    entries = []
    for provider in rows:
        name = getattr(provider, "name", None)
        if not name:
            continue
        domain = getattr(provider, "domain", "unknown")
        ptype = reg.type_of(name) or getattr(provider, "provider_type", "mock")
        enabled = reg.is_enabled(name) and getattr(provider, "enabled", True)
        requires_key = False
        auth_configured = False
        if name == "openmeteo_weather" or name == "openmeteo_forecast":
            requires_key = False
            auth_configured = False
        elif name == "openmeteo_air_quality":
            requires_key = settings.air_quality_api_key is not None
            auth_configured = bool(settings.air_quality_api_key)
        entries.append(
            {
                "name": name,
                "domain": domain,
                "provider_type": ptype,
                "enabled": enabled,
                "requires_api_key": requires_key,
                "auth_configured": auth_configured,
                "fallback_enabled": getattr(provider, "fallback_enabled", True),
                "description": (
                    "Deterministic synthetic source for demos/tests (never real data)."
                    if ptype == "mock"
                    else "Open-Meteo live API (public, key optional)."
                ),
            }
        )
    # Satellite foundation: interface + deterministic mock, disabled by default.
    entries.append(
        {
            "name": MockSatelliteProvider.name,
            "domain": "satellite",
            "provider_type": "mock",
            "enabled": False,
            "requires_api_key": False,
            "auth_configured": False,
            "fallback_enabled": False,
            "description": (
                "Satellite/remote-sensing FOUNDATION: interface + deterministic "
                "mock only. No real satellite source is configured."
            ),
        }
    )

    existing = {row.name for row in db.query(DataSourceModel.name).all()}
    added = 0
    for entry in entries:
        row = (
            db.query(DataSourceModel)
            .filter(DataSourceModel.name == entry["name"])
            .first()
        )
        if row is None:
            db.add(DataSourceModel(**entry, updated_at=utcnow()))
            added += 1
        else:
            for k, v in entry.items():
                setattr(row, k, v)
            row.updated_at = utcnow()
    db.commit()
    return added


def seed_health_status(db: Session, reg: ProviderRegistry) -> None:
    """Record a synthetic successful contact for mock providers so the provider
    status endpoint shows meaningful (mock) health data."""
    now = utcnow()
    from ..core.enums import FreshnessStatus, ProviderStatus

    for provider in reg.providers():
        row = (
            db.query(ProviderStatusModel)
            .filter(ProviderStatusModel.name == provider.name)
            .first()
        )
        if row is None:
            continue
        row.status = ProviderStatus.ONLINE.value
        row.last_successful_request_at = now
        row.last_latency_ms = 4
        row.success_count = 1
        row.freshness = FreshnessStatus.FRESH.value
        row.last_check = now
    db.commit()


def generate_demo_samples(days: int = 2, seed: int = 2026) -> None:
    """Generate deterministic sample JSON into data/samples for transparency."""
    import json
    import os
    from pathlib import Path

    from ..adapters.weather import WeatherAdapter
    from ..providers.mock.locations import data_poor_location_id

    out = Path(__file__).resolve().parents[3] / "data" / "samples"
    out.mkdir(parents=True, exist_ok=True)

    scenarios = ["NORMAL_DAY", "EXTREME_HEAT"]
    end = utcnow().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    reg = register_all_mock_providers()

    for scenario in scenarios:
        set_scenario(Scenario(scenario))
        weather_prov = reg["mock_weather"]
        raws = weather_prov.fetch_observations("DEMO-WARD-01", start, end, seed=seed)  # type: ignore[attr-defined]
        canonical = WeatherAdapter().adapt_many(raws)
        payload = [s.model_dump(mode="json") for s in canonical]
        (out / f"weather_{scenario.lower()}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    set_scenario(Scenario.DATA_POOR_AREA)
    weather_prov = reg["mock_weather"]
    raws = weather_prov.fetch_observations(data_poor_location_id(), start, end, seed=seed)  # type: ignore[attr-defined]
    canonical = WeatherAdapter().adapt_many(raws)
    (out / "weather_data_poor_area.json").write_text(
        json.dumps([s.model_dump(mode="json") for s in canonical], indent=2),
        encoding="utf-8",
    )
    set_scenario(Scenario.NORMAL_DAY)


def list_canonical_flows() -> List[str]:
    """Human-readable record of implemented provider→adapter→schema flows."""
    return [
        "mock_weather → WeatherAdapter → WeatherObservation",
        "mock_forecast → WeatherForecastAdapter → WeatherForecast",
        "mock_air_quality → AirQualityAdapter → AirQualityObservation",
        "mock_gis → LocationAdapter → Location",
        "mock_vulnerability → VulnerabilityAdapter → VulnerabilityRecord",
        "mock_health → HealthOutcomeAdapter → HealthOutcome (aggregated, de-identified)",
    ]