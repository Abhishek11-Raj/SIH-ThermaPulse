"""Canonical air-quality observation adapter."""
from __future__ import annotations

from typing import List, Optional

from ..providers.base import RawObservation
from ..schemas.air_quality import AirQualityObservation
from ..schemas.common import SpatialReference, TemporalReference
from ..services.quality import assess_air_quality, sanitize
from .common import BaseAdapter

_FIELD_MAP = {
    "pm25_ugm3": "pm25",
    "pm10_ugm3": "pm10",
    "o3_ugm3": "o3",
    "no2_ugm3": "no2",
    "so2_ugm3": "so2",
    "co_mgm3": "co",
    "aqi_index": "aqi",
}


class AirQualityAdapter(BaseAdapter):
    """Converts provider-native AQ observations.

    Missing pollutants remain None even if the provider omitted them; a missing
    PM10 is never stored as 0.
    """

    adapter_name = "air_quality.mock.v1"
    default_source = "mock"

    def to_observation(
        self,
        raw: RawObservation,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> AirQualityObservation:
        values: dict = {}
        for native, canonical in _FIELD_MAP.items():
            values[canonical] = raw.fields.get(native) if raw.fields.get(native) is not None else None

        assessment = assess_air_quality(values, raw.observed_at)
        safe = sanitize(values, assessment)
        source = self.source_for(raw)
        provenance = self.provenance(
            provider=raw.provider_name,
            source_timestamp=raw.observed_at,
            quality=assessment.flag,
            source=source,
        )

        return AirQualityObservation(
            observation_id=self.new_id("aq"),
            source=source,
            provider=raw.provider_name,
            location_id=raw.location_id,
            latitude=latitude,
            longitude=longitude,
            observed_at=raw.observed_at,
            source_timestamp=raw.observed_at,
            pm25=safe.get("pm25"),
            pm10=safe.get("pm10"),
            o3=safe.get("o3"),
            no2=safe.get("no2"),
            so2=safe.get("so2"),
            co=safe.get("co"),
            aqi=safe.get("aqi"),
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
    ) -> List[AirQualityObservation]:
        return [self.to_observation(r, latitude, longitude) for r in raws]