"""Canonical health-outcome data contract.

KESHAV learns HEAT → HEALTH relationships from AGGREGATED, DE-IDENTIFIED health
outcomes only. This schema deliberately contains NO personally identifiable
information: no name, phone, Aadhaar, home address or medical record number.

Designed around: aggregation, de-identification, data minimization and purpose
limitation.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from ..core.enums import HealthAggregationLevel, QualityFlag
from .common import Provenance, QualityAssessment, TimeWindow


class HealthOutcome(BaseModel):
    """Aggregated, de-identified health outcome for an area and time period."""

    outcome_id: str
    location_id: str
    time_period: TimeWindow
    aggregation_level: HealthAggregationLevel

    heat_illness_cases: Optional[int] = Field(default=None, ge=0)
    emergency_visits: Optional[int] = Field(default=None, ge=0)
    hospital_admissions: Optional[int] = Field(default=None, ge=0)
    respiratory_admissions: Optional[int] = Field(default=None, ge=0)
    cardiovascular_admissions: Optional[int] = Field(default=None, ge=0)
    mortality_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Only where lawfully and ethically available; aggregated only",
    )
    surveillance_indicators: Optional[dict] = None

    source: str
    provider: str
    quality_flag: QualityFlag = QualityFlag.VALID
    quality_assessment: Optional[QualityAssessment] = None
    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    provenance: Optional[Provenance] = None

    # Explicit guardrails: this contract never carries individual identifiers.
    # (kept as documentation-of-intent on the schema)
    _forbidden_identifiers = frozenset(
        {"name", "phone", "aadhaar", "address", "mrn", "patient_id"}
    )


class HealthOutcomeList(BaseModel):
    outcomes: List[HealthOutcome]
    count: int = 0