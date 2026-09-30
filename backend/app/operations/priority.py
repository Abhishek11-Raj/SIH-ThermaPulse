"""Operational priority engine evaluating multi-criteria decision scores for city wards."""
from __future__ import annotations

from typing import List
from .schemas import (
    CityPriorityListResponse,
    FactorContribution,
    OperationalPriorityRequest,
    OperationalPriorityScoreResponse,
)
from ..utils.time import utcnow


class OperationalPriorityEngine:
    """Evaluates multi-criteria operational priority across health risk, thermal load, and infrastructure."""

    WEIGHTS = {
        "health_risk": 0.25,
        "thermal_stress": 0.20,
        "nighttime_deficit": 0.15,
        "vulnerable_population": 0.15,
        "outdoor_workers": 0.10,
        "resource_shortage": 0.10,
        "hospital_surge": 0.05,
    }

    def evaluate_priority(self, req: OperationalPriorityRequest) -> OperationalPriorityScoreResponse:
        contributions: List[FactorContribution] = []

        # 1. Health Risk
        norm_hr = req.health_risk_probability * 100.0
        c_hr = norm_hr * self.WEIGHTS["health_risk"]
        contributions.append(
            FactorContribution(
                factor_name="Health Risk Probability",
                raw_value=req.health_risk_probability,
                normalized_score=norm_hr,
                weight=self.WEIGHTS["health_risk"],
                weighted_contribution=c_hr,
                data_source="Step 4 AI Risk Model",
                confidence="HIGH" if not req.is_out_of_distribution else "MEDIUM",
            )
        )

        # 2. Thermal Stress Score
        norm_ts = min(100.0, max(0.0, (req.thermal_stress_score - 25.0) * 3.5))
        c_ts = norm_ts * self.WEIGHTS["thermal_stress"]
        contributions.append(
            FactorContribution(
                factor_name="Thermal Stress Index",
                raw_value=req.thermal_stress_score,
                normalized_score=norm_ts,
                weight=self.WEIGHTS["thermal_stress"],
                weighted_contribution=c_ts,
                data_source="Step 3 Thermal Engine",
                confidence="HIGH",
            )
        )

        # 3. Nighttime Recovery Deficit
        norm_nt = min(100.0, req.nighttime_recovery_deficit * 25.0)
        c_nt = norm_nt * self.WEIGHTS["nighttime_deficit"]
        contributions.append(
            FactorContribution(
                factor_name="Nighttime Recovery Deficit",
                raw_value=req.nighttime_recovery_deficit,
                normalized_score=norm_nt,
                weight=self.WEIGHTS["nighttime_deficit"],
                weighted_contribution=c_nt,
                data_source="Step 3 Nocturnal Engine",
                confidence="HIGH",
            )
        )

        # 4. Vulnerable Population Fraction
        norm_vp = req.vulnerable_population_fraction * 100.0
        c_vp = norm_vp * self.WEIGHTS["vulnerable_population"]
        contributions.append(
            FactorContribution(
                factor_name="Vulnerable Population Share",
                raw_value=req.vulnerable_population_fraction,
                normalized_score=norm_vp,
                weight=self.WEIGHTS["vulnerable_population"],
                weighted_contribution=c_vp,
                data_source="Step 1 Demographic Census",
                confidence="HIGH",
            )
        )

        # 5. Outdoor Worker Fraction
        norm_ow = req.outdoor_worker_fraction * 100.0
        c_ow = norm_ow * self.WEIGHTS["outdoor_workers"]
        contributions.append(
            FactorContribution(
                factor_name="Outdoor Worker Density",
                raw_value=req.outdoor_worker_fraction,
                normalized_score=norm_ow,
                weight=self.WEIGHTS["outdoor_workers"],
                weighted_contribution=c_ow,
                data_source="Step 1 Livelihood Survey",
                confidence="MEDIUM",
            )
        )

        # 6. Resource Shortage Severity
        norm_rs = req.resource_shortage_severity * 100.0
        c_rs = norm_rs * self.WEIGHTS["resource_shortage"]
        contributions.append(
            FactorContribution(
                factor_name="Resource Shortage Severity",
                raw_value=req.resource_shortage_severity,
                normalized_score=norm_rs,
                weight=self.WEIGHTS["resource_shortage"],
                weighted_contribution=c_rs,
                data_source="Municipal Resource Inventory",
                confidence="HIGH",
            )
        )

        # 7. Hospital Surge Occupancy
        norm_hs = min(100.0, req.hospital_surge_occupancy * 50.0)
        c_hs = norm_hs * self.WEIGHTS["hospital_surge"]
        contributions.append(
            FactorContribution(
                factor_name="Hospital Emergency Surge",
                raw_value=req.hospital_surge_occupancy,
                normalized_score=norm_hs,
                weight=self.WEIGHTS["hospital_surge"],
                weighted_contribution=c_hs,
                data_source="Health System Surveillance",
                confidence="HIGH",
            )
        )

        # Alert severity multiplier bonus
        alert_bonus = 5.0 if req.alert_severity_code == "EXTREME_DANGER" else (3.0 if req.alert_severity_code == "HIGH_RISK" else 0.0)
        contributions.append(
            FactorContribution(
                factor_name="Alert Severity Urgency",
                raw_value=1.0 if alert_bonus > 0 else 0.0,
                normalized_score=alert_bonus * 10.0,
                weight=0.05,
                weighted_contribution=alert_bonus,
                data_source="Step 7 Alert Engine",
                confidence="HIGH",
            )
        )

        raw_score = sum(c.weighted_contribution for c in contributions)

        # Apply OOD / Data Quality Penalty
        penalty = 0.0
        limitations = []
        if req.is_out_of_distribution:
            penalty += 10.0
            limitations.append("Meteorological inputs outside model training distribution; score adjusted with uncertainty buffer.")
        if req.uncertainty_level > 0.3:
            penalty += (req.uncertainty_level * 15.0)
            limitations.append("High forecast epistemic uncertainty present.")

        final_score = round(max(0.0, min(100.0, raw_score - penalty)), 1)

        if final_score >= 80.0:
            level = "CRITICAL"
            rec = "Immediate deployment of mobile hydration and active cooling hubs required within 60 minutes."
        elif final_score >= 65.0:
            level = "URGENT"
            rec = "Pre-position water tankers and alert community health workers within 2 hours."
        elif final_score >= 50.0:
            level = "ELEVATED"
            rec = "Heightened monitoring and scheduled public transit cooling checks."
        elif final_score >= 35.0:
            level = "NORMAL"
            rec = "Standard advisory and routine station maintenance."
        else:
            level = "LOW"
            rec = "Baseline operations."

        return OperationalPriorityScoreResponse(
            location_id=req.location_id,
            priority_score=final_score,
            operational_risk_level=level,
            rank_order=None,
            urgency_recommendation=rec,
            factor_contributions=contributions,
            uncertainty_penalty_applied=round(penalty, 1),
            data_quality_limitations=limitations,
            evaluated_at=utcnow(),
        )

    def rank_city_zones(self, requests: List[OperationalPriorityRequest]) -> CityPriorityListResponse:
        scores = [self.evaluate_priority(r) for r in requests]
        scores.sort(key=lambda x: x.priority_score, reverse=True)

        for idx, s in enumerate(scores):
            s.rank_order = idx + 1

        crit = sum(1 for s in scores if s.operational_risk_level == "CRITICAL")
        urg = sum(1 for s in scores if s.operational_risk_level == "URGENT")

        return CityPriorityListResponse(
            evaluated_at=utcnow(),
            total_wards_evaluated=len(scores),
            critical_wards_count=crit,
            urgent_wards_count=urg,
            ward_rankings=scores,
        )
