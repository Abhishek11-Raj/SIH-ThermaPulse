"""Pydantic V2 schemas for Step 9:
Operational Decision Support, City-Scale Planning, Resource Optimization,
Scenario Orchestration, Resilience Planning & Human-in-the-Loop Response Management.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from ..utils.time import utcnow


# ============================================================
# 1. Operational Priority & Multi-Criteria Schemas
# ============================================================

class FactorContribution(BaseModel):
    factor_name: str
    raw_value: float
    normalized_score: float
    weight: float
    weighted_contribution: float
    data_source: str
    confidence: str = "HIGH"


class OperationalPriorityRequest(BaseModel):
    location_id: str
    health_risk_probability: float = Field(..., ge=0.0, le=1.0)
    thermal_stress_score: float = Field(..., ge=0.0, le=100.0)
    nighttime_recovery_deficit: float = Field(default=0.0, ge=0.0)
    vulnerable_population_fraction: float = Field(..., ge=0.0, le=1.0)
    outdoor_worker_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    resource_shortage_severity: float = Field(default=0.0, ge=0.0, le=1.0)
    hospital_surge_occupancy: float = Field(default=0.5, ge=0.0, le=2.0)
    alert_severity_code: str = "WATCH"
    forecast_lead_time_hours: float = Field(default=24.0, ge=0.0)
    is_out_of_distribution: bool = False
    uncertainty_level: float = Field(default=0.1, ge=0.0, le=1.0)


class OperationalPriorityScoreResponse(BaseModel):
    location_id: str
    priority_score: float = Field(..., ge=0.0, le=100.0)
    operational_risk_level: Literal["CRITICAL", "URGENT", "ELEVATED", "NORMAL", "LOW"]
    rank_order: Optional[int] = None
    urgency_recommendation: str
    factor_contributions: List[FactorContribution]
    uncertainty_penalty_applied: float = 0.0
    data_quality_limitations: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=utcnow)


class CityPriorityListResponse(BaseModel):
    evaluated_at: datetime = Field(default_factory=utcnow)
    total_wards_evaluated: int
    critical_wards_count: int
    urgent_wards_count: int
    ward_rankings: List[OperationalPriorityScoreResponse]


# ============================================================
# 2. Resource Inventory & Gap Schemas
# ============================================================

class ResourceBase(BaseModel):
    resource_id: str
    location_id: str
    zone_id: Optional[str] = None
    resource_type: str
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_capacity: float = Field(default=100.0, ge=0.0)
    available_capacity: float = Field(default=100.0, ge=0.0)
    capacity_unit: str = "PERSONS"
    operating_hours: str = "09:00-18:00"
    status: Literal["AVAILABLE", "LIMITED", "FULL", "UNAVAILABLE", "UNKNOWN"] = "AVAILABLE"
    confidence: Literal["VERIFIED", "ESTIMATED", "UNKNOWN"] = "VERIFIED"
    source: str = "MUNICIPAL_INVENTORY"
    provenance: Optional[Dict[str, Any]] = None
    is_synthetic: bool = False


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    available_capacity: Optional[float] = None
    status: Optional[Literal["AVAILABLE", "LIMITED", "FULL", "UNAVAILABLE", "UNKNOWN"]] = None
    operating_hours: Optional[str] = None
    confidence: Optional[Literal["VERIFIED", "ESTIMATED", "UNKNOWN"]] = None


class ResourceResponse(ResourceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_updated_at: datetime


class ResourceListResponse(BaseModel):
    resources: List[ResourceResponse]
    total_count: int


class ResourceGapResponse(BaseModel):
    gap_id: str
    location_id: str
    zone_id: Optional[str] = None
    resource_type: str
    demanded_capacity: float
    available_capacity: float
    deficit_capacity: float
    coverage_ratio: float
    travel_distance_km: Optional[float] = None
    travel_time_minutes: Optional[float] = None
    unmet_demand_count: int
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    actionable_recommendation: str
    identified_at: datetime = Field(default_factory=utcnow)


class ResourceGapSummaryResponse(BaseModel):
    evaluated_at: datetime = Field(default_factory=utcnow)
    total_gaps_count: int
    critical_deficits_count: int
    gaps: List[ResourceGapResponse]


# ============================================================
# 3. Constrained Resource Allocation Schemas
# ============================================================

class WardAllocationItem(BaseModel):
    location_id: str
    allocated_mobile_cooling_vans: int = 0
    allocated_water_tankers: int = 0
    allocated_field_outreach_teams: int = 0
    allocated_ors_depots_packets: int = 0
    allocated_ambulances: int = 0
    expected_coverage_ratio: float
    unmet_vulnerable_count: int


class EquityAllocationAudit(BaseModel):
    equity_constraint_satisfied: bool
    vulnerable_ward_allocation_share: float
    general_ward_allocation_share: float
    disparity_ratio: float
    notes: str


class ResourceAllocationRequest(BaseModel):
    target_date: str
    available_mobile_cooling_vans: int = Field(default=5, ge=0)
    available_water_tankers: int = Field(default=10, ge=0)
    available_field_outreach_teams: int = Field(default=15, ge=0)
    available_ors_packets: int = Field(default=10000, ge=0)
    available_ambulances: int = Field(default=6, ge=0)
    equity_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    urgency_weight: float = Field(default=0.6, ge=0.0, le=1.0)


class ResourceAllocationResponse(BaseModel):
    allocation_id: str
    target_date: str
    generated_at: datetime = Field(default_factory=utcnow)
    total_resources_dispatched: Dict[str, int]
    ward_allocations: List[WardAllocationItem]
    equity_audit: EquityAllocationAudit
    objective_score: float
    governance_notice: str = "RECOMMENDATION_ONLY_REQUIRES_HUMAN_AUTHORIZATION"


# ============================================================
# 4. Multi-Intervention Scenario Orchestration Schemas
# ============================================================

class ScenarioSimulationRequest(BaseModel):
    scenario_name: str
    location_id: str
    target_date: str
    additional_cooling_centers_count: int = 0
    additional_water_tankers_count: int = 0
    workplace_midday_shutdown: bool = False
    cool_roof_coverage_increase_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    outreach_alert_coverage_pct: float = Field(default=0.0, ge=0.0, le=100.0)


class ScenarioSimulationResponse(BaseModel):
    scenario_id: str
    scenario_name: str
    location_id: str
    target_date: str
    baseline_risk_probability: float
    counterfactual_risk_probability: float
    risk_delta: float
    relative_risk_reduction_pct: float
    feasibility_status: Literal["FEASIBLE", "PARTIALLY_FEASIBLE", "NOT_FEASIBLE", "UNKNOWN"]
    estimated_coverage_count: int
    estimated_resource_cost: Optional[float] = None
    causal_status: str = "MODEL_BASED_COUNTERFACTUAL"
    uncertainty_range: Dict[str, float]
    evaluated_at: datetime = Field(default_factory=utcnow)


class ScenarioCompareRequest(BaseModel):
    scenarios: List[ScenarioSimulationRequest]


class ScenarioCompareResponse(BaseModel):
    comparison_matrix: List[ScenarioSimulationResponse]
    recommended_scenario_id: str
    rationale: str


# ============================================================
# 5. Operational Plan & Action Task Schemas
# ============================================================

class ActionTaskCreate(BaseModel):
    plan_id: str
    location_id: str
    zone_id: Optional[str] = None
    action_type: str
    title: str
    description: str
    assigned_team: Optional[str] = None
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "HIGH"
    due_at: Optional[datetime] = None


class ActionTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: str
    plan_id: str
    location_id: str
    zone_id: Optional[str] = None
    action_type: str
    title: str
    description: str
    assigned_team: Optional[str] = None
    priority: str
    due_at: Optional[datetime] = None
    status: Literal["PLANNED", "APPROVED", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"]
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    failure_reason: Optional[str] = None
    evidence_notes: Optional[str] = None
    evidence_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class ActionTaskAssignRequest(BaseModel):
    assigned_team: str
    assigned_by: str
    due_at: Optional[datetime] = None


class ActionTaskCompleteRequest(BaseModel):
    status: Literal["COMPLETED", "FAILED"]
    completed_by: str
    evidence_notes: Optional[str] = None
    coverage_achieved_count: int = 0
    failure_reason: Optional[str] = None


class ActionTaskListResponse(BaseModel):
    tasks: List[ActionTaskResponse]
    total_count: int


class OperationalPlanCreate(BaseModel):
    plan_name: str
    target_date: str
    forecast_horizon_hours: int = 48
    priority_level: Literal["CRITICAL", "PRIORITY", "ROUTINE"] = "PRIORITY"
    summary: str
    sla_target_minutes: int = 120
    target_wards: List[str] = Field(default_factory=list)


class OperationalPlanApproveRequest(BaseModel):
    approved_by: str
    approval_notes: Optional[str] = None


class OperationalPlanRejectRequest(BaseModel):
    rejected_by: str
    rejection_reason: str


class OperationalPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    plan_id: str
    plan_name: str
    plan_version: int
    target_date: str
    forecast_horizon_hours: int
    status: Literal["DRAFT", "REVIEW", "APPROVED", "REJECTED", "EXECUTED", "CANCELLED"]
    priority_level: str
    created_by: str
    created_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    summary: str
    sla_target_minutes: int
    sla_status: str
    total_tasks_count: int
    completed_tasks_count: int
    tasks: Optional[List[ActionTaskResponse]] = None


class OperationalPlanListResponse(BaseModel):
    plans: List[OperationalPlanResponse]
    total_count: int


# ============================================================
# 6. Operational Zone & City Resilience Schemas
# ============================================================

class OperationalZoneCreate(BaseModel):
    zone_id: str
    location_id: str
    zone_name: str
    population_total: int = 50000
    vulnerable_population: int = 15000
    outdoor_worker_count: int = 8000
    baseline_cooling_capacity: int = 500
    baseline_water_capacity_lpd: float = 25000.0
    hospital_beds_count: int = 120
    ambulance_stations_count: int = 2
    is_synthetic: bool = False


class OperationalZoneResponse(OperationalZoneCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    operational_risk_level: str
    priority_score: float
    priority_rank: int
    last_evaluated_at: datetime
    data_quality_grade: str


class OperationalZoneListResponse(BaseModel):
    zones: List[OperationalZoneResponse]
    total_count: int


class CityResilienceDimension(BaseModel):
    dimension_name: str
    score: float = Field(..., ge=0.0, le=100.0)
    status: Literal["CRITICAL", "DEFICIT", "MODERATE", "ADEQUATE", "OPTIMAL"]
    description: str


class CityResilienceResponse(BaseModel):
    composite_resilience_score: float
    overall_status: str
    dimensions: List[CityResilienceDimension]
    compound_heat_power_strain_index: float
    compound_heat_water_stress_index: float
    evaluated_at: datetime = Field(default_factory=utcnow)


class OperationalPerformanceReport(BaseModel):
    total_plans_generated: int
    approved_plans_count: int
    total_tasks_dispatched: int
    completed_tasks_count: int
    failed_tasks_count: int
    overall_completion_rate: float
    mean_response_latency_minutes: float
    sla_compliance_rate: float
    unmet_demand_trend: str
    evaluation_timestamp: datetime = Field(default_factory=utcnow)
