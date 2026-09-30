"""Ingestion status/logs endpoints (Step 2).

What these exist for: at a glance, an operator (or the dashboard) can answer
"did ingestion succeed, how long did it take, did it fall back to cache or
mock, and are failure rates climbing?" without digging through log files.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.operations import IngestionLog as IngestionLogModel
from ...schemas.system import IngestionRunDetail, IngestionStatusResponse

router = APIRouter()


def _run_to_detail(row: IngestionLogModel) -> IngestionRunDetail:
    return IngestionRunDetail(
        id=row.id,
        ingestion_id=row.ingestion_id,
        source=row.source,
        provider=row.provider,
        domain=row.domain,
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        records_received=row.records_received,
        records_accepted=row.records_accepted,
        records_rejected=row.records_rejected,
        records_flagged=row.records_flagged,
        error_message=row.error_message,
        quality_summary=row.quality_summary,
        duration_ms=row.duration_ms,
        fallback_used=row.fallback_used,
        fallback_source=row.fallback_source,
    )


@router.get(
    "/api/v1/ingestion/status",
    response_model=IngestionStatusResponse,
    tags=["system"],
)
def ingestion_status(db: Session = Depends(get_db)) -> IngestionStatusResponse:
    rows = db.query(IngestionLogModel).order_by(IngestionLogModel.started_at.desc()).all()
    by_status: dict = {}
    by_source: dict = {}
    fallback_count = 0
    durations = [r.duration_ms for r in rows if r.duration_ms is not None]
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        key = row.source or "unknown"
        by_source[key] = by_source.get(key, 0) + 1
        if row.fallback_used:
            fallback_count += 1
    return IngestionStatusResponse(
        total_runs=len(rows),
        by_status=by_status,
        by_source=by_source,
        fallback_count=fallback_count,
        average_duration_ms=int(sum(durations) / len(durations)) if durations else None,
        recent_runs=[_run_to_detail(r) for r in rows[:25]],
    )


@router.get(
    "/api/v1/ingestion/logs",
    response_model=List[IngestionRunDetail],
    tags=["system"],
)
def ingestion_logs(
    limit: int = Query(50, ge=1, le=500),
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[IngestionRunDetail]:
    q = db.query(IngestionLogModel)
    if source:
        q = q.filter(IngestionLogModel.source == source)
    if status:
        q = q.filter(IngestionLogModel.status == status)
    rows = q.order_by(IngestionLogModel.started_at.desc()).limit(limit).all()
    return [_run_to_detail(r) for r in rows]