"""Canonical physical units and conversions for KESHAV.

Every value entering a canonical schema is normalized to these KESHAV units:

    temperature   → °C        (celsius)
    wind speed    → m/s
    pressure      → hPa
    precipitation → mm
    solar rad     → W/m²
    visibility    → km
    humidity      → % (0..100)
    pollutants    → µg/m³ (CO in mg/m³, as defined by the AQ schema)

Providers may send any supported unit; the normalization layer converts before
the adapter/canonical boundary and records the original unit in provenance so
the transformation is auditable. We never infer units from field names alone —
the provider must declare them (an explicit ``unit`` per value or a provider
default table).
"""

from __future__ import annotations

from typing import Dict, Optional

# Canonical units (single source of truth).
CANONICAL_UNITS: Dict[str, str] = {
    "temperature": "celsius",
    "wind_speed": "mps",
    "wind_direction": "degrees",
    "pressure": "hpa",
    "precipitation": "mm",
    "solar_radiation": "wm2",
    "visibility": "km",
    "relative_humidity": "percent",
    "uv_index": "uv_index",
    "pm25": "ugm3",
    "pm10": "ugm3",
    "o3": "ugm3",
    "no2": "ugm3",
    "so2": "ugm3",
    "co": "mgm3",
    "aqi": "aqi_index",
}

_KNOWN_TEMP = {"celsius", "c", "C", "celsius", "degc", "celsius"}
_KNOWN_WIND = {"mps", "m/s", "ms", "kmh", "km/h", "kph", "knots", "kt", "mph"}
_KNOWN_PRES = {"hpa", "pa", "kpa", "mmhg", "inhg", "atm", "mbar"}
_KNOWN_PREC = {"mm", "cm", "inch", "in", "in/day"}
_SOLAR = {"wm2", "w/m2", "w/m^2", "wm-2"}


class UnitConversionError(ValueError):
    """Raised when a requested unit conversion is unknown or impossible."""


def _norm(unit: str) -> str:
    return str(unit).strip().lower().replace(" ", "").replace("/", "")


def convert_temperature(value: float, from_unit: str) -> float:
    """Convert a temperature to canonical °C."""
    u = _norm(from_unit)
    if u in {"c", "celsius", "degc", "°c"}:
        return float(value)
    if u in {"f", "fahrenheit", "degf", "°f"}:
        return (float(value) - 32.0) * 5.0 / 9.0
    if u in {"k", "kelvin"}:
        return float(value) - 273.15
    raise UnitConversionError(f"unknown temperature unit {from_unit!r}")


def convert_wind_speed(value: float, from_unit: str) -> float:
    """Convert a wind speed to canonical m/s."""
    u = _norm(from_unit)
    if u in {"mps", "ms", "m/s"}:
        return float(value)
    if u in {"kmh", "km/h", "kph"}:
        return float(value) / 3.6
    if u in {"mph"}:
        return float(value) * 0.44704
    if u in {"knots", "kt", "kn"}:
        return float(value) * 0.514444
    raise UnitConversionError(f"unknown wind-speed unit {from_unit!r}")


def convert_pressure(value: float, from_unit: str) -> float:
    """Convert a pressure to canonical hPa."""
    u = _norm(from_unit)
    if u in {"hpa", "mbar", "millibar"}:
        return float(value)
    if u in {"pa"}:
        return float(value) / 100.0
    if u in {"kpa"}:
        return float(value) * 10.0
    if u in {"mmhg", "torr"}:
        return float(value) * 1.333224
    if u in {"inhg"}:
        return float(value) * 33.8639
    if u in {"atm"}:
        return float(value) * 1013.25
    raise UnitConversionError(f"unknown pressure unit {from_unit!r}")


def convert_precipitation(value: float, from_unit: str) -> float:
    """Convert precipitation to canonical mm."""
    u = _norm(from_unit)
    if u in {"mm"}:
        return float(value)
    if u in {"cm"}:
        return float(value) * 10.0
    if u in {"inch", "in"}:
        return float(value) * 25.4
    raise UnitConversionError(f"unknown precipitation unit {from_unit!r}")


def convert_co_from_ugm3(value: float) -> float:
    """Open-Meteo gives CO in µg/m³; KESHAV canonical CO is mg/m³."""
    return float(value) / 1000.0


def convert_pollutant_ugm3(value: float) -> float:
    """Pollutants are canonical in µg/m³; pass-through for auditable clarity."""
    return float(value)


def convert_named(variable: str, value: float, from_unit: Optional[str]) -> float:
    """Route a value to KESHAV canonical units by variable name.

    ``from_unit`` is required except for variables that are inherently canonical
    (per the provider's contract). Never silently guess.
    """
    if value is None:
        return None  # type: ignore[return-value]
    canonical_for = {
        "temperature": convert_temperature,
        "wind_speed": convert_wind_speed,
        "pressure": convert_pressure,
        "precipitation": convert_precipitation,
        "rainfall": convert_precipitation,
    }
    converter = canonical_for.get(variable)
    if converter is None:
        return float(value)
    if from_unit is None:
        raise UnitConversionError(
            f"{variable} needs an explicit unit for conversion; none provided"
        )
    return converter(value, from_unit)