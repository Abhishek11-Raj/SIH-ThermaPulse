"""Strategic Adaptation Portfolio Engine: Long-term resilience investments,
multi-intervention synergy modeling, cost-effectiveness, equity evaluation,
and Multi-Objective Pareto Frontier optimization.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..models.digital_twin import AdaptationPortfolioDB
from ..models.city_operations import OperationalZoneDB
from ..utils.time import utcnow
from .schemas import (
    AdaptationInterventionSpec,
    AdaptationPortfolioCreate,
    AdaptationPortfolioResponse,
    AdaptationPortfolioSimulateRequest,
    ParetoFrontierResponse,
    ParetoPortfolioItem,
    PortfolioStatus,
    StrategicInterventionType,
)

INTERVENTION_CATALOG = {
    StrategicInterventionType.COOL_ROOF_RETROFIT: {
        "name": "High-Albedo Cool Roof Retrofits",
        "description": "Applies high solar-reflectance coatings on residential and commercial rooftops.",
        "max_exposure_reduction_pct": 22.0,
        "default_unit_cost": 450.0,  # USD/sqm equivalent or scaled index
        "equity_weight": 0.85,
        "co_benefits": ["Reduced indoor night temperatures", "Decreased air conditioning electricity demand"],
    },
    StrategicInterventionType.URBAN_CANOPY_AFFORESTATION: {
        "name": "Urban Canopy & Pocket Forest Afforestation",
        "description": "Plants dense shade tree canopies and micro-forests along urban street corridors.",
        "max_exposure_reduction_pct": 18.0,
        "default_unit_cost": 800.0,
        "equity_weight": 0.90,
        "co_benefits": ["Air quality improvement", "Stormwater retention", "Biodiversity"],
    },
    StrategicInterventionType.COOL_PAVEMENT_COATING: {
        "name": "Reflective / Permeable Cool Pavements",
        "description": "Replaces dark asphalt with reflective and permeable cool pavement coatings.",
        "max_exposure_reduction_pct": 12.0,
        "default_unit_cost": 320.0,
        "equity_weight": 0.70,
        "co_benefits": ["Reduced pedestrian radiative stress", "Decreased nighttime UHI"],
    },
    StrategicInterventionType.PUBLIC_SHADE_NETWORK: {
        "name": "Public Transit & Pedestrian Shade Canopies",
        "description": "Erects tensile solar/passive shade structures over bus stops, markets, and sidewalks.",
        "max_exposure_reduction_pct": 15.0,
        "default_unit_cost": 250.0,
        "equity_weight": 0.95,
        "co_benefits": ["Protects outdoor transit commuters and street vendors"],
    },
    StrategicInterventionType.DISTRIBUTED_COOLING_HUBS: {
        "name": "Decentralized Air-Conditioned Community Cooling Hubs",
        "description": "Establishes backup-powered municipal cooling hubs within 10-minute walking distance.",
        "max_exposure_reduction_pct": 25.0,
        "default_unit_cost": 1200.0,
        "equity_weight": 1.0,
        "co_benefits": ["Emergency medical triage point", "Clean air shelter during dust/smog"],
    },
    StrategicInterventionType.EMERGENCY_WATER_RESILIENCE: {
        "name": "Solar-Powered Drinking Water ATMs & Misting Kiosks",
        "description": "Deploys chilled drinking water stations and misting kiosks in high-density informal settlements.",
        "max_exposure_reduction_pct": 14.0,
        "default_unit_cost": 300.0,
        "equity_weight": 1.0,
        "co_benefits": ["Direct dehydration prevention", "Public health hygiene"],
    },
    StrategicInterventionType.GRID_BACKUP_SOLAR_STORAGE: {
        "name": "Microgrid Solar + Battery Storage for Critical Cooling",
        "description": "Installs islandable solar photovoltaic microgrids with BESS on hospitals and shelters.",
        "max_exposure_reduction_pct": 16.0,
        "default_unit_cost": 1500.0,
        "equity_weight": 0.80,
        "co_benefits": ["Zero-carbon backup power during heatwave grid blackouts"],
    },
    StrategicInterventionType.HEAT_ADAPTIVE_WORK_ORDINANCE: {
        "name": "Mandatory Midday Work Suspension & Shift Scheduling",
        "description": "Legislates mandatory paid rest breaks and shifted working hours for outdoor workers.",
        "max_exposure_reduction_pct": 30.0,
        "default_unit_cost": 100.0,
        "equity_weight": 1.0,
        "co_benefits": ["Immediate occupational heatstroke reduction"],
    },
}


class StrategicAdaptationEngine:
    """Simulates strategic portfolios and calculates Pareto trade-offs."""

    @classmethod
    def get_intervention_catalog(cls) -> List[Dict[str, Any]]:
        """Returns the full catalog of strategic resilience interventions."""
        catalog = []
        for itype, meta in INTERVENTION_CATALOG.items():
            catalog.append({
                "intervention_type": itype.value,
                "name": meta["name"],
                "description": meta["description"],
                "max_exposure_reduction_pct": meta["max_exposure_reduction_pct"],
                "default_unit_cost": meta["default_unit_cost"],
                "equity_weight": meta["equity_weight"],
                "co_benefits": meta["co_benefits"],
            })
        return catalog

    @classmethod
    def simulate_portfolio(
        cls,
        db: Session,
        target_locations: List[str],
        interventions: List[AdaptationInterventionSpec],
        portfolio_name: str = "Simulated Portfolio",
        portfolio_id: Optional[str] = None,
        user_id: str = "MUNICIPAL_OPERATOR",
    ) -> AdaptationPortfolioResponse:
        """Simulates cumulative portfolio impact across exposure, risk, cost, and equity."""
        pid = portfolio_id or f"port_{uuid.uuid4().hex[:8]}"

        total_exposure_reduction = 0.0
        total_cost: Optional[float] = 0.0
        has_cost = True
        equity_accumulator = 0.0
        intervention_records = []

        # Calculate combined effects with diminishing returns (synergy formula)
        # Exposure_Red_Total = 1 - \prod (1 - r_i * coverage_i)
        remaining_exposure = 1.0

        for spec in interventions:
            cat = INTERVENTION_CATALOG.get(spec.intervention_type)
            if not cat:
                continue

            cov_fraction = spec.coverage_pct / 100.0
            max_red = cat["max_exposure_reduction_pct"] / 100.0
            effect = max_red * cov_fraction

            remaining_exposure *= (1.0 - effect)

            unit_cost = spec.unit_cost_estimate if spec.unit_cost_estimate is not None else cat["default_unit_cost"]
            if unit_cost is not None:
                step_cost = unit_cost * (spec.coverage_pct * 100.0)  # scaled by coverage
                total_cost = (total_cost or 0.0) + step_cost
            else:
                has_cost = False

            equity_accumulator += cat["equity_weight"] * cov_fraction

            intervention_records.append({
                "intervention_type": spec.intervention_type.value,
                "coverage_pct": spec.coverage_pct,
                "implementation_horizon_months": spec.implementation_horizon_months,
                "estimated_cost": unit_cost * (spec.coverage_pct * 100.0) if unit_cost else None,
                "target_zone_id": spec.target_zone_id,
            })

        total_exposure_reduction = round((1.0 - remaining_exposure) * 100.0, 1)
        
        # Risk delta calculation (modeled non-linear relation: risk_delta = - (exposure_red / 100) * baseline_risk)
        baseline_risk = 0.72
        risk_delta = -round(baseline_risk * (total_exposure_reduction / 100.0) * 0.85, 3)

        # Population protected count
        total_pop = 0
        for loc_id in target_locations:
            zone = db.execute(
                select(OperationalZoneDB).where(OperationalZoneDB.location_id == loc_id)
            ).scalar_one_or_none()
            if zone:
                total_pop += zone.vulnerable_population
            else:
                total_pop += 15000

        pop_protected = int(total_pop * (total_exposure_reduction / 100.0))

        cost_val = round(total_cost, 2) if (has_cost and total_cost is not None) else None
        cost_status = "ESTIMATED" if cost_val is not None else "COST_DATA_UNAVAILABLE"

        cost_eff = None
        if cost_val and abs(risk_delta) > 0.001:
            cost_eff = round(cost_val / (abs(risk_delta) * pop_protected), 2) if pop_protected > 0 else round(cost_val / abs(risk_delta), 2)

        # Equity disparity ratio (1.0 = equal, < 1.0 = disparity in favor of vulnerable)
        avg_equity = equity_accumulator / max(1, len(interventions))
        equity_ratio = round(max(0.60, 1.20 - avg_equity * 0.5), 2)

        summary_text = (
            f"Portfolio achieves {total_exposure_reduction}% thermal exposure reduction across {len(target_locations)} zones, "
            f"protecting ~{pop_protected:,} vulnerable residents with modeled risk delta of {risk_delta}."
        )

        return AdaptationPortfolioResponse(
            portfolio_id=pid,
            portfolio_name=portfolio_name,
            target_locations=target_locations,
            interventions=intervention_records,
            status=PortfolioStatus.SIMULATED.value,
            simulated_exposure_reduction_pct=total_exposure_reduction,
            simulated_risk_delta=risk_delta,
            population_protected_count=pop_protected,
            estimated_capital_cost=cost_val,
            cost_status=cost_status,
            cost_effectiveness_ratio=cost_eff,
            equity_disparity_ratio=equity_ratio,
            feasibility_status="FEASIBLE",
            causal_status="MODEL_BASED_COUNTERFACTUAL",
            summary=summary_text,
            created_by=user_id,
            created_at=utcnow(),
        )

    @classmethod
    def create_and_persist_portfolio(
        cls, db: Session, req: AdaptationPortfolioCreate, user_id: str = "MUNICIPAL_OPERATOR"
    ) -> AdaptationPortfolioResponse:
        """Creates and persists an adaptation portfolio in the database."""
        sim = cls.simulate_portfolio(
            db=db,
            target_locations=req.target_locations,
            interventions=req.interventions,
            portfolio_name=req.portfolio_name,
            user_id=user_id,
        )

        row = AdaptationPortfolioDB(
            portfolio_id=sim.portfolio_id,
            portfolio_name=sim.portfolio_name,
            target_locations=sim.target_locations,
            interventions=sim.interventions,
            status=PortfolioStatus.PROPOSED.value,
            simulated_exposure_reduction_pct=sim.simulated_exposure_reduction_pct,
            simulated_risk_delta=sim.simulated_risk_delta,
            population_protected_count=sim.population_protected_count,
            estimated_capital_cost=sim.estimated_capital_cost,
            cost_status=sim.cost_status,
            cost_effectiveness_ratio=sim.cost_effectiveness_ratio,
            equity_disparity_ratio=sim.equity_disparity_ratio,
            feasibility_status=sim.feasibility_status,
            causal_status=sim.causal_status,
            summary=req.summary or sim.summary,
            created_by=user_id,
            created_at=utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        return AdaptationPortfolioResponse.model_validate(row)

    @classmethod
    def list_portfolios(cls, db: Session) -> List[AdaptationPortfolioResponse]:
        """Lists all adaptation portfolios."""
        rows = db.execute(select(AdaptationPortfolioDB).order_by(desc(AdaptationPortfolioDB.created_at))).scalars().all()
        return [AdaptationPortfolioResponse.model_validate(r) for r in rows]

    @classmethod
    def approve_portfolio(
        cls, db: Session, portfolio_id: str, approved_by: str, notes: Optional[str] = None
    ) -> AdaptationPortfolioResponse:
        """Approves a proposed adaptation portfolio under human-in-the-loop governance."""
        row = db.execute(
            select(AdaptationPortfolioDB).where(AdaptationPortfolioDB.portfolio_id == portfolio_id)
        ).scalar_one_or_none()

        if not row:
            raise ValueError(f"Portfolio '{portfolio_id}' not found")

        row.status = PortfolioStatus.APPROVED.value
        row.approved_by = approved_by
        row.approved_at = utcnow()
        row.approval_notes = notes

        db.commit()
        db.refresh(row)
        return AdaptationPortfolioResponse.model_validate(row)

    @classmethod
    def compute_pareto_frontier(
        cls, db: Session, location_id: str
    ) -> ParetoFrontierResponse:
        """Evaluates multiple strategic portfolios to find the Pareto optimal set (Cost vs Risk Reduction vs Equity)."""
        # Predefined portfolio candidates for optimization
        candidates_spec = [
            {
                "id": "p_cool_roof_basic",
                "name": "Cool Roofs Fast Track",
                "interventions": [
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.COOL_ROOF_RETROFIT, coverage_pct=30.0),
                ],
            },
            {
                "id": "p_green_canopy_focus",
                "name": "Urban Forestry & Shading",
                "interventions": [
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.URBAN_CANOPY_AFFORESTATION, coverage_pct=25.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.PUBLIC_SHADE_NETWORK, coverage_pct=40.0),
                ],
            },
            {
                "id": "p_high_protection_equity",
                "name": "Comprehensive Vulnerable Protection",
                "interventions": [
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.DISTRIBUTED_COOLING_HUBS, coverage_pct=35.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.EMERGENCY_WATER_RESILIENCE, coverage_pct=50.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.HEAT_ADAPTIVE_WORK_ORDINANCE, coverage_pct=80.0),
                ],
            },
            {
                "id": "p_infrastructure_resilience",
                "name": "Microgrid & Deep Infrastructure",
                "interventions": [
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.GRID_BACKUP_SOLAR_STORAGE, coverage_pct=30.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.COOL_ROOF_RETROFIT, coverage_pct=40.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.COOL_PAVEMENT_COATING, coverage_pct=20.0),
                ],
            },
            {
                "id": "p_maximum_resilience",
                "name": "Maximum Climate Adaptation Master Package",
                "interventions": [
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.COOL_ROOF_RETROFIT, coverage_pct=60.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.URBAN_CANOPY_AFFORESTATION, coverage_pct=40.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.DISTRIBUTED_COOLING_HUBS, coverage_pct=50.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.GRID_BACKUP_SOLAR_STORAGE, coverage_pct=40.0),
                    AdaptationInterventionSpec(intervention_type=StrategicInterventionType.HEAT_ADAPTIVE_WORK_ORDINANCE, coverage_pct=90.0),
                ],
            },
        ]

        evaluated: List[ParetoPortfolioItem] = []

        for cand in candidates_spec:
            sim = cls.simulate_portfolio(
                db=db,
                target_locations=[location_id],
                interventions=cand["interventions"],
                portfolio_name=cand["name"],
                portfolio_id=cand["id"],
            )

            # Equity score normalized (0-100, higher is more equitable)
            eq_score = round((2.0 - sim.equity_disparity_ratio) * 50.0, 1)
            risk_red = sim.simulated_exposure_reduction_pct

            evaluated.append(
                ParetoPortfolioItem(
                    portfolio_id=cand["id"],
                    portfolio_name=cand["name"],
                    cost=sim.estimated_capital_cost,
                    risk_reduction_pct=risk_red,
                    equity_score=eq_score,
                    is_pareto_optimal=False,
                    rank=1,
                )
            )

        # Determine Pareto Optimality (Non-dominated in Risk Reduction vs Cost vs Equity)
        for i, p1 in enumerate(evaluated):
            dominated = False
            for j, p2 in enumerate(evaluated):
                if i != j and p1.cost is not None and p2.cost is not None:
                    # p2 dominates p1 if p2 has >= risk_red, <= cost, >= equity and strictly better in one
                    if (
                        p2.risk_reduction_pct >= p1.risk_reduction_pct
                        and p2.cost <= p1.cost
                        and p2.equity_score >= p1.equity_score
                        and (p2.risk_reduction_pct > p1.risk_reduction_pct or p2.cost < p1.cost or p2.equity_score > p1.equity_score)
                    ):
                        dominated = True
                        break
            p1.is_pareto_optimal = not dominated

        # Rank candidates by multi-objective score
        for idx, item in enumerate(sorted(evaluated, key=lambda x: (x.is_pareto_optimal, x.risk_reduction_pct), reverse=True)):
            item.rank = idx + 1

        pareto_optimal = [p for p in evaluated if p.is_pareto_optimal]

        tradeoff_summary = (
            f"Evaluated {len(evaluated)} portfolio strategies for {location_id}. Found {len(pareto_optimal)} Pareto-optimal "
            f"configurations representing optimal trade-offs between capital expenditure, risk reduction, and social equity."
        )

        return ParetoFrontierResponse(
            location_id=location_id,
            portfolios_evaluated_count=len(evaluated),
            pareto_optimal_portfolios=pareto_optimal,
            all_candidates=evaluated,
            tradeoff_summary=tradeoff_summary,
        )
