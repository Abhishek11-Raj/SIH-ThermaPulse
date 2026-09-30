"""Deterministic MOCK satellite / remote-sensing provider.

FOUNDATION ONLY — Step 2 provides the satellite interface plus this mock. There
is NO real satellite integration configured. Everything produced here is
explicitly synthetic (``provider_type="mock"``, provenance source ``mock``) and
must never be presented as a real satellite observation.

Products modelled for future use:
    land surface temperature (lst_c)
    NDVI
    land cover class
    impervious surface fraction
    water-body flag
    built-up density
    vegetation index

Acquisition metadata preserved on every record: acquisition time, spatial
resolution, product/source and cloud/quality fraction.

This provider is NOT part of the default mock registry (so Step 1 provider
counts and endpoints are unchanged). It is registered on demand via
``register_satellite_mock_providers()`` and listed in the data-source registry
as ``enabled=False`` unless explicitly enabled.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...core.enums import Scenario
from ...providers.base import RawObservation, register_provider
from ...utils.time import utcnow

LAND_COVER_CLASSES = ["built_up", "vegetation", "bare", "water", "agriculture"]


class MockSatelliteProvider:
    """Synthetic satellite cell provider (clearly marked mock)."""

    name = "mock_satellite"
    domain = "satellite"
    provider_type = "mock"
    products = ["lst", "ndvi", "land_cover", "impervious_surface",
                "water_body", "built_up_density"]
    spatial_resolution_km: Optional[float] = 1.0

    def __init__(self, scenario: Scenario = Scenario.NORMAL_DAY) -> None:
        self._scenario = scenario

    def fetch_cell(
        self,
        latitude: float,
        longitude: float,
        moment: datetime,
        **options: Any,
    ) -> RawObservation:
        seed = options.get("seed", 2026)
        key = f"{seed}|{self._scenario.value}|{latitude:.4f}|{longitude:.4f}|{moment.isoformat()}"
        rng = random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:12], 16))
        hot = self._scenario in (
            Scenario.EXTREME_HEAT, Scenario.HOT_NIGHT,
            Scenario.PERSISTENT_HEAT, Scenario.HEAT_PLUS_POLLUTION,
        )
        fields = {
            "lst_c": round(28.0 + (12.0 if hot else 4.0) + rng.uniform(-2, 2), 1),
            "ndvi": round(rng.uniform(0.05, 0.6), 3),
            "land_cover_class": rng.choice(LAND_COVER_CLASSES),
            "impervious_surface_pct": round(rng.uniform(10, 85), 1),
            "water_body_flag": int(rng.random() < 0.05),
            "built_up_density": round(rng.uniform(0.05, 0.8), 3),
            "cloud_fraction": round(rng.uniform(0.0, 0.3), 2),
            "product": "mock-lst-ndvi-v1",
            "acquisition_time": moment.isoformat(),
            "spatial_resolution_km": self.spatial_resolution_km,
        }
        return RawObservation(
            self.name,
            f"CELL:{latitude:.4f},{longitude:.4f}",
            moment,
            fields,
            source="mock",
        )

    def fetch_geometry_extent(
        self,
        location_id: str,
        moment: datetime,
        **options: Any,
    ) -> List[RawObservation]:
        # Deterministic mock "scene" covering a location's extent.
        seed = options.get("seed", 2026)
        cells = [(19.87, 75.34), (19.88, 75.34), (19.87, 75.35), (19.88, 75.35)]
        return [self.fetch_cell(lat, lon, moment, seed=seed) for lat, lon in cells]


def register_satellite_mock_providers(
    scenario: Scenario = Scenario.NORMAL_DAY,
) -> dict:
    provider = MockSatelliteProvider(scenario=scenario)
    register_provider(provider)
    return {provider.name: provider}