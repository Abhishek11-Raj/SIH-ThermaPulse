"""Shared FastAPI dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.config import Settings, settings
from ..core.database import get_db as _get_db
from ..models.location import Location as LocationModel
from ..providers import ProviderRegistry, registry
from ..utils.time import utcnow

get_db = _get_db


def get_settings() -> Settings:
    return settings


def get_registry() -> ProviderRegistry:
    return registry


def get_thermal_service(db: Session = Depends(get_db)) -> ThermalCalculationService:
    from app.thermal.service import ThermalCalculationService
    return ThermalCalculationService(db)


def resolve_location(db: Session, location_id: Optional[str] = None) -> LocationModel:
    """Resolve a location id; fall back to the first ward."""
    if location_id:
        row = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f"location {location_id!r} not found")
        return row
    row = (
        db.query(LocationModel)
        .filter(LocationModel.type.in_(["ward", "point", "city"]))
        .order_by(LocationModel.location_id)
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No locations available; seed the database first",
        )
    return row


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Tolerant ISO-8601 parse (naive → UTC). Raises HTTP 422 on garbage."""
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    candidates = [cleaned, cleaned.replace(" ", "+")]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"invalid datetime: {value!r}",
    )


def parse_window(
    start: Optional[str],
    end: Optional[str],
    hours: int = 48,
) -> tuple[datetime, datetime]:
    """Return (start, end). Missing bounds default to the last ``hours``."""
    end_dt = parse_datetime(end) or utcnow().replace(minute=0, second=0, microsecond=0)
    start_dt = parse_datetime(start) or (end_dt - timedelta(hours=hours))
    return start_dt, end_dt