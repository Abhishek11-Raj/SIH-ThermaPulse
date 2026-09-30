"""Step 2 operational models: provider cache, spatial mappings and the data
source registry.

These extend (never replace) the Step 1 tables. New tables are created by
``init_db()`` (create_all) — existing tables are not altered.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class ProviderCache(Base):
    """TTL-cached provider responses with explicit freshness metadata."""

    __tablename__ = "provider_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class SpatialMapping(Base):
    """A recorded mapping from a source geometry to a KESHAV location.

    Mapping method is preserved (e.g. ``nearest_point``), along with the
    distance/resolution where applicable and a quality flag. This supports the
    rule: never pretend a point observation is ward measurement; record the
    transformation so downstream consumers can audit precision.
    """

    __tablename__ = "spatial_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mapping_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="point")  # point|grid|raster|polygon
    source_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_location_id: Mapped[str] = mapped_column(String(64), index=True)
    mapping_method: Mapped[str] = mapped_column(String(64), default="nearest_point")
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution_unit: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    quality_flag: Mapped[str] = mapped_column(String(16), default="VALID")
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DataSource(Base):
    """Registry of every data source KESHAV knows about (real + mock).

    This is intentionally separate from ``provider_status`` (which tracks runtime
    health): the registry holds static configuration/type metadata so the API can
    answer "which providers exist, are they real or mock, are they enabled, do
    they require a key, would fallback apply?" without exposing credentials.
    """

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    provider_type: Mapped[str] = mapped_column(String(16), default="mock")  # mock|real|cache
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)