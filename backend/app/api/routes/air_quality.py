"""Air-quality observations endpoint — canonical schema only."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.air_quality import AirQualityObservation
from ...services.ingest import ingest_air_quality
from ..dependencies import parse_window, resolve_location

router = APIRouter()


class AirQualityList(BaseModel):
    observations: List[AirQualityObservation]
    count: int = 0


@router.get(
    "/api/v1/air-quality",
    response_model=AirQualityList,
    tags=["air-quality"],
)
def get_air_quality(
    location_id: Optional[str] = Query(default=None),
    start: Optional[str] = Query(default=None, description="ISO-8601 start (UTC)"),
    end: Optional[str] = Query(default=None, description="ISO-8601 end (UTC)"),
    seed: int = Query(default=2026, ge=0),
    db: Session = Depends(get_db),
) -> AirQualityList:
    """Return canonical air-quality observations for a location window."""
    loc = resolve_location(db, location_id)
    start_dt, end_dt = parse_window(start, end, hours=48)
    canonical, _tracker = ingest_air_quality(db, loc.location_id, start_dt, end_dt, seed=seed)
    return AirQualityList(observations=canonical, count=len(canonical))