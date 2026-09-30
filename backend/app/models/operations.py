"""Operational ORM models: data-quality records, ingestion logs, provider status
and audit logs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class DataQualityRecord(Base):
    __tablename__ = "data_quality_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    record_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    quality_flag: Mapped[str] = mapped_column(String(16), default="VALID", index=True)
    missing_variables: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    issues: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="STARTED", index=True)
    records_received: Mapped[int] = mapped_column(Integer, default=0)
    records_accepted: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    records_flagged: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    # --- Step 2 additions (nullable, safe to add to existing databases) -------
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    ingestion_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fallback_used: Mapped[Optional[bool]] = mapped_column(nullable=True)
    fallback_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class ProviderStatus(Base):
    __tablename__ = "provider_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    last_successful_request_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    auth_configured: Mapped[bool] = mapped_column(default=False)
    freshness: Mapped[str] = mapped_column(String(16), default="UNAVAILABLE")
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    last_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)