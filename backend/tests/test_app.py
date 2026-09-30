"""Smoke tests: the app starts and core endpoints respond."""

from __future__ import annotations


def test_app_imports_and_root_redirects(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (200, 307, 302)
    if r.status_code in (307, 302):
        assert "location" in r.headers
    else:
        # 200 = landing HTML page
        assert "Thermapulse" in r.text or "KESHAV" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["environment"], str)
    assert "api_version" in body


def test_api_v1_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_system_info(client):
    r = client.get("/api/v1/system/info")
    assert r.status_code == 200
    body = r.json()
    assert "api_version" in body
    assert "application" in body
    assert "environment" in body
    assert "mock_mode" in body
    assert body["mock_mode"] is True
    assert body["database_dialect"] == "sqlite"


def test_landing_page_redirects_to_docs(client):
    r = client.get("/", follow_redirects=True)
    assert r.status_code == 200


def test_dashboard_static_mount(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Thermapulse" in r.text or "KESHAV" in r.text


def test_openapi_available(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/locations" in paths
    assert "/api/v1/weather" in paths
    assert "/api/v1/forecast" in paths
    assert "/api/v1/air-quality" in paths


def test_unknown_api_route_404(client):
    assert client.get("/api/v1/does-not-exist").status_code == 404