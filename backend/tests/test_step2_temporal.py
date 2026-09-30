"""Step 2 tests: timezone handling and temporal alignment primitives."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.temporal import (
    align_hourly_to_daily,
    bucket_records_by_period,
    ensure_utc,
    localize,
    rolling_stat,
    utc_day_key,
)


def test_zoneinfo_resolvable_for_default_tz():
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Asia/Kolkata")
    dt = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    assert dt.astimezone(zone).utcoffset() == timedelta(hours=5, minutes=30)


def test_localize_returns_ist_offset():
    dt = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    ist = localize(dt, "Asia/Kolkata")
    assert ist.utcoffset() == timedelta(hours=5, minutes=30)


def test_ensure_utc_naive_assumed_utc():
    assert ensure_utc(datetime(2026, 9, 28, 0, 0)).tzinfo == timezone.utc


def test_utc_day_key():
    dt = datetime(2026, 9, 28, 23, 30, tzinfo=timezone.utc)
    assert utc_day_key(dt) == "2026-09-28"


def test_align_hourly_to_daily():
    base = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)
    records = [
        {"observed_at": base + timedelta(hours=i), "value": 20.0 + i}
        for i in range(10)
    ]
    daily, summary = align_hourly_to_daily(records)
    assert daily[0]["coverage_hours"] == 10
    assert daily[0]["min"] == 20.0
    assert daily[0]["max"] == 29.0
    assert daily[0]["mean"] == pytest.approx(24.5)
    assert summary["records_processed"] == 10


def test_align_hourly_missing_not_zero():
    base = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)
    records = [
        {"observed_at": base + timedelta(hours=i), "value": 20.0 if i % 2 == 0 else None}
        for i in range(6)
    ]
    daily, _ = align_hourly_to_daily(records)
    assert daily[0]["coverage_hours"] == 3
    assert daily[0]["min"] == 20.0  # nulls excluded, never zeroed


def test_align_coverage_requirement():
    base = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)
    records = [{"observed_at": base + timedelta(hours=i), "value": 1.0} for i in range(4)]
    _, summary = align_hourly_to_daily(records, require_coverage=6)
    assert summary["days_below_requirement"] == 1


def test_rolling_stat():
    base = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)
    records = [
        {"observed_at": base + timedelta(hours=i), "value": float(i)}
        for i in range(6)
    ]
    windows = rolling_stat(records, window_hours=3)
    assert len(windows) == 4  # 6 - 3 + 1 fully covered windows
    assert windows[0]["mean_value"] == pytest.approx(1.0)


def test_bucket_records_by_period():
    base = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)
    records = [
        {"observed_at": base + timedelta(minutes=i), "value": float(i % 5)}
        for i in range(10)
    ]
    buckets = bucket_records_by_period(records, period_minutes=60)
    assert len(buckets) == 1
    assert buckets[0]["samples"] == 10