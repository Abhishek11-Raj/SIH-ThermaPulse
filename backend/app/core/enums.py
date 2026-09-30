"""Single source of truth for KESHAV domain enums.

These are shared by the SQLAlchemy models and the canonical Pydantic schemas so
the database, validators, mock providers and API never drift apart on the
meaning of a flag. Use structured enums everywhere — never bare strings.
"""

from __future__ import annotations

from enum import Enum


class QualityFlag(str, Enum):
    """Structured data-quality flags attached to every observation.

    MISSING means the value was absent (never converted to zero).
    IMPUTED means a later pipeline stage filled the gap — never done silently.
    """

    VALID = "VALID"
    SUSPECT = "SUSPECT"
    MISSING = "MISSING"
    STALE = "STALE"
    INVALID = "INVALID"
    IMPUTED = "IMPUTED"


class MissingState(str, Enum):
    """Distinct states for missing data. Do not collapse these."

    ``UNAVAILABLE`` = source exists but did not provide it.
    ``STALE``       = data is too old to trust.
    ``INVALID``     = value was present but rejected.
    ``IMPUTED``     = downstream stage filled it (never in Step 1).
    """

    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    INVALID = "invalid"
    IMPUTED = "imputed"


class FreshnessStatus(str, Enum):
    """Freshness of a source relative to its expected update cadence."""

    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class IngestionStatus(str, Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ProviderStatus(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class LocationType(str, Enum):
    COUNTRY = "country"
    STATE = "state"
    DISTRICT = "district"
    CITY = "city"
    WARD = "ward"
    ZONE = "zone"
    NEIGHBORHOOD = "neighborhood"
    POINT = "point"  # station / sensor site


class DataDomain(str, Enum):
    """High-level source categories. Each has its own freshness cadence."""

    WEATHER = "weather"
    WEATHER_FORECAST = "weather_forecast"
    AIR_QUALITY = "air_quality"
    GIS = "gis"
    SATELLITE = "satellite"
    HEALTH = "health"
    VULNERABILITY = "vulnerability"


class SpatialReferenceType(str, Enum):
    POINT = "point"
    RASTER_CELL = "raster_cell"
    POLYGON = "polygon"
    GRID = "grid"
    PRACTICE = "practice"  # clinical/practice area, coarsely geolocated


class TemporalResolutionUnit(str, Enum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class SpatialResolutionUnit(str, Enum):
    DEGREES = "degrees"
    KILOMETERS = "km"
    METERS = "m"


class TimeWindowType(str, Enum):
    POINT = "point"
    WINDOW = "window"


class HealthAggregationLevel(str, Enum):
    """Aggregation level of a health outcome record.

    Health data is always aggregated and de-identified; never individual.
    """

    DAILY_AREA = "daily_area"
    WEEKLY_AREA = "weekly_area"
    MONTHLY_AREA = "monthly_area"
    SEASON_AREA = "season_area"


class CoverageClass(str, Enum):
    """Equity-oriented coverage labels (foundation for coverage auditing)."""

    DATA_RICH = "DATA_RICH"
    ADEQUATE = "ADEQUATE"
    DATA_POOR = "DATA_POOR"


class Scenario(str, Enum):
    """Deterministic demo/training scenarios for mock mode."""

    NORMAL_DAY = "NORMAL_DAY"
    EXTREME_HEAT = "EXTREME_HEAT"
    HOT_NIGHT = "HOT_NIGHT"
    PERSISTENT_HEAT = "PERSISTENT_HEAT"
    HEAT_PLUS_POLLUTION = "HEAT_PLUS_POLLUTION"
    DATA_POOR_AREA = "DATA_POOR_AREA"