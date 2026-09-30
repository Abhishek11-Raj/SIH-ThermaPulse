"""API-facing schemas for data quality, ingestion, provider status and system."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..core.enums import FreshnessStatus, IngestionStatus, ProviderStatus
from .common import QualityIssue, QualityFlag


class DataQualityRecord(BaseModel):
    """A stored quality evaluation for one ingested record."""

    record_id: Optional[str] = None
    source: str
    provider: str
    domain: str
    record_reference: Optional[str] = None
    quality_flag: QualityFlag
    missing_variables: List[str] = Field(default_factory=list)
    issues: List[QualityIssue] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.utcnow())


class DataQualitySummary(BaseModel):
    """Rollup of quality flags, optionally filtered by source/provider."""

    total_records: int = 0
    by_flag: Dict[str, int] = Field(default_factory=dict)
    rejected_count: int = 0
    flagged_count: int = 0


class IngestionLogSchema(BaseModel):
    """One ingestion run (start → end) for a source+provider."""

    ingestion_id: Optional[int] = None
    source: str
    provider: str
    domain: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: IngestionStatus = IngestionStatus.STARTED
    records_received: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    records_flagged: int = 0
    error_message: Optional[str] = None
    quality_summary: Optional[Dict[str, Any]] = None


class ProviderHealth(BaseModel):
    """Public-safe provider health. API keys / auth secrets are NEVER exposed."""

    name: str
    domain: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    provider_type: str = "mock"          # mock | real (Step 2)
    enabled: bool = True                 # registration/enablement gate (Step 2)
    last_successful_request_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_latency_ms: Optional[int] = None
    auth_configured: bool = False
    freshness: FreshnessStatus = FreshnessStatus.UNAVAILABLE
    failure_count: int = 0
    success_count: int = 0


class IngestionRunDetail(BaseModel):
    """One ingestion run including Step 2 latency/fallback metadata."""

    id: Optional[int] = None
    ingestion_id: Optional[str] = None
    source: str
    provider: str
    domain: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: IngestionStatus = IngestionStatus.STARTED
    records_received: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    records_flagged: int = 0
    error_message: Optional[str] = None
    quality_summary: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    fallback_used: Optional[bool] = None
    fallback_source: Optional[str] = None


class IngestionStatusResponse(BaseModel):
    """Rollup of ingestion activity plus recent run details."""

    total_runs: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_source: Dict[str, int] = Field(default_factory=dict)
    fallback_count: int = 0
    average_duration_ms: Optional[int] = None
    recent_runs: List[IngestionRunDetail] = Field(default_factory=list)


class SystemInfo(BaseModel):
    """Safe system information (no secrets, no credentials)."""

    application: str
    environment: str
    api_version: str
    data_pipeline_version: str
    model_version: Optional[str] = None
    mock_mode: bool
    database_dialect: str
    utc_time: datetime
    security: Dict[str, Any] = Field(default_factory=dict)
    note: str


class ServiceHealth(BaseModel):
    status: str = "ok"
    application: str
    api_version: str
    environment: str
    database: str
    utc_time: datetime