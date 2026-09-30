"""Step 2 tests: ingestion orchestrator with fallback + provenance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.enums import DataDomain
from app.providers import register_all_mock_providers, registry
from app.providers.base import register_provider
from app.services.ingest import (
    default_window,
    ingest_air_quality,
    ingest_forecast,
    ingest_weather,
)
from app.services.retry import ProviderUnavailableError
from app.models.operations import IngestionLog as IngestionLogModel
from app.utils.time import utcnow


class _DownWeather:
    name = "openmeteo_weather"
    domain = "weather"

    def fetch_observations(self, location_id, start, end, **options):
        raise ProviderUnavailableError("simulated outage")


@pytest.fixture()
def mock_registry():
    register_all_mock_providers()
    return registry


def _latest_log_for(db, ingestion_id):
    from sqlalchemy import desc

    return (
        db.query(IngestionLogModel)
        .filter(IngestionLogModel.ingestion_id == ingestion_id)
        .order_by(desc(IngestionLogModel.id))
        .first()
    )


def _past_window(hours=4):
    start = datetime(2026, 3, 10, 0, 0, tzinfo=timezone.utc)
    return start, start + timedelta(hours=hours)


def test_mock_ingestion_records_no_fallback(db, mock_registry):
    start, end = _past_window()
    canonical, tracker = ingest_weather(db, "DEMO-WARD-MK", start, end, reg=mock_registry)
    assert len(canonical) == 5  # 4-hour window, hourly grid, both endpoints included
    assert tracker.fallback_used is False
    log = _latest_log_for(db, tracker.ingestion_id)
    assert log is not None
    assert log.status == "SUCCESS"
    assert log.provider == "mock_weather"
    assert log.records_accepted == len(canonical)
    assert log.records_received >= log.records_accepted
    assert log.duration_ms is not None
    assert log.domain == DataDomain.WEATHER.value


def test_satellite_field_in_placeholder():
    # Guard: no thermal index fields ever leak into Step 2 ingestion.
    from app.services.temporal import align_hourly_to_daily

    base = utcnow().replace(minute=0, second=0, microsecond=0)
    recs = [{"observed_at": base + timedelta(hours=i), "value": 25.0 + i} for i in range(6)]
    daily, _ = align_hourly_to_daily(recs)
    assert "heat_index" not in daily[0]
    assert "wbgt" not in daily[0]


def test_fallback_ingestion_records_fallback_source(db, mock_registry, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "weather_provider", "openmeteo")
    register_provider(_DownWeather())
    start, end = _past_window()
    canonical, tracker = ingest_weather(db, "DEMO-DOWN-01", start, end, reg=mock_registry)
    assert canonical
    assert tracker.fallback_used is True
    assert tracker.fallback_source == "mock"
    # Canonical records are still valid quality observations from the mock source.
    assert canonical[0].provider == "mock_weather"
    log = _latest_log_for(db, tracker.ingestion_id)
    assert log.fallback_used is True
    assert log.fallback_source == "mock"


def test_forecast_and_aq_ingestion_keep_mock_counts(db, mock_registry):
    issued = utcnow().replace(minute=0, second=0, microsecond=0)
    forecasts, ft = ingest_forecast(db, "DEMO-WARD-01", issued, horizon_hours=24, reg=mock_registry)
    assert len(forecasts) == 24
    start, end = default_window(4)
    aq, at = ingest_air_quality(db, "DEMO-WARD-01", start, end, reg=mock_registry)
    assert len(aq) == 5
    assert ft.fallback_used is False
    assert at.fallback_used is False