"""Canonical health-outcome adapter. Aggregated & de-identified only."""
from __future__ import annotations

from typing import Dict

from ..schemas.common import Provenance, TimeWindow
from ..schemas.health import HealthAggregationLevel, HealthOutcome  # noqa: F401
from ..schemas.health import HealthOutcome as HealthOutcomeSchema
from ..services.quality import assess_health
from ..utils.ids import new_record_id
from .common import BaseAdapter


class HealthOutcomeAdapter(BaseAdapter):
    """Maps provider-native aggregated outcome rows to the canonical contract.

    Refuses to carry any identifiable field (guard against future misuse).
    """

    adapter_name = "health.mock.v1"
    default_source = "mock"

    _IDENTIFIERS = {"name", "phone", "aadhaar", "address", "mrn", "patient_id"}

    def to_record(self, raw: Dict[str, object]) -> HealthOutcomeSchema:
        forbidden = self._IDENTIFIERS.intersection({k.lower() for k in raw})
        if forbidden:
            raise ValueError(f"Identifiable fields not allowed in health data: {sorted(forbidden)}")

        period_start = raw["period_start"]  # type: ignore[index]
        period_end = raw["period_end"]  # type: ignore[index]
        counts: Dict[str, object] = {
            "heat_illness_cases": raw.get("heat_illness_cases"),
            "emergency_visits": raw.get("emergency_visits"),
            "hospital_admissions": raw.get("hospital_admissions"),
            "respiratory_admissions": raw.get("respiratory_admissions"),
            "cardiovascular_admissions": raw.get("cardiovascular_admissions"),
            "mortality_count": raw.get("mortality_count"),
        }
        assessment = assess_health(counts)
        prov = Provenance(
            source="mock",
            provider="mock_health",
            adapter=self.adapter_name,
            source_timestamp=period_start,
            quality_status=assessment.flag,
        )
        return HealthOutcomeSchema(
            outcome_id=new_record_id("hlth"),
            location_id=raw["location_id"],  # type: ignore[index]
            time_period=TimeWindow(start=period_start, end=period_end),
            aggregation_level=HealthAggregationLevel.DAILY_AREA,
            heat_illness_cases=counts.get("heat_illness_cases"),  # type: ignore[arg-type]
            emergency_visits=counts.get("emergency_visits"),  # type: ignore[arg-type]
            hospital_admissions=counts.get("hospital_admissions"),  # type: ignore[arg-type]
            respiratory_admissions=counts.get("respiratory_admissions"),  # type: ignore[arg-type]
            cardiovascular_admissions=counts.get("cardiovascular_admissions"),  # type: ignore[arg-type]
            mortality_count=counts.get("mortality_count"),  # type: ignore[arg-type]
            surveillance_indicators=raw.get("surveillance_indicators"),  # type: ignore[arg-type]
            source="mock",
            provider="mock_health",
            quality_flag=assessment.flag,
            quality_assessment=assessment,
            provenance=prov,
        )