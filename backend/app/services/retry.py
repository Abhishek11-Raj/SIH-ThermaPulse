"""Bounded retry and failure taxonomy for external providers.

Distinguishes transient failures (retry) from permanent failures (do not retry):

    transient network error  → retry
    timeout                  → retry
    rate limit               → retry with longer backoff, respect Retry-After
    authentication failure   → do NOT retry
    invalid response         → do NOT retry
    provider unavailable     → retry (typically DNS/connect refused)

The policy is bounded: never an uncontrolled loop.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


class ProviderErrorKind(str, Enum):
    NETWORK = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH = "authentication_failure"
    INVALID_RESPONSE = "invalid_response"
    UNAVAILABLE = "provider_unavailable"


class ProviderError(Exception):
    """A controlled provider failure with a stable classification.

    ``kind`` decides retry behavior. ``should_retry`` is derived from the kind.
    """

    def __init__(
        self,
        kind: ProviderErrorKind,
        message: str,
        retry_after_seconds: Optional[float] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after_seconds = retry_after_seconds
        self.status_code = status_code

    @property
    def should_retry(self) -> bool:
        return self.kind in {
            ProviderErrorKind.NETWORK,
            ProviderErrorKind.TIMEOUT,
            ProviderErrorKind.RATE_LIMIT,
            ProviderErrorKind.UNAVAILABLE,
        }

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "message": self.message,
            "retry_after_seconds": self.retry_after_seconds,
            "status_code": self.status_code,
            "should_retry": self.should_retry,
        }


class ProviderAuthError(ProviderError):
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(
            ProviderErrorKind.AUTH, message, status_code=status_code
        )


class ProviderRateLimitError(ProviderError):
    def __init__(
        self, message: str, retry_after_seconds: Optional[float] = None,
        status_code: int = 429,
    ) -> None:
        super().__init__(
            ProviderErrorKind.RATE_LIMIT, message,
            retry_after_seconds=retry_after_seconds, status_code=status_code,
        )


class ProviderTimeoutError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(ProviderErrorKind.TIMEOUT, message)


class ProviderInvalidResponseError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(ProviderErrorKind.INVALID_RESPONSE, message)


class ProviderUnavailableError(ProviderError):
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(
            ProviderErrorKind.UNAVAILABLE, message, status_code=status_code
        )


def classify_status_code(status_code: int, message: str = "") -> ProviderErrorKind:
    """Classify an HTTP status into the provider error taxonomy."""
    if status_code in (401, 403):
        return ProviderErrorKind.AUTH
    if status_code == 429:
        return ProviderErrorKind.RATE_LIMIT
    if 500 <= status_code <= 599 or status_code == 503:
        return ProviderErrorKind.UNAVAILABLE
    if 400 <= status_code < 500:
        return ProviderErrorKind.INVALID_RESPONSE
    return ProviderErrorKind.UNAVAILABLE


def error_for_status(status_code: int, message: str = "") -> ProviderError:
    kind = classify_status_code(status_code, message)
    return ProviderError(kind, message or f"HTTP {status_code}", status_code=status_code)


@dataclass
class RetryPolicy:
    """Bounded retry configuration (defaults tuned for demo safety)."""

    max_attempts: int = 3        # total attempts (1 initial + retries)
    base_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 8.0
    jitter: float = 0.3
    retry_on: frozenset = frozenset(
        {
            ProviderErrorKind.NETWORK,
            ProviderErrorKind.TIMEOUT,
            ProviderErrorKind.RATE_LIMIT,
            ProviderErrorKind.UNAVAILABLE,
        }
    )

    def should_retry_error(self, error: ProviderError) -> bool:
        return error.should_retry and error.kind in self.retry_on

    def sleep_before(self, attempt_index: int, error: ProviderError) -> float:
        """Backoff for the retry at ``attempt_index`` (0-based retry count)."""
        base = self.base_backoff_seconds * (2 ** attempt_index)
        base = min(base, self.max_backoff_seconds)
        if error.kind == ProviderErrorKind.RATE_LIMIT and error.retry_after_seconds:
            base = max(base, float(error.retry_after_seconds))
        if self.jitter:
            base = base * (1.0 - self.jitter + random.uniform(0, self.jitter * 2))
        return max(0.1, base)


def with_bounded_retry(
    policy: RetryPolicy,
    operation: Callable[[], T],
    on_error: Optional[Callable[[ProviderError, int], None]] = None,
) -> T:
    """Run ``operation`` with bounded retries.

    Permanent errors (auth / invalid response) raise immediately. Transient
    errors are retried up to ``max_attempts`` with backoff; the final failure
    is re-raised for the caller (ingestion layer) to handle via fallback.
    """
    last_error: Optional[ProviderError] = None
    for attempt in range(policy.max_attempts):
        try:
            return operation()
        except ProviderError as exc:
            last_error = exc
            if not policy.should_retry_error(exc):
                raise
            if attempt == policy.max_attempts - 1:
                break
            if on_error is not None:
                on_error(exc, attempt)
            time.sleep(policy.sleep_before(attempt, exc))
    raise last_error  # type: ignore[misc]  (non-None when loop exhausted)