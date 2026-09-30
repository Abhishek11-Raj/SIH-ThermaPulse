"""Step 2 unit tests: canonical units and conversions."""

from __future__ import annotations

import pytest

from app.core.units import (
    CANONICAL_UNITS,
    UnitConversionError,
    convert_co_from_ugm3,
    convert_named,
    convert_pollutant_ugm3,
    convert_precipitation,
    convert_pressure,
    convert_temperature,
    convert_wind_speed,
)


def test_canonical_units_are_stable():
    assert CANONICAL_UNITS["temperature"] == "celsius"
    assert CANONICAL_UNITS["wind_speed"] == "mps"
    assert CANONICAL_UNITS["pressure"] == "hpa"
    assert CANONICAL_UNITS["precipitation"] == "mm"
    assert CANONICAL_UNITS["co"] == "mgm3"


def test_temperature_conversions():
    assert convert_temperature(25.0, "C") == 25.0
    assert convert_temperature(77.0, "F") == pytest.approx(25.0, abs=1e-6)
    assert convert_temperature(298.15, "K") == pytest.approx(25.0, abs=1e-6)


def test_wind_speed_conversions():
    assert convert_wind_speed(10.0, "m/s") == 10.0
    assert convert_wind_speed(36.0, "km/h") == pytest.approx(10.0)
    assert convert_wind_speed(19.44, "knots") == pytest.approx(10.0, abs=0.01)


def test_pressure_conversions():
    assert convert_pressure(1013.0, "hPa") == 1013.0
    assert convert_pressure(101300.0, "Pa") == pytest.approx(1013.0)
    assert convert_pressure(29.92, "inHg") == pytest.approx(1013.2, abs=0.5)


def test_precipitation_conversions():
    assert convert_precipitation(10.0, "mm") == 10.0
    assert convert_precipitation(10.0, "cm") == 100.0
    assert convert_precipitation(1.0, "inch") == pytest.approx(25.4)


def test_co_conversion():
    # Open-Meteo sends CO in µg/m³; canonical is mg/m³.
    assert convert_co_from_ugm3(1000.0) == 1.0
    assert convert_pollutant_ugm3(40.0) == 40.0  # pass-through for other pollutants


def test_convert_named_dispatch():
    assert convert_named("temperature", 20.0, "C") == 20.0
    assert convert_named("wind_speed", 5.0, "m/s") == 5.0
    assert convert_named("pressure", 1000.0, "hPa") == 1000.0
    assert convert_named("precipitation", 2.0, "mm") == 2.0
    assert convert_named("aqi", 61, None) == 61.0  # inherently canonical


def test_convert_named_rejects_unknown_unit():
    with pytest.raises(UnitConversionError):
        convert_named("temperature", 20.0, "furlongs")


def test_convert_named_requires_explicit_unit():
    # No implicit assumption about ambiguous native units.
    with pytest.raises(UnitConversionError):
        convert_named("temperature", 20.0, None)


def test_conversion_unknown_unit_raises():
    with pytest.raises(UnitConversionError):
        convert_pressure(10.0, "barleycorns")