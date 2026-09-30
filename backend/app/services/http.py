"""Safe HTTP fetching for external providers.

Security properties:
    - SSRF-safe: the fetch target host must be in the configured allow-list
      (or the fixed provider base URL). Arbitrary user-supplied URLs are never
      fetched.
    - Timeouts on connect/read to bound request duration.
    - Bounded retries for transient failures only.
    - API keys may be sent only to the allow-listed provider host; the key
      value is never logged and never echoed in errors.
    - Response bodies are JSON only; anything else is an invalid response.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import httpx

from .retry import (
    ProviderAuthError,
    ProviderError,
    ProviderErrorKind,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RetryPolicy,
    error_for_status,
    with_bounded_retry,
)

logger = logging.getLogger("keshav.http")

DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass
class HttpResult:
    """A successful validated JSON response plus latency metadata."""

    data: Any
    status_code: int
    url: str
    latency_ms: int
    next_allow_json: bool = False


class SafeHttpClient:
    """Small JSON HTTP client with retry + SSRF guard.

    ``allowed_hosts`` restricts which hosts may be contacted. Requests for other
    hosts raise ``ProviderError`` (invalid_response) before any network I/O.
    """

    def __init__(
        self,
        allowed_hosts: set,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_policy: Optional[RetryPolicy] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.allowed_hosts = {h.lower().rstrip(".") for h in allowed_hosts}
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self._transport = transport
        self._last_retry_logged: list = []

    # -- fetch --------------------------------------------------------------
    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "apikey",
    ) -> HttpResult:
        host = urlparse(url).hostname or ""
        self._assert_allowed(host)

        def _request() -> HttpResult:
            request_headers = dict(headers or {})
            if api_key:
                # Secrets are sent only to the allow-listed provider host and
                # are never logged.
                request_headers[api_key_header] = api_key
            with self._client() as client:
                started = __import__("time").monotonic()
                try:
                    resp = client.get(
                        url, params=params, headers=request_headers
                    )
                except httpx.TimeoutException as exc:
                    raise ProviderTimeoutError(f"timeout requesting {host}") from exc
                except httpx.NetworkError as exc:
                    raise ProviderError(
                        ProviderErrorKind.NETWORK,
                        f"network error requesting {host}: {exc.__class__.__name__}",
                    ) from exc
                latency_ms = int((__import__("time").monotonic() - started) * 1000)
                if resp.status_code == 401 or resp.status_code == 403:
                    raise ProviderAuthError(
                        f"authentication failed from {host}", resp.status_code
                    )
                if resp.status_code == 429:
                    retry_after = self._retry_after(resp)
                    raise ProviderRateLimitError(
                        f"rate limited by {host}", retry_after, resp.status_code
                    )
                if resp.status_code >= 400:
                    raise error_for_status(
                        resp.status_code, f"provider {host} returned HTTP {resp.status_code}"
                    )
                content_type = (resp.headers.get("content-type") or "").lower()
                if "json" not in content_type and not resp.text.lstrip().startswith(("{", "[")):
                    raise ProviderInvalidResponseError(
                        f"provider {host} returned non-JSON content-type {content_type!r}"
                    )
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise ProviderInvalidResponseError(
                        f"provider {host} returned invalid JSON"
                    ) from exc
                if isinstance(data, dict) and "error" in data:
                    raise ProviderInvalidResponseError(
                        f"provider {host} returned error payload: {data['error']}"
                    )
                return HttpResult(
                    data=data,
                    status_code=resp.status_code,
                    url=url,
                    latency_ms=latency_ms,
                )

        try:
            return with_bounded_retry(
                self.retry_policy, _request,
                on_error=self._log_retry,
            )
        except ProviderError as exc:
            logger.warning(
                "provider request to %s failed kind=%s", host, exc.kind.value
            )
            raise

    def _client(self) -> httpx.Client:
        kwargs: Dict[str, Any] = {
            "timeout": httpx.Timeout(
                connect=self.timeout_seconds,
                read=self.timeout_seconds,
                write=self.timeout_seconds,
                pool=self.timeout_seconds,
            ),
            "follow_redirects": False,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    @staticmethod
    def _retry_after(resp: httpx.Response) -> Optional[float]:
        raw = resp.headers.get("retry-after")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    def _assert_allowed(self, host: str) -> None:
        if not host:
            raise ProviderError(
                ProviderErrorKind.INVALID_RESPONSE, "refusing request without a host"
            )
        if host.lower().rstrip(".") not in self.allowed_hosts:
            raise ProviderError(
                ProviderErrorKind.INVALID_RESPONSE,
                f"refusing outbound request to non-allow-listed host {host!r}",
            )

    def _log_retry(self, error: ProviderError, attempt: int) -> None:
        logger.info("retrying provider request attempt=%d kind=%s", attempt + 1, error.kind.value)