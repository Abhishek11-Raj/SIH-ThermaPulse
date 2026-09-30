"""Provider registry endpoint — merges static configuration (data_sources)
with runtime health (provider_status) and the in-memory provider registry.

Answers operator questions: which providers exist, are they real or mock, are
they enabled, do they require an API key, is one configured, would fallback
apply? No credential values are ever exposed.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...models.operations import ProviderStatus as ProviderStatusModel
from ...models.step2 import DataSource as DataSourceModel
from ...providers import registry
from ...schemas.datasource import ProviderRegistryEntry, ProviderRegistryResponse

router = APIRouter()


@router.get(
    "/api/v1/provider-registry",
    response_model=ProviderRegistryResponse,
    tags=["system"],
)
def provider_registry(db: Session = Depends(get_db)) -> ProviderRegistryResponse:
    datasources = {
        row.name: row
        for row in db.query(DataSourceModel).all()
    }
    healths = {
        row.name: row
        for row in db.query(ProviderStatusModel).all()
    }
    configured = {
        "weather": settings.weather_provider,
        "forecast": settings.forecast_provider,
        "air_quality": settings.air_quality_provider,
    }
    providers: List[ProviderRegistryEntry] = []
    for provider in registry.providers():
        name = getattr(provider, "name", None)
        if not name:
            continue
        ds = datasources.get(name)
        h = healths.get(name)
        providers.append(
            ProviderRegistryEntry(
                name=name,
                domain=getattr(provider, "domain", "unknown"),
                provider_type=(
                    ds.provider_type if ds is not None
                    else registry.type_of(name) or "mock"
                ),
                enabled=(
                    registry.is_enabled(name)
                    and (ds.enabled if ds is not None else True)
                ),
                fallback_enabled=(
                    ds.fallback_enabled if ds is not None else True
                ),
                status=(h.status if h is not None else "UNKNOWN"),
                auth_configured=(
                    ds.auth_configured
                    if ds is not None
                    else bool(getattr(provider, "auth_configured", False))
                ),
                freshness=(h.freshness if h is not None else "UNAVAILABLE"),
                last_successful_request_at=(
                    h.last_successful_request_at if h is not None else None
                ),
                last_failure_at=(h.last_failure_at if h is not None else None),
                last_latency_ms=(h.last_latency_ms if h is not None else None),
                failure_count=(h.failure_count if h is not None else 0),
                success_count=(h.success_count if h is not None else 0),
            )
        )
    providers.sort(key=lambda p: p.name)
    satellite = None
    if "mock_satellite" in datasources:
        satellite = datasources["mock_satellite"]
    satellites: dict = {}
    if satellite is not None:
        satellites = {
            "name": satellite.name,
            "provider_type": satellite.provider_type,
            "enabled": satellite.enabled,
            "requires_api_key": satellite.requires_api_key,
            "auth_configured": satellite.auth_configured,
            "fallback_enabled": satellite.fallback_enabled,
            "description": satellite.description,
        }
    return ProviderRegistryResponse(
        mock_mode=settings.mock_mode,
        configured=configured,
        providers=providers,
        satellite=satellites,
    )