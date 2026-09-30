"""Data-quality endpoint: recent quality records + rollup summary."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.operations import DataQualityRecord as QualityModel
from ...schemas.system import DataQualitySummary

router = APIRouter()


@router.get("/api/v1/data-quality", response_model=dict, tags=["data-quality"])
def data_quality(
    source: Optional[str] = Query(default=None),
    flag: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    """Recent data-quality records (records flagged as non-VALID) + rollup."""
    q = db.query(QualityModel)
    if source:
        q = q.filter(QualityModel.source == source)
    if flag:
        q = q.filter(QualityModel.quality_flag == flag)
    rows = q.order_by(QualityModel.checked_at.desc()).limit(limit).all()

    roll_query = db.query(
        QualityModel.quality_flag, func.count(QualityModel.id)
    ).group_by(QualityModel.quality_flag)
    if source:
        roll_query = roll_query.filter(QualityModel.source == source)
    by_flag = {k: int(v) for k, v in roll_query.all()}
    total = db.query(func.count(QualityModel.id)).scalar() or 0
    flagged = sum(v for k, v in by_flag.items() if k != "VALID")

    records = [
        {
            "record_id": r.id,
            "source": r.source,
            "provider": r.provider,
            "domain": r.domain,
            "record_reference": r.record_reference,
            "quality_flag": r.quality_flag,
            "missing_variables": r.missing_variables or [],
            "issues": r.issues or [],
            "checked_at": r.checked_at,
        }
        for r in rows
    ]
    summary = DataQualitySummary(
        total_records=total,
        by_flag=by_flag,
        flagged_count=flagged,
        rejected_count=by_flag.get("INVALID", 0),
    ).model_dump(mode="json")
    return {"summary": summary, "records": records, "count": len(records)}


@router.get("/api/v1/data-quality/audit", response_model=dict, tags=["data-quality"])
def data_quality_audit(
    db: Session = Depends(get_db),
) -> dict:
    """Quality audit grouped by domain, provider and location.

    Reports rejected/flagged counts and missing-variable tallies per group so
    audits can see which sources fail validation most often — without exposing
    raw record details.
    """
    rows = db.query(QualityModel).all()
    by_domain: dict = {}
    by_provider: dict = {}
    by_location: dict = {}
    missing_vars_tally: dict = {}
    for r in rows:
        domain = by_domain.setdefault(r.domain, {"flagged": 0, "rejected": 0, "total": 0})
        provider = by_provider.setdefault(r.provider, {"flagged": 0, "rejected": 0, "total": 0})
        location = by_location.setdefault(r.record_reference or "none", {"flagged": 0, "rejected": 0, "total": 0})
        for bucket in (domain, provider, location):
            bucket["total"] += 1
            if r.quality_flag != "VALID":
                bucket["flagged"] += 1
            if r.quality_flag == "INVALID":
                bucket["rejected"] += 1
        for var in r.missing_variables or []:
            missing_vars_tally[var] = missing_vars_tally.get(var, 0) + 1
    return {
        "groups": {
            "by_domain": by_domain,
            "by_provider": by_provider,
            "by_location": by_location,
        },
        "missing_variables_tally": missing_vars_tally,
        "note": (
            "Counts flagged and rejected records per group. Missing variables "
            "are tallied separately (missing never equals zero)."
        ),
    }