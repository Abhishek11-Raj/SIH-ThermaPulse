"""Heatwave Persistence and Cumulative Exposure — STEP 3.

Implements:
- Heatwave duration tracking
- Consecutive hot/extreme days
- Intensity above baseline
- Cumulative heat burden
- Peak heat tracking
- Recovery periods between events

References:
- Perkins & Alexander (2013). "On the measurement of heatwaves."
- Russo et al. (2015). "Magnitude of extreme heat waves in present climate."
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from ..core.enums import QualityFlag


@dataclass
class HeatwaveEvent:
    """A single heatwave event."""
    start_date: datetime
    end_date: datetime
    duration_days: int
    peak_temperature_c: float
    peak_heat_index_c: Optional[float]
    peak_wbgt_c: Optional[float]
    mean_temperature_c: float
    intensity_above_baseline_c: float
    hot_days: int
    extreme_days: int
    recovery_days_after: int = 0
    quality: QualityFlag = QualityFlag.VALID


@dataclass
class PersistenceResult:
    """Heatwave persistence analysis result."""
    current_event: Optional[HeatwaveEvent]
    previous_events: List[HeatwaveEvent]
    consecutive_hot_days: int
    consecutive_extreme_days: int
    days_since_last_event: int
    cumulative_heat_burden: float
    quality: QualityFlag
    extrapolated: bool
    validity_note: Optional[str]


def detect_heatwave_days(
    daily_temps: List[float],
    daily_heat_indices: List[Optional[float]],
    baseline_percentile_90: float,
    baseline_percentile_975: float,
    temp_threshold_c: Optional[float] = None,
) -> List[dict]:
    """
    Detect hot and extreme days from daily data.

    Args:
        daily_temps: Daily maximum temperatures
        daily_heat_indices: Daily maximum heat indices
        baseline_percentile_90: 90th percentile threshold for hot day
        baseline_percentile_975: 97.5th percentile threshold for extreme day
        temp_threshold_c: Optional fixed temperature threshold

    Returns:
        List of day classifications
    """
    if len(daily_temps) != len(daily_heat_indices):
        raise ValueError("Temperature and heat index arrays must have same length")

    results = []

    for i, (temp, hi) in enumerate(zip(daily_temps, daily_heat_indices)):
        is_hot = False
        is_extreme = False

        if temp is not None:
            if temp_threshold_c is not None:
                is_hot = temp >= temp_threshold_c
                is_extreme = temp >= temp_threshold_c + 3.0
            else:
                is_hot = temp >= baseline_percentile_90
                is_extreme = temp >= baseline_percentile_975

        results.append({
            "index": i,
            "temperature_c": temp,
            "heat_index_c": hi,
            "hot_day": is_hot,
            "extreme_day": is_extreme,
        })

    return results


def identify_heatwave_events(
    day_classifications: List[dict],
    min_duration: int = 3,
    max_gap_days: int = 1,
) -> List[HeatwaveEvent]:
    """
    Identify heatwave events from day classifications.

    A heatwave is a period of at least min_duration consecutive hot days,
    allowing gaps of up to max_gap_days.

    Args:
        day_classifications: Output from detect_heatwave_days
        min_duration: Minimum consecutive hot days for a heatwave
        max_gap_days: Maximum gap days allowed within a heatwave

    Returns:
        List of HeatwaveEvent objects
    """
    events = []
    i = 0
    n = len(day_classifications)

    while i < n:
        if not day_classifications[i]["hot_day"]:
            i += 1
            continue

        start_idx = i
        hot_count = 0
        extreme_count = 0
        gap_count = 0
        max_temp = day_classifications[i]["temperature_c"] or 0
        max_hi = day_classifications[i]["heat_index_c"]
        sum_temp = 0
        temp_count = 0

        while i < n:
            day = day_classifications[i]
            is_hot = day["hot_day"]
            is_extreme = day["extreme_day"]

            if is_hot:
                hot_count += 1
                if day["temperature_c"] is not None:
                    max_temp = max(max_temp, day["temperature_c"])
                    sum_temp += day["temperature_c"]
                    temp_count += 1
                if day["heat_index_c"] is not None:
                    max_hi = max(max_hi or 0, day["heat_index_c"])
                if is_extreme:
                    extreme_count += 1
                gap_count = 0
            else:
                if gap_count < max_gap_days:
                    gap_count += 1
                else:
                    break

            i += 1

        duration = i - start_idx
        if hot_count >= min_duration:
            event = HeatwaveEvent(
                start_date=day_classifications[start_idx].get("date", datetime.utcnow()),
                end_date=day_classifications[i-1].get("date", datetime.utcnow()),
                duration_days=duration,
                peak_temperature_c=max_temp,
                peak_heat_index_c=max_hi,
                peak_wbgt_c=None,
                mean_temperature_c=sum_temp / temp_count if temp_count > 0 else 0,
                intensity_above_baseline_c=max_temp - baseline_percentile_90 if 'baseline_percentile_90' in dir() else 0,
                hot_days=hot_count,
                extreme_days=extreme_count,
            )
            events.append(event)
        else:
            i = start_idx + 1

    return events


def calculate_persistence_metrics(
    daily_temps: List[float],
    daily_heat_indices: List[Optional[float]],
    daily_dates: List[datetime],
    baseline_90: float,
    baseline_975: float,
    quality: Optional[QualityFlag] = None,
) -> PersistenceResult:
    """
    Calculate complete persistence metrics from daily time series.

    Args:
        daily_temps: Daily maximum temperatures
        daily_heat_indices: Daily maximum heat indices
        daily_dates: Corresponding dates
        baseline_90: 90th percentile baseline temperature
        baseline_975: 97.5th percentile baseline temperature
        quality: Input quality flag

    Returns:
        PersistenceResult with all persistence metrics
    """
    base_quality = quality or QualityFlag.VALID
    extrapolated = False
    validity_note = None

    if not daily_temps or not daily_dates:
        return PersistenceResult(
            current_event=None,
            previous_events=[],
            consecutive_hot_days=0,
            consecutive_extreme_days=0,
            days_since_last_event=0,
            cumulative_heat_burden=0.0,
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Insufficient daily data",
        )

    day_classes = detect_heatwave_days(
        daily_temps, daily_heat_indices, baseline_90, baseline_975
    )

    for i, dc in enumerate(day_classes):
        dc["date"] = daily_dates[i] if i < len(daily_dates) else None

    events = identify_heatwave_events(day_classes)

    current_event = None
    if events:
        last_event = events[-1]
        last_date = daily_dates[-1] if daily_dates else None
        if last_event.end_date and last_date:
            days_diff = (last_date - last_event.end_date).days
            if days_diff <= 1:
                current_event = last_event

    consec_hot = 0
    consec_extreme = 0
    for dc in reversed(day_classes):
        if dc["hot_day"]:
            consec_hot += 1
        else:
            break

    for dc in reversed(day_classes):
        if dc["extreme_day"]:
            consec_extreme += 1
        else:
            break

    days_since = 0
    if events:
        last_event_end = events[-1].end_date
        if last_date := daily_dates[-1]:
            days_since = (last_date - last_event_end).days

    burden = sum(max(0, t - baseline_90) for t in daily_temps if t is not None)

    return PersistenceResult(
        current_event=current_event,
        previous_events=events[:-1] if current_event else events,
        consecutive_hot_days=consec_hot,
        consecutive_extreme_days=consec_extreme,
        days_since_last_event=days_since,
        cumulative_heat_burden=burden,
        quality=base_quality,
        extrapolated=extrapolated,
        validity_note=validity_note,
    )


def calculate_cumulative_heat_burden(
    hourly_temps: List[float],
    baseline_temp_c: float,
    threshold_method: str = "above_baseline"
) -> float:
    """
    Calculate cumulative heat burden from hourly temperatures.

    Args:
        hourly_temps: Hourly temperatures
        baseline_temp_c: Baseline temperature threshold
        threshold_method: "above_baseline" or "above_threshold"

    Returns:
        Cumulative heat burden in degree-hours
    """
    return sum(max(0, t - baseline_temp_c) for t in hourly_temps if t is not None)