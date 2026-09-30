"""Step 2 tests: SSRF-safe HTTP client with bounded retries + raw validation."""

from __future__ import annotations

import httpx
import pytest

from app.services.http import SafeHttpClient
from app.services.retry import (
    ProviderAuthError,
    ProviderError,
    ProviderErrorKind,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    RetryPolicy,
)
from app.services.validation import (
    RawValidationResult,
    validate_hourly_time_series,
)


def _mock_transport(payload):
    return httpx.MockTransport(lambda request: httpx.Response(200, json=payload))


def test_ssrf_guard_blocks_non_allowed_host():
    client = SafeHttpClient(allowed_hosts={"api.example.com"}, transport=_mock_transport({}))
    with pytest.raises(ProviderError) as excinfo:
        client.get_json("http://evil.internal:8080/")
    assert excinfo.value.kind == ProviderErrorKind.INVALID_RESPONSE


def test_allowed_host_returns_json():
    client = SafeHttpClient(
        allowed_hosts={"api.example.com"},
        transport=_mock_transport({"hello": "world"}),
    )
    result = client.get_json("https://api.example.com/v1/data")
    assert result.data == {"hello": "world"}
    assert result.status_code == 200


def test_timeout_classified_and_retried():
    def handler(request):
        raise httpx.ConnectTimeout("took too long")

    client = SafeHttpClient(
        allowed_hosts={"api.example.com"},
        retry_policy=RetryPolicy(max_attempts=2, base_backoff_seconds=0.01),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderError) as excinfo:
        client.get_json("https://api.example.com/v1/data")
    assert excinfo.value.kind == ProviderErrorKind.NETWORK or excinfo.value.kind == ProviderErrorKind.TIMEOUT


def test_401_is_auth_failure():
    client = SafeHttpClient(
        allowed_hosts={"api.example.com"},
        retry_policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.01),
        transport=httpx.MockTransport(lambda r: httpx.Response(401, json={})),
    )
    with pytest.raises(ProviderAuthError):
        client.get_json("https://api.example.com/v1/data")


def test_invalid_json_rejected():
    def handler(request):
        return httpx.Response(200, content=b"not json", headers={"content-type": "application/json"})

    client = SafeHttpClient(
        allowed_hosts={"api.example.com"},
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderInvalidResponseError):
        client.get_json("https://api.example.com/v1/data")


# --- raw payload validation --------------------------------------------------


def _hourly_payload(n=3):
    return {
        "latitude": 19.88,
        "longitude": 75.34,
        "hourly": {
            "time": [
                f"2026-09-28T0{i}:00:00Z" for i in range(n)
            ],
            "temperature_2m": [25.0, 26.0, 27.0],
            "relative_humidity_2m": [50, 48, 46],
        },
    }


def test_valid_hourly_payload_passes():
    result = validate_hourly_time_series(_hourly_payload(), "L1", "prov", "weather")
    assert result.valid is True


def test_mismatched_lengths_fail():
    payload = _hourly_payload()
    payload["hourly"]["temperature_2m"] = [25.0]  # wrong length
    with pytest.raises(ProviderInvalidResponseError):
        validate_hourly_time_series(payload, "L1", "prov", "weather")


def test_bad_timestamp_fails():
    payload = _hourly_payload()
    payload["hourly"]["time"][1] = "not-a-time"
    with pytest.raises(ProviderInvalidResponseError):
        validate_hourly_time_series(payload, "L1", "prov", "weather")


def test_duplicate_timestamp_fails():
    payload = _hourly_payload()
    payload["hourly"]["time"][1] = payload["hourly"]["time"][0]
    with pytest.raises(ProviderInvalidResponseError):
        validate_hourly_time_series(payload, "L1", "prov", "weather")


def test_missing_coordinates_fails():
    payload = _hourly_payload()
    del payload["latitude"]
    with pytest.raises(ProviderInvalidResponseError):
        validate_hourly_time_series(payload, "L1", "prov", "weather")


def test_missing_hourly_fails():
    payload = _hourly_payload()
    del payload["hourly"]
    with pytest.raises(ProviderInvalidResponseError):
        validate_hourly_time_series(payload, "L1", "prov", "weather")


def test_null_values_allowed():
    payload = _hourly_payload()
    payload["hourly"]["relative_humidity_2m"] = [50, None, 46]
    result = validate_hourly_time_series(payload, "L1", "prov", "weather")
    assert result.valid is True


def test_raw_validation_collects_issues():
    result = RawValidationResult()
    result.error("a", "broken")
    assert result.valid is False
    with pytest.raises(ProviderInvalidResponseError):
        result.raise_if_invalid("provider-x")