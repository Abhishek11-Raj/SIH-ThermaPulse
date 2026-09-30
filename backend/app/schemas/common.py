"""Common canonical contract types: provenance, spatial/temporal references,
quality assessments, freshness and coverage.

Everything here is meant to be re-used by all KESHAV data products so that
provenance and quality are never lost during transformation.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..core.enums import (
    CoverageClass,
    FreshnessStatus,
    QualityFlag,
    SpatialReferenceType,
    SpatialResolutionUnit,
    TemporalResolutionUnit,
    TimeWindowType,
)


class Provenance(BaseModel):
    """Traceability for every data record.

    Helps answer: "Where did this value come from?"
    """

    source: str = Field(..., description="Source system, e.g. 'imd', 'mock_weather'")
    provider: str = Field(..., description="Provider name inside the source")
    adapter: str = Field(default="", description="Adapter that produced the canonical record")
    source_timestamp: Optional[datetime] = None
    ingestion_timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="When KESHAV ingested this record",
    )
    version: Optional[str] = Field(default=None, description="Provider/model version")
    quality_status: QualityFlag = QualityFlag.VALID
    notes: List[str] = Field(default_factory=list)


class SpatialReference(BaseModel):
    """How a record is located in space.

    No scientific interpolation is performed in Step 1; this abstraction simply
    records the geometry type and native resolution so later engines can align.
    """

    ref_type: SpatialReferenceType = SpatialReferenceType.POINT
    resolution_value: Optional[float] = Field(
        default=None, description="Size of one cell/resolution unit"
    )
    resolution_unit: SpatialResolutionUnit = SpatialResolutionUnit.DEGREES
    geometry_reference: Optional[str] = Field(
        default=None, description="External geometry id/URL (GIS integration later)"
    )
    crs: Optional[str] = Field(default=None, description="Coordinate reference system")


class TemporalReference(BaseModel):
    """How a record is located in time (native resolution preserved)."""

    ref_type: TimeWindowType = TimeWindowType.POINT
    resolution_value: Optional[float] = None
    resolution_unit: TemporalResolutionUnit = TemporalResolutionUnit.HOUR


class TimeWindow(BaseModel):
    """An open/closed interval for alignment between different sources."""

    start: datetime
    end: datetime

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment <= self.end

    def overlaps(self, other: "TimeWindow") -> bool:
        return self.start <= other.end and other.start <= self.end


class LocationMapping(BaseModel):
    """Maps source-native geo identifiers to KESHAV canonical locations."""

    canonical_location_id: str
    source_id: str
    source_geo_identifier: str
    matched_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    match_quality: QualityFlag = QualityFlag.VALID
    notes: List[str] = Field(default_factory=list)


class QualityIssue(BaseModel):
    """A single structured quality finding."""

    code: str = Field(..., description="Stable machine-readable code, e.g. 'out_of_range'")
    variable: Optional[str] = None
    severity: QualityFlag = QualityFlag.SUSPECT
    message: str = Field(default="")


class QualityAssessment(BaseModel):
    """Structured result of evaluating one record."""

    flag: QualityFlag = QualityFlag.VALID
    missing_variables: List[str] = Field(default_factory=list)
    issues: List[QualityIssue] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.utcnow())

    def summarize(self) -> str:
        codes = [i.code for i in self.issues]
        return f"{self.flag.value}: {','.join(codes) or 'ok'}"


class Freshness(BaseModel):
    """Freshness of one source at a point in time.

    Cadences are domain-specific (weather ≈ hourly, health ≈ daily, satellite
    ≈ coarser). The status is computed relative to the record's native cadence.
    """

    source: str
    provider: str
    domain: str
    last_observed_at: Optional[datetime] = None
    last_ingestion_at: Optional[datetime] = None
    expected_update_frequency: Optional[str] = None
    status: FreshnessStatus = FreshnessStatus.UNAVAILABLE


class VariableCoverage(BaseModel):
    """Coverage of a single variable for a location."""

    variable: str
    expected_records: int
    present_records: int
    missing_records: int = 0
    missingness_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    span_start: Optional[datetime] = None
    span_end: Optional[datetime] = None


class CoverageReport(BaseModel):
    """Spatial/temporal/variable coverage for one location.

    Encoding the principle: no data must never be interpreted as "low risk".
    Missing data raises uncertainty; low coverage yields lower confidence.
    """

    model_config = ConfigDict(extra="ignore")

    location_id: str
    domain: str
    provider: str
    window: Optional[TimeWindow] = None
    variable_coverage: List[VariableCoverage] = Field(default_factory=list)
    spatial_resolution: SpatialReference = Field(default_factory=SpatialReference)
    temporal_resolution: TemporalReference = Field(default_factory=TemporalReference)
    overall_missingness_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    coverage_class: CoverageClass = CoverageClass.DATA_POOR
    equity_note: str = Field(
        default=(
            "Data-poor locations yield higher uncertainty and lower confidence. "
            "No data is never treated as low risk."
        ),
    )


class CoverageByLocation(BaseModel):
    """Coverage rollup across locations — the basis for equity auditing."""

    location_id: str
    location_name: Optional[str] = None
    domains: List[CoverageReport] = Field(default_factory=list)

    def overall_missingness(self) -> float:
        if not self.domains:
            return 1.0
        return sum(d.overall_missingness_rate for d in self.domains) / len(self.domains)