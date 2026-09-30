"""Provider abstraction layer.

Principle:  PROVIDER → ADAPTER → CANONICAL DATA MODEL

A *provider* owns the external/system-specific details of fetching data
(IMD, Open-Meteo, satellites, municipal AQ networks, health surveillance...).
An *adapter* converts provider-native records into canonical KESHAV schemas.

Downstream modules consume only canonical schemas. Adding a new government or
satellite source must never force a rewrite of the rest of the application.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..core.enums import (
    DataDomain,
    FreshnessStatus,
    ProviderStatus,
    Scenario,
)

# ---------------------------------------------------------------------------
# Raw (provider-native) record shapes
# ---------------------------------------------------------------------------


class RawObservation:
    """Base container for provider-native observation payloads.

    ``fields`` holds provider-specific keys (e.g. ``{"temp_c": 32}``); the
    adapter decides how they map to canonical variables. Never passed
    downstream beyond the adapter boundary. ``source`` names the origin system
    (e.g. ``mock`` or ``openmeteo``); providers that do not set it fall back to
    the adapter default.
    """

    def __init__(
        self,
        provider_name: str,
        location_id: str,
        observed_at: datetime,
        fields: Dict[str, Any],
        source: Optional[str] = None,
    ) -> None:
        self.provider_name = provider_name
        self.location_id = location_id
        self.observed_at = observed_at
        self.fields = fields
        self.source = source or provider_name


class RawForecast:
    """Provider-native forecast payload (one or more validity windows)."""

    def __init__(
        self,
        provider_name: str,
        location_id: str,
        issued_at: datetime,
        # List of (valid_from, valid_to, fields)
        periods: List[Tuple[datetime, datetime, Dict[str, Any]]],
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        self.provider_name = provider_name
        self.location_id = location_id
        self.issued_at = issued_at
        self.periods = periods
        self.model_name = model_name
        self.model_version = model_version
        self.source = source or provider_name


# ---------------------------------------------------------------------------
# Provider interfaces (Protocol). Each future source implements one or more.
# ---------------------------------------------------------------------------


class WeatherObservationProvider:
    """Interface: sources of measured weather observations."""

    name: str
    domain: str = DataDomain.WEATHER.value

    def fetch_observations(
        self,
        location_id: str,
        start: datetime,
        end: datetime,
        **options: Any,
    ) -> List[RawObservation]:
        raise NotImplementedError


class WeatherForecastProvider:
    """Interface: sources of weather forecasts (kept distinct from obs)."""

    name: str
    domain: str = DataDomain.WEATHER_FORECAST.value

    def fetch_forecast(
        self,
        location_id: str,
        issued_at: datetime,
        horizon_hours: int = 120,
        **options: Any,
    ) -> List[RawForecast]:
        raise NotImplementedError


class AirQualityProvider:
    """Interface: sources of air-quality observations."""

    name: str
    domain: str = DataDomain.AIR_QUALITY.value

    def fetch_observations(
        self,
        location_id: str,
        start: datetime,
        end: datetime,
        **options: Any,
    ) -> List[RawObservation]:
        raise NotImplementedError


class GeoSpatialProvider:
    """Interface: GIS / administrative-geometry sources."""

    name: str
    domain: str = DataDomain.GIS.value

    def fetch_locations(self, **options: Any) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def fetch_geometry(self, location_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class SatelliteProvider:
    """Interface: satellite / raster environmental products.

    Future variables: land surface temperature, NDVI, land cover, impervious
    surface, vegetation, water bodies, built-up density. No real satellite
    source is configured in Step 2 — only this interface and a clearly-marked
    deterministic mock are provided. Acquisition metadata (time, resolution,
    product, cloud/quality) must be preserved on every record.
    """

    name: str
    domain: str = DataDomain.SATELLITE.value
    products: List[str] = []

    def fetch_cell(
        self,
        latitude: float,
        longitude: float,
        moment: datetime,
        **options: Any,
    ) -> RawObservation:
        raise NotImplementedError

    def fetch_geometry_extent(
        self,
        location_id: str,
        moment: datetime,
        **options: Any,
    ) -> List[RawObservation]:
        raise NotImplementedError


class HealthOutcomeProvider:
    """Interface: aggregated, de-identified health-outcome sources."""

    name: str
    domain: str = DataDomain.HEALTH.value

    def fetch_outcomes(
        self,
        location_id: str,
        period_start: datetime,
        period_end: datetime,
        **options: Any,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError


class VulnerabilityProvider:
    """Interface: vulnerability / demographic data sources (nullable fields)."""

    name: str
    domain: str = DataDomain.VULNERABILITY.value

    def fetch_vulnerability(
        self,
        location_id: str,
        reference_date: datetime,
        **options: Any,
    ) -> Dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Provider registry and health
# ---------------------------------------------------------------------------


class ProviderHealthState:
    """Observable health of one provider. NEVER exposes credentials."""

    def __init__(
        self,
        provider_name: str,
        domain: str,
        provider_type: str = "mock",
        enabled: bool = True,
    ) -> None:
        self.name = provider_name
        self.domain = domain
        self.provider_type = provider_type
        self.enabled = enabled
        self.status: ProviderStatus = ProviderStatus.UNKNOWN
        self.last_success_at: Optional[datetime] = None
        self.last_failure_at: Optional[datetime] = None
        self.last_latency_ms: Optional[int] = None
        self.auth_configured: bool = False
        self.failures = 0
        self.successes = 0
        self.freshness: FreshnessStatus = FreshnessStatus.UNAVAILABLE

    def record_success(self, latency_ms: int) -> None:
        from ..utils.time import utcnow

        self.status = ProviderStatus.ONLINE
        self.last_success_at = utcnow()
        self.last_latency_ms = latency_ms
        self.successes += 1

    def record_failure(self, message: str) -> None:
        from ..utils.time import utcnow

        self.status = ProviderStatus.OFFLINE
        self.last_failure_at = utcnow()
        self.failures += 1

    def public_view(self) -> Dict[str, Any]:
        """Domain-agnostic, secret-free health record."""
        return {
            "name": self.name,
            "domain": self.domain,
            "provider_type": self.provider_type,
            "enabled": self.enabled,
            "status": self.status.value,
            "last_successful_request_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
            "last_latency_ms": self.last_latency_ms,
            "auth_configured": self.auth_configured,
            "freshness": self.freshness.value,
            "failure_count": self.failures,
            "success_count": self.successes,
        }


class ProviderRegistry:
    """Central registry of provider instances for all domains."""

    def __init__(self) -> None:
        self._providers: Dict[str, object] = {}
        self._health: Dict[str, ProviderHealthState] = {}
        self._types: Dict[str, str] = {}
        self._enabled: Dict[str, bool] = {}

    def register(self, provider: object) -> None:
        self._providers[provider.name] = provider  # type: ignore[attr-defined]
        ptype = getattr(provider, "provider_type", "mock")
        enabled = getattr(provider, "enabled", True)
        self._types[provider.name] = ptype  # type: ignore[attr-defined]
        self._enabled[provider.name] = enabled  # type: ignore[attr-defined]
        self._health[provider.name] = ProviderHealthState(  # type: ignore[index]
            provider.name, getattr(provider, "domain", "unknown"), ptype, enabled  # type: ignore[attr-defined]
        )

    def get(self, name: str) -> object:
        return self._providers[name]

    def __getitem__(self, name: str) -> object:
        return self._providers[name]

    def providers(self) -> List[object]:
        return list(self._providers.values())

    def by_domain(self, domain: DataDomain) -> List[object]:
        return [p for p in self._providers.values() if getattr(p, "domain", None) == domain.value]

    def type_of(self, name: str) -> Optional[str]:
        return self._types.get(name)

    def is_enabled(self, name: str) -> bool:
        return self._enabled.get(name, True)

    def health(self, name: str) -> ProviderHealthState:
        return self._health.setdefault(
            name, ProviderHealthState(name, "unknown")
        )

    def health_snapshot(self) -> List[Dict[str, Any]]:
        return [h.public_view() for h in self._health.values()]


registry = ProviderRegistry()


def register_provider(provider: object) -> object:
    """Convenience: register a provider and return it."""
    registry.register(provider)
    return provider


# Scenario control for mock providers (default demo mode).
_active_scenario: Scenario = Scenario.NORMAL_DAY
_active_seed: int = 2026


def set_scenario(scenario: Scenario) -> None:
    global _active_scenario
    _active_scenario = scenario


def active_scenario() -> Scenario:
    return _active_scenario


def set_mock_seed(seed: int) -> None:
    global _active_seed
    _active_seed = seed


def mock_seed() -> int:
    return _active_seed