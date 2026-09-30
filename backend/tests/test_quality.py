"""Quality pipeline: flags, sanitization, freshness — 'missing ≠ zero'."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.enums import FreshnessStatus, QualityFlag
from app.schemas.common import QualityAssessment
from app.services.quality import (
    assess_air_quality,
    assess_weather,
    freshness_status,
    sanitize,
)


def _ts(hours: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def test_assess_weather_valid():
    values = {
        "temperature": 30.0,
        "relative_humidity": 50.0,
        "wind_speed": 3.0,
        "pressure": 1008.0,
        "cloud_cover": 30.0,
        "solar_radiation": 400.0,
    }
    qa = assess_weather(values, _ts())
    assert qa.flag == QualityFlag.VALID
    assert qa.missing_variables == []


def test_assess_weather_flags_missing_variables():
    values = {"temperature": None, "relative_humidity": None}
    qa = assess_weather(values, _ts())
    assert qa.flag == QualityFlag.MISSING
    assert "temperature" in qa.missing_variables
    assert "relative_humidity" in qa.missing_variables


def test_assess_weather_flags_implausible_as_invalid():
    qa = assess_weather({"temperature": 999.0}, _ts())
    assert qa.flag == QualityFlag.INVALID
    assert any(i.code == "out_of_range" for i in qa.issues)


def test_sanitize_downgrades_invalid_to_none_keeps_original():
    values = {"temperature": 999.0, "relative_humidity": 45.0}
    qa = assess_weather(values, _ts())
    clean = sanitize(values, qa)
    assert clean["temperature"] is None
    assert clean["relative_humidity"] == 45.0


def test_sanitize_keeps_missing_null():
    qa = assess_weather({"temperature": None}, _ts())
    clean = sanitize({"temperature": None}, qa)
    assert clean["temperature"] is None


def test_assess_forecast_applies_same_discipline():
    from app.services.quality import assess_forecast

    values = {
        "temperature": 33.0,
        "relative_humidity": 40.0,
        "wind_speed": 4.0,
        "wind_direction": 200.0,
        "pressure": 1005.0,
        "rainfall": 0.0,
        "cloud_cover": 20.0,
        "solar_radiation": 500.0,
        "visibility": 10.0,
        "uv_index": 4.0,
    }
    qa = assess_forecast(values, _ts(hours=2), _ts(hours=1), _ts())
    assert qa.flag == QualityFlag.VALID


def test_assess_air_quality_null_allowed_missing_flagged():
    qa = assess_air_quality({"pm25": 55.0, "pm10": None}, _ts())
    assert qa.flag == QualityFlag.MISSING
    assert "o3" in qa.missing_variables
    assert "pm10" not in qa.missing_variables  # omitted sensor channel, not counted


def test_freshness_status_per_domain_cadence():
    fresh = freshness_status(_ts(hours=0), expected_update_hours=1)
    aging = freshness_status(_ts(hours=1.5), expected_update_hours=1)
    stale = freshness_status(_ts(hours=2.5), expected_update_hours=1)
    assert fresh == FreshnessStatus.FRESH
    assert aging == FreshnessStatus.AGING
    assert stale == FreshnessStatus.STALE


def test_freshness_unavailable_when_no_data():
    assert freshness_status(None, expected_update_hours=1) == FreshnessStatus.UNAVAILABLE


def test_freshness_unavailable_when_data_is_far_beyond_cadence():
    assert freshness_status(_ts(hours=30), expected_update_hours=1) == FreshnessStatus.UNAVAILABLE


def test_quality_assessment_summarize_roundtrip():
    qa = QualityAssessment(flag=QualityFlag.SUSPECT, issues=[])
    assert qa.summarize() == "SUSPECT: ok"