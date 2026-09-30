"""Weather observations endpoint — canonical schema only."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.weather import WeatherObservationList
from ...services.ingest import ingest_weather
from ..dependencies import parse_window, resolve_location

router = APIRouter()


@router.get("/api/v1/weather", response_model=WeatherObservationList, tags=["weather"])
def get_weather(
    location_id: Optional[str] = Query(default=None),
    start: Optional[str] = Query(default=None, description="ISO-8601 start (UTC)"),
    end: Optional[str] = Query(default=None, description="ISO-8601 end (UTC)"),
    seed: int = Query(default=2026, ge=0),
    db: Session = Depends(get_db),
) -> WeatherObservationList:
    loc = resolve_location(db, location_id)
    start_dt, end_dt = parse_window(start, end, hours=48)
    canonical, _tracker = ingest_weather(db, loc.location_id, start_dt, end_dt, seed=seed)
    return WeatherObservationList(observations=canonical, count=len(canonical))