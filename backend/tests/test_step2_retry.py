"""Step 2 tests: bounded retry and error taxonomy."""

from __future__ import annotations

import pytest

from app.services.retry import (
    ProviderAuthError,
    ProviderError,
    ProviderErrorKind,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RetryPolicy,
    with_bounded_retry,
    classify_status_code,
)


def test_kinds_retry_classification():
    assert ProviderError(ProviderErrorKind.NETWORK, "x").should_retry is True
    assert ProviderError(ProviderErrorKind.TIMEOUT, "x").should_retry is True
    assert ProviderError(ProviderErrorKind.RATE_LIMIT, "x").should_retry is True
    assert ProviderError(ProviderErrorKind.UNAVAILABLE, "x").should_retry is True
    assert ProviderError(ProviderErrorKind.AUTH, "x").should_retry is False
    assert ProviderError(ProviderErrorKind.INVALID_RESPONSE, "x").should_retry is False


def test_status_classification():
    assert classify_status_code(401) == ProviderErrorKind.AUTH
    assert classify_status_code(403) == ProviderErrorKind.AUTH
    assert classify_status_code(429) == ProviderErrorKind.RATE_LIMIT
    assert classify_status_code(500) == ProviderErrorKind.UNAVAILABLE
    assert classify_status_code(422) == ProviderErrorKind.INVALID_RESPONSE


def test_auth_and_invalid_never_retry():
    calls = []

    def op():
        calls.append(1)
        raise ProviderAuthError("nope")

    with pytest.raises(ProviderAuthError):
        with_bounded_retry(RetryPolicy(max_attempts=5), op)
    assert len(calls) == 1  # no retry on auth

    calls.clear()

    def op2():
        calls.append(1)
        raise ProviderInvalidResponseError("bad payload")

    with pytest.raises(ProviderInvalidResponseError):
        with_bounded_retry(RetryPolicy(max_attempts=5), op2)
    assert len(calls) == 1


def test_transient_error_retries_then_succeeds():
    calls = []

    def op():
        calls.append(1)
        if len(calls) < 3:
            raise ProviderTimeoutError("slow")
        return "ok"

    result = with_bounded_retry(
        RetryPolicy(max_attempts=5, base_backoff_seconds=0.01), op
    )
    assert result == "ok"
    assert len(calls) == 3


def test_exhausts_attempts():
    calls = []

    def op():
        calls.append(1)
        raise ProviderUnavailableError("down")

    with pytest.raises(ProviderUnavailableError):
        with_bounded_retry(
            RetryPolicy(max_attempts=3, base_backoff_seconds=0.01), op
        )
    assert len(calls) == 3


def test_rate_limit_respects_retry_after():
    policy = RetryPolicy(max_attempts=2, base_backoff_seconds=1.0, jitter=0.0)
    err = ProviderRateLimitError("limited", retry_after_seconds=9.0)
    sleep = policy.sleep_before(0, err)
    assert sleep >= 9.0
    err2 = ProviderTimeoutError("x")
    assert policy.sleep_before(0, err2) >= 1.0


def test_policy_respects_retry_on_filter():
    policy = RetryPolicy(
        max_attempts=5, retry_on=frozenset({ProviderErrorKind.TIMEOUT})
    )
    calls = []

    def op():
        calls.append(1)
        raise ProviderError(ProviderErrorKind.NETWORK, "flaky")

    with pytest.raises(ProviderError):
        with_bounded_retry(policy, op)
    assert len(calls) == 1  # network not in allowed set