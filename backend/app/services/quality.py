"""Data-quality layer.

Every ingested record is evaluated for: missing values, implausible ranges,
impossible timestamps, stale data, unit mismatch and schema validity. Bad data
is flagged — never silently discarded and never silently "fixed".

Flags: VALID | SUSPECT | MISSING | STALE | INVALID | IMPUTED
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from ..core.enums import FreshnessStatus, QualityFlag
from ..schemas.common import QualityAssessment, QualityIssue

EARLIEST_PLAUSIBLE = datetime(1950, 1, 1, tzinfo=timezone.utc)

# Domain-specific bounds used by the assessment (kept with the schemas' ideals).
WEATHER_RANGES: Dict[str, tuple] = {
    "temperature": (-90.0, 60.0),
    "relative_humidity": (0.0, 100.0),
    "wind_speed": (0.0, 150.0),
    "wind_direction": (0.0, 360.0),
    "pressure": (800.0, 1100.0),
    "rainfall": (0.0, 1000.0),
    "cloud_cover": (0.0, 100.0),
    "solar_radiation": (0.0, 1500.0),
    "visibility": (0.0, 100.0),
    "uv_index": (0.0, 20.0),
}

AQ_RANGES: Dict[str, tuple] = {
    "pm25": (0.0, 2000.0),
    "pm10": (0.0, 5000.0),
    "o3": (0.0, 1000.0),
    "no2": (0.0, 2000.0),
    "so2": (0.0, 2000.0),
    "co": (0.0, 200.0),
    "aqi": (0.0, 1000.0),
}

# Variables whose absence is a missingness concern (not a friendly zero).
EXPECTED_WEATHER = [
    "temperature", "relative_humidity", "wind_speed", "pressure",
    "cloud_cover", "solar_radiation",
]
EXPECTED_AQ = ["pm25", "o3", "no2", "so2", "co"]


def _flag_issues(
    assessment: QualityAssessment, severity: QualityFlag, variable: str, code: str, message: str
) -> None:
    assessment.issues.append(QualityIssue(code=code, variable=variable, severity=severity, message=message))


def assess_weather(
    values: Dict[str, float | None], observed_at: datetime,
    temperature_unit: str = "C", allowed_future_minutes: int = 30,
) -> QualityAssessment:
    """Assess a provisional weather record. Never raises; always flags."""
    a = QualityAssessment(flag=QualityFlag.VALID)
    now = datetime.now(timezone.utc)
    obs = observed_at
    if obs.tzinfo is None:
        obs = obs.replace(tzinfo=timezone.utc)

    for var in EXPECTED_WEATHER:
        if values.get(var) is None:
            a.missing_variables.append(var)
            _flag_issues(a, QualityFlag.MISSING, var, "missing_value", f"{var} missing (kept null, not zeroed)")

    for var, (lo, hi) in WEATHER_RANGES.items():
        v = values.get(var)
        if v is None:
            continue
        if not (lo <= v <= hi):
            _flag_issues(a, QualityFlag.INVALID, var, "out_of_range",
                         f"{var}={v} outside plausible range [{lo}, {hi}]")

    if temperature_unit not in {"C", "F", "K"}:
        _flag_issues(a, QualityFlag.INVALID, "temperature_unit", "unit_mismatch",
                     f"unknown unit {temperature_unit!r}")

    if obs < EARLIEST_PLAUSIBLE:
        _flag_issues(a, QualityFlag.INVALID, "observed_at", "impossible_timestamp", "observed_at before 1950")
    if obs > now.replace(tzinfo=timezone.utc) and (obs - now).total_seconds() > allowed_future_minutes * 60:
        _flag_issues(a, QualityFlag.INVALID, "observed_at", "future_timestamp", "observed_at in the future beyond grace")

    a.flag = _merge_flag(a)
    return a


def assess_forecast(
    values: Dict[str, float | None],
    issued_at: datetime, valid_from: datetime, valid_to: datetime,
    temperature_unit: str = "C",
) -> QualityAssessment:
    a = QualityAssessment(flag=QualityFlag.VALID)
    for var, (lo, hi) in WEATHER_RANGES.items():
        v = values.get(var)
        if v is None:
            a.missing_variables.append(var)
            _flag_issues(a, QualityFlag.MISSING, var, "missing_value", f"{var} missing in forecast")
            continue
        if not (lo <= v <= hi):
            _flag_issues(a, QualityFlag.INVALID, var, "out_of_range", f"{var}={v} outside [{lo},{hi}]")
    if temperature_unit not in {"C", "F", "K"}:
        _flag_issues(a, QualityFlag.INVALID, "temperature_unit", "unit_mismatch", "unknown unit")
    if valid_to < valid_from:
        _flag_issues(a, QualityFlag.INVALID, "valid_window", "invalid_window", "valid_to before valid_from")
    if issued_at > valid_from:
        _flag_issues(a, QualityFlag.SUSPECT, "issued_at", "issue_after_validity", "issued_at after valid_from")
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    if issued_at < EARLIEST_PLAUSIBLE:
        _flag_issues(a, QualityFlag.INVALID, "issued_at", "impossible_timestamp", "issued_at before 1950")
    a.flag = _merge_flag(a)
    return a


def assess_air_quality(values: Dict[str, float | None], observed_at: datetime) -> QualityAssessment:
    a = QualityAssessment(flag=QualityFlag.VALID)
    now = datetime.now(timezone.utc)
    for var in EXPECTED_AQ:
        if values.get(var) is None:
            a.missing_variables.append(var)
            _flag_issues(a, QualityFlag.MISSING, var, "missing_value",
                         f"{var} missing (kept null, not zeroed)")
    for var, (lo, hi) in AQ_RANGES.items():
        v = values.get(var)
        if v is None:
            continue
        if not (lo <= v <= hi):
            _flag_issues(a, QualityFlag.INVALID, var, "out_of_range", f"{var}={v} outside [{lo},{hi}]")
    obs = observed_at
    if obs.tzinfo is None:
        obs = obs.replace(tzinfo=timezone.utc)
    if obs < EARLIEST_PLAUSIBLE or obs > now.replace(tzinfo=timezone.utc):
        _flag_issues(a, QualityFlag.INVALID, "observed_at", "impossible_or_future_timestamp", "timestamp implausible")
    a.flag = _merge_flag(a)
    return a


def assess_vulnerability(factors: Dict[str, float | None]) -> QualityAssessment:
    a = QualityAssessment(flag=QualityFlag.VALID)
    for key, value in factors.items():
        if value is None:
            a.missing_variables.append(key)
            _flag_issues(a, QualityFlag.MISSING, key, "missing_value",
                         f"vulnerability factor {key} unavailable")
        elif not (0.0 <= value <= 1.0):
            _flag_issues(a, QualityFlag.INVALID, key, "out_of_range", f"{key}={value} outside [0,1]")
    a.flag = _merge_flag(a)
    return a


def assess_health(values: Dict[str, int | None]) -> QualityAssessment:
    a = QualityAssessment(flag=QualityFlag.VALID)
    if values.get("mortality_count") is None:
        _flag_issues(a, QualityFlag.MISSING, "mortality_count", "unavailable",
                     "mortality not legally available; left null")
    if values.get("heat_illness_cases") is None:
        a.missing_variables.append("heat_illness_cases")
        _flag_issues(a, QualityFlag.MISSING, "heat_illness_cases", "missing_value", "no surveillance")
    a.flag = _merge_flag(a)
    return a


def _merge_flag(a: QualityAssessment) -> QualityFlag:
    if any(i.severity == QualityFlag.INVALID for i in a.issues):
        return QualityFlag.INVALID
    if any(i.severity == QualityFlag.MISSING for i in a.issues):
        return QualityFlag.MISSING
    if any(i.severity == QualityFlag.SUSPECT for i in a.issues):
        return QualityFlag.SUSPECT
    if a.issues:
        return QualityFlag.SUSPECT
    return QualityFlag.VALID


def sanitize(values: Dict[str, float | None], assessment: QualityAssessment) -> Dict[str, float | None]:
    """Return a copy where INVALID values become None (never zero, never kept).

    Original values remain recorded in assessment issues — nothing is lost.
    """
    invalid_vars = {i.variable for i in assessment.issues if i.severity == QualityFlag.INVALID}
    out = dict(values)
    for var in invalid_vars:
        if var in out and out[var] is not None:
            out[var] = None
    return out


def summarize_flags(assessments: Sequence[QualityAssessment]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for a in assessments:
        counts[a.flag.value] = counts.get(a.flag.value, 0) + 1
    return counts


def freshness_status(
    last_observed_at: Optional[datetime],
    expected_update_hours: float,
    now: Optional[datetime] = None,
) -> FreshnessStatus:
    """Domain-cadence-aware freshness. Thresholds are per-source, never global."""
    if last_observed_at is None:
        return FreshnessStatus.UNAVAILABLE
    n = now or datetime.now(timezone.utc)
    if last_observed_at.tzinfo is None:
        last_observed_at = last_observed_at.replace(tzinfo=timezone.utc)
    age_hours = (n - last_observed_at).total_seconds() / 3600.0
    if age_hours <= expected_update_hours:
        return FreshnessStatus.FRESH
    if age_hours <= expected_update_hours * 2:
        return FreshnessStatus.AGING
    if age_hours <= expected_update_hours * 3:
        return FreshnessStatus.STALE
    return FreshnessStatus.UNAVAILABLE