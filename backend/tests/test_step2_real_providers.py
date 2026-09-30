"""Step 2 tests: real Open-Meteo provider parsing (network-stubbed)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.providers.real import (
    OpenMeteoAirQualityProvider,
    OpenMeteoForecastProvider,
    OpenMeteoWeatherProvider,
)
from app.providers.base import RawForecast, RawObservation

_UTC = timezone.utc


def _hourly_times(n):
    base = datetime(2026, 9, 28, 0, 0, tzinfo=_UTC)
    return [(base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(n)]


def _weather_payload(n=3):
    times = _hourly_times(n)
    return {
        "latitude": 19.88,
        "longitude": 75.34,
        "timezone": "UTC",
        "hourly": {
            "time": times,
            "temperature_2m": [25.0 + i for i in range(n)],
            "relative_humidity_2m": [50 - i for i in range(n)],
            "wind_speed_10m": [3.0 + 0.25 * i for i in range(n)],
            "wind_direction_10m": [90 + 10 * i for i in range(n)],
            "pressure_msl": [1010.0 - 0.5 * i for i in range(n)],
            "precipitation": [0.0, 0.2, None] + [0.0] * (n - 3),
            "cloud_cover": [10 + 10 * i for i in range(n)],
            "shortwave_radiation": [0.0, 200.0, 400.0] + [0.0] * (n - 3),
            "visibility": [10000 - 500 * i for i in range(n)],
            "uv_index": [i % 6 for i in range(n)],
        },
    }


def _aq_payload(n=3):
    times = _hourly_times(n)
    return {
        "latitude": 19.88,
        "longitude": 75.34,
        "hourly": {
            "time": times,
            "pm10": [40.0, 45.0, None] + [40.0] * (n - 3),
            "pm2_5": [25.0, 30.0, 28.0] + [25.0] * (n - 3),
            "ozone": [60.0, 62.0, 61.0] + [60.0] * (n - 3),
            "nitrogen_dioxide": [20.0, 21.0, 19.0] + [20.0] * (n - 3),
            "sulphur_dioxide": [5.0, 6.0, 4.0] + [5.0] * (n - 3),
            "carbon_monoxide": [1000.0, 1200.0, 900.0] + [1000.0] * (n - 3),
            "us_aqi": [61, 65, 58] + [61] * (n - 3),
            "european_aqi": [70, 75, 66] + [70] * (n - 3),
        },
    }


def _transport(payload):
    return httpx.MockTransport(lambda request: httpx.Response(200, json=payload))


def test_weather_provider_maps_fields_and_units():
    provider = OpenMeteoWeatherProvider(transport=_transport(_weather_payload()))
    start = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    raws = provider.fetch_observations("DEMO-WARD-01", start, end, latitude=19.88, longitude=75.34)
    assert len(raws) == 3
    first = raws[0]
    assert isinstance(first, RawObservation)
    assert first.location_id == "DEMO-WARD-01"
    assert first.source == "openmeteo"
    assert first.fields["temp_c"] == 25.0
    assert first.fields["pressure_hpa"] == 1010.0
    assert first.fields["visibility_km"] == pytest.approx(10.0, abs=0.01)  # 10000 m → km
    assert first.fields["temperature_unit"] == "C"


def test_weather_provider_null_precipitation_stays_null():
    provider = OpenMeteoWeatherProvider(transport=_transport(_weather_payload()))
    start = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    raws = provider.fetch_observations("L", start, end, latitude=19.88, longitude=75.34)
    assert raws[2].fields["rainfall_mm"] is None


def test_forecast_provider_produces_periods():
    provider = OpenMeteoForecastProvider(transport=_transport(_weather_payload(48)))
    issued = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)
    raws = provider.fetch_forecast("DEMO-WARD-01", issued, horizon_hours=24,
                                   latitude=19.88, longitude=75.34)
    assert len(raws) == 1
    forecast = raws[0]
    assert isinstance(forecast, RawForecast)
    assert len(forecast.periods) == 24
    valid_from, valid_to, fields = forecast.periods[0]
    assert valid_to - valid_from == timedelta(hours=1)
    assert forecast.model_name == "Open-Meteo"
    assert forecast.source == "openmeteo"


def test_aq_provider_converts_co_and_missing_stays_null():
    provider = OpenMeteoAirQualityProvider(transport=_transport(_aq_payload()))
    start = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    raws = provider.fetch_observations("L", start, end, latitude=19.88, longitude=75.34)
    assert len(raws) == 3
    first = raws[0]
    # 1000 µg/m³ CO → 1.0 mg/m³
    assert first.fields["co_mgm3"] == 1.0
    assert first.fields["aqi_index"] == 61
    # PM10 null preserved (never zeroed)
    assert raws[2].fields["pm10_ugm3"] is None


def test_provider_requires_coordinates():
    provider = OpenMeteoWeatherProvider(transport=_transport(_weather_payload()))
    start = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    with pytest.raises(ValueError):
        provider.fetch_observations("L", start, end)