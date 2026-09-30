"""Health-outcomes endpoint — AGGREGATED, DE-IDENTIFIED records only."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.health import HealthOutcomeList
from ...services.ingest import ingest_health_outcomes
from ..dependencies import parse_window, resolve_location

router = APIRouter()


@router.get("/api/v1/health-outcomes", response_model=HealthOutcomeList, tags=["health"])
def get_health_outcomes(
    location_id: Optional[str] = Query(default=None),
    start: Optional[str] = Query(default=None, description="ISO-8601 period start"),
    end: Optional[str] = Query(default=None, description="ISO-8601 period end"),
    seed: int = Query(default=2026, ge=0),
    db: Session = Depends(get_db),
) -> HealthOutcomeList:
    loc = resolve_location(db, location_id)
    start_dt, end_dt = parse_window(start, end, hours=48)
    canonical, _tracker = ingest_health_outcomes(
        db, loc.location_id, start_dt, end_dt, seed=seed
    )
    return HealthOutcomeList(outcomes=canonical, count=len(canonical))