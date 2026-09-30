"""Forecast endpoint — canonical weather forecast schema.

Distinct from observations: preserves issued_at vs valid_from/valid_to so a
forecast track record can be built in later stages.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.forecast import WeatherForecastList
from ...services.ingest import ingest_forecast
from ...utils.time import utcnow
from ..dependencies import resolve_location

router = APIRouter()


@router.get("/api/v1/forecast", response_model=WeatherForecastList, tags=["forecast"])
def get_forecast(
    location_id: Optional[str] = Query(default=None),
    issued_at: Optional[str] = Query(default=None, description="ISO-8601 issue time (UTC)"),
    horizon_hours: int = Query(default=120, ge=1, le=240),
    seed: int = Query(default=2026, ge=0),
    db: Session = Depends(get_db),
) -> WeatherForecastList:
    loc = resolve_location(db, location_id)
    issue = (
        datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        if issued_at
        else utcnow().replace(minute=0, second=0, microsecond=0)
    )
    canonical, _tracker = ingest_forecast(db, loc.location_id, issue, horizon_hours, seed=seed)
    return WeatherForecastList(forecasts=canonical, count=len(canonical))