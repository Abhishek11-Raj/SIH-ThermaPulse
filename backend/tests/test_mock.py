"""Mock providers must be deterministic, scenario-driven and gap-aware."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.enums import Scenario
from app.providers import registry
from app.providers.mock.providers import register_all_mock_providers
from app.providers.base import set_scenario, set_mock_seed


def _window(hours: int = 48) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return end - timedelta(hours=hours), end


def _snapshot(provider, location_id: str, start, end, seed: int):
    rows = provider.fetch_observations(location_id, start, end, seed=seed)
    return [
        (r.observed_at.isoformat(), tuple(sorted(r.fields.items())))
        for r in rows
    ]


def test_all_mock_providers_registered():
    reg = register_all_mock_providers()
    assert {"mock_weather", "mock_forecast", "mock_air_quality",
            "mock_gis", "mock_vulnerability", "mock_health"}.issubset(reg.keys())


def test_mock_weather_is_deterministic():
    register_all_mock_providers()
    set_scenario(Scenario.NORMAL_DAY)
    set_mock_seed(2026)
    start, end = _window()
    prov = registry["mock_weather"]
    a = _snapshot(prov, "DEMO-WARD-01", start, end, 2026)
    b = _snapshot(prov, "DEMO-WARD-01", start, end, 2026)
    assert a == b
    assert len(a) == 49  # 48h inclusive hourly window


def test_different_seed_changes_values():
    register_all_mock_providers()
    set_scenario(Scenario.NORMAL_DAY)
    start, end = _window()
    prov = registry["mock_weather"]
    a = _snapshot(prov, "DEMO-WARD-01", start, end, 2026)
    b = _snapshot(prov, "DEMO-WARD-01", start, end, 2027)
    assert a != b


def test_extreme_heat_hotter_than_normal_day():
    register_all_mock_providers()
    start, end = _window()
    prov = registry["mock_weather"]

    set_scenario(Scenario.NORMAL_DAY)
    normal = [r.fields["temp_c"] for r in prov.fetch_observations("DEMO-WARD-01", start, end, seed=2026) if r.fields.get("temp_c") is not None]

    set_scenario(Scenario.EXTREME_HEAT)
    extreme = [r.fields["temp_c"] for r in prov.fetch_observations("DEMO-WARD-01", start, end, seed=2026) if r.fields.get("temp_c") is not None]

    assert max(extreme) > max(normal)
    set_scenario(Scenario.NORMAL_DAY)


def test_data_poor_scenario_reduces_records_and_nulls_temperature():
    register_all_mock_providers()
    start, end = _window()
    prov = registry["mock_weather"]

    set_scenario(Scenario.NORMAL_DAY)
    full = prov.fetch_observations("DEMO-WARD-03", start, end, seed=2026)

    set_scenario(Scenario.DATA_POOR_AREA)
    gaps = prov.fetch_observations("DEMO-WARD-03", start, end, seed=2026)

    assert len(gaps) < len(full)
    # Any record produced at hour 6 must carry an explicit None temperature.
    hour6 = [r for r in gaps if r.observed_at.hour == 6]
    assert all(r.fields.get("temp_c") is None for r in hour6)
    set_scenario(Scenario.NORMAL_DAY)


def test_data_poor_scenario_does_not_apply_to_other_wards():
    """DATA_POOR_AREA scenario affects only the designated demo ward."""
    register_all_mock_providers()
    start, end = _window()
    prov = registry["mock_weather"]

    set_scenario(Scenario.DATA_POOR_AREA)
    rows = prov.fetch_observations("DEMO-WARD-01", start, end, seed=2026)
    assert len(rows) == 49
    set_scenario(Scenario.NORMAL_DAY)


def test_forecast_horizon_matches_requested_hours():
    register_all_mock_providers()
    issued = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    prov = registry["mock_forecast"]
    raw = prov.fetch_forecast("DEMO-WARD-01", issued, horizon_hours=24)
    assert len(raw) == 1
    assert len(raw[0].periods) == 24
    assert raw[0].model_name == "mock-forecast-v1"