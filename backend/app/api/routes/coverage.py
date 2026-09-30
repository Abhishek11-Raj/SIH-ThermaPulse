"""Coverage endpoints — equity-aware data coverage by location."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.common import CoverageByLocation, TimeWindow
from ...services.coverage import (
    aggregate_by_location,
    coverage_reports_from_db,
)
from ...services.coverage_audit import coverage_audit, ingest_status_summary
from ..dependencies import resolve_location

router = APIRouter()


@router.get("/api/v1/coverage", response_model=List[CoverageByLocation], tags=["coverage"])
def get_coverage(
    location_id: Optional[str] = Query(default=None),
    window_hours: int = Query(default=48, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
):
    """Coverage per location across domains (weather, AQ, health, vulnerability).

    Data-poor locations are reported as higher missingness → higher uncertainty.
    No data is never treated as low risk.
    """
    locs = [resolve_location(db, location_id)]
    from datetime import timedelta

    from ...utils.time import utcnow

    end = utcnow()
    start = end - timedelta(hours=window_hours)
    window = TimeWindow(start=start, end=end)
    reports: list = []
    for loc in locs:
        reports.extend(coverage_reports_from_db(db, loc.location_id, window))
    return aggregate_by_location(reports)


@router.get("/api/v1/coverage/audit", response_model=dict, tags=["coverage"])
def get_coverage_audit(
    location_id: Optional[str] = Query(default=None),
    window_hours: int = Query(default=48, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
) -> dict:
    """Cross-cutting coverage & quality audit (locations, variables, temporal,
    spatial, providers; equity-aware)."""
    if location_id:
        resolve_location(db, location_id)
    audit = coverage_audit(db, location_id=location_id, window_hours=window_hours)
    audit["ingestion"] = ingest_status_summary(db)
    return audit