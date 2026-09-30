"""Ingestion logging and orchestration for provider → adapter flows."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from ..core.enums import IngestionStatus
from ..models.operations import IngestionLog as IngestionLogModel
from ..schemas.common import QualityAssessment
from ..services.quality import summarize_flags
from ..utils.time import utcnow


class IngestionTracker:
    """Tracks one ingestion run and persists it to ``ingestion_logs``.

    Step 2 additions: a stable ``ingestion_id``/``request_id``, wall-clock
    ``duration_ms``, and explicit fallback fields so every log answers "was
    this a live fetch, cache replay, or mock fallback?" without ambiguity.
    """

    def __init__(
        self,
        db: Session,
        source: str,
        provider: str,
        domain: str,
        request_id: Optional[str] = None,
    ) -> None:
        self.db = db
        self.source = source
        self.provider = provider
        self.domain = domain
        self.started_at = utcnow()
        self.assessments: List[QualityAssessment] = []
        self.received = 0
        self.rejected = 0
        self.error_message: Optional[str] = None
        self.request_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        self.ingestion_id = f"ing_{uuid.uuid4().hex[:12]}"
        self.fallback_used = False
        self.fallback_source: Optional[str] = None
        self.row: IngestionLogModel = IngestionLogModel(
            source=source,
            provider=provider,
            domain=domain,
            started_at=self.started_at,
            status=IngestionStatus.STARTED.value,
            request_id=self.request_id,
            ingestion_id=self.ingestion_id,
        )
        db.add(self.row)
        db.commit()

    def add_assessment(self, assessment: Optional[QualityAssessment]) -> None:
        if assessment is not None:
            self.assessments.append(assessment)

    def add_flag_summary(self, flags: Sequence[str]) -> None:
        for flag in flags:
            pass  # retained for future dashboard aggregations

    def mark_fallback(self, source: str) -> None:
        self.fallback_used = True
        self.fallback_source = source

    def complete(
        self,
        accepted: int,
        rejected: int = 0,
        duplicate: int = 0,
        error_message: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> IngestionLogModel:
        self.accepted = accepted
        self.duplicate = duplicate
        self.received = accepted + rejected
        self.rejected = rejected
        self.error_message = error_message
        summary = summarize_flags(self.assessments)
        flagged = sum(v for k, v in summary.items() if k != "VALID")
        status = (
            IngestionStatus.FAILED
            if rejected > 0 and accepted == 0
            else IngestionStatus.PARTIAL
            if rejected > 0 or flagged > 0
            else IngestionStatus.SUCCESS
        )
        self.row.status = status.value
        self.row.completed_at = utcnow()
        self.row.duration_ms = max(
            0, int((self.row.completed_at - self.started_at).total_seconds() * 1000)
        )
        self.row.records_received = self.received
        self.row.records_accepted = accepted
        self.row.records_rejected = rejected
        self.row.records_flagged = flagged
        self.row.error_message = error_message
        self.row.quality_summary = summary
        self.row.fallback_used = self.fallback_used
        self.row.fallback_source = self.fallback_source
        if extra:
            for k, v in extra.items():
                setattr(self.row, k, v)
        self.db.commit()
        self.db.refresh(self.row)
        return self.row


def recent_ingestion_logs(
    db: Session, limit: int = 50, source: Optional[str] = None
) -> List[IngestionLogModel]:
    q = db.query(IngestionLogModel)
    if source:
        q = q.filter(IngestionLogModel.source == source)
    return q.order_by(IngestionLogModel.started_at.desc()).limit(limit).all()