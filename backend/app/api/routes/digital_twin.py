"""REST API routes for Step 10:
Heat Resilience Digital Twin, Climate Scenario Simulation, Long-Term Adaptation Planning,
Infrastructure Resilience, and Strategic Investment Decision Support.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import AuditEvent, AuditLogger, Role, require_role
from ...digital_twin.adaptation_engine import StrategicAdaptationEngine
from ...digital_twin.cascade_engine import ResilienceCascadeEngine
from ...digital_twin.climate_scenario_engine import ClimateScenarioEngine
from ...digital_twin.resilience_engine import ResilienceFrameworkEngine
from ...digital_twin.strategic_roadmap import StrategicRoadmapEngine
from ...digital_twin.twin_engine import DigitalTwinEngine
from ...digital_twin.schemas import (
    AdaptationPortfolioCreate,
    AdaptationPortfolioResponse,
    AdaptationPortfolioSimulateRequest,
    CascadeSimulationRequest,
    CascadeSimulationResponse,
    ClimateScenarioCreate,
    ClimateScenarioResponse,
    ClimateSimulationRequest,
    ClimateSimulationResponse,
    DigitalTwinStateResponse,
    ParetoFrontierResponse,
    PortfolioApprovalRequest,
    ResilienceGapsResponse,
    ResilienceProfileCreate,
    ResilienceProfileResponse,
    StrategicPlanCreate,
    StrategicPlanResponse,
    StrategicRoadmapResponse,
    TwinSnapshotCreate,
    TwinSnapshotResponse,
)

logger = logging.getLogger("keshav.api.digital_twin")
audit = AuditLogger(logger)

router = APIRouter(prefix="/api/v1", tags=["digital-twin", "resilience", "scenarios", "adaptation", "strategic-plans"])


# ============================================================
# 1. Digital Twin Multi-Layer State & Snapshots
# ============================================================

@router.get("/twin/state", response_model=DigitalTwinStateResponse)
def get_digital_twin_state(
    location_id: str = Query("LOC_DELHI_001", description="Location ID to query digital twin state"),
    city_id: str = Query("DELHI_NCR", description="City/Region ID"),
    db: Session = Depends(get_db),
):
    """Retrieve the multi-layer live state of the Heat Resilience Digital Twin for a location."""
    return DigitalTwinEngine.get_current_twin_state(db, location_id=location_id, city_id=city_id)


@router.post("/twin/snapshots", response_model=TwinSnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_twin_snapshot(
    req: TwinSnapshotCreate,
    current_role: Role = Depends(require_role(Role.MUNICIPAL_OPERATOR)),
    db: Session = Depends(get_db),
):
    """Capture an immutable state snapshot of the digital twin [RBAC: MUNICIPAL_OPERATOR, ADMIN]."""
    snapshot = DigitalTwinEngine.create_snapshot(db, req, user_id=current_role.value)
    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="CREATE_TWIN_SNAPSHOT",
            resource=snapshot.snapshot_id,
            details={"location_id": req.location_id, "time_dimension": req.time_dimension.value},
        ),
        session=db,
    )
    return snapshot


@router.get("/twin/snapshots", response_model=List[TwinSnapshotResponse])
def list_twin_snapshots(
    location_id: Optional[str] = Query(None, description="Optional location filter"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List historical immutable digital twin snapshots."""
    return DigitalTwinEngine.list_snapshots(db, location_id=location_id, limit=limit)


# ============================================================
# 2. 10-Dimension Resilience Framework & Gap Analysis
# ============================================================

@router.get("/resilience/profile", response_model=ResilienceProfileResponse)
def get_resilience_profile(
    location_id: str = Query("LOC_DELHI_001"),
    target_score: float = Query(80.0, ge=0.0, le=100.0),
    db: Session = Depends(get_db),
):
    """Evaluate 10-dimension urban heat resilience profile with strengths, weaknesses, and gaps."""
    return ResilienceFrameworkEngine.evaluate_profile(db, location_id=location_id, target_resilience_score=target_score)


@router.get("/resilience/gaps", response_model=ResilienceGapsResponse)
def get_resilience_gaps(
    location_id: str = Query("LOC_DELHI_001"),
    target_score: float = Query(80.0, ge=0.0, le=100.0),
    db: Session = Depends(get_db),
):
    """Evaluate itemized adaptation gaps and prioritized action recommendations across 10 dimensions."""
    return ResilienceFrameworkEngine.calculate_gaps(db, location_id=location_id, target_score=target_score)


# ============================================================
# 3. Climate Projection Scenarios & Simulation
# ============================================================

@router.get("/scenarios/climate", response_model=List[ClimateScenarioResponse])
def list_climate_scenarios(db: Session = Depends(get_db)):
    """List scientific climate warming pathways and projection scenarios (2030, 2040, 2050)."""
    return ClimateScenarioEngine.list_scenarios(db)


@router.post("/scenarios/climate", response_model=ClimateScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_climate_scenario(
    req: ClimateScenarioCreate,
    current_role: Role = Depends(require_role(Role.ANALYST)),
    db: Session = Depends(get_db),
):
    """Register a custom climate projection scenario [RBAC: ANALYST, ADMIN]."""
    scen = ClimateScenarioEngine.create_scenario(db, req)
    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="CREATE_CLIMATE_SCENARIO",
            resource=scen.scenario_id,
            details={"scenario_name": scen.scenario_name, "time_horizon": scen.time_horizon},
        ),
        session=db,
    )
    return scen


@router.post("/scenarios/climate/simulate", response_model=ClimateSimulationResponse)
def simulate_climate_scenario(
    req: ClimateSimulationRequest,
    db: Session = Depends(get_db),
):
    """Simulate projected heat index and health risk delta under a climate warming scenario."""
    return ClimateScenarioEngine.simulate_scenario(db, req)


# ============================================================
# 4. Cascading Infrastructure Failure Simulation
# ============================================================

@router.post("/scenarios/cascade/simulate", response_model=CascadeSimulationResponse)
def simulate_cascading_failure(
    req: CascadeSimulationRequest,
    db: Session = Depends(get_db),
):
    """Simulate compound cascading failure dynamics across power, cooling, water, and healthcare."""
    return ResilienceCascadeEngine.simulate_cascade(db, req)


# ============================================================
# 5. Strategic Adaptation Portfolios & Pareto Frontier
# ============================================================

@router.get("/adaptation/interventions")
def get_strategic_interventions_catalog():
    """Retrieve the strategic heat adaptation intervention library with cost and equity factors."""
    return {"interventions": StrategicAdaptationEngine.get_intervention_catalog()}


@router.post("/adaptation/simulate", response_model=AdaptationPortfolioResponse)
def simulate_adaptation_portfolio(
    req: AdaptationPortfolioSimulateRequest,
    db: Session = Depends(get_db),
):
    """Simulate multi-intervention long-term portfolio synergy, exposure reduction, and risk delta."""
    return StrategicAdaptationEngine.simulate_portfolio(
        db=db,
        target_locations=req.target_locations,
        interventions=req.interventions,
        portfolio_name=req.portfolio_name or "Simulated Portfolio",
        portfolio_id=req.portfolio_id,
    )


@router.post("/adaptation/portfolios", response_model=AdaptationPortfolioResponse, status_code=status.HTTP_201_CREATED)
def create_adaptation_portfolio(
    req: AdaptationPortfolioCreate,
    current_role: Role = Depends(require_role(Role.MUNICIPAL_OPERATOR)),
    db: Session = Depends(get_db),
):
    """Create and persist a proposed adaptation investment portfolio [RBAC: MUNICIPAL_OPERATOR, ADMIN]."""
    port = StrategicAdaptationEngine.create_and_persist_portfolio(db, req, user_id=current_role.value)
    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="CREATE_ADAPTATION_PORTFOLIO",
            resource=port.portfolio_id,
            details={"portfolio_name": port.portfolio_name, "locations_count": len(port.target_locations)},
        ),
        session=db,
    )
    return port


@router.get("/adaptation/portfolios", response_model=List[AdaptationPortfolioResponse])
def list_adaptation_portfolios(db: Session = Depends(get_db)):
    """List all registered adaptation portfolios."""
    return StrategicAdaptationEngine.list_portfolios(db)


@router.post("/adaptation/portfolios/{portfolio_id}/approve", response_model=AdaptationPortfolioResponse)
def approve_adaptation_portfolio(
    portfolio_id: str,
    req: PortfolioApprovalRequest,
    current_role: Role = Depends(require_role(Role.HEALTH_OFFICIAL)),
    db: Session = Depends(get_db),
):
    """Authorize a strategic adaptation portfolio under human-in-the-loop governance [RBAC: HEALTH_OFFICIAL, ADMIN]."""
    port = StrategicAdaptationEngine.approve_portfolio(
        db=db, portfolio_id=portfolio_id, approved_by=req.approved_by, notes=req.notes
    )
    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="APPROVE_ADAPTATION_PORTFOLIO",
            resource=portfolio_id,
            details={"approved_by": req.approved_by, "notes": req.notes},
        ),
        session=db,
    )
    return port


@router.get("/adaptation/pareto", response_model=ParetoFrontierResponse)
def get_adaptation_pareto_frontier(
    location_id: str = Query("LOC_DELHI_001"),
    db: Session = Depends(get_db),
):
    """Evaluate multi-objective trade-offs (Cost vs Risk Reduction vs Equity) to find Pareto-optimal packages."""
    return StrategicAdaptationEngine.compute_pareto_frontier(db, location_id=location_id)


# ============================================================
# 6. Strategic Resilience Roadmaps & Plans
# ============================================================

@router.get("/strategic-plans/roadmap", response_model=StrategicRoadmapResponse)
def get_strategic_roadmap(
    location_id: str = Query("LOC_DELHI_001"),
    horizon: str = Query("2030"),
    db: Session = Depends(get_db),
):
    """Generate sequenced multi-horizon strategic resilience roadmap (NOW, SHORT_TERM, MEDIUM_TERM, LONG_TERM)."""
    return StrategicRoadmapEngine.generate_roadmap(db, location_id=location_id, target_horizon=horizon)


@router.post("/strategic-plans", response_model=StrategicPlanResponse, status_code=status.HTTP_201_CREATED)
def create_strategic_plan(
    req: StrategicPlanCreate,
    current_role: Role = Depends(require_role(Role.MUNICIPAL_OPERATOR)),
    db: Session = Depends(get_db),
):
    """Create a formal strategic adaptation plan [RBAC: MUNICIPAL_OPERATOR, ADMIN]."""
    plan = StrategicRoadmapEngine.create_strategic_plan(db, req, user_id=current_role.value)
    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="CREATE_STRATEGIC_PLAN",
            resource=plan.plan_id,
            details={"plan_name": plan.plan_name, "target_horizon": plan.target_horizon},
        ),
        session=db,
    )
    return plan


@router.get("/strategic-plans", response_model=List[StrategicPlanResponse])
def list_strategic_plans(db: Session = Depends(get_db)):
    """List all formal strategic adaptation plans."""
    return StrategicRoadmapEngine.list_strategic_plans(db)


@router.post("/strategic-plans/{plan_id}/status", response_model=StrategicPlanResponse)
def update_strategic_plan_status(
    plan_id: str,
    status_update: str = Query(..., description="New status e.g. REVIEW, APPROVED, IMPLEMENTING, IMPLEMENTED, REJECTED"),
    notes: Optional[str] = Query(None),
    current_role: Role = Depends(require_role(Role.HEALTH_OFFICIAL)),
    db: Session = Depends(get_db),
):
    """Update strategic plan governance status [RBAC: HEALTH_OFFICIAL, ADMIN]."""
    plan = StrategicRoadmapEngine.update_plan_status(
        db, plan_id=plan_id, new_status=status_update, user_id=current_role.value, notes=notes
    )
    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="UPDATE_STRATEGIC_PLAN_STATUS",
            resource=plan_id,
            details={"new_status": status_update, "updated_by": current_role.value},
        ),
        session=db,
    )
    return plan
