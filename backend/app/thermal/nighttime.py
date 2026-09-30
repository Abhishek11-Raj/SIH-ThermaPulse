"""Nighttime Heat Analysis — STEP 3.

Implements nighttime heat metrics including:
- Tmin, nighttime mean/max temperature
- Hot night detection (configurable percentile-based)
- Consecutive hot nights
- Nighttime anomaly from baseline
- Recovery window analysis

References:
- McGregor et al. (2015). "Heatwave definitions and their relevance for
  heat-health impact studies."
- Perkins & Alexander (2013). "On the measurement of heatwaves."
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from .schemas import ThermalInput
from ..core.enums import QualityFlag
from ..models.thermal import NighttimeHeatMetric


@dataclass
class NighttimeResult:
    """Nighttime heat analysis result for a single night."""
    night_start: datetime
    night_end: datetime
    min_temperature_c: Optional[float]
    mean_temperature_c: Optional[float]
    max_temperature_c: Optional[float]
    anomaly_c: Optional[float]
    percentile: Optional[float]
    hot_night: bool
    consecutive_hot_nights: int
    duration_hours_above_threshold: Optional[float]
    recovery_deficit: Optional[float]
    recovery_status: Optional[str]
    recovery_hours: Optional[float]
    baseline_percentile: float
    threshold_used_c: Optional[float]
    method: str
    quality: QualityFlag
    extrapolated: bool
    validity_note: Optional[str]


def calculate_nighttime_temperatures(
    hourly_temps: List[float],
    hourly_times: List[datetime],
    night_start_hour: int = 20,
    night_end_hour: int = 8
) -> tuple:
    """
    Extract nighttime temperatures from hourly data.

    Args:
        hourly_temps: List of hourly temperatures
        hourly_times: Corresponding timestamps
        night_start_hour: Hour when night begins (20 = 8 PM)
        night_end_hour: Hour when night ends (8 = 8 AM)

    Returns:
        (night_temps, night_times) for the night period
    """
    if not hourly_temps or not hourly_times or len(hourly_temps) != len(hourly_times):
        return [], []

    night_temps = []
    night_times = []

    for temp, t in zip(hourly_temps, hourly_times):
        hour = t.hour
        # Night period: 20:00-23:59 and 00:00-07:59
        if hour >= night_start_hour or hour < night_end_hour:
            night_temps.append(temp)
            night_times.append(t)

    return night_temps, night_times


def calculate_nighttime_stats(
    night_temps: List[float],
    baseline_temps: Optional[List[float]] = None,
    percentile: float = 90.0
) -> dict:
    """
    Calculate nighttime statistics including anomaly from baseline.

    Args:
        night_temps: Temperatures during night hours
        baseline_temps: Historical nighttime temperatures for percentile calculation
        percentile: Percentile for hot night threshold (default 90th)

    Returns:
        Dict with min, mean, max, anomaly, percentile, threshold
    """
    if not night_temps:
        return {
            "min_temp_c": None,
            "mean_temp_c": None,
            "max_temp_c": None,
            "anomaly_c": None,
            "percentile": None,
            "threshold_c": None,
        }

    min_temp = min(night_temps)
    mean_temp = sum(night_temps) / len(night_temps)
    max_temp = max(night_temps)

    # Calculate threshold from baseline if available
    threshold_c = None
    anomaly_c = None
    night_percentile = None

    if baseline_temps and len(baseline_temps) > 10:
        # Calculate threshold as specified percentile of baseline
        sorted_baseline = sorted(baseline_temps)
        idx = int(len(sorted_baseline) * percentile / 100.0)
        idx = min(idx, len(sorted_baseline) - 1)
        threshold_c = sorted_baseline[idx]

        # Anomaly = mean_temp - baseline_mean
        baseline_mean = sum(baseline_temps) / len(baseline_temps)
        anomaly_c = mean_temp - baseline_mean

        # What percentile is this night in the baseline?
        below = sum(1 for t in baseline_temps if t <= mean_temp)
        night_percentile = (below / len(baseline_temps)) * 100.0

    return {
        "min_temp_c": min_temp,
        "mean_temp_c": mean_temp,
        "max_temp_c": max_temp,
        "anomaly_c": anomaly_c,
        "percentile": night_percentile,
        "threshold_c": threshold_c,
    }


def calculate_recovery_deficit(
    night_temps: List[float],
    recovery_threshold_c: float = 25.0,
    night_start_hour: int = 20,
    night_end_hour: int = 8
) -> tuple:
    """
    Calculate nighttime recovery deficit.

    Recovery deficit = accumulated hours above recovery threshold
    during the nighttime recovery window.

    Args:
        night_temps: Nighttime temperatures
        recovery_threshold_c: Temperature above which recovery is impaired
        night_start_hour, night_end_hour: Night period definition

    Returns:
        (recovery_deficit, recovery_hours, recovery_status)
    """
    if not night_temps:
        return None, None, "no_data"

    # Hours above recovery threshold
    hours_above = sum(1 for t in night_temps if t >= recovery_threshold_c)
    total_hours = len(night_temps)

    if total_hours == 0:
        return None, None, "no_data"

    # Deficit as degree-hours above threshold
    deficit = sum(max(0, t - recovery_threshold_c) for t in night_temps)

    # Status
    if hours_above == 0:
        status = "full_recovery"
    elif hours_above / total_hours < 0.3:
        status = "partial_recovery"
    elif hours_above / total_hours < 0.7:
        status = "impaired_recovery"
    else:
        status = "minimal_recovery"

    return deficit, hours_above, status


def analyze_nighttime_heat(
    hourly_temps: List[float],
    hourly_times: List[datetime],
    baseline_night_temps: Optional[List[float]] = None,
    config: Optional[dict] = None,
    quality: Optional[QualityFlag] = None
) -> NighttimeResult:
    """
    Complete nighttime heat analysis for a single night.

    Args:
        hourly_temps: Hourly temperatures for 24+ hours
        hourly_times: Corresponding timestamps
        baseline_night_temps: Historical nighttime temps for percentile
        config: Configuration dict with night_start_hour, night_end_hour,
                nighttime_percentile, recovery_threshold_c
        quality: Input quality flag

    Returns:
        NighttimeResult with all nighttime metrics
    """
    config = config or {}
    night_start_hour = config.get("nighttime_start_hour", 20)
    night_end_hour = config.get("nighttime_end_hour", 8)
    percentile = config.get("nighttime_percentile", 90.0)
    recovery_threshold = config.get("recovery_threshold_c", 25.0)
    base_quality = quality or QualityFlag.VALID

    # Extract nighttime temperatures
    night_temps, night_times = calculate_nighttime_temperatures(
        hourly_temps, hourly_times, night_start_hour, night_end_hour
    )

    if not night_temps:
        return NighttimeResult(
            night_start=hourly_times[0] if hourly_times else datetime.utcnow(),
            night_end=hourly_times[-1] if hourly_times else datetime.utcnow(),
            min_temperature_c=None,
            mean_temperature_c=None,
            max_temperature_c=None,
            anomaly_c=None,
            percentile=None,
            hot_night=False,
            consecutive_hot_nights=0,
            duration_hours_above_threshold=None,
            recovery_deficit=None,
            recovery_status="no_data",
            recovery_hours=None,
            baseline_percentile=percentile,
            threshold_used_c=None,
            method="nighttime_analysis_v1",
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="No nighttime data available",
        )

    # Calculate stats
    stats = calculate_nighttime_stats(night_temps, baseline_night_temps, percentile)

    # Hot night detection
    hot_night = False
    if stats["threshold_c"] is not None and stats["mean_temp_c"] is not None:
        hot_night = stats["mean_temp_c"] >= stats["threshold_c"]

    # Recovery deficit
    deficit, hours_above, status = calculate_recovery_deficit(
        night_temps, recovery_threshold, night_start_hour, night_end_hour
    )

    # Duration above threshold
    duration_above = hours_above if hours_above else 0.0

    return NighttimeResult(
        night_start=night_times[0] if night_times else hourly_times[0],
        night_end=night_times[-1] if night_times else hourly_times[-1],
        min_temperature_c=stats["min_temp_c"],
        mean_temperature_c=stats["mean_temp_c"],
        max_temperature_c=stats["max_temp_c"],
        anomaly_c=stats["anomaly_c"],
        percentile=stats["percentile"],
        hot_night=hot_night,
        consecutive_hot_nights=0,  # Set by caller based on history
        duration_hours_above_threshold=duration_above,
        recovery_deficit=deficit,
        recovery_status=status,
        recovery_hours=hours_above,
        baseline_percentile=percentile,
        threshold_used_c=stats["threshold_c"],
        method="nighttime_analysis_v1",
        quality=base_quality,
        extrapolated=False,
        validity_note=None,
    )


def build_baseline_from_history(
    historical_hourly_temps: List[List[float]],
    historical_hourly_times: List[List[datetime]],
    night_start_hour: int = 20,
    night_end_hour: int = 8
) -> List[float]:
    """
    Build nighttime temperature baseline from historical data.

    Args:
        historical_hourly_temps: List of hourly temperature arrays for each day
        historical_hourly_times: Corresponding timestamps
        night_start_hour, night_end_hour: Night period definition

    Returns:
        List of nighttime mean temperatures for percentile calculation
    """
    baseline = []

    for temps, times in zip(historical_hourly_temps, historical_hourly_times):
        night_temps, _ = calculate_nighttime_temperatures(
            temps, times, night_start_hour, night_end_hour
        )
        if night_temps:
            baseline.append(sum(night_temps) / len(night_temps))

    return baseline