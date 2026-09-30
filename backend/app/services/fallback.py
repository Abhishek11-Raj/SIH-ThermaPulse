"""Provider fallback resolution: live → cache → mock.

The fallback chain is explicit and auditable:

    live source (if available)   → freshness isn't even considered
    cache (TTL window)           → marked fallback_used=True, source="cache"
    deterministic mock provider  → marked fallback_used=True, source="mock"

Never is mock or cached data presented as live. Every fallback writes its
decision back through the ingestion tracker (``fallback_used`` /
``fallback_source``) and surfaces cache freshness.

Provider resolution per domain is driven by configuration:
    WEATHER_PROVIDER, FORECAST_PROVIDER, AIR_QUALITY_PROVIDER = mock | openmeteo
In mock mode the default, the "live" step IS the mock provider — the chain then
behaves exactly as Step 1 (no cache read, no fallback records).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, List, Optional

from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.enums import DataDomain
from ..providers import ProviderRegistry
from ..providers.base import RawForecast, RawObservation
from ..utils.time import utcnow
from .cache import CacheEntry, get_cache_entry, store_cache_entry
from .retry import ProviderError

RawSet = Any  # List[RawObservation] | List[RawForecast]


@dataclass
class FallbackResult:
    raws: RawSet
    provider_name: str
    source_used: str
    fallback_used: bool
    fallback_source: Optional[str]
    cache_freshness: Optional[str]
    latency_ms: int
    live_error: Optional[str] = None

    def tracker_extra(self) -> dict:
        return {
            "fallback_used": self.fallback_used,
            "fallback_source": self.fallback_source,
            "provider": self.provider_name,
        }


def configured_primary_name(domain: str) -> str:
    """Map a domain to its configured primary provider name."""
    mapping = {
        DataDomain.WEATHER.value: settings.weather_provider,
        DataDomain.WEATHER_FORECAST.value: settings.forecast_provider,
        DataDomain.AIR_QUALITY.value: settings.air_quality_provider,
    }
    choice = mapping.get(domain, "mock")
    if choice == "openmeteo":
        if domain == DataDomain.WEATHER.value:
            return "openmeteo_weather"
        if domain == DataDomain.WEATHER_FORECAST.value:
            return "openmeteo_forecast"
        return "openmeteo_air_quality"
    if choice == "mock":
        return {
            DataDomain.WEATHER.value: "mock_weather",
            DataDomain.WEATHER_FORECAST.value: "mock_forecast",
            DataDomain.AIR_QUALITY.value: "mock_air_quality",
        }.get(domain, "mock_weather")
    return choice


def is_real_provider(domain: str) -> bool:
    choice = {
        DataDomain.WEATHER.value: settings.weather_provider,
        DataDomain.WEATHER_FORECAST.value: settings.forecast_provider,
        DataDomain.AIR_QUALITY.value: settings.air_quality_provider,
    }.get(domain, "mock")
    return choice == "openmeteo"


def fetch_with_fallback(
    db: Session,
    reg: ProviderRegistry,
    domain: str,
    location_id: str,
    fetch: Callable[[object], RawSet],
    cache_ttl_seconds: Optional[int] = None,
    cache_extra_parts: tuple = (),
) -> FallbackResult:
    """Run the live fetch; degrade to cache then mock on controlled failure.

    ``fetch`` receives a provider instance and returns provider-native raws
    (it must NOT swallow provider errors — fallback relies on ProviderError).
    """
    if not is_real_provider(domain):
        provider_name = configured_primary_name(domain)
        started = monotonic_ms()
        raws = fetch(reg.get(provider_name))
        return FallbackResult(
            raws=raws,
            provider_name=provider_name,
            source_used="live",
            fallback_used=False,
            fallback_source=None,
            cache_freshness=None,
            latency_ms=monotonic_ms() - started,
        )

    ttl = cache_ttl_seconds or (
        settings.forecast_cache_ttl_seconds
        if domain == DataDomain.WEATHER_FORECAST.value
        else settings.provider_cache_ttl_seconds
    )
    live_name = configured_primary_name(domain)
    started = monotonic_ms()
    try:
        raws = fetch(reg.get(live_name))
        store_cache_entry(
            db,
            provider=live_name,
            domain=domain,
            location_id=location_id,
            value=_raws_to_jsonable(raws),
            ttl_seconds=ttl,
            source_timestamp=utcnow(),
            *cache_extra_parts,
        )
        return FallbackResult(
            raws=raws,
            provider_name=live_name,
            source_used="live",
            fallback_used=False,
            fallback_source=None,
            cache_freshness=None,
            latency_ms=monotonic_ms() - started,
        )
    except ProviderError as exc:
        latency_ms = monotonic_ms() - started
        entry = get_cache_entry(
            db, live_name, domain, location_id, *cache_extra_parts
        )
        if entry is not None:
            return FallbackResult(
                raws=_jsonable_to_raws(entry.value),
                provider_name=live_name,
                source_used="cache",
                fallback_used=True,
                fallback_source="cache",
                cache_freshness=entry.freshness.value,
                latency_ms=latency_ms,
                live_error=exc.message,
            )
        mock_provider_name = _mock_name_for(domain)
        mock_started = monotonic_ms()
        try:
            raws = fetch(reg.get(mock_provider_name))
            return FallbackResult(
                raws=raws,
                provider_name=mock_provider_name,
                source_used="mock",
                fallback_used=True,
                fallback_source="mock",
                cache_freshness=None,
                latency_ms=(monotonic_ms() - mock_started) + latency_ms,
                live_error=exc.message,
            )
        except Exception as mock_exc:  # final isolation: report, don't crash
            raise ProviderError(
                exc.kind,
                f"live provider failed ({exc.message}) and mock fallback also failed ({mock_exc})",
            ) from mock_exc


def _mock_name_for(domain: str) -> str:
    return {
        DataDomain.WEATHER.value: "mock_weather",
        DataDomain.WEATHER_FORECAST.value: "mock_forecast",
        DataDomain.AIR_QUALITY.value: "mock_air_quality",
    }.get(domain, "mock_weather")


def _raws_to_jsonable(raws: RawSet) -> List[dict]:
    out = []
    for r in raws:
        if isinstance(r, RawForecast):
            out.append(
                {
                    "kind": "forecast",
                    "provider_name": r.provider_name,
                    "location_id": r.location_id,
                    "issued_at": r.issued_at.isoformat(),
                    "model_name": r.model_name,
                    "model_version": r.model_version,
                    "source": r.source,
                    "periods": [
                        [p[0].isoformat(), p[1].isoformat(), p[2]] for p in r.periods
                    ],
                }
            )
        else:
            out.append(
                {
                    "kind": "observation",
                    "provider_name": r.provider_name,
                    "location_id": r.location_id,
                    "observed_at": r.observed_at.isoformat(),
                    "fields": r.fields,
                    "source": r.source,
                }
            )
    return out


def _jsonable_to_raws(entries: List[dict]) -> RawSet:
    out: List[Any] = []
    for e in entries:
        if e.get("kind") == "forecast":
            periods = [
                (
                    datetime.fromisoformat(p[0]),
                    datetime.fromisoformat(p[1]),
                    p[2],
                )
                for p in e["periods"]
            ]
            out.append(
                RawForecast(
                    e["provider_name"],
                    e["location_id"],
                    datetime.fromisoformat(e["issued_at"]),
                    periods,
                    model_name=e.get("model_name"),
                    model_version=e.get("model_version"),
                    source=e.get("source") or e["provider_name"],
                )
            )
        else:
            out.append(
                RawObservation(
                    e["provider_name"],
                    e["location_id"],
                    datetime.fromisoformat(e["observed_at"]),
                    dict(e["fields"]),
                    source=e.get("source") or e["provider_name"],
                )
            )
    return out


def monotonic_ms() -> int:
    import time

    return int(time.monotonic() * 1000)