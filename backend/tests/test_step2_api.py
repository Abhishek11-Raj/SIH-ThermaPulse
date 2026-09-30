"""Step 2 tests: new API endpoints and enriched provider status."""

from __future__ import annotations


def test_provider_status_still_six_with_metadata(client):
    r = client.get("/api/v1/provider-status")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 6
    domains = {d["domain"] for d in data}
    assert domains == {
        "weather", "weather_forecast", "air_quality", "gis",
        "vulnerability", "health",
    }
    # Step 2 enrichment present but additive
    for entry in data:
        assert "provider_type" in entry
        assert "enabled" in entry


def test_provider_registry_endpoint(client):
    r = client.get("/api/v1/provider-registry")
    assert r.status_code == 200
    payload = r.json()
    assert payload["mock_mode"] is True
    assert payload["configured"]["weather"] in ("mock", "openmeteo")
    providers = payload["providers"]
    by_name = {p["name"]: p for p in providers}
    assert "mock_weather" in by_name
    assert by_name["mock_weather"]["provider_type"] == "mock"
    # Satellite foundation present but disabled (interface + mock only).
    sat = payload["satellite"]
    assert isinstance(sat, dict)
    assert sat["enabled"] is False
    assert "mock" in sat["description"].lower()


def test_data_sources_endpoint_never_exposes_secrets(client):
    r = client.get("/api/v1/data-sources")
    assert r.status_code == 200
    payload = r.json()
    assert isinstance(payload, list)
    for source in payload:
        assert "requires_api_key" in source
        assert "auth_configured" in source
        items = source.values()
        assert not any(isinstance(v, str) and "test-secret" in v.lower() for v in items)


def test_ingestion_status_and_logs(client):
    # Trigger some ingestion, then inspect status/logs.
    assert client.get("/api/v1/weather?location_id=DEMO-WARD-01").status_code == 200
    st = client.get("/api/v1/ingestion/status")
    assert st.status_code == 200
    payload = st.json()
    assert payload["total_runs"] >= 1
    assert "by_status" in payload
    assert "recent_runs" in payload
    run = payload["recent_runs"][0]
    assert "duration_ms" in run
    assert "fallback_used" in run
    logs = client.get("/api/v1/ingestion/logs?limit=10")
    assert logs.status_code == 200
    assert len(logs.json()) >= 1


def test_ingestion_logs_show_fallback_fields(client):
    logs = client.get("/api/v1/ingestion/logs")
    first = logs.json()[0]
    assert "fallback_used" in first
    assert "fallback_source" in first
    assert "ingestion_id" in first


def test_coverage_audit_endpoint(client):
    r = client.get("/api/v1/coverage/audit")
    assert r.status_code == 200
    payload = r.json()
    assert "per_location" in payload
    assert "provider_coverage" in payload
    assert "variable_missingness" in payload
    assert "temporal" in payload and "freshness_by_domain" in payload["temporal"]
    assert "equity" in payload
    equity = payload["equity"]
    assert "data_poor_with_high_vulnerability" in equity
    assert "equity_rule" in equity


def test_coverage_audit_single_location(client):
    r = client.get("/api/v1/coverage/audit?location_id=DEMO-WARD-01")
    assert r.status_code == 200
    assert r.json()["locations_covered"] >= 1


def test_data_quality_audit_endpoint(client):
    r = client.get("/api/v1/data-quality/audit")
    assert r.status_code == 200
    payload = r.json()
    assert "groups" in payload
    assert "by_domain" in payload["groups"]
    assert "missing_variables_tally" in payload


def test_coverage_endpoint_still_works(client):
    assert client.get("/api/v1/coverage").status_code == 200