"""API schemas for the Step 2 provider registry / data-source metadata.

The data-source registry is static configuration (type, enabled, auth
requirements, fallback), the provider registry merges that configuration with
runtime health. Secrets are never represented here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..core.enums import ProviderStatus


class DataSourceInfo(BaseModel):
    """Static configuration for one data source (no runtime health)."""

    name: str
    domain: str
    provider_type: str        # mock | real | cache
    enabled: bool
    requires_api_key: bool
    auth_configured: bool
    fallback_enabled: bool
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    def safe_dict(self) -> Dict[str, Any]:
        """Serialization that never leaks a key value, only presence."""
        return {
            "name": self.name,
            "domain": self.domain,
            "provider_type": self.provider_type,
            "enabled": self.enabled,
            "requires_api_key": self.requires_api_key,
            "auth_configured": self.auth_configured,
            "fallback_enabled": self.fallback_enabled,
            "description": self.description,
            "updated_at": self.updated_at,
        }


class ProviderRegistryEntry(BaseModel):
    """One provider in the extended registry (config + health)."""

    name: str
    domain: str
    provider_type: str
    enabled: bool
    fallback_enabled: bool
    status: ProviderStatus = ProviderStatus.UNKNOWN
    auth_configured: bool = False
    freshness: str = "UNAVAILABLE"
    last_successful_request_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_latency_ms: Optional[int] = None
    failure_count: int = 0
    success_count: int = 0


class ProviderRegistryResponse(BaseModel):
    """The full provider registry seen by operators (config + health)."""

    mock_mode: bool
    configured: Dict[str, str] = Field(default_factory=dict)
    providers: List[ProviderRegistryEntry] = Field(default_factory=list)
    satellite: Dict[str, Any] = Field(default_factory=dict)
    note: str = (
        "Registry metadata is configuration; runtime health is provider_status. "
        "Credentials are never exposed."
    )


class SpatialMappingSchema(BaseModel):
    mapping_id: str
    source_id: str
    source_name: Optional[str] = None
    source_type: str = "point"
    source_latitude: Optional[float] = None
    source_longitude: Optional[float] = None
    target_location_id: str
    mapping_method: str = "nearest_point"
    distance_km: Optional[float] = None
    resolution_value: Optional[float] = None
    resolution_unit: Optional[str] = None
    quality_flag: str = "VALID"
    provenance: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())