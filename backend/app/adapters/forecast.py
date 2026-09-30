"""Canonical weather forecast adapter."""
from __future__ import annotations

from typing import List, Optional

from ..providers.base import RawForecast
from ..schemas.common import SpatialReference, TemporalReference
from ..schemas.forecast import WeatherForecast
from ..services.quality import assess_forecast, sanitize
from .common import BaseAdapter

_FIELD_MAP = {
    "temp_c": "temperature",
    "rel_hum_pct": "relative_humidity",
    "wind_mps": "wind_speed",
    "pressure_hpa": "pressure",
    "rainfall_mm": "rainfall",
    "cloud_cover_pct": "cloud_cover",
    "solar_wm2": "solar_radiation",
}


class WeatherForecastAdapter(BaseAdapter):
    """Converts provider-native forecasts, preserving issued vs valid windows.

    This separation is what later powers the FORECAST TRACK RECORD: we always
    know when a forecast was issued and which period it predicted.
    """

    adapter_name = "forecast.mock.v1"
    default_source = "mock"

    def to_forecast(
        self,
        raw: RawForecast,
        index: int,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> WeatherForecast:
        valid_from, valid_to, fields = raw.periods[index]
        values: dict = {}
        for native, canonical in _FIELD_MAP.items():
            values[canonical] = fields.get(native)

        unit = fields.get("temperature_unit", "C")
        assessment = assess_forecast(values, raw.issued_at, valid_from, valid_to, temperature_unit=unit)
        safe = sanitize(values, assessment)
        horizon_hours = max(0, int((valid_to - valid_from).total_seconds() // 3600))

        source = self.source_for(raw)
        provenance = self.provenance(
            provider=raw.provider_name,
            source_timestamp=raw.issued_at,
            version=raw.model_version,
            quality=assessment.flag,
            source=source,
        )

        return WeatherForecast(
            forecast_id=self.new_id("fct"),
            source=source,
            provider=raw.provider_name,
            location_id=raw.location_id,
            latitude=latitude,
            longitude=longitude,
            issued_at=raw.issued_at,
            valid_from=valid_from,
            valid_to=valid_to,
            forecast_horizon_hours=horizon_hours,
            temperature=safe.get("temperature"),
            temperature_unit=unit,
            relative_humidity=safe.get("relative_humidity"),
            wind_speed=safe.get("wind_speed"),
            pressure=safe.get("pressure"),
            rainfall=safe.get("rainfall"),
            cloud_cover=safe.get("cloud_cover"),
            solar_radiation=safe.get("solar_radiation"),
            model_name=raw.model_name,
            model_version=raw.model_version,
            quality_flag=assessment.flag,
            quality_assessment=assessment,
            spatial_resolution=SpatialReference(ref_type="grid"),
            temporal_resolution=TemporalReference(ref_type="window", resolution_value=1, resolution_unit="hour"),
            provenance=provenance,
        )

    def adapt_many(
        self,
        raws: List[RawForecast],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[WeatherForecast]:
        out: List[WeatherForecast] = []
        for raw in raws:
            for i in range(len(raw.periods)):
                out.append(self.to_forecast(raw, i, latitude, longitude))
        return out