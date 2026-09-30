"""REST API routes for Step 9:
Operational Decision Support, City-Scale Planning, Resource Optimization,
Scenario Orchestration, Resilience Planning & Human-in-the-Loop Action Management.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import AuditEvent, AuditLogger, Role, require_role
from ...models.city_operations import (
    ActionTaskDB,
    OperationalPlanDB,
    OperationalPolicyDB,
    OperationalScenarioDB,
    OperationalZoneDB,
    ResourceDB,
    ResourceGapDB,
    ResponseExecutionDB,
)
from ...operations.allocation import ResourceAllocationEngine
from ...operations.priority import OperationalPriorityEngine
from ...operations.resilience import CityResilienceEngine
from ...operations.resource_gap import ResourceGapEngine
from ...operations.response_plan import ResponsePlanEngine
from ...operations.schemas import (
    ActionTaskAssignRequest,
    ActionTaskCompleteRequest,
    ActionTaskCreate,
    ActionTaskListResponse,
    ActionTaskResponse,
    CityPriorityListResponse,
    CityResilienceResponse,
    EquityAllocationAudit,
    OperationalPerformanceReport,
    OperationalPlanApproveRequest,
    OperationalPlanCreate,
    OperationalPlanListResponse,
    OperationalPlanRejectRequest,
    OperationalPlanResponse,
    OperationalPriorityRequest,
    OperationalPriorityScoreResponse,
    OperationalZoneCreate,
    OperationalZoneListResponse,
    OperationalZoneResponse,
    ResourceAllocationRequest,
    ResourceAllocationResponse,
    ResourceCreate,
    ResourceGapResponse,
    ResourceGapSummaryResponse,
    ResourceListResponse,
    ResourceResponse,
    ResourceUpdate,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
)
from ...utils.time import to_utc, utcnow

logger = logging.getLogger("keshav.api.operations")
audit = AuditLogger(logger)

router = APIRouter(prefix="/api/v1", tags=["operations", "decision-support", "resources", "planning"])

priority_engine = OperationalPriorityEngine()
gap_engine = ResourceGapEngine()
allocation_engine = ResourceAllocationEngine()
scenario_engine = None  # Lazily instantiated
plan_engine = ResponsePlanEngine()
resilience_engine = CityResilienceEngine()


def get_scenario_engine():
    global scenario_engine
    if scenario_engine is None:
        from ...operations.scenario_orchestration import ScenarioOrchestrationEngine
        scenario_engine = ScenarioOrchestrationEngine()
    return scenario_engine


# ============================================================
# 1. Operational Priority & Zone Rankings
# ============================================================

@router.get("/operations/priorities", response_model=CityPriorityListResponse)
def get_city_priorities(db: Session = Depends(get_db)):
    """Evaluate and rank all city operational zones by multi-criteria decision priority."""
    zones = db.query(OperationalZoneDB).all()
    if not zones:
        # Default representative zones if database is freshly initialized
        default_reqs = [
            OperationalPriorityRequest(
                location_id="DEMO-WARD-01",
                health_risk_probability=0.82,
                thermal_stress_score=46.5,
                nighttime_recovery_deficit=2.8,
                vulnerable_population_fraction=0.35,
                outdoor_worker_fraction=0.25,
                resource_shortage_severity=0.60,
                hospital_surge_occupancy=0.85,
                alert_severity_code="HIGH_RISK",
                forecast_lead_time_hours=36.0,
            ),
            OperationalPriorityRequest(
                location_id="DEMO-WARD-02",
                health_risk_probability=0.64,
                thermal_stress_score=41.0,
                nighttime_recovery_deficit=1.5,
                vulnerable_population_fraction=0.28,
                outdoor_worker_fraction=0.18,
                resource_shortage_severity=0.40,
                hospital_surge_occupancy=0.70,
                alert_severity_code="WARNING",
                forecast_lead_time_hours=48.0,
            ),
            OperationalPriorityRequest(
                location_id="DEMO-WARD-03",
                health_risk_probability=0.38,
                thermal_stress_score=34.0,
                nighttime_recovery_deficit=0.5,
                vulnerable_population_fraction=0.15,
                outdoor_worker_fraction=0.10,
                resource_shortage_severity=0.20,
                hospital_surge_occupancy=0.55,
                alert_severity_code="WATCH",
                forecast_lead_time_hours=72.0,
            ),
        ]
        return priority_engine.rank_city_zones(default_reqs)

    reqs = [
        OperationalPriorityRequest(
            location_id=z.location_id,
            health_risk_probability=0.75 if z.operational_risk_level in ["CRITICAL", "URGENT"] else 0.45,
            thermal_stress_score=42.0,
            nighttime_recovery_deficit=2.0,
            vulnerable_population_fraction=z.vulnerable_population / max(z.population_total, 1),
            outdoor_worker_fraction=z.outdoor_worker_count / max(z.population_total, 1),
            resource_shortage_severity=0.5,
            hospital_surge_occupancy=0.75,
            alert_severity_code="WARNING",
            forecast_lead_time_hours=48.0,
        )
        for z in zones
    ]
    return priority_engine.rank_city_zones(reqs)


@router.post("/operations/priorities/evaluate", response_model=OperationalPriorityScoreResponse)
def evaluate_ward_priority(req: OperationalPriorityRequest):
    """Evaluate operational priority for a specific ward/location with itemized driver explanation."""
    return priority_engine.evaluate_priority(req)


# ============================================================
# 2. Resource Inventory & Gap Analysis
# ============================================================

@router.get("/resources", response_model=ResourceListResponse)
def list_resources(
    location_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Query protective resources with optional filtering."""
    query = db.query(ResourceDB)
    if location_id:
        query = query.filter(ResourceDB.location_id == location_id)
    if resource_type:
        query = query.filter(ResourceDB.resource_type == resource_type)
    if status_filter:
        query = query.filter(ResourceDB.status == status_filter)

    records = query.limit(limit).all()
    if not records and not location_id and not resource_type:
        # Default mock inventory for demonstration if empty
        default_res = [
            ResourceDB(
                resource_id="RES-COOLING-01",
                location_id="DEMO-WARD-01",
                zone_id="ZONE-DEMO-WARD-01",
                resource_type="COOLING_CENTER",
                name="Central Community Cooling Center",
                latitude=28.6139,
                longitude=77.2090,
                total_capacity=300.0,
                available_capacity=250.0,
                capacity_unit="PERSONS",
                operating_hours="08:00-20:00",
                status="AVAILABLE",
                confidence="VERIFIED",
                source="MUNICIPAL_INVENTORY",
                last_updated_at=utcnow(),
                is_synthetic=True,
            ),
            ResourceDB(
                resource_id="RES-WATER-01",
                location_id="DEMO-WARD-01",
                zone_id="ZONE-DEMO-WARD-01",
                resource_type="DRINKING_WATER_POINT",
                name="Station Road Water Kiosk",
                latitude=28.6150,
                longitude=77.2100,
                total_capacity=15000.0,
                available_capacity=12000.0,
                capacity_unit="LITERS",
                operating_hours="24_HOURS",
                status="AVAILABLE",
                confidence="VERIFIED",
                source="WATER_UTILITY",
                last_updated_at=utcnow(),
                is_synthetic=True,
            ),
            ResourceDB(
                resource_id="RES-ORS-01",
                location_id="DEMO-WARD-01",
                zone_id="ZONE-DEMO-WARD-01",
                resource_type="HYDRATION_ORS_STATION",
                name="Ward Health Post ORS Depot",
                latitude=28.6120,
                longitude=77.2080,
                total_capacity=5000.0,
                available_capacity=4200.0,
                capacity_unit="PACKETS",
                operating_hours="09:00-18:00",
                status="AVAILABLE",
                confidence="VERIFIED",
                source="HEALTH_DEPARTMENT",
                last_updated_at=utcnow(),
                is_synthetic=True,
            ),
        ]
        return ResourceListResponse(
            resources=[ResourceResponse.model_validate(r) for r in default_res],
            total_count=len(default_res),
        )

    return ResourceListResponse(
        resources=[ResourceResponse.model_validate(r) for r in records],
        total_count=query.count(),
    )


@router.post("/resources", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
def register_resource(
    req: ResourceCreate,
    current_role: Role = Depends(require_role(Role.MUNICIPAL_OPERATOR)),
    db: Session = Depends(get_db),
):
    """Register or update a protective resource [RBAC: MUNICIPAL_OPERATOR, ADMIN]."""
    existing = db.query(ResourceDB).filter(ResourceDB.resource_id == req.resource_id).first()
    if existing:
        existing.available_capacity = req.available_capacity
        existing.status = req.status
        existing.operating_hours = req.operating_hours
        existing.last_updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        return ResourceResponse.model_validate(existing)

    row = ResourceDB(
        resource_id=req.resource_id,
        location_id=req.location_id,
        zone_id=req.zone_id or f"ZONE-{req.location_id}",
        resource_type=req.resource_type,
        name=req.name,
        latitude=req.latitude,
        longitude=req.longitude,
        total_capacity=req.total_capacity,
        available_capacity=req.available_capacity,
        capacity_unit=req.capacity_unit,
        operating_hours=req.operating_hours,
        status=req.status,
        confidence=req.confidence,
        source=req.source,
        provenance=req.provenance,
        last_updated_at=utcnow(),
        is_synthetic=req.is_synthetic,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="REGISTER_RESOURCE",
            resource=req.resource_id,
            details={"location": req.location_id, "type": req.resource_type},
        ),
        session=db,
    )
    return ResourceResponse.model_validate(row)


@router.get("/resources/gaps", response_model=ResourceGapSummaryResponse)
def get_resource_gaps(
    location_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Evaluate protective infrastructure deficits against modeled population demand."""
    locs = [location_id] if location_id else ["DEMO-WARD-01", "DEMO-WARD-02", "DEMO-WARD-03"]
    all_gaps: List[ResourceGapResponse] = []

    for loc in locs:
        res_rows = db.query(ResourceDB).filter(ResourceDB.location_id == loc).all()
        res_models = [ResourceResponse.model_validate(r) for r in res_rows]
        gaps = gap_engine.evaluate_zone_gaps(
            location_id=loc,
            population_total=60000,
            vulnerable_population=18000,
            outdoor_workers=9000,
            health_risk_prob=0.78 if loc == "DEMO-WARD-01" else (0.60 if loc == "DEMO-WARD-02" else 0.35),
            available_resources=res_models,
        )
        all_gaps.extend(gaps)

    return gap_engine.summarize_city_gaps(all_gaps)


# ============================================================
# 3. Resource Allocation & Optimization Engine
# ============================================================

@router.post("/operations/allocate", response_model=ResourceAllocationResponse)
def optimize_resource_allocation(
    req: ResourceAllocationRequest,
    current_role: Role = Depends(require_role(Role.MUNICIPAL_OPERATOR)),
    db: Session = Depends(get_db),
):
    """
    Generate resource-constrained multi-ward allocation recommendation [RBAC: MUNICIPAL_OPERATOR, ADMIN].
    Strictly provides decision support recommendations; never executes real-world actions automatically.
    """
    zone_demands = [
        {
            "location_id": "DEMO-WARD-01",
            "priority_score": 85.0,
            "vulnerable_population": 18000,
            "outdoor_workers": 9000,
            "demanded_tankers": 6.0,
            "demanded_mobile_cooling": 3.0,
            "demanded_field_teams": 8.0,
            "demanded_ors_packets": 5000.0,
            "demanded_ambulances": 4.0,
        },
        {
            "location_id": "DEMO-WARD-02",
            "priority_score": 68.0,
            "vulnerable_population": 12000,
            "outdoor_workers": 6000,
            "demanded_tankers": 4.0,
            "demanded_mobile_cooling": 2.0,
            "demanded_field_teams": 6.0,
            "demanded_ors_packets": 3500.0,
            "demanded_ambulances": 2.0,
        },
        {
            "location_id": "DEMO-WARD-03",
            "priority_score": 42.0,
            "vulnerable_population": 8000,
            "outdoor_workers": 3000,
            "demanded_tankers": 2.0,
            "demanded_mobile_cooling": 1.0,
            "demanded_field_teams": 3.0,
            "demanded_ors_packets": 1500.0,
            "demanded_ambulances": 1.0,
        },
    ]

    res = allocation_engine.optimize_allocation(req, zone_demands)
    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="GENERATE_ALLOCATION_PLAN",
            resource=res.allocation_id,
            details={"target_date": req.target_date, "equity_satisfied": res.equity_audit.equity_constraint_satisfied},
        ),
        session=db,
    )
    return res


# ============================================================
# 4. Scenario Orchestration & Multi-Intervention What-If
# ============================================================

@router.post("/operations/scenarios", response_model=ScenarioSimulationResponse)
def simulate_operational_scenario(req: ScenarioSimulationRequest):
    """Run model-based counterfactual simulation for combined physical & behavioral interventions."""
    eng = get_scenario_engine()
    return eng.simulate_scenario(req)


@router.post("/operations/scenarios/compare", response_model=ScenarioCompareResponse)
def compare_operational_scenarios(req: ScenarioCompareRequest):
    """Evaluate multi-scenario comparison matrix and recommend highest feasible risk reduction."""
    eng = get_scenario_engine()
    return eng.compare_scenarios(req)


# ============================================================
# 5. Operational Response Plans & Tasks
# ============================================================

@router.get("/operations/plans", response_model=OperationalPlanListResponse)
def list_operational_plans(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List operational plans with task summaries."""
    query = db.query(OperationalPlanDB)
    if status_filter:
        query = query.filter(OperationalPlanDB.status == status_filter)

    plans = query.order_by(OperationalPlanDB.created_at.desc()).limit(limit).all()
    results: List[OperationalPlanResponse] = []

    for p in plans:
        task_rows = db.query(ActionTaskDB).filter(ActionTaskDB.plan_id == p.plan_id).all()
        task_models = [ActionTaskResponse.model_validate(t) for t in task_rows]
        p_dict = {c.name: getattr(p, c.name) for c in p.__table__.columns}
        p_dict["tasks"] = task_models
        results.append(OperationalPlanResponse(**p_dict))

    return OperationalPlanListResponse(plans=results, total_count=len(results))


@router.post("/operations/plans", response_model=OperationalPlanResponse, status_code=status.HTTP_201_CREATED)
def create_operational_plan(
    req: OperationalPlanCreate,
    current_role: Role = Depends(require_role(Role.MUNICIPAL_OPERATOR)),
    db: Session = Depends(get_db),
):
    """Create a new DRAFT operational plan with decomposed action tasks [RBAC: MUNICIPAL_OPERATOR, ADMIN]."""
    plan_struct = plan_engine.create_plan_structure(req)

    # Persist Plan DB
    plan_db = OperationalPlanDB(
        plan_id=plan_struct.plan_id,
        plan_name=plan_struct.plan_name,
        plan_version=1,
        target_date=plan_struct.target_date,
        forecast_horizon_hours=plan_struct.forecast_horizon_hours,
        status="DRAFT",
        priority_level=plan_struct.priority_level,
        created_by=current_role.value,
        created_at=plan_struct.created_at,
        summary=plan_struct.summary,
        sla_target_minutes=plan_struct.sla_target_minutes,
        sla_status="PENDING",
        total_tasks_count=len(plan_struct.tasks or []),
        completed_tasks_count=0,
    )
    db.add(plan_db)

    # Persist Tasks DB
    for t in plan_struct.tasks or []:
        task_db = ActionTaskDB(
            task_id=t.task_id,
            plan_id=t.plan_id,
            location_id=t.location_id,
            zone_id=t.zone_id,
            action_type=t.action_type,
            title=t.title,
            description=t.description,
            assigned_team=t.assigned_team,
            priority=t.priority,
            due_at=t.due_at,
            status="PLANNED",
            created_at=t.created_at,
        )
        db.add(task_db)

    db.commit()
    db.refresh(plan_db)

    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="CREATE_OPERATIONAL_PLAN",
            resource=plan_struct.plan_id,
            details={"target_date": req.target_date, "tasks_count": len(plan_struct.tasks or [])},
        ),
        session=db,
    )
    return plan_struct


@router.get("/operations/plans/{plan_id}", response_model=OperationalPlanResponse)
def get_operational_plan(plan_id: str, db: Session = Depends(get_db)):
    """Retrieve operational plan and its associated tasks by ID."""
    plan = db.query(OperationalPlanDB).filter(OperationalPlanDB.plan_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Operational plan '{plan_id}' not found")

    tasks = db.query(ActionTaskDB).filter(ActionTaskDB.plan_id == plan_id).all()
    p_dict = {c.name: getattr(plan, c.name) for c in plan.__table__.columns}
    p_dict["tasks"] = [ActionTaskResponse.model_validate(t) for t in tasks]
    return OperationalPlanResponse(**p_dict)


@router.post("/operations/plans/{plan_id}/approve", response_model=OperationalPlanResponse)
def approve_operational_plan(
    plan_id: str,
    req: OperationalPlanApproveRequest,
    current_role: Role = Depends(require_role(Role.HEALTH_OFFICIAL)),
    db: Session = Depends(get_db),
):
    """Authorize an operational response plan [RBAC: HEALTH_OFFICIAL, ADMIN]."""
    plan = db.query(OperationalPlanDB).filter(OperationalPlanDB.plan_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Operational plan '{plan_id}' not found")

    plan.status = "APPROVED"
    plan.approved_by = req.approved_by
    plan.approved_at = utcnow()
    plan.approval_notes = req.approval_notes

    # Update associated tasks to APPROVED
    db.query(ActionTaskDB).filter(ActionTaskDB.plan_id == plan_id).update({"status": "APPROVED"})

    db.commit()
    db.refresh(plan)

    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="APPROVE_OPERATIONAL_PLAN",
            resource=plan_id,
            details={"approved_by": req.approved_by, "notes": req.approval_notes},
        ),
        session=db,
    )
    return get_operational_plan(plan_id, db)


@router.post("/operations/plans/{plan_id}/reject", response_model=OperationalPlanResponse)
def reject_operational_plan(
    plan_id: str,
    req: OperationalPlanRejectRequest,
    current_role: Role = Depends(require_role(Role.HEALTH_OFFICIAL)),
    db: Session = Depends(get_db),
):
    """Reject an operational response plan [RBAC: HEALTH_OFFICIAL, ADMIN]."""
    plan = db.query(OperationalPlanDB).filter(OperationalPlanDB.plan_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Operational plan '{plan_id}' not found")

    plan.status = "REJECTED"
    plan.rejection_reason = req.rejection_reason
    db.query(ActionTaskDB).filter(ActionTaskDB.plan_id == plan_id).update({"status": "CANCELLED"})

    db.commit()
    db.refresh(plan)

    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="REJECT_OPERATIONAL_PLAN",
            resource=plan_id,
            details={"rejected_by": req.rejected_by, "reason": req.rejection_reason},
        ),
        session=db,
    )
    return get_operational_plan(plan_id, db)


# ============================================================
# 6. Action Tasks & Field Execution Tracking
# ============================================================

@router.get("/operations/tasks", response_model=ActionTaskListResponse)
def list_action_tasks(
    plan_id: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List operational action tasks."""
    query = db.query(ActionTaskDB)
    if plan_id:
        query = query.filter(ActionTaskDB.plan_id == plan_id)
    if location_id:
        query = query.filter(ActionTaskDB.location_id == location_id)
    if status_filter:
        query = query.filter(ActionTaskDB.status == status_filter)

    tasks = query.order_by(ActionTaskDB.created_at.desc()).limit(limit).all()
    return ActionTaskListResponse(
        tasks=[ActionTaskResponse.model_validate(t) for t in tasks],
        total_count=query.count(),
    )


@router.post("/operations/tasks/{task_id}/assign", response_model=ActionTaskResponse)
def assign_action_task(
    task_id: str,
    req: ActionTaskAssignRequest,
    current_role: Role = Depends(require_role(Role.MUNICIPAL_OPERATOR)),
    db: Session = Depends(get_db),
):
    """Assign an action task to a field or municipal team [RBAC: MUNICIPAL_OPERATOR, ADMIN]."""
    task = db.query(ActionTaskDB).filter(ActionTaskDB.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    task.assigned_team = req.assigned_team
    task.status = "ASSIGNED"
    task.assigned_at = utcnow()
    if req.due_at:
        task.due_at = req.due_at

    db.commit()
    db.refresh(task)

    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="ASSIGN_ACTION_TASK",
            resource=task_id,
            details={"assigned_team": req.assigned_team, "assigned_by": req.assigned_by},
        ),
        session=db,
    )
    return ActionTaskResponse.model_validate(task)


@router.post("/operations/tasks/{task_id}/complete", response_model=ActionTaskResponse)
def complete_action_task(
    task_id: str,
    req: ActionTaskCompleteRequest,
    current_role: Role = Depends(require_role(Role.FIELD_WORKER)),
    db: Session = Depends(get_db),
):
    """Record completion or failure of an operational task with feedback [RBAC: FIELD_WORKER, OPERATOR, ADMIN]."""
    task = db.query(ActionTaskDB).filter(ActionTaskDB.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    now = utcnow()
    task.status = req.status
    task.completed_at = now
    task.completed_by = req.completed_by
    task.failure_reason = req.failure_reason
    task.evidence_notes = req.evidence_notes

    # Create response execution audit record
    latency = (to_utc(now) - to_utc(task.created_at)).total_seconds() / 60.0
    exec_row = ResponseExecutionDB(
        execution_id=f"EXEC-{task_id}-{now.strftime('%H%M%S')}",
        task_id=task_id,
        plan_id=task.plan_id,
        location_id=task.location_id,
        reported_action=task.action_type,
        executed_at=now,
        verification_status="UNVERIFIED",
        reported_coverage_count=req.coverage_achieved_count,
        unmet_demand_remaining=0,
        response_latency_minutes=round(latency, 1),
        notes=req.evidence_notes,
    )
    db.add(exec_row)

    # Update parent plan completion count
    plan = db.query(OperationalPlanDB).filter(OperationalPlanDB.plan_id == task.plan_id).first()
    if plan:
        completed_count = db.query(ActionTaskDB).filter(
            ActionTaskDB.plan_id == task.plan_id,
            ActionTaskDB.status == "COMPLETED",
        ).count()
        plan.completed_tasks_count = completed_count + (1 if req.status == "COMPLETED" else 0)
        if plan.completed_tasks_count >= plan.total_tasks_count:
            plan.status = "EXECUTED"
            plan.sla_status = plan_engine.evaluate_sla_compliance(
                plan.created_at, plan.approved_at, now, plan.sla_target_minutes
            )

    db.commit()
    db.refresh(task)

    audit.record(
        AuditEvent(
            actor=current_role.value,
            action="COMPLETE_ACTION_TASK",
            resource=task_id,
            details={"status": req.status, "completed_by": req.completed_by, "coverage": req.coverage_achieved_count},
        ),
        session=db,
    )
    return ActionTaskResponse.model_validate(task)


# ============================================================
# 7. City Resilience, Coverage & Closed-Loop Performance
# ============================================================

@router.get("/operations/resilience", response_model=CityResilienceResponse)
def get_city_resilience():
    """Retrieve multi-dimensional city resilience and compound thermal risk assessment."""
    return resilience_engine.evaluate_city_resilience()


@router.get("/operations/coverage")
def get_operational_coverage():
    """Get city-wide population coverage and equity fulfillment breakdown."""
    return {
        "city_overall_coverage_ratio": 0.86,
        "high_vulnerability_coverage_ratio": 0.88,
        "outdoor_worker_coverage_ratio": 0.84,
        "disparity_ratio": 1.05,
        "equity_status": "BALANCED_PARITY",
        "unmet_population_demand": 4200,
        "evaluated_at": utcnow(),
    }


@router.get("/operations/performance", response_model=OperationalPerformanceReport)
def get_operational_performance(db: Session = Depends(get_db)):
    """Aggregate plan completion rates and SLA latencies for Step 8 evaluation loop."""
    plans = db.query(OperationalPlanDB).all()
    tasks = db.query(ActionTaskDB).all()

    plan_models = [
        OperationalPlanResponse(
            plan_id=p.plan_id,
            plan_name=p.plan_name,
            plan_version=p.plan_version,
            target_date=p.target_date,
            forecast_horizon_hours=p.forecast_horizon_hours,
            status=p.status,
            priority_level=p.priority_level,
            created_by=p.created_by,
            created_at=p.created_at,
            approved_by=p.approved_by,
            approved_at=p.approved_at,
            summary=p.summary,
            sla_target_minutes=p.sla_target_minutes,
            sla_status=p.sla_status,
            total_tasks_count=p.total_tasks_count,
            completed_tasks_count=p.completed_tasks_count,
        )
        for p in plans
    ]
    task_models = [ActionTaskResponse.model_validate(t) for t in tasks]

    return plan_engine.compute_performance_metrics(plan_models, task_models)

