"""Configuration, secret redaction, CORS parsing."""

from __future__ import annotations

import pytest


def test_settings_load_from_env():
    from app.core.config import Settings

    s = Settings()
    assert s.env == "test"  # set by conftest
    assert s.app_env == "test"
    assert s.mock_mode is True
    assert s.mock_seed == 2026


def test_safe_dict_redacts_secrets():
    from app.core.config import Settings

    safe = Settings().safe_dict()
    joined = str(safe).lower()
    assert "test-secret-weather-key" not in joined
    assert "test-secret-aq-key" not in joined


def test_settings_redact_keeps_public_values():
    from app.core.config import Settings

    out = Settings().redact({"WEATHER_API_KEY": "abc123", "name": "dashboard"})
    assert out["WEATHER_API_KEY"].startswith("[REDACTED]")
    assert out["name"] == "dashboard"


def test_cors_origins_parsing():
    from app.core.config import Settings

    s = Settings(cors_origins="https://a.example, https://b.example")
    assert set(s.cors_origins) == {"https://a.example", "https://b.example"}


def test_cors_origins_validation_rejects_wildcard():
    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(cors_origins="*")


def test_security_redact_helpers():
    from app.core.security import redact, _looks_secret

    assert _looks_secret("API_KEY")
    assert _looks_secret("password")
    assert not _looks_secret("mock_seed")
    out = redact({"API_KEY": "super-secret"})
    assert out["API_KEY"].startswith("[REDACTED]")


def test_audit_event_redacts_details():
    from app.core.security import AuditEvent, redact

    ev = AuditEvent(actor="system", action="seed", resource="location", details={"api_key": "x"})
    safe = redact(ev.details)
    assert safe["api_key"].startswith("[REDACTED]")