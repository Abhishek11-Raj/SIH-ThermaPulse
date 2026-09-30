"""Schema validators: the last line of defense at API/service boundaries.

Canonical schema constructors already enforce ranges and units; these helpers
provide explicit, testable entry points and translate validation failures into
structured errors.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError


class RecordValidationError(Exception):
    """Raised when a canonical record fails schema validation."""

    def __init__(self, record_type: str, errors: Any) -> None:
        self.record_type = record_type
        self.errors = errors
        super().__init__(f"{record_type} failed validation: {errors}")


def validate_record(schema_type: type[BaseModel], values: dict) -> BaseModel:
    """Validate ``values`` against ``schema_type``; raise RecordValidationError."""
    try:
        return schema_type.model_validate(values)
    except ValidationError as exc:
        raise RecordValidationError(schema_type.__name__, exc.errors()) from exc


def validate_weather(values: dict):
    from ..schemas.weather import WeatherObservation

    return validate_record(WeatherObservation, values)


def validate_forecast(values: dict):
    from ..schemas.forecast import WeatherForecast

    return validate_record(WeatherForecast, values)


def validate_air_quality(values: dict):
    from ..schemas.air_quality import AirQualityObservation

    return validate_record(AirQualityObservation, values)