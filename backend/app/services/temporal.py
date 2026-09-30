"""Temporal alignment primitives.

Pure functions for aligning heterogeneous observation timestamps onto a shared
temporal axis. These are the building blocks downstream pipelines use for
weather-to-health joins and coverage audits. Nothing here computes heat or
WBGT indices — Step 2 only aligns time.

Conventions:
    - internal timestamps are UTC (naive is treated as UTC via utils.time.to_utc)
    - source timestamps are preserved verbatim alongside the normalized form
    - alignment is explicit: the caller decides the target grain (hour/day)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


def ensure_utc(dt: datetime) -> datetime:
    """Normalize to UTC (naive assumed UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_day_key(dt: datetime) -> str:
    """Canonical day bucket for a timestamp (UTC date string)."""
    return ensure_utc(dt).strftime("%Y-%m-%d")


def localize(dt: datetime, zone_name: str = "Asia/Kolkata") -> datetime:
    """Attach IANA timezone (falling back to UTC if tzdata is absent)."""
    try:
        from zoneinfo import ZoneInfo

        return ensure_utc(dt).astimezone(ZoneInfo(zone_name))
    except Exception:
        return ensure_utc(dt)


def align_hourly_to_daily(
    records: Sequence[Dict[str, Any]],
    value_key: str = "value",
    require_coverage: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Aggregate hourly records into daily buckets.

    Returns ``(daily_records, summary)`` where each daily record has:
        day, min, max, mean, sample_count, coverage_hours
    ``coverage_hours`` counts non-null hours (missing hours are NOT zero-filled);
    ``summary.coverage_requirements`` reflects the caller-requested threshold.
    """
    buckets: Dict[str, List[Optional[float]]] = defaultdict(list)
    null_series = []
    for rec in records:
        ts = rec.get("observed_at") or rec.get("timestamp") or rec.get("valid_from")
        if ts is None:
            null_series.append(rec)
            continue
        day = utc_day_key(ts)
        buckets[day].append(rec.get(value_key))

    daily = []
    for day in sorted(buckets):
        values = [v for v in buckets[day] if isinstance(v, (int, float))]
        sample_count = len(values)
        coverage_hours = sample_count
        if values:
            daily.append(
                {
                    "day": day,
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                    "mean": round(sum(values) / len(values), 3),
                    "sample_count": sample_count,
                    "coverage_hours": coverage_hours,
                }
            )
        else:
            daily.append(
                {
                    "day": day,
                    "min": None,
                    "max": None,
                    "mean": None,
                    "sample_count": 0,
                    "coverage_hours": 0,
                }
            )

    coverage_shortfalls = [
        day for day in daily
        if require_coverage is not None and day["coverage_hours"] < require_coverage
    ]
    summary = {
        "days": len(daily),
        "records_processed": len(records),
        "records_without_timestamp": len(null_series),
        "coverage_requirement_hours": require_coverage,
        "days_below_requirement": len(coverage_shortfalls),
        "shortfall_days": coverage_shortfalls,
    }
    return daily, summary


def rolling_stat(
    records: Sequence[Dict[str, Any]],
    window_hours: int,
    value_key: str = "value",
    stat: str = "mean",
) -> List[Dict[str, Any]]:
    """Rolling window statistic over a time-sorted series (pure).

    Only fully-covered windows are reported; partially covered windows are
    omitted from output (missing hours never imputed with zeros).
    """
    if window_hours < 1:
        raise ValueError("window_hours must be >= 1")
    sorted_records = sorted(
        records,
        key=lambda r: ensure_utc(r.get("observed_at") or r.get("timestamp") or r.get("valid_from")),
    )
    if len(sorted_records) < window_hours:
        return []
    out = []
    window_start_ts = ensure_utc(
        sorted_records[0].get("observed_at") or sorted_records[0].get("timestamp") or sorted_records[0].get("valid_from")
    )
    for end_idx in range(window_hours - 1, len(sorted_records)):
        window = sorted_records[end_idx - (window_hours - 1): end_idx + 1]
        values = [w.get(value_key) for w in window]
        if any(v is None for v in values):
            continue
        if stat == "mean":
            result: Any = round(sum(values) / len(values), 3)
        elif stat == "max":
            result = round(max(values), 3)
        elif stat == "min":
            result = round(min(values), 3)
        elif stat == "count":
            result = len([v for v in values if v is not None])
        else:
            raise ValueError(f"unsupported stat {stat!r}")
        out.append(
            {
                "window_end": ensure_utc(
                    window[-1].get("observed_at") or window[-1].get("timestamp") or window[-1].get("valid_from")
                ),
                "window_start": ensure_utc(
                    window[0].get("observed_at") or window[0].get("timestamp") or window[0].get("valid_from")
                ),
                f"{stat}_{value_key}": result,
                "window_hours": len(window),
            }
        )
    return out


def bucket_records_by_period(
    records: Sequence[Dict[str, Any]],
    period_minutes: int,
    value_key: str = "value",
    aggregate: str = "mean",
) -> List[Dict[str, Any]]:
    """Group records into fixed UTC buckets of ``period_minutes``."""
    if period_minutes <= 0:
        raise ValueError("period_minutes must be positive")
    ordered = sorted(
        records,
        key=lambda r: ensure_utc(r.get("observed_at") or r.get("timestamp") or r.get("valid_from")),
    )
    buckets: Dict[str, List[Any]] = defaultdict(list)
    for rec in ordered:
        ts = ensure_utc(rec.get("observed_at") or rec.get("timestamp") or rec.get("valid_from"))
        epoch = ts.timestamp()
        bucket_start = int(epoch // (period_minutes * 60)) * period_minutes * 60
        key = datetime.fromtimestamp(bucket_start, tz=timezone.utc).isoformat()
        buckets[key].append(rec)
    out = []
    for key in sorted(buckets):
        vals = [r.get(value_key) for r in buckets[key] if isinstance(r.get(value_key), (int, float))]
        if not vals:
            continue
        if aggregate == "mean":
            stat: Any = round(sum(vals) / len(vals), 3)
        elif aggregate == "max":
            stat = round(max(vals), 3)
        elif aggregate == "count":
            stat = len(vals)
        else:
            raise ValueError(f"unsupported aggregate {aggregate!r}")
        out.append({"period_start": key, "value": stat, "samples": len(vals)})
    return out