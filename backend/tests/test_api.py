"""End-to-end API contract tests across all live endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _window(hours: int = 48) -> tuple[str, str]:
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours)
    return start.isoformat(), end.isoformat()


def test_locations_list(client):
    r = client.get("/api/v1/locations")
    body = r.json()
    assert r.status_code == 200
    assert body["count"] == 10
    assert any(x["location_id"] == "DEMO-WARD-01" for x in body["locations"])


def test_locations_filtered(client):
    r = client.get("/api/v1/locations?location_type=ward")
    body = r.json()
    assert all(x["type"] == "ward" for x in body["locations"])
    assert body["count"] == 3


def test_weather_endpoint_returns_canonical(client):
    start, end = _window()
    r = client.get(f"/api/v1/weather?start={start}&end={end}&location_id=DEMO-WARD-01")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 49  # 48h inclusive hourly window
    o = body["observations"][0]
    assert o["location_id"] == "DEMO-WARD-01"
    assert "temperature" in o
    assert "quality_flag" in o
    assert "provenance" in o
    assert "observed_at" in o
    assert "forecast_id" not in o  # observations are never forecasts


def test_weather_endpoint_unknown_location_404(client):
    r = client.get("/api/v1/weather?location_id=DEMO-NOPE")
    assert r.status_code == 404


def test_weather_rejects_bad_window(client):
    r = client.get("/api/v1/weather?start=garbage")
    assert r.status_code == 422


def test_forecast_endpoint_preserves_issued_vs_valid(client):
    r = client.get(
        "/api/v1/forecast?location_id=DEMO-WARD-01&horizon_hours=24"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 24
    f = body["forecasts"][0]
    assert "issued_at" in f and "valid_from" in f and "valid_to" in f
    assert f["issued_at"] <= f["valid_from"]
    assert f["valid_to"] > f["valid_from"]
    assert f["forecast_horizon_hours"] == 1  # per-window horizon
    assert "observed_at" not in f
    assert f["model_name"] == "mock-forecast-v1"


def test_air_quality_endpoint(client):
    start, end = _window()
    r = client.get(f"/api/v1/air-quality?start={start}&end={end}&location_id=DEMO-WARD-01")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 49  # 48h inclusive hourly window
    obs = body["observations"][0]
    assert "pm10" in obs or "pm25" in obs


def test_air_quality_missing_never_zero(client):
    start, end = _window()
    r = client.get(f"/api/v1/air-quality?start={start}&end={end}&location_id=DEMO-WARD-01")
    assert r.status_code == 200
    body = r.json()
    assert all(o["pm10"] is None for o in body["observations"])  # provider omits pm10


def test_data_quality_endpoint_returns_summary(client):
    r = client.get("/api/v1/data-quality")
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert "flagged_count" in body["summary"]


def test_coverage_endpoint_encodes_equity(client):
    r = client.get("/api/v1/coverage?location_id=DEMO-WARD-01")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and len(body) >= 1
    assert any("equity_note" in str(d) for d in body)


def test_provider_status_endpoint(client):
    r = client.get("/api/v1/provider-status")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 6
    assert {p["domain"] for p in body} == {
        "weather", "weather_forecast", "air_quality", "gis", "vulnerability", "health",
    }


def test_health_outcomes_aggregated_and_deidentified(client):
    r = client.get("/api/v1/health-outcomes?location_id=DEMO-WARD-01")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    o = body["outcomes"][0]
    assert "heat_illness_cases" in o or "emergency_visits" in o
    assert all("patient_id" not in str(x).lower() for x in [o])
    assert all(("name" not in k) and ("phone" not in k) and ("aadhaar" not in k) for k in o)


def test_vulnerability_endpoint(client):
    r = client.get("/api/v1/vulnerability?location_id=DEMO-WARD-01")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1


def test_model_registry_is_explicitly_empty(client):
    r = client.get("/api/v1/model-registry")
    assert r.status_code == 200
    body = r.json()
    assert body["models"] == []


def test_canonical_flows_documented(client):
    r = client.get("/api/v1/canonical-flows")
    assert r.status_code == 200
    flows = " | ".join(r.json()["flows"])
    assert "mock_weather → WeatherAdapter → WeatherObservation" in flows
    assert len(r.json()["flows"]) == 6