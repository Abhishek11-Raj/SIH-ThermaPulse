"""Canonical schema validation — contracts behave as documented."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.core.enums import QualityFlag
from app.schemas.air_quality import AirQualityObservation
from app.schemas.common import CoverageReport, Provenance, TimeWindow
from app.schemas.forecast import WeatherForecast
from app.schemas.health import HealthOutcome
from app.schemas.vulnerability import VulnerabilityRecord
from app.schemas.weather import WeatherObservation


def _ts(hours: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def _weather(**overrides) -> WeatherObservation:
    base = dict(
        observation_id="obs-1",
        source="mock",
        provider="mock_weather",
        location_id="DEMO-WARD-01",
        observed_at=_ts(),
        temperature=30.0,
    )
    base.update(overrides)
    return WeatherObservation(**base)


# ---------------------------------------------------------------------------


def test_valid_weather_observation():
    obs = _weather()
    assert obs.quality_flag == QualityFlag.VALID
    assert obs.temperature == 30.0


def test_missing_weather_field_is_none_not_zero():
    obs = WeatherObservation(
        observation_id="obs-2",
        source="mock",
        provider="mock_weather",
        location_id="DEMO-WARD-01",
        observed_at=_ts(),
        temperature=None,
        relative_humidity=None,
    )
    assert obs.temperature is None
    assert obs.relative_humidity is None


def test_weather_out_of_range_is_a_quality_concern_not_schema_failure():
    """The schema intentionally does not reject extreme values: the quality layer
    evaluates plausibility per-record and flags them INVALID (kept null)."""
    obs = _weather(temperature=500.0)
    assert obs.temperature == 500.0
    assert obs.quality_flag == QualityFlag.VALID  # quality assessment runs later


def test_weather_rejects_bad_unit():
    with pytest.raises(ValidationError):
        _weather(temperature_unit="Z")


def test_weather_rejects_negative_humidity():
    with pytest.raises(ValidationError):
        _weather(relative_humidity=-1.0)


def test_weather_rejects_wind_direction_over_360():
    with pytest.raises(ValidationError):
        _weather(wind_direction=400)


# ---------------------------------------------------------------------------


def test_forecast_distinct_from_observation():
    f = WeatherForecast(
        forecast_id="f-1",
        source="mock",
        provider="mock_forecast",
        location_id="DEMO-WARD-01",
        issued_at=_ts(hours=2),
        valid_from=_ts(hours=1),
        valid_to=_ts(),
        forecast_horizon_hours=1,
        temperature=31.0,
    )
    assert f.issued_at <= f.valid_from
    assert f.forecast_horizon_hours == 1


def test_forecast_rejects_reversed_window():
    with pytest.raises(ValidationError):
        WeatherForecast(
            forecast_id="f-2",
            source="mock",
            provider="mock_forecast",
            location_id="DEMO-WARD-01",
            issued_at=_ts(hours=4),
            valid_from=_ts(hours=2),
            valid_to=_ts(hours=3),
            forecast_horizon_hours=1,
        )


def test_forecast_rejects_negative_horizon():
    with pytest.raises(ValidationError):
        WeatherForecast(
            forecast_id="f-3",
            source="mock",
            provider="mock_forecast",
            location_id="DEMO-WARD-01",
            issued_at=_ts(),
            valid_from=_ts(),
            valid_to=_ts() + timedelta(hours=1),
            forecast_horizon_hours=-1,
        )


# ---------------------------------------------------------------------------


def test_aq_null_pollutant_is_allowed():
    obs = AirQualityObservation(
        observation_id="aq-1",
        source="mock",
        provider="mock_air_quality",
        location_id="DEMO-WARD-01",
        observed_at=_ts(),
        pm10=None,
        pm25=40.5,
    )
    assert obs.pm10 is None
    assert obs.pm25 == 40.5


def test_aq_rejects_negative_pm25():
    with pytest.raises(ValidationError):
        AirQualityObservation(
            observation_id="aq-2",
            source="mock",
            provider="mock_air_quality",
            location_id="DEMO-WARD-01",
            observed_at=_ts(),
            pm25=-5.0,
        )


# ---------------------------------------------------------------------------


def test_health_outcome_rejects_identifiers():
    with pytest.raises(ValidationError):
        HealthOutcome(
            outcome_id="h-1",
            location_id="DEMO-WARD-01",
            time_period=TimeWindow(start=_ts(hours=1), end=_ts()),
            source="mock",
            provider="mock_health",
            patient_id="secret-person",
        )


def test_health_outcome_allows_aggregated_counts_only():
    h = HealthOutcome(
        outcome_id="h-2",
        location_id="DEMO-WARD-01",
        time_period=TimeWindow(start=_ts(hours=1), end=_ts()),
        aggregation_level="daily_area",
        heat_illness_cases=5,
        emergency_visits=12,
        source="mock",
        provider="mock_health",
    )
    assert h.heat_illness_cases == 5
    assert h.aggregation_level == "daily_area"


# ---------------------------------------------------------------------------


def test_vulnerability_allows_null_factors():
    v = VulnerabilityRecord(
        vulnerability_id="v-1",
        location_id="DEMO-WARD-03",
        reference_date=_ts(),
        source="mock",
        provider="mock_vulnerability",
    )
    assert v.factors.outdoor_worker_share is None
    assert v.factors.elderly_population_share is None
    assert "outdoor_worker_share" in v.factors.model_fields


# ---------------------------------------------------------------------------


def test_provenance_recorded():
    obs = _weather(provenance=Provenance(source="mock", provider="mock_weather"))
    assert obs.provenance.source == "mock"
    assert obs.provenance.provider == "mock_weather"


def test_quality_assessment_flags_and_summarize():
    from app.schemas.common import QualityAssessment

    qa = QualityAssessment(flag=QualityFlag.SUSPECT)
    assert qa.summarize().startswith("SUSPECT")


def test_time_window_contains_and_overlaps():
    w = TimeWindow(start=_ts(hours=3), end=_ts(hours=1))
    assert w.contains(_ts(hours=2))
    assert not w.contains(_ts())
    assert w.overlaps(TimeWindow(start=_ts(hours=4), end=_ts(hours=2)))


def test_coverage_report_equity_note():
    r = CoverageReport(location_id="DEMO-WARD-03", domain="weather", provider="mock")
    assert "No data is never treated as low risk" in r.equity_note
    assert r.coverage_class == "DATA_POOR"


def test_documented_derived_metrics_not_in_weather():
    """The canonical weather schema must NOT carry derived thermal metrics —
    those are later-stage engines and would violate 'no claims without
    implementation'."""
    fields = {f for f in WeatherObservation.model_fields}
    assert not ({"heat_index", "utci"} & fields)