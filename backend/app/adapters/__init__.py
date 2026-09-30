"""Adapters: map provider-native records to canonical KESHAV schemas.

An adapter may call validators, attach provenance and record data-quality
assessments — but never loses the source timeline during transformation.
"""

from .air_quality import AirQualityAdapter
from .common import BaseAdapter
from .forecast import WeatherForecastAdapter
from .health import HealthOutcomeAdapter
from .location import LocationAdapter
from .vulnerability import VulnerabilityAdapter
from .weather import WeatherAdapter

__all__ = [
    "BaseAdapter",
    "WeatherAdapter",
    "WeatherForecastAdapter",
    "AirQualityAdapter",
    "LocationAdapter",
    "VulnerabilityAdapter",
    "HealthOutcomeAdapter",
]