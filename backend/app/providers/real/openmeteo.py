"""Real Open-Meteo providers (weather / forecast / air quality).

Production intent: when ``WEATHER_PROVIDER=openmeteo`` (etc.) KESHAV fetches
live data. Open-Meteo exposes a public JSON API requiring no key; base URL is
configurable. Every request:

    - goes through SafeHttpClient (allow-listed host, timeouts, bounded retry,
      SSRF guard, redacted secrets)
    - validates the raw payload BEFORE any conversion
    - is clearly labeled ``provider_type="real"`` and ``source="openmeteo"`` —
      fallback/cache/mock provenance is recorded separately at the ingestion
      layer, never mixed in here.

Unit conventions used on the wire (matches KESHAV canonicals): degrees C,
windspeed in m/s, precipitation in mm, pressure in hPa, and AQ in µg/m³
(CO is converted to mg/m³ only at the adapter boundary).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ...core.config import settings
from ...providers.base import (
    AirQualityProvider,
    RawForecast,
    RawObservation,
    WeatherForecastProvider,
    WeatherObservationProvider,
)
from ...services.http import SafeHttpClient
from ...services.retry import RetryPolicy
from ...services.validation import validate_hourly_time_series
from ...utils.time import to_utc

OPEN_METEO_HOURLY_PARAMS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "pressure_msl",
    "precipitation",
    "cloud_cover",
    "shortwave_radiation",
    "visibility",
    "uv_index",
]

# native open-meteo key → KESHAV canonical
WEATHER_FIELD_MAP = {
    "temperature_2m": "temp_c",
    "relative_humidity_2m": "rel_hum_pct",
    "wind_speed_10m": "wind_mps",
    "wind_direction_10m": "wind_dir_deg",
    "pressure_msl": "pressure_hpa",
    "precipitation": "rainfall_mm",
    "cloud_cover": "cloud_cover_pct",
    "shortwave_radiation": "solar_wm2",
    "visibility": "visibility_km",
    "uv_index": "uv_index",
}


def _coerce(latitude: float, longitude: float) -> tuple:
    return float(latitude), float(longitude)


class BaseOpenMeteoProvider:
    provider_type = "real"
    source_label = "openmeteo"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        retry_policy: Optional[RetryPolicy] = None,
        transport: Any = None,
    ) -> None:
        self.base_url = (base_url or settings.open_meteo_base_url).rstrip("/")
        host = self.base_url.split("//")[-1].split("/")[0]
        self.client = SafeHttpClient(
            allowed_hosts={host},
            timeout_seconds=timeout_seconds or settings.provider_timeout_seconds,
            retry_policy=retry_policy
            or RetryPolicy(
                max_attempts=settings.provider_max_attempts,
                base_backoff_seconds=settings.provider_base_backoff_seconds,
            ),
            transport=transport,
        )

    def _hourly_unit_adjustments(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Apply wire-level unit fixes (visibility is meters; canonical is km)."""
        vis = fields.get("visibility_km")
        if isinstance(vis, (int, float)):
            fields["visibility_km"] = round(vis / 1000.0, 3)
        return fields


class OpenMeteoWeatherProvider(BaseOpenMeteoProvider, WeatherObservationProvider):
    name = "openmeteo_weather"
    domain = "weather"
    enabled = True

    def fetch_observations(
        self,
        location_id: str,
        start: datetime,
        end: datetime,
        **options: Any,
    ) -> List[RawObservation]:
        latitude = options.get("latitude")
        longitude = options.get("longitude")
        if latitude is None or longitude is None:
            raise ValueError("openmeteo weather requires latitude/longitude in options")
        lat, lon = _coerce(latitude, longitude)
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(OPEN_METEO_HOURLY_PARAMS),
            "start_date": to_utc(start).date().isoformat(),
            "end_date": to_utc(end).date().isoformat(),
            "timezone": "UTC",
            "temperature_unit": "celsius",
            "windspeed_unit": "ms",
            "precipitation_unit": "mm",
        }
        result = self.client.get_json(f"{self.base_url}/forecast", params=params)
        validate_hourly_time_series(result.data, location_id, self.name, "weather")
        return self._to_observations(result.data, location_id)

    def _to_observations(
        self, payload: Dict[str, Any], location_id: str
    ) -> List[RawObservation]:
        hourly = payload["hourly"]
        times = hourly["time"]
        out: List[RawObservation] = []
        for idx, t in enumerate(times):
            fields: Dict[str, Any] = {}
            for native, canonical in WEATHER_FIELD_MAP.items():
                if native in hourly:
                    fields[canonical] = hourly[native][idx] if idx < len(hourly[native]) else None
            fields["temperature_unit"] = "C"
            fields = self._hourly_unit_adjustments(fields)
            observed_at = datetime.fromisoformat(t.replace("Z", "+00:00"))
            out.append(
                RawObservation(
                    self.name, location_id, observed_at, fields, source=self.source_label
                )
            )
        return out


class OpenMeteoForecastProvider(BaseOpenMeteoProvider, WeatherForecastProvider):
    name = "openmeteo_forecast"
    domain = "weather_forecast"
    enabled = True
    model_name = "Open-Meteo"

    def fetch_forecast(
        self,
        location_id: str,
        issued_at: datetime,
        horizon_hours: int = 120,
        **options: Any,
    ) -> List[RawForecast]:
        latitude = options.get("latitude")
        longitude = options.get("longitude")
        if latitude is None or longitude is None:
            raise ValueError("openmeteo forecast requires latitude/longitude in options")
        lat, lon = _coerce(latitude, longitude)
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(OPEN_METEO_HOURLY_PARAMS),
            "forecast_days": max(1, (horizon_hours + 23) // 24),
            "timezone": "UTC",
            "temperature_unit": "celsius",
            "windspeed_unit": "ms",
            "precipitation_unit": "mm",
        }
        result = self.client.get_json(f"{self.base_url}/forecast", params=params)
        validate_hourly_time_series(result.data, location_id, self.name, "weather_forecast")
        hourly = result.data["hourly"]
        times = hourly["time"]
        issued = to_utc(issued_at)
        periods: List[tuple] = []
        for idx, t in enumerate(times):
            valid_from = datetime.fromisoformat(t.replace("Z", "+00:00"))
            fields: Dict[str, Any] = {}
            for native, canonical in WEATHER_FIELD_MAP.items():
                if native in hourly:
                    fields[canonical] = hourly[native][idx] if idx < len(hourly[native]) else None
            fields["temperature_unit"] = "C"
            fields = self._hourly_unit_adjustments(fields)
            periods.append((valid_from, valid_from + timedelta(hours=1), fields))
            if len(periods) >= horizon_hours:
                break
        return [
            RawForecast(
                self.name,
                location_id,
                issued,
                periods,
                model_name=self.model_name,
                source=self.source_label,
            )
        ]


class OpenMeteoAirQualityProvider(BaseOpenMeteoProvider, AirQualityProvider):
    name = "openmeteo_air_quality"
    domain = "air_quality"
    enabled = True

    AQ_FIELD_MAP = {
        "pm10": "pm10_ugm3",
        "pm2_5": "pm25_ugm3",
        "ozone": "o3_ugm3",
        "nitrogen_dioxide": "no2_ugm3",
        "sulphur_dioxide": "so2_ugm3",
        "carbon_monoxide": "co_mgm3",
    }

    def fetch_observations(
        self,
        location_id: str,
        start: datetime,
        end: datetime,
        **options: Any,
    ) -> List[RawObservation]:
        latitude = options.get("latitude")
        longitude = options.get("longitude")
        if latitude is None or longitude is None:
            raise ValueError("openmeteo air quality requires latitude/longitude in options")
        lat, lon = _coerce(latitude, longitude)
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(self.AQ_FIELD_MAP.keys()) + ",us_aqi,european_aqi",
            "start_date": to_utc(start).date().isoformat(),
            "end_date": to_utc(end).date().isoformat(),
            "timezone": "UTC",
        }
        result = self.client.get_json(f"{self.base_url}/air-quality", params=params)
        validate_hourly_time_series(result.data, location_id, self.name, "air_quality")
        return self._to_observations(result.data, location_id)

    def _to_observations(
        self, payload: Dict[str, Any], location_id: str
    ) -> List[RawObservation]:
        hourly = payload["hourly"]
        times = hourly["time"]
        out: List[RawObservation] = []
        for idx, t in enumerate(times):
            fields: Dict[str, Any] = {}
            for native, canonical in self.AQ_FIELD_MAP.items():
                if native in hourly:
                    raw_value = hourly[native][idx] if idx < len(hourly[native]) else None
                    if native == "carbon_monoxide" and isinstance(raw_value, (int, float)):
                        # Open-Meteo sends CO in µg/m³; canonical is mg/m³.
                        raw_value = round(raw_value / 1000.0, 3)
                    fields[canonical] = raw_value
            aqi = (
                hourly["us_aqi"][idx]
                if "us_aqi" in hourly and hourly.get("us_aqi") and idx < len(hourly["us_aqi"])
                else (hourly["european_aqi"][idx] if "european_aqi" in hourly and hourly.get("european_aqi") else None)
            )
            fields["aqi_index"] = aqi
            observed_at = datetime.fromisoformat(t.replace("Z", "+00:00"))
            out.append(
                RawObservation(
                    self.name, location_id, observed_at, fields, source=self.source_label
                )
            )
        return out