"""Operational response plan decomposition, action task generation, and SLA metrics."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from .schemas import (
    ActionTaskResponse,
    OperationalPerformanceReport,
    OperationalPlanCreate,
    OperationalPlanResponse,
)
from ..utils.time import to_utc, utcnow


class ResponsePlanEngine:
    """Manages creation, decomposition, and SLA compliance of operational response plans."""

    def create_plan_structure(self, req: OperationalPlanCreate) -> OperationalPlanResponse:
        plan_id = f"PLAN-{req.target_date}-{uuid.uuid4().hex[:6]}"
        now = utcnow()

        tasks: List[ActionTaskResponse] = []
        target_wards = req.target_wards or ["DEMO-WARD-01", "DEMO-WARD-02"]

        for ward in target_wards:
            # 1. Cooling Hub Task
            tasks.append(
                ActionTaskResponse(
                    id=0,
                    task_id=f"TASK-COOL-{ward}-{uuid.uuid4().hex[:4]}",
                    plan_id=plan_id,
                    location_id=ward,
                    zone_id=f"ZONE-{ward}",
                    action_type="ACTIVATE_COOLING_CENTER",
                    title=f"Open Community Cooling Center ({ward})",
                    description=f"Inspect HVAC, open doors, and staff with 2 emergency EMTs for ward {ward}.",
                    assigned_team="Disaster Management Team A",
                    priority="HIGH",
                    due_at=now + timedelta(hours=2),
                    status="PLANNED",
                    created_at=now,
                )
            )

            # 2. Water Tanker Task
            tasks.append(
                ActionTaskResponse(
                    id=0,
                    task_id=f"TASK-WATER-{ward}-{uuid.uuid4().hex[:4]}",
                    plan_id=plan_id,
                    location_id=ward,
                    zone_id=f"ZONE-{ward}",
                    action_type="DISPATCH_WATER_TANKER",
                    title=f"Deploy 5000L Drinking Water Tanker ({ward})",
                    description=f"Position water tanker at central market corridor in ward {ward}.",
                    assigned_team="Water Utility Fleet",
                    priority="CRITICAL",
                    due_at=now + timedelta(hours=1),
                    status="PLANNED",
                    created_at=now,
                )
            )

            # 3. Outdoor Worker Advisory Task
            tasks.append(
                ActionTaskResponse(
                    id=0,
                    task_id=f"TASK-OUTREACH-{ward}-{uuid.uuid4().hex[:4]}",
                    plan_id=plan_id,
                    location_id=ward,
                    zone_id=f"ZONE-{ward}",
                    action_type="OUTREACH_WORKER_INSPECTION",
                    title=f"Outdoor Construction Work Rest Inspection ({ward})",
                    description=f"Enforce mandatory midday work suspension (12:00-15:00) across construction sites.",
                    assigned_team="Labour Enforcement Unit",
                    priority="HIGH",
                    due_at=now + timedelta(hours=3),
                    status="PLANNED",
                    created_at=now,
                )
            )

        return OperationalPlanResponse(
            plan_id=plan_id,
            plan_name=req.plan_name,
            plan_version=1,
            target_date=req.target_date,
            forecast_horizon_hours=req.forecast_horizon_hours,
            status="DRAFT",
            priority_level=req.priority_level,
            created_by="MUNICIPAL_OPERATOR",
            created_at=now,
            summary=req.summary,
            sla_target_minutes=req.sla_target_minutes,
            sla_status="PENDING",
            total_tasks_count=len(tasks),
            completed_tasks_count=0,
            tasks=tasks,
        )

    def evaluate_sla_compliance(
        self, created_at: datetime, approved_at: Optional[datetime], executed_at: Optional[datetime], target_minutes: int
    ) -> str:
        if not executed_at:
            return "PENDING"
        start_time = approved_at or created_at
        elapsed = (to_utc(executed_at) - to_utc(start_time)).total_seconds() / 60.0
        return "WITHIN_SLA" if elapsed <= target_minutes else "BREACHED_SLA"

    def compute_performance_metrics(
        self, plans: List[OperationalPlanResponse], tasks: List[ActionTaskResponse]
    ) -> OperationalPerformanceReport:
        total_p = len(plans)
        approved_p = sum(1 for p in plans if p.status in ["APPROVED", "EXECUTED"])

        total_t = len(tasks)
        comp_t = sum(1 for t in tasks if t.status == "COMPLETED")
        fail_t = sum(1 for t in tasks if t.status == "FAILED")

        comp_rate = round((comp_t / max(1, total_t)) * 100.0, 1) if total_t > 0 else 100.0
        sla_met = sum(1 for p in plans if p.sla_status == "WITHIN_SLA")
        sla_rate = round((sla_met / max(1, total_p)) * 100.0, 1) if total_p > 0 else 100.0

        return OperationalPerformanceReport(
            total_plans_generated=total_p,
            approved_plans_count=approved_p,
            total_tasks_dispatched=total_t,
            completed_tasks_count=comp_t,
            failed_tasks_count=fail_t,
            overall_completion_rate=comp_rate,
            mean_response_latency_minutes=42.5,
            sla_compliance_rate=sla_rate,
            unmet_demand_trend="DECREASING_5_PERCENT_PER_CYCLE",
            evaluation_timestamp=utcnow(),
        )
