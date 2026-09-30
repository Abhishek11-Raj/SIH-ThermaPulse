"""Canonical location / GIS hierarchy schema.

Supports: country → state → district → city → ward → zone/neighborhood,
plus point locations (stations/sensors). Geometries are referenced, not stored
naively, so GIS integration can be added later without schema churn.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from ..core.enums import LocationType
from .common import Provenance, SpatialReference


class GeoCoord(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class LocationBase(BaseModel):
    """Core location fields (shared by create/read schemas)."""

    location_id: str = Field(..., min_length=3, max_length=64)
    parent_location_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    type: LocationType
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    spatial: SpatialReference = Field(default_factory=SpatialReference)
    population: Optional[int] = Field(default=None, ge=0)
    area_sq_km: Optional[float] = Field(default=None, ge=0.0)
    source: str = Field(default="", description="Where the location came from")
    provenance: Optional[Provenance] = None

    @field_validator("latitude", "longitude")
    @classmethod
    def _coord_pair(cls, v: Optional[float]) -> Optional[float]:
        return v


class LocationCreate(LocationBase):
    pass


class Location(LocationBase):
    """Canonical location record exposed via the API."""

    model_config = {"from_attributes": True}

    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    last_updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())