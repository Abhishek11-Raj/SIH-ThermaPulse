"""Raw provider-response validation.

Runs BEFORE any canonical conversion. The goal: invalid external payloads must
not reach the canonical database; the failure must be recorded instead.

Checks implemented here operate on provider-native payloads (dictionaries).
Validating canonical schemas happens later in the adapters (services.quality).

Rationale for separating the two: a provider may be "structurally valid HTTP"
yet not match KESHAV's expectations (wrong variable names, naive timestamps,
implausible units). That must be caught here with a provider-scoped error.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..services.retry import ProviderInvalidResponseError

# Structural requirements per domain (variable → expected value type).
_REQUIRED_TYPES: Dict[str, Dict[str, type]] = {
    "weather": {"temperature_2m": (int, float), "time": str},
    "air_quality": {"time": str},
}


class RawPayloadIssue(Exception):
    """A concrete validation problem in a raw provider payload."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


class RawValidationResult:
    """Aggregated outcome of raw payload validation."""

    def __init__(self) -> None:
        self.errors: List[RawPayloadIssue] = []
        self.warnings: List[RawPayloadIssue] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(RawPayloadIssue(path, message))

    def warn(self, path: str, message: str) -> None:
        self.warnings.append(RawPayloadIssue(path, message))

    @property
    def valid(self) -> bool:
        return not self.errors

    def raise_if_invalid(self, provider: str) -> None:
        if self.errors:
            detail = "; ".join(f"{e.path}: {e.message}" for e in self.errors[:5])
            raise ProviderInvalidResponseError(
                f"{provider} returned an invalid payload: {detail}"
            )


def validate_hourly_time_series(
    payload: Dict[str, Any],
    location_id: str,
    provider: str,
    domain: str,
) -> RawValidationResult:
    """Validate the common ``hourly`` time-series shape used by real providers.

    Ensures:
      - top-level ``latitude``/``longitude`` are numeric (location info)
      - ``hourly`` is a dict with a ``time`` list of valid ISO timestamps
      - every hourly variable list has the same length as ``time``
      - all variable values are numeric or None (never strings when numbers expected)
    """
    result = RawValidationResult()

    try:
        lat = payload.get("latitude")
        lon = payload.get("longitude")
    except AttributeError:
        lat = lon = None
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        result.error("latitude/longitude", "missing numeric coordinates")
    if not (-90.0 <= float(lat) <= 90.0 if isinstance(lat, (int, float)) else False):
        result.error("latitude", "outside [-90, 90]")
    if not (-180.0 <= float(lon) <= 180.0 if isinstance(lon, (int, float)) else False):
        result.error("longitude", "outside [-180, 180]")

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        result.error("hourly", "missing 'hourly' series object")
        result.raise_if_invalid(provider)
        return result

    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        result.error("hourly.time", "missing or empty time array")
    else:
        parsed = []
        seen = set()
        for idx, t in enumerate(times):
            if not isinstance(t, str):
                result.error(f"hourly.time[{idx}]", "not a string timestamp")
                continue
            try:
                dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
            except ValueError:
                result.error(f"hourly.time[{idx}]", f"invalid ISO timestamp {t!r}")
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone_utc())
            parsed.append(dt)
            # Duplicate timestamps are invalid for a time series.
            if dt.isoformat() in seen:
                result.error(f"hourly.time[{idx}]", "duplicate timestamp in series")
            seen.add(dt.isoformat())
        if parsed:
            if parsed != sorted(parsed):
                result.warn("hourly.time", "timestamps not strictly sorted (will be re-order-safe)")

    for key, series in hourly.items():
        if key == "time":
            continue
        if not isinstance(series, list):
            result.error(f"hourly.{key}", "variable is not a list")
            continue
        len_ok = isinstance(times, list) and len(series) == len(times)
        if not len_ok:
            result.error(
                f"hourly.{key}",
                f"length {len(series)} != time length {len(times) if isinstance(times, list) else '?'}",
            )
        for idx, value in enumerate(series):
            if value is None:
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                result.error(f"hourly.{key}[{idx}]", "non-numeric value in series")
    result.warn("coverage.location", f"location {location_id!r} mapped by coordinates")
    result.raise_if_invalid(provider)
    return result


def timezone_utc():
    from datetime import timezone

    return timezone.utc


def ensure_numeric(value: Any, path: str, result: RawValidationResult) -> Optional[float]:
    """Require a numeric (or null) value; returns float or None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        result.error(path, f"expected numeric, got {type(value).__name__}")
        return None
    return float(value)