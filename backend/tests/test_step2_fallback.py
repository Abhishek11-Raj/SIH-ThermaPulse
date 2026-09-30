"""Step 2 tests: provider fallback (live → cache → mock) with provenance."""

from __future__ import annotations

import pytest

from app.providers import register_all_mock_providers, registry
from app.providers.base import RawObservation, register_provider
from app.services.fallback import (
    configured_primary_name,
    fetch_with_fallback,
    is_real_provider,
)
from app.services.retry import ProviderError, ProviderUnavailableError
from app.services.cache import store_cache_entry
from app.utils.time import utcnow


class _DownProvider:
    name = "openmeteo_weather"
    domain = "weather"

    def fetch_observations(self, location_id, start, end, **options):
        raise ProviderUnavailableError("simulated outage")


class _DownAQProvider:
    name = "openmeteo_air_quality"
    domain = "air_quality"

    def fetch_observations(self, location_id, start, end, **options):
        raise ProviderUnavailableError("simulated outage")


@pytest.fixture()
def mock_registry():
    register_all_mock_providers()
    return registry


def test_configured_provider_names():
    assert configured_primary_name("weather") in ("mock_weather", "openmeteo_weather")


def test_is_real_provider_honors_settings(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "weather_provider", "openmeteo")
    assert is_real_provider("weather") is True
    monkeypatch.setattr(settings, "weather_provider", "mock")
    assert is_real_provider("weather") is False


def test_mock_mode_skips_fallback(db, mock_registry, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "weather_provider", "mock")

    def fetch(provider):
        return provider.fetch_observations("DEMO-WARD-01", utcnow(), utcnow())

    result = fetch_with_fallback(db, mock_registry, "weather", "DEMO-WARD-01", fetch)
    assert result.source_used == "live"
    assert result.fallback_used is False
    assert result.provider_name == "mock_weather"


def test_live_failure_falls_back_to_cache(db, mock_registry, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "weather_provider", "openmeteo")
    down = _DownProvider()
    register_provider(down)
    store_cache_entry(
        db, "openmeteo_weather", "weather", "DEMO-WARD-01",
        [{"kind": "observation", "provider_name": "openmeteo_weather",
          "location_id": "DEMO-WARD-01", "observed_at": utcnow().isoformat(),
          "fields": {"temp_c": 30.0}, "source": "openmeteo"}],
        ttl_seconds=3600.0,
    )

    def fetch(provider):
        return provider.fetch_observations("DEMO-WARD-01", utcnow(), utcnow())

    result = fetch_with_fallback(db, mock_registry, "weather", "DEMO-WARD-01", fetch)
    assert result.fallback_used is True
    assert result.fallback_source == "cache"
    assert result.source_used == "cache"
    assert result.cache_freshness == "FRESH"
    assert result.live_error is not None


def test_live_failure_without_cache_falls_back_to_mock(db, mock_registry, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "weather_provider", "openmeteo")
    down = _DownProvider()
    register_provider(down)

    def fetch(provider):
        return provider.fetch_observations("DEMO-WARD-02", utcnow(), utcnow())

    result = fetch_with_fallback(db, mock_registry, "weather", "DEMO-WARD-02", fetch)
    assert result.fallback_used is True
    assert result.fallback_source == "mock"
    assert result.source_used == "mock"
    raws = list(result.raws)
    assert raws  # deterministic mock produced records
    assert raws[0].provider_name == "mock_weather"


def test_final_failure_is_raised(db, mock_registry, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "weather_provider", "openmeteo")
    register_provider(_DownProvider())


    class _UnavailableMock:
        name = "mock_weather"
        domain = "weather"

        def fetch_observations(self, *a, **k):
            raise ProviderUnavailableError("mock broken too")

    monkeypatch.setattr(mock_registry, "_providers", {
        **mock_registry._providers, "mock_weather": _UnavailableMock(),
    })

    def fetch(provider):
        return provider.fetch_observations("DEMO-WARD-99", utcnow(), utcnow())

    with pytest.raises(ProviderError):
        fetch_with_fallback(db, mock_registry, "weather", "DEMO-WARD-99", fetch)