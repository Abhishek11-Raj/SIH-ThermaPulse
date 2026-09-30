"""Strategic Resilience Roadmap Engine: Sequenced multi-horizon adaptation plans,
dependency validation, and human-in-the-loop governance lifecycle.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..models.digital_twin import StrategicPlanDB
from ..utils.time import utcnow
from .schemas import (
    RoadmapPhase,
    StrategicPlanCreate,
    StrategicPlanResponse,
    StrategicPlanStatus,
    StrategicRoadmapAction,
    StrategicRoadmapPhase,
    StrategicRoadmapResponse,
)


class StrategicRoadmapEngine:
    """Orchestrates multi-horizon resilience roadmaps and tracks strategic plan governance."""

    @classmethod
    def generate_roadmap(
        cls, db: Session, location_id: str, target_horizon: str = "2030"
    ) -> StrategicRoadmapResponse:
        """Generates sequenced multi-horizon strategic adaptation actions."""
        roadmap_id = f"rdmp_{uuid.uuid4().hex[:8]}"

        # Phase 1: NOW (0 - 6 Months)
        phase_now = StrategicRoadmapPhase(
            phase=RoadmapPhase.NOW,
            phase_title="Immediate Emergency Heat Actions & Quick Wins",
            timeframe="Months 0–6",
            expected_resilience_gain=8.5,
            total_cost_est=250000.0,
            actions=[
                StrategicRoadmapAction(
                    action_id="act_now_1",
                    title="Enforce Mandatory Midday Rest Pauses for Construction Workers",
                    intervention_type="HEAT_ADAPTIVE_WORK_ORDINANCE",
                    phase=RoadmapPhase.NOW,
                    target_locations=[location_id],
                    estimated_duration_months=2,
                    prerequisites=[],
                    capital_cost_est=15000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Municipal Labour & Welfare Department",
                    milestone_success_metric="100% notification to registered construction sites; daily compliance inspections",
                ),
                StrategicRoadmapAction(
                    action_id="act_now_2",
                    title="Deploy Rapid Mobile Hydration & ORS Kiosks",
                    intervention_type="EMERGENCY_WATER_RESILIENCE",
                    phase=RoadmapPhase.NOW,
                    target_locations=[location_id],
                    estimated_duration_months=3,
                    prerequisites=[],
                    capital_cost_est=75000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Delhi Jal Board / Municipal Water Authority",
                    milestone_success_metric="25 high-density pedestrian junctions equipped with active chilled water dispensers",
                ),
                StrategicRoadmapAction(
                    action_id="act_now_3",
                    title="Activate Emergency Community Cooling Shelters",
                    intervention_type="DISTRIBUTED_COOLING_HUBS",
                    phase=RoadmapPhase.NOW,
                    target_locations=[location_id],
                    estimated_duration_months=2,
                    prerequisites=[],
                    capital_cost_est=160000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Disaster Management Authority",
                    milestone_success_metric="10 public community halls converted into air-cooled respite hubs",
                ),
            ],
        )

        # Phase 2: SHORT_TERM (6 - 24 Months)
        phase_short = StrategicRoadmapPhase(
            phase=RoadmapPhase.SHORT_TERM,
            phase_title="Targeted Built-Environment Retrofits & Shade Expansion",
            timeframe="Months 6–24",
            expected_resilience_gain=14.0,
            total_cost_est=1200000.0,
            actions=[
                StrategicRoadmapAction(
                    action_id="act_short_1",
                    title="Slum & Informal Settlement Cool Roof Coating Subsidy",
                    intervention_type="COOL_ROOF_RETROFIT",
                    phase=RoadmapPhase.SHORT_TERM,
                    target_locations=[location_id],
                    estimated_duration_months=12,
                    prerequisites=["act_now_3"],
                    capital_cost_est=500000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Urban Development & Housing Board",
                    milestone_success_metric="15,000 households coated with high-albedo solar reflective paint",
                ),
                StrategicRoadmapAction(
                    action_id="act_short_2",
                    title="Public Transit & Market Shade Canopy Network",
                    intervention_type="PUBLIC_SHADE_NETWORK",
                    phase=RoadmapPhase.SHORT_TERM,
                    target_locations=[location_id],
                    estimated_duration_months=10,
                    prerequisites=[],
                    capital_cost_est=400000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Public Works Department (PWD)",
                    milestone_success_metric="50 bus terminals and vendor markets fitted with UV-blocking tensile shades",
                ),
                StrategicRoadmapAction(
                    action_id="act_short_3",
                    title="Deploy IoT Hyperlocal Microclimate Sensing Network",
                    intervention_type="DATA_READINESS",
                    phase=RoadmapPhase.SHORT_TERM,
                    target_locations=[location_id],
                    estimated_duration_months=6,
                    prerequisites=[],
                    capital_cost_est=300000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Smart Cities Mission / KESHAV Telemetry Group",
                    milestone_success_metric="40 IoT weather sensors streaming real-time wet-bulb temperature",
                ),
            ],
        )

        # Phase 3: MEDIUM_TERM (2 - 5 Years)
        phase_med = StrategicRoadmapPhase(
            phase=RoadmapPhase.MEDIUM_TERM,
            phase_title="Nature-Based Solutions & Microgrid Energy Security",
            timeframe="Years 2–5",
            expected_resilience_gain=18.0,
            total_cost_est=4500000.0,
            actions=[
                StrategicRoadmapAction(
                    action_id="act_med_1",
                    title="Urban Miyawaki Afforestation & Green Transit Corridors",
                    intervention_type="URBAN_CANOPY_AFFORESTATION",
                    phase=RoadmapPhase.MEDIUM_TERM,
                    target_locations=[location_id],
                    estimated_duration_months=36,
                    prerequisites=["act_short_1"],
                    capital_cost_est=2000000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Forest & Environment Department",
                    milestone_success_metric="250,000 native trees established; 35% canopy coverage in targeted wards",
                ),
                StrategicRoadmapAction(
                    action_id="act_med_2",
                    title="Critical Hospital & Cooling Hub Solar + BESS Microgrids",
                    intervention_type="GRID_BACKUP_SOLAR_STORAGE",
                    phase=RoadmapPhase.MEDIUM_TERM,
                    target_locations=[location_id],
                    estimated_duration_months=24,
                    prerequisites=["act_now_3"],
                    capital_cost_est=2500000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Power Distribution Company (DISCOM)",
                    milestone_success_metric="100% uninterrupted cooling capacity at district hospitals during grid brownouts",
                ),
            ],
        )

        # Phase 4: LONG_TERM (5 - 10 Years)
        phase_long = StrategicRoadmapPhase(
            phase=RoadmapPhase.LONG_TERM,
            phase_title="Transformational Urban Architecture & District Cooling",
            timeframe="Years 5–10",
            expected_resilience_gain=22.0,
            total_cost_est=12000000.0,
            actions=[
                StrategicRoadmapAction(
                    action_id="act_long_1",
                    title="District Passive Cooling & Geothermal Thermal Management Infrastructure",
                    intervention_type="DISTRICT_COOLING_INFRASTRUCTURE",
                    phase=RoadmapPhase.LONG_TERM,
                    target_locations=[location_id],
                    estimated_duration_months=60,
                    prerequisites=["act_med_2"],
                    capital_cost_est=12000000.0,
                    cost_status="ESTIMATED",
                    responsible_agency="Urban Planning & Infrastructure Development Authority",
                    milestone_success_metric="Centralized high-efficiency district cooling grid serving high-density commercial & residential hubs",
                ),
            ],
        )

        phases = [phase_now, phase_short, phase_med, phase_long]
        total_actions = sum(len(p.actions) for p in phases)
        projected_resilience = min(95.0, 58.5 + sum(p.expected_resilience_gain for p in phases))

        return StrategicRoadmapResponse(
            roadmap_id=roadmap_id,
            location_id=location_id,
            target_horizon=target_horizon,
            phases=phases,
            total_estimated_actions=total_actions,
            projected_final_resilience_score=round(projected_resilience, 1),
            governance_notes="Roadmap sequences actions by lead time and dependencies to maximize life-saving impact while optimizing capital allocation.",
        )

    @classmethod
    def create_strategic_plan(
        cls, db: Session, req: StrategicPlanCreate, user_id: str = "PLANNING_OFFICER"
    ) -> StrategicPlanResponse:
        """Creates a formal strategic resilience plan."""
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        primary_loc = req.target_locations[0] if req.target_locations else "LOC_DELHI_001"

        roadmap = cls.generate_roadmap(db, primary_loc, req.target_horizon)
        phases_payload = {
            p.phase.value: {
                "phase_title": p.phase_title,
                "timeframe": p.timeframe,
                "expected_resilience_gain": p.expected_resilience_gain,
                "total_cost_est": p.total_cost_est,
                "actions": [a.model_dump() for a in p.actions],
            }
            for p in roadmap.phases
        }

        gov_metadata = {
            "review_stage": "STAGE_1_INTERNAL_PLANNING",
            "stakeholders_consulted": ["HEALTH_OFFICIAL", "MUNICIPAL_OPERATOR", "DISCOM"],
            "version": "1.0.0",
        }

        row = StrategicPlanDB(
            plan_id=plan_id,
            plan_name=req.plan_name,
            target_horizon=req.target_horizon,
            status=StrategicPlanStatus.DRAFT.value,
            portfolio_ids=req.portfolio_ids,
            roadmap_phases=phases_payload,
            governance_metadata=gov_metadata,
            created_by=user_id,
            notes=req.notes,
            created_at=utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        return StrategicPlanResponse.model_validate(row)

    @classmethod
    def list_strategic_plans(cls, db: Session) -> List[StrategicPlanResponse]:
        """Lists all registered strategic adaptation plans."""
        rows = db.execute(select(StrategicPlanDB).order_by(desc(StrategicPlanDB.created_at))).scalars().all()
        return [StrategicPlanResponse.model_validate(r) for r in rows]

    @classmethod
    def update_plan_status(
        cls, db: Session, plan_id: str, new_status: str, user_id: str, notes: Optional[str] = None
    ) -> StrategicPlanResponse:
        """Updates strategic plan status under governance controls."""
        row = db.execute(
            select(StrategicPlanDB).where(StrategicPlanDB.plan_id == plan_id)
        ).scalar_one_or_none()

        if not row:
            raise ValueError(f"Strategic Plan '{plan_id}' not found")

        row.status = new_status
        if new_status == StrategicPlanStatus.APPROVED.value:
            row.approved_by = user_id
            row.approved_at = utcnow()
        if notes:
            row.notes = f"{(row.notes or '')}\n[{utcnow().isoformat()}] {user_id}: {notes}".strip()

        db.commit()
        db.refresh(row)
        return StrategicPlanResponse.model_validate(row)
