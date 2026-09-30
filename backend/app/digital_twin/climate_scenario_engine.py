"""Climate Scenario Simulation Engine: Long-term warming pathways,
compound heat-pollution stress, and demographic exposure projections.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..models.digital_twin import ClimateScenarioDB
from ..models.thermal import ThermalStressResult
from ..models.city_operations import OperationalZoneDB
from ..utils.time import utcnow
from .schemas import (
    ClimateScenarioCreate,
    ClimateScenarioResponse,
    ClimateSimulationRequest,
    ClimateSimulationResponse,
    ScenarioCategory,
)

BUILTIN_SCENARIOS = [
    {
        "scenario_id": "SSP2_45_2030",
        "scenario_name": "Moderate Warming Pathway (2030)",
        "category": ScenarioCategory.MODERATE_WARMING.value,
        "time_horizon": "2030",
        "delta_tmax_c": 1.2,
        "delta_tmin_c": 1.4,
        "delta_heatwave_days": 4.5,
        "delta_humidity_pct": 2.0,
        "delta_pm25_pct": -5.0,
        "urban_density_factor": 1.05,
        "source": "IPCC AR6 Working Group I (SSP2-4.5 South Asia)",
        "uncertainty_range": {"tmax_p10": 0.8, "tmax_p90": 1.7},
    },
    {
        "scenario_id": "SSP2_45_2050",
        "scenario_name": "Moderate Warming Mid-Century (2050)",
        "category": ScenarioCategory.MODERATE_WARMING.value,
        "time_horizon": "2050",
        "delta_tmax_c": 2.1,
        "delta_tmin_c": 2.5,
        "delta_heatwave_days": 12.0,
        "delta_humidity_pct": 3.5,
        "delta_pm25_pct": -10.0,
        "urban_density_factor": 1.15,
        "source": "IPCC AR6 Working Group I (SSP2-4.5 South Asia)",
        "uncertainty_range": {"tmax_p10": 1.5, "tmax_p90": 2.9},
    },
    {
        "scenario_id": "SSP5_85_2030",
        "scenario_name": "High Emissions Warming Pathway (2030)",
        "category": ScenarioCategory.HIGH_WARMING.value,
        "time_horizon": "2030",
        "delta_tmax_c": 1.8,
        "delta_tmin_c": 2.2,
        "delta_heatwave_days": 8.0,
        "delta_humidity_pct": 1.5,
        "delta_pm25_pct": 5.0,
        "urban_density_factor": 1.08,
        "source": "IPCC AR6 Working Group I (SSP5-8.5 Regional Downscaling)",
        "uncertainty_range": {"tmax_p10": 1.2, "tmax_p90": 2.4},
    },
    {
        "scenario_id": "SSP5_85_2050",
        "scenario_name": "Extreme Climate Scenario (2050)",
        "category": ScenarioCategory.EXTREME_HEAT.value,
        "time_horizon": "2050",
        "delta_tmax_c": 3.6,
        "delta_tmin_c": 4.2,
        "delta_heatwave_days": 24.0,
        "delta_humidity_pct": 4.0,
        "delta_pm25_pct": 15.0,
        "urban_density_factor": 1.25,
        "source": "IPCC AR6 Working Group I (SSP5-8.5 Severe Case)",
        "uncertainty_range": {"tmax_p10": 2.8, "tmax_p90": 4.6},
    },
    {
        "scenario_id": "HOTTER_NIGHTS_2040",
        "scenario_name": "Compound Nocturnal Heat Stress (2040)",
        "category": ScenarioCategory.HOTTER_NIGHTS.value,
        "time_horizon": "2040",
        "delta_tmax_c": 1.9,
        "delta_tmin_c": 3.8,
        "delta_heatwave_days": 16.0,
        "delta_humidity_pct": 5.0,
        "delta_pm25_pct": 0.0,
        "urban_density_factor": 1.20,
        "source": "Urban Heat Island + CMIP6 Nocturnal Ensemble",
        "uncertainty_range": {"tmin_p10": 2.9, "tmin_p90": 4.8},
    },
    {
        "scenario_id": "COMPOUND_HEAT_PM25_2035",
        "scenario_name": "Compound Heat & PM2.5 Air Pollution (2035)",
        "category": ScenarioCategory.COMPOUND_HEAT_POLLUTION.value,
        "time_horizon": "2040",
        "delta_tmax_c": 2.2,
        "delta_tmin_c": 2.4,
        "delta_heatwave_days": 14.0,
        "delta_humidity_pct": 1.0,
        "delta_pm25_pct": 25.0,
        "urban_density_factor": 1.12,
        "source": "Integrated Air Quality & Climate Projection Modeling",
        "uncertainty_range": {"tmax_p10": 1.6, "tmax_p90": 2.8},
    },
]


class ClimateScenarioEngine:
    """Simulates climate projection scenarios and computes health risk deltas."""

    @classmethod
    def seed_builtin_scenarios(cls, db: Session) -> None:
        """Ensures all standard scientific warming scenarios exist in the database."""
        for item in BUILTIN_SCENARIOS:
            existing = db.execute(
                select(ClimateScenarioDB).where(ClimateScenarioDB.scenario_id == item["scenario_id"])
            ).scalar_one_or_none()
            if not existing:
                row = ClimateScenarioDB(
                    scenario_id=item["scenario_id"],
                    scenario_name=item["scenario_name"],
                    category=item["category"],
                    time_horizon=item["time_horizon"],
                    delta_tmax_c=item["delta_tmax_c"],
                    delta_tmin_c=item["delta_tmin_c"],
                    delta_heatwave_days=item["delta_heatwave_days"],
                    delta_humidity_pct=item["delta_humidity_pct"],
                    delta_pm25_pct=item["delta_pm25_pct"],
                    urban_density_factor=item["urban_density_factor"],
                    source=item["source"],
                    uncertainty_range=item["uncertainty_range"],
                    is_synthetic=False,
                    created_at=utcnow(),
                )
                db.add(row)
        db.commit()

    @classmethod
    def list_scenarios(cls, db: Session) -> List[ClimateScenarioResponse]:
        """Lists all available climate projection scenarios."""
        cls.seed_builtin_scenarios(db)
        rows = db.execute(select(ClimateScenarioDB).order_by(ClimateScenarioDB.time_horizon)).scalars().all()
        return [ClimateScenarioResponse.model_validate(r) for r in rows]

    @classmethod
    def create_scenario(cls, db: Session, req: ClimateScenarioCreate) -> ClimateScenarioResponse:
        """Registers a custom user-defined climate scenario."""
        scenario_id = req.scenario_id or f"scen_{uuid.uuid4().hex[:8]}"
        row = ClimateScenarioDB(
            scenario_id=scenario_id,
            scenario_name=req.scenario_name,
            category=req.category.value,
            time_horizon=req.time_horizon,
            delta_tmax_c=req.delta_tmax_c,
            delta_tmin_c=req.delta_tmin_c,
            delta_heatwave_days=req.delta_heatwave_days,
            delta_humidity_pct=req.delta_humidity_pct,
            delta_pm25_pct=req.delta_pm25_pct,
            urban_density_factor=req.urban_density_factor,
            assumptions=req.assumptions,
            source=req.source,
            uncertainty_range=req.uncertainty_range,
            is_synthetic=False,
            created_at=utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return ClimateScenarioResponse.model_validate(row)

    @classmethod
    def simulate_scenario(
        cls, db: Session, req: ClimateSimulationRequest
    ) -> ClimateSimulationResponse:
        """Simulates the impact of a climate scenario on local heat index and health risk."""
        cls.seed_builtin_scenarios(db)

        scenario = db.execute(
            select(ClimateScenarioDB).where(ClimateScenarioDB.scenario_id == req.scenario_id)
        ).scalar_one_or_none()

        if not scenario:
            raise ValueError(f"Climate scenario '{req.scenario_id}' not found")

        # Baseline thermal telemetry
        thermal = db.execute(
            select(ThermalStressResult)
            .where(ThermalStressResult.location_id == req.location_id)
            .order_by(desc(ThermalStressResult.timestamp))
        ).scalars().first()

        def compute_hi(temp_c: float, rh_pct: float) -> float:
            t_f = temp_c * 9.0 / 5.0 + 32.0
            hi_f = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh_pct * 0.094))
            if hi_f >= 80.0:
                hi_f = (
                    -42.379
                    + 2.04901523 * t_f
                    + 10.14333127 * rh_pct
                    - 0.22475541 * t_f * rh_pct
                    - 0.00683783 * t_f * t_f
                    - 0.05481717 * rh_pct * rh_pct
                    + 0.00122874 * t_f * t_f * rh_pct
                    + 0.00085282 * t_f * rh_pct * rh_pct
                    - 0.00000199 * t_f * t_f * rh_pct * rh_pct
                )
            return round((hi_f - 32.0) * 5.0 / 9.0, 2)

        base_tmax = req.base_temperature_c or (thermal.air_temperature_c if (thermal and thermal.air_temperature_c is not None) else 40.0)
        base_rh = req.base_humidity_pct or (thermal.relative_humidity if (thermal and thermal.relative_humidity is not None) else 50.0)
        base_hi = (thermal.heat_index_c if (thermal and thermal.heat_index_c is not None and req.base_temperature_c is None) else compute_hi(base_tmax, base_rh))

        # Projected temperature & humidity
        proj_tmax = round(base_tmax + scenario.delta_tmax_c, 2)
        proj_rh = max(10.0, min(100.0, base_rh + scenario.delta_humidity_pct))
        
        # Heat index projection with urban density adjustment
        proj_hi = round(compute_hi(proj_tmax, proj_rh) + (scenario.urban_density_factor - 1.0) * 1.5, 2)

        # Baseline & Projected Health Risk Probability (Logistic response function)
        base_logit = -5.5 + 0.11 * base_hi
        base_risk = 1.0 / (1.0 + math.exp(-base_logit))

        proj_logit = -5.5 + 0.11 * proj_hi + (0.005 * scenario.delta_pm25_pct)
        proj_risk = 1.0 / (1.0 + math.exp(-proj_logit))

        risk_mult = round(proj_risk / max(0.01, base_risk), 2)

        # Exposed population
        zone = db.execute(
            select(OperationalZoneDB).where(OperationalZoneDB.location_id == req.location_id)
        ).scalar_one_or_none()
        vulnerable_pop = zone.vulnerable_population if zone else 15000
        exposed_count = int(vulnerable_pop * min(1.0, 0.65 + proj_risk * 0.35))

        unc_lower = round(max(0.0, proj_risk * 0.85), 3)
        unc_upper = round(min(1.0, proj_risk * 1.18), 3)

        return ClimateSimulationResponse(
            location_id=req.location_id,
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.scenario_name,
            time_horizon=scenario.time_horizon,
            baseline_tmax=round(base_tmax, 2),
            projected_tmax=proj_tmax,
            baseline_heat_index=round(base_hi, 2),
            projected_heat_index=proj_hi,
            baseline_risk_probability=round(base_risk, 3),
            projected_risk_probability=round(proj_risk, 3),
            risk_multiplier=risk_mult,
            heatwave_days_per_year_projected=round(10.0 + scenario.delta_heatwave_days, 1),
            vulnerable_population_exposed=exposed_count,
            uncertainty_bounds={"lower_bound_p10": unc_lower, "upper_bound_p90": unc_upper},
            scientific_disclaimer="PROJECTION_ONLY_NOT_DETERMINISTIC_FORECAST",
        )
