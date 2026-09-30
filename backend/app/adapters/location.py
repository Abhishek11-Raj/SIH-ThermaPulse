"""Canonical location schema adapter (from provider-native GIS rows)."""
from __future__ import annotations

from typing import Dict, List

from ..providers.base import ProviderRegistry
from ..schemas.location import Location
from ..schemas.common import Provenance, SpatialReference
from .common import BaseAdapter


class LocationAdapter(BaseAdapter):
    """Maps provider-native GIS rows into canonical locations."""

    adapter_name = "gis.mock.v1"
    default_source = "mock"

    def to_location(self, row: Dict[str, object]) -> Location:
        lat = row.get("lat")
        lon = row.get("lon")
        prov = Provenance(
            source="mock",
            provider=row.get("source", "mock_gis"),
            adapter=self.adapter_name,
            quality_status="VALID",
        )
        return Location(
            location_id=row["loc_id"],  # type: ignore[index]
            parent_location_id=row.get("parent"),  # type: ignore[arg-type]
            name=row["name"],  # type: ignore[index]
            type=row["type"],  # type: ignore[index]
            latitude=lat,  # type: ignore[arg-type]
            longitude=lon,  # type: ignore[arg-type]
            spatial=SpatialReference(ref_type="polygon", geometry_reference=None),
            population=row.get("pop"),  # type: ignore[arg-type]
            area_sq_km=row.get("area"),  # type: ignore[arg-type]
            source="mock_gis",
            provenance=prov,
        )

    def adapt_all(
        self,
        rows: List[Dict[str, object]],
    ) -> List[Location]:
        return [self.to_location(r) for r in rows]

    def from_mock_gis(self, registry: ProviderRegistry) -> List[Location]:
        provider = registry.get("mock_gis")
        return self.adapt_all(provider.fetch_locations())  # type: ignore[union-attr]