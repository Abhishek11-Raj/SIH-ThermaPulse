"""Pydantic V2 schemas for Step 10: Heat Resilience Digital Twin, Climate Scenarios,
Adaptation Portfolios, Cascading Risks, and Strategic Roadmaps.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..utils.time import utcnow


class TimeDimension(str, Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    FORECAST = "FORECAST"
    SCENARIO = "SCENARIO"
    LONG_TERM_PROJECTION = "LONG_TERM_PROJECTION"


class DataState(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    FORECAST = "FORECAST"
    PROJECTED = "PROJECTED"
    MODELED = "MODELED"
    SIMULATED = "SIMULATED"
    RECOMMENDED = "RECOMMENDED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"


class RelationshipStatus(str, Enum):
    MODEL_BASED = "MODEL_BASED"
    ASSOCIATIONAL = "ASSOCIATIONAL"
    CAUSALLY_VALIDATED = "CAUSALLY_VALIDATED"


class ResilienceDimension(str, Enum):
    HEAT_EXPOSURE = "HEAT_EXPOSURE"
    NIGHTTIME_RECOVERY = "NIGHTTIME_RECOVERY"
    HEALTHCARE_ACCESS = "HEALTHCARE_ACCESS"
    COOLING_ACCESS = "COOLING_ACCESS"
    WATER_ACCESS = "WATER_ACCESS"
    POWER_RESILIENCE = "POWER_RESILIENCE"
    GREEN_INFRASTRUCTURE = "GREEN_INFRASTRUCTURE"
    EMERGENCY_RESPONSE = "EMERGENCY_RESPONSE"
    DATA_READINESS = "DATA_READINESS"
    COMMUNITY_PROTECTION = "COMMUNITY_PROTECTION"


class ResilienceGrade(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class ScenarioCategory(str, Enum):
    BASELINE = "BASELINE"
    MODERATE_WARMING = "MODERATE_WARMING"
    HIGH_WARMING = "HIGH_WARMING"
    EXTREME_HEAT = "EXTREME_HEAT"
    HOTTER_NIGHTS = "HOTTER_NIGHTS"
    COMPOUND_HEAT_POLLUTION = "COMPOUND_HEAT_POLLUTION"


class PortfolioStatus(str, Enum):
    PROPOSED = "PROPOSED"
    SIMULATED = "SIMULATED"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"
    CANCELLED = "CANCELLED"


class StrategicPlanStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    IMPLEMENTING = "IMPLEMENTING"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class RoadmapPhase(str, Enum):
    NOW = "NOW"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    LONG_TERM = "LONG_TERM"


# ---------------------------------------------------------------------------
# Resilience Profile Schemas
# ---------------------------------------------------------------------------

class DimensionScore(BaseModel):
    dimension: ResilienceDimension
    score: float = Field(..., ge=0.0, le=100.0, description="Dimension resilience score 0-100")
    weight: float = Field(default=0.10, ge=0.0, le=1.0)
    data_state: DataState = Field(default=DataState.DERIVED)
    details: Dict[str, Any] = Field(default_factory=dict)


class ResilienceProfileCreate(BaseModel):
    location_id: str
    target_resilience_score: float = Field(default=80.0, ge=0.0, le=100.0)
    weights_override: Optional[Dict[str, float]] = None


class ResilienceProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: str
    location_id: str
    composite_resilience_score: float
    resilience_grade: str
    dimension_scores: Dict[str, DimensionScore]
    strengths: List[str]
    weaknesses: List[str]
    adaptation_gap: float
    target_resilience_score: float
    uncertainty_score: float
    missing_dimensions_count: int
    confidence_level: str
    evaluated_at: datetime
    is_synthetic: bool = False


class ResilienceGapItem(BaseModel):
    dimension: ResilienceDimension
    current_score: float
    target_score: float
    gap: float
    priority_level: str
    recommended_actions: List[str] = Field(default_factory=list)


class ResilienceGapsResponse(BaseModel):
    location_id: str
    overall_gap: float
    target_score: float
    current_composite_score: float
    dimension_gaps: List[ResilienceGapItem]
    top_priority_dimensions: List[str]


# ---------------------------------------------------------------------------
# Digital Twin Snapshots & State
# ---------------------------------------------------------------------------

class TwinSnapshotCreate(BaseModel):
    location_id: str
    city_id: str = "DELHI_NCR"
    time_dimension: TimeDimension = TimeDimension.CURRENT
    target_year: int = Field(default=2026, ge=2020, le=2100)
    description: Optional[str] = None


class TwinSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    location_id: str
    city_id: str
    time_dimension: str
    target_year: int
    data_version: str
    model_version: str
    config_version: str
    state_payload: Dict[str, Any]
    state_hash: str
    description: Optional[str] = None
    created_by: str
    created_at: datetime
    is_synthetic: bool = False


class DigitalTwinStateResponse(BaseModel):
    location_id: str
    city_id: str
    time_dimension: TimeDimension
    target_year: int
    state_hash: str
    thermal_layer: Dict[str, Any]
    risk_layer: Dict[str, Any]
    vulnerability_layer: Dict[str, Any]
    infrastructure_layer: Dict[str, Any]
    operational_layer: Dict[str, Any]
    resilience_summary: Dict[str, Any]
    data_freshness_status: str
    last_updated_at: datetime


# ---------------------------------------------------------------------------
# Climate Scenario Schemas
# ---------------------------------------------------------------------------

class ClimateScenarioCreate(BaseModel):
    scenario_id: Optional[str] = None
    scenario_name: str
    category: ScenarioCategory
    time_horizon: Literal["NEAR_TERM", "2030", "2040", "2050"]
    delta_tmax_c: float = Field(default=1.5, ge=-10.0, le=20.0)
    delta_tmin_c: float = Field(default=1.8, ge=-10.0, le=20.0)
    delta_heatwave_days: float = Field(default=5.0, ge=0.0, le=100.0)
    delta_humidity_pct: float = Field(default=0.0, ge=-50.0, le=50.0)
    delta_pm25_pct: float = Field(default=0.0, ge=-50.0, le=100.0)
    urban_density_factor: float = Field(default=1.0, ge=0.5, le=3.0)
    assumptions: Optional[Dict[str, Any]] = None
    source: str = "IPCC_AR6_REGIONAL_PROJECTIONS"
    uncertainty_range: Optional[Dict[str, Any]] = None


class ClimateScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    scenario_name: str
    category: str
    time_horizon: str
    delta_tmax_c: float
    delta_tmin_c: float
    delta_heatwave_days: float
    delta_humidity_pct: float
    delta_pm25_pct: float
    urban_density_factor: float
    assumptions: Optional[Dict[str, Any]] = None
    source: str
    uncertainty_range: Optional[Dict[str, Any]] = None
    is_synthetic: bool = False
    created_at: datetime


class ClimateSimulationRequest(BaseModel):
    location_id: str
    scenario_id: str
    base_temperature_c: Optional[float] = None
    base_humidity_pct: Optional[float] = None


class ClimateSimulationResponse(BaseModel):
    location_id: str
    scenario_id: str
    scenario_name: str
    time_horizon: str
    baseline_tmax: float
    projected_tmax: float
    baseline_heat_index: float
    projected_heat_index: float
    baseline_risk_probability: float
    projected_risk_probability: float
    risk_multiplier: float
    heatwave_days_per_year_projected: float
    vulnerable_population_exposed: int
    uncertainty_bounds: Dict[str, float]
    scientific_disclaimer: str = "PROJECTION_ONLY_NOT_DETERMINISTIC_FORECAST"


# ---------------------------------------------------------------------------
# Cascading Failure Graph Schemas
# ---------------------------------------------------------------------------

class CascadeNode(BaseModel):
    id: str
    name: str
    layer: str  # CLIMATE, INFRASTRUCTURE, SOCIAL, HEALTH, RESPONSE
    status: str  # NORMAL, STRESSED, CRITICAL, FAILED, MITIGATED
    stress_index: float = Field(..., ge=0.0, le=1.0)
    capacity_remaining_pct: float = Field(..., ge=0.0, le=100.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CascadeEdge(BaseModel):
    source: str
    target: str
    relationship_type: str  # DRIVES, STRAINS, FAILS, OVERLOADS
    coupling_strength: float = Field(..., ge=0.0, le=1.0)
    relationship_status: RelationshipStatus = RelationshipStatus.MODEL_BASED
    description: str


class CascadeSimulationRequest(BaseModel):
    location_id: str
    scenario_id: str
    power_grid_contingency: bool = False
    water_system_strain: bool = False
    cooling_failure_rate_pct: float = Field(default=0.0, ge=0.0, le=100.0)


class CascadeSimulationResponse(BaseModel):
    graph_id: str
    scenario_id: str
    location_id: str
    compound_stress_index: float
    power_stress_level: float
    water_deficit_level: float
    cooling_failure_probability: float
    healthcare_surge_multiplier: float
    nodes: List[CascadeNode]
    edges: List[CascadeEdge]
    relationship_status: str
    critical_failure_path: List[str]
    simulated_at: datetime


# ---------------------------------------------------------------------------
# Adaptation Portfolio & Pareto Optimization Schemas
# ---------------------------------------------------------------------------

class StrategicInterventionType(str, Enum):
    COOL_ROOF_RETROFIT = "COOL_ROOF_RETROFIT"
    URBAN_CANOPY_AFFORESTATION = "URBAN_CANOPY_AFFORESTATION"
    COOL_PAVEMENT_COATING = "COOL_PAVEMENT_COATING"
    PUBLIC_SHADE_NETWORK = "PUBLIC_SHADE_NETWORK"
    DISTRIBUTED_COOLING_HUBS = "DISTRIBUTED_COOLING_HUBS"
    EMERGENCY_WATER_RESILIENCE = "EMERGENCY_WATER_RESILIENCE"
    GRID_BACKUP_SOLAR_STORAGE = "GRID_BACKUP_SOLAR_STORAGE"
    HEAT_ADAPTIVE_WORK_ORDINANCE = "HEAT_ADAPTIVE_WORK_ORDINANCE"


class AdaptationInterventionSpec(BaseModel):
    intervention_type: StrategicInterventionType
    coverage_pct: float = Field(default=20.0, ge=0.0, le=100.0)
    target_zone_id: Optional[str] = None
    unit_cost_estimate: Optional[float] = None
    implementation_horizon_months: int = Field(default=12, ge=1, le=120)


class AdaptationPortfolioCreate(BaseModel):
    portfolio_name: str
    target_locations: List[str]
    interventions: List[AdaptationInterventionSpec]
    summary: Optional[str] = None


class AdaptationPortfolioSimulateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    portfolio_name: Optional[str] = "Simulated Portfolio"
    target_locations: List[str]
    interventions: List[AdaptationInterventionSpec]
    budget_cap: Optional[float] = None


class AdaptationPortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    portfolio_name: str
    target_locations: List[str]
    interventions: List[Dict[str, Any]]
    status: str
    simulated_exposure_reduction_pct: float
    simulated_risk_delta: float
    population_protected_count: int
    estimated_capital_cost: Optional[float] = None
    cost_status: str
    cost_effectiveness_ratio: Optional[float] = None
    equity_disparity_ratio: float
    feasibility_status: str
    causal_status: str
    summary: str
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    created_at: datetime


class ParetoPortfolioItem(BaseModel):
    portfolio_id: str
    portfolio_name: str
    cost: Optional[float]
    risk_reduction_pct: float
    equity_score: float
    is_pareto_optimal: bool
    rank: int


class ParetoFrontierResponse(BaseModel):
    location_id: str
    portfolios_evaluated_count: int
    pareto_optimal_portfolios: List[ParetoPortfolioItem]
    all_candidates: List[ParetoPortfolioItem]
    tradeoff_summary: str


class PortfolioApprovalRequest(BaseModel):
    approved_by: str
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Strategic Plan & Roadmap Schemas
# ---------------------------------------------------------------------------

class StrategicRoadmapAction(BaseModel):
    action_id: str
    title: str
    intervention_type: str
    phase: RoadmapPhase
    target_locations: List[str]
    estimated_duration_months: int
    prerequisites: List[str] = Field(default_factory=list)
    capital_cost_est: Optional[float] = None
    cost_status: str = "ESTIMATED"
    responsible_agency: str
    milestone_success_metric: str


class StrategicRoadmapPhase(BaseModel):
    phase: RoadmapPhase
    phase_title: str
    timeframe: str
    actions: List[StrategicRoadmapAction]
    total_cost_est: Optional[float] = None
    expected_resilience_gain: float


class StrategicRoadmapResponse(BaseModel):
    roadmap_id: str
    location_id: str
    target_horizon: str
    phases: List[StrategicRoadmapPhase]
    total_estimated_actions: int
    projected_final_resilience_score: float
    governance_notes: str


class StrategicPlanCreate(BaseModel):
    plan_name: str
    target_horizon: Literal["2030", "2040", "2050", "MULTI_YEAR"] = "2030"
    target_locations: List[str]
    portfolio_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class StrategicPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    plan_name: str
    target_horizon: str
    status: str
    portfolio_ids: List[str]
    roadmap_phases: Dict[str, Any]
    governance_metadata: Optional[Dict[str, Any]] = None
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
