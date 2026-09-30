"""Data coverage & equity-aware coverage services.

Encodes the core equity principle: NO DATA ≠ LOW RISK. Poor coverage raises
uncertainty and lowers confidence. Coverage is tracked by location so that
sensor-rich and sensor-poor wards can be compared for audits later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from ..core.enums import CoverageClass, DataDomain
from ..schemas.common import (
    CoverageByLocation,
    CoverageReport,
    TimeWindow,
    VariableCoverage,
)


def compute_variable_coverage(
    variable: str,
    expected_timesteps: int,
    present: int,
    window: Optional[TimeWindow] = None,
) -> VariableCoverage:
    expected = max(expected_timesteps, 1)
    missing = expected - present
    rate = round(missing / expected, 4) if expected else 0.0
    return VariableCoverage(
        variable=variable,
        expected_records=expected_timesteps,
        present_records=present,
        missing_records=max(0, missing),
        missingness_rate=min(1.0, rate),
        span_start=window.start if window else None,
        span_end=window.end if window else None,
    )


def coverage_class(missingness_rate: float) -> CoverageClass:
    if missingness_rate <= 0.05:
        return CoverageClass.DATA_RICH
    if missingness_rate <= 0.35:
        return CoverageClass.ADEQUATE
    return CoverageClass.DATA_POOR


def build_coverage_report(
    location_id: str,
    domain: str,
    provider: str,
    expected_timesteps: int,
    record_counts: Dict[str, int],
    window: Optional[TimeWindow] = None,
) -> CoverageReport:
    """Build a coverage report for one domain/location.

    ``record_counts`` maps variable → number of present records. Variables
    missing entirely from the provider are still counted as expected but absent,
    so a provider that simply does not send a variable produces higher
    missingness — exactly the "known unknown" the equity layer needs.
    """
    if not record_counts:
        vars_seen: List[str] = []
    else:
        vars_seen = list(record_counts)

    coverage_vars: List[VariableCoverage] = []
    total_missing = 0
    # Every expected variable for the domain.
    expected_vars = _expected_variables(domain, vars_seen)
    for var in expected_vars:
        present = record_counts.get(var, 0)
        vc = compute_variable_coverage(var, expected_timesteps, present, window)
        coverage_vars.append(vc)
        total_missing += vc.missing_records

    overall = 0.0
    if expected_vars:
        overall = min(1.0, round(total_missing / (expected_timesteps * len(expected_vars)), 4))

    return CoverageReport(
        location_id=location_id,
        domain=domain,
        provider=provider,
        window=window,
        variable_coverage=coverage_vars,
        overall_missingness_rate=overall,
        coverage_class=coverage_class(overall),
        equity_note=(
            "Data-poor locations yield higher uncertainty and lower confidence. "
            "No data is never treated as low risk."
        ),
    )


def _expected_variables(domain: str, seen: List[str]) -> List[str]:
    domain_defaults = {
        DataDomain.WEATHER.value: [
            "temperature", "relative_humidity", "wind_speed", "pressure",
            "rainfall", "cloud_cover", "solar_radiation", "visibility",
        ],
        DataDomain.WEATHER_FORECAST.value: [
            "temperature", "relative_humidity", "wind_speed", "pressure",
            "rainfall", "cloud_cover", "solar_radiation",
        ],
        DataDomain.AIR_QUALITY.value: ["pm25", "pm10", "o3", "no2", "so2", "co", "aqi"],
        DataDomain.HEALTH.value: [
            "heat_illness_cases", "emergency_visits", "hospital_admissions",
            "respiratory_admissions", "cardiovascular_admissions",
        ],
        DataDomain.VULNERABILITY.value: [
            "elderly_population_share", "children_population_share",
            "outdoor_worker_share", "housing_vulnerability_index",
            "cooling_access_share",
        ],
    }
    defaults = domain_defaults.get(domain, [])
    merged = list(dict.fromkeys([*defaults, *seen]))
    return merged


def aggregate_by_location(
    reports: List[CoverageReport],
) -> List[CoverageByLocation]:
    grouped: Dict[str, List[CoverageReport]] = {}
    for r in reports:
        grouped.setdefault(r.location_id, []).append(r)
    return [
        CoverageByLocation(location_id=loc, domains=grouped[loc])
        for loc in sorted(grouped)
    ]


def coverage_reports_from_db(
    db,
    location_id: str,
    window: Optional[TimeWindow] = None,
) -> List[CoverageReport]:
    """Compute per-domain coverage reports for one location from stored rows.

    Expected granularity is inferred per domain (hourly for weather/AQ, daily
    for health/vulnerability) so missingness is measured against the domain's
    own temporal resolution — never a universal cadence.
    """
    from datetime import timedelta

    from ..models.weather import (  # noqa: F401
        AirQualityObservation as AQModel,
        WeatherObservation as WeatherModel,
    )
    from ..models.vulnerability import (
        HealthOutcome as HealthModel,
        VulnerabilityData as VulnerabilityModel,
    )

    win = window or TimeWindow(
        start=datetime.utcnow() - timedelta(hours=48),
        end=datetime.utcnow(),
    )
    reports: List[CoverageReport] = []

    weather_rows = db.query(WeatherModel).filter(
        WeatherModel.location_id == location_id,
        WeatherModel.observed_at >= win.start,
        WeatherModel.observed_at <= win.end,
    ).all()
    # Per-variable non-null counts: a null temperature in a present row is a
    # missing value for that variable — counted, never zeroed.
    counts_w: Dict[str, int] = {}
    for var in ["temperature", "relative_humidity", "wind_speed", "pressure",
                "rainfall", "cloud_cover", "solar_radiation", "visibility"]:
        counts_w[var] = sum(1 for r in weather_rows if getattr(r, var) is not None)
    reports.append(build_coverage_report(
        location_id, "weather", "mock_weather",
        expected_timesteps=_hours_in(win),
        record_counts=counts_w, window=win,
    ))

    counts_aq = {}
    for var in ["pm25", "pm10", "o3", "no2", "so2", "co", "aqi"]:
        counts_aq[var] = db.query(AQModel).filter(
            AQModel.location_id == location_id,
            AQModel.observed_at >= win.start,
            AQModel.observed_at <= win.end,
        ).count()
    reports.append(build_coverage_report(
        location_id, "air_quality", "mock_air_quality",
        expected_timesteps=_hours_in(win),
        record_counts=counts_aq, window=win,
    ))

    counts_vul = {}
    for var in ["elderly_population_share", "children_population_share",
                "outdoor_worker_share", "housing_vulnerability_index",
                "cooling_access_share"]:
        counts_vul[var] = db.query(VulnerabilityModel).filter(
            VulnerabilityModel.location_id == location_id,
            VulnerabilityModel.reference_date >= win.start,
            VulnerabilityModel.reference_date <= win.end,
        ).count()
    reports.append(build_coverage_report(
        location_id, "vulnerability", "mock_vulnerability",
        expected_timesteps=_days_in(win),
        record_counts=counts_vul, window=win,
    ))

    counts_health = {}
    for var in ["heat_illness_cases", "emergency_visits", "hospital_admissions",
                "respiratory_admissions", "cardiovascular_admissions"]:
        counts_health[var] = db.query(HealthModel).filter(
            HealthModel.location_id == location_id,
            HealthModel.period_start >= win.start,
            HealthModel.period_end <= win.end,
        ).count()
    reports.append(build_coverage_report(
        location_id, "health", "mock_health",
        expected_timesteps=_days_in(win),
        record_counts=counts_health, window=win,
    ))
    return reports


def _hours_in(win: TimeWindow) -> int:
    delta = (win.end - win.start).total_seconds()
    return max(1, int(delta // 3600) + 1)


def _days_in(win: TimeWindow) -> int:
    delta = (win.end - win.start).total_seconds()
    return max(1, int(delta // 86400) + 1)