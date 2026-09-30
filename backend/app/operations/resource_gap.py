"""Resource gap analysis evaluating deficits between modeled demand and available protective infrastructure."""
from __future__ import annotations

import math
import uuid
from typing import List
from .schemas import ResourceGapResponse, ResourceGapSummaryResponse, ResourceResponse
from ..utils.time import utcnow


class ResourceGapEngine:
    """Evaluates physical and mobile resource deficits."""

    DEMAND_NORMS = {
        "COOLING_CENTER": 0.08,  # 8% of vulnerable population requires public cooling shelter
        "DRINKING_WATER_POINT": 2.5,  # 2.5 liters/person/day for outdoor & vulnerable
        "HYDRATION_ORS_STATION": 0.35,  # 0.35 ORS packets per vulnerable person
        "AMBULANCE": 1.0 / 25000.0,  # 1 heat-equipped ambulance per 25k residents
    }

    def evaluate_zone_gaps(
        self,
        location_id: str,
        population_total: int,
        vulnerable_population: int,
        outdoor_workers: int,
        health_risk_prob: float,
        available_resources: List[ResourceResponse],
    ) -> List[ResourceGapResponse]:
        gaps: List[ResourceGapResponse] = []

        # Risk scaling factor
        risk_factor = 1.0 + (health_risk_prob * 0.5)

        # 1. Cooling Shelter Demand vs Supply
        demanded_cooling = round(vulnerable_population * self.DEMAND_NORMS["COOLING_CENTER"] * risk_factor)
        avail_cooling = sum(
            r.available_capacity
            for r in available_resources
            if r.resource_type == "COOLING_CENTER" and r.status in ["AVAILABLE", "LIMITED"]
        )
        def_cooling = max(0.0, demanded_cooling - avail_cooling)
        cov_cooling = round(min(1.0, avail_cooling / max(1.0, demanded_cooling)), 2)

        gaps.append(
            ResourceGapResponse(
                gap_id=f"GAP-COOL-{location_id}-{uuid.uuid4().hex[:6]}",
                location_id=location_id,
                resource_type="COOLING_CENTER",
                demanded_capacity=float(demanded_cooling),
                available_capacity=float(avail_cooling),
                deficit_capacity=float(def_cooling),
                coverage_ratio=cov_cooling,
                travel_distance_km=1.8,
                travel_time_minutes=22.0,
                unmet_demand_count=int(def_cooling),
                severity="CRITICAL" if cov_cooling < 0.4 else ("HIGH" if cov_cooling < 0.7 else "LOW"),
                actionable_recommendation=f"Deploy {math.ceil(def_cooling / 100.0)} mobile cooling buses or activate community centers.",
                identified_at=utcnow(),
            )
        )

        # 2. Water Capacity Demand vs Supply
        demanded_water = round((outdoor_workers + vulnerable_population * 0.5) * self.DEMAND_NORMS["DRINKING_WATER_POINT"] * risk_factor)
        avail_water = sum(
            r.available_capacity
            for r in available_resources
            if r.resource_type == "DRINKING_WATER_POINT" and r.status in ["AVAILABLE", "LIMITED"]
        )
        def_water = max(0.0, demanded_water - avail_water)
        cov_water = round(min(1.0, avail_water / max(1.0, demanded_water)), 2)

        gaps.append(
            ResourceGapResponse(
                gap_id=f"GAP-WATER-{location_id}-{uuid.uuid4().hex[:6]}",
                location_id=location_id,
                resource_type="DRINKING_WATER_POINT",
                demanded_capacity=float(demanded_water),
                available_capacity=float(avail_water),
                deficit_capacity=float(def_water),
                coverage_ratio=cov_water,
                travel_distance_km=0.6,
                travel_time_minutes=8.0,
                unmet_demand_count=int(def_water / 2.5),
                severity="CRITICAL" if cov_water < 0.5 else ("HIGH" if cov_water < 0.75 else "LOW"),
                actionable_recommendation=f"Dispatch {math.ceil(def_water / 5000.0)} drinking water tankers (5000L capacity).",
                identified_at=utcnow(),
            )
        )

        # 3. ORS Depot Demand vs Supply
        demanded_ors = round(vulnerable_population * self.DEMAND_NORMS["HYDRATION_ORS_STATION"] * risk_factor)
        avail_ors = sum(
            r.available_capacity
            for r in available_resources
            if r.resource_type == "HYDRATION_ORS_STATION" and r.status in ["AVAILABLE", "LIMITED"]
        )
        def_ors = max(0.0, demanded_ors - avail_ors)
        cov_ors = round(min(1.0, avail_ors / max(1.0, demanded_ors)), 2)

        gaps.append(
            ResourceGapResponse(
                gap_id=f"GAP-ORS-{location_id}-{uuid.uuid4().hex[:6]}",
                location_id=location_id,
                resource_type="HYDRATION_ORS_STATION",
                demanded_capacity=float(demanded_ors),
                available_capacity=float(avail_ors),
                deficit_capacity=float(def_ors),
                coverage_ratio=cov_ors,
                travel_distance_km=0.4,
                travel_time_minutes=5.0,
                unmet_demand_count=int(def_ors),
                severity="HIGH" if cov_ors < 0.5 else "LOW",
                actionable_recommendation=f"Replenish {int(def_ors)} ORS packets across ward clinics.",
                identified_at=utcnow(),
            )
        )

        return gaps

    def summarize_city_gaps(self, gaps: List[ResourceGapResponse]) -> ResourceGapSummaryResponse:
        crit = sum(1 for g in gaps if g.severity == "CRITICAL")
        return ResourceGapSummaryResponse(
            evaluated_at=utcnow(),
            total_gaps_count=len(gaps),
            critical_deficits_count=crit,
            gaps=gaps,
        )
