"""Canonical weather observation adapter."""
from __future__ import annotations

from typing import List, Optional

from ..providers.base import RawObservation
from ..schemas.common import SpatialReference, TemporalReference
from ..schemas.weather import WeatherObservation
from ..services.quality import assess_weather, sanitize
from .common import BaseAdapter

# Mock-provider native keys → canonical variable names.
_FIELD_MAP = {
    "temp_c": "temperature",
    "rel_hum_pct": "relative_humidity",
    "wind_mps": "wind_speed",
    "wind_dir_deg": "wind_direction",
    "pressure_hpa": "pressure",
    "rainfall_mm": "rainfall",
    "cloud_cover_pct": "cloud_cover",
    "solar_wm2": "solar_radiation",
    "visibility_km": "visibility",
    "uv_index": "uv_index",
}


class WeatherAdapter(BaseAdapter):
    """Converts provider-native weather observations to canonical schema.

    Missing values stay None (never zero). Invalid values are downgraded to
    None with the reason preserved in the quality assessment.
    """

    adapter_name = "weather.mock.v1"
    default_source = "mock"

    def to_observation(
        self,
        raw: RawObservation,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> WeatherObservation:
        values: dict = {}
        for native, canonical in _FIELD_MAP.items():
            values[canonical] = raw.fields.get(native)

        unit = raw.fields.get("temperature_unit", "C")
        assessment = assess_weather(values, raw.observed_at, temperature_unit=unit)
        safe = sanitize(values, assessment)

        source = self.source_for(raw)
        provenance = self.provenance(
            provider=raw.provider_name,
            source_timestamp=raw.observed_at,
            quality=assessment.flag,
            source=source,
        )
        provenance.quality_status = assessment.flag

        return WeatherObservation(
            observation_id=self.new_id("wxn"),
            source=source,
            provider=raw.provider_name,
            location_id=raw.location_id,
            latitude=latitude,
            longitude=longitude,
            observed_at=raw.observed_at,
            source_timestamp=raw.observed_at,
            temperature=safe.get("temperature"),
            temperature_unit=unit,
            relative_humidity=safe.get("relative_humidity"),
            wind_speed=safe.get("wind_speed"),
            wind_direction=safe.get("wind_direction"),
            pressure=safe.get("pressure"),
            rainfall=safe.get("rainfall"),
            cloud_cover=safe.get("cloud_cover"),
            solar_radiation=safe.get("solar_radiation"),
            visibility=safe.get("visibility"),
            uv_index=safe.get("uv_index"),
            quality_flag=assessment.flag,
            quality_assessment=assessment,
            spatial_resolution=SpatialReference(ref_type="point"),
            temporal_resolution=TemporalReference(ref_type="point", resolution_value=1, resolution_unit="hour"),
            provenance=provenance,
        )

    def adapt_many(
        self,
        raws: List[RawObservation],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[WeatherObservation]:
        return [self.to_observation(r, latitude, longitude) for r in raws]