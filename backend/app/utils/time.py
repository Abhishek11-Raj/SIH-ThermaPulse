"""Temporal utilities. All internal timestamps are UTC."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current time in UTC (naive is avoided; we return timezone-aware)."""
    return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    """Normalize to UTC. Naive datetimes are assumed UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)