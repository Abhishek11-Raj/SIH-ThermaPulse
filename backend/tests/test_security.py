"""Security guarantees observable through APIs and passed configs."""

from __future__ import annotations


def test_secrets_are_never_exposed_by_system_info(client):
    r = client.get("/api/v1/system/info")
    assert r.status_code == 200
    text = r.text.lower()
    assert "test-secret-weather-key" not in text
    assert "test-secret-aq-key" not in text
    assert "api_key" not in text
    assert "password" not in text


def test_provider_status_exposes_no_credentials(client):
    r = client.get("/api/v1/provider-status")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    blobs = " ".join(str(b).lower() for b in body)
    assert "test-secret" not in blobs


def test_error_responses_do_not_leak_stack_traces(client):
    r = client.get("/api/v1/weather?start=not-a-date")
    assert r.status_code == 422
    assert "Traceback" not in r.text


def test_cors_middleware_present(client):
    r = client.get("/api/v1/health", headers={"Origin": "http://127.0.0.1:8000"})
    assert r.status_code == 200
    allow = r.headers.get("access-control-allow-origin")
    assert allow and allow == "http://127.0.0.1:8000"


def test_security_redact_never_exposes_value():
    from app.core.security import redact

    out = redact({"TOKEN": "super-secret", "X": 1})
    assert out["TOKEN"].startswith("[REDACTED]")
    assert "super-secret" not in str(out)