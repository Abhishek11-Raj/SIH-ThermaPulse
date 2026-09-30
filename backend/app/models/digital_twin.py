"""SQLAlchemy ORM models for Step 10: Heat Resilience Digital Twin, Climate Scenario
Simulation, Long-Term Adaptation Planning, Infrastructure Resilience, and Policy Support.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class TwinSnapshotDB(Base):
    """Digital twin multi-layer state snapshot with temporal and data versioning."""
    __tablename__ = "twin_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    city_id: Mapped[str] = mapped_column(String(64), default="DELHI_NCR", index=True)
    time_dimension: Mapped[str] = mapped_column(String(32), default="CURRENT", index=True)  # CURRENT, HISTORICAL, FORECAST, SCENARIO, LONG_TERM_PROJECTION
    target_year: Mapped[int] = mapped_column(Integer, default=2026)
    data_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    model_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    config_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    state_payload: Mapped[Dict[str, Any]] = mapped_column(JSON)
    state_hash: Mapped[str] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class ResilienceProfileDB(Base):
    """Multi-dimensional urban heat resilience profile with transparent gap analysis."""
    __tablename__ = "resilience_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    composite_resilience_score: Mapped[float] = mapped_column(Float, default=50.0)  # 0 to 100
    resilience_grade: Mapped[str] = mapped_column(String(16), default="MODERATE")  # VERY_LOW, LOW, MODERATE, HIGH, VERY_HIGH
    dimension_scores: Mapped[Dict[str, Any]] = mapped_column(JSON)
    strengths: Mapped[List[str]] = mapped_column(JSON, default=list)
    weaknesses: Mapped[List[str]] = mapped_column(JSON, default=list)
    adaptation_gap: Mapped[float] = mapped_column(Float, default=20.0)
    target_resilience_score: Mapped[float] = mapped_column(Float, default=80.0)
    uncertainty_score: Mapped[float] = mapped_column(Float, default=0.15)
    missing_dimensions_count: Mapped[int] = mapped_column(Integer, default=0)
    confidence_level: Mapped[str] = mapped_column(String(32), default="MEDIUM")
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class ClimateScenarioDB(Base):
    """Climate projection scenario parameters grounded in scientific warming pathways."""
    __tablename__ = "climate_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scenario_name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64), index=True)  # BASELINE, MODERATE_WARMING, HIGH_WARMING, EXTREME_HEAT, HOTTER_NIGHTS, COMPOUND_HEAT_POLLUTION
    time_horizon: Mapped[str] = mapped_column(String(32), index=True)  # NEAR_TERM, 2030, 2040, 2050
    delta_tmax_c: Mapped[float] = mapped_column(Float, default=1.5)
    delta_tmin_c: Mapped[float] = mapped_column(Float, default=1.8)
    delta_heatwave_days: Mapped[float] = mapped_column(Float, default=5.0)
    delta_humidity_pct: Mapped[float] = mapped_column(Float, default=0.0)
    delta_pm25_pct: Mapped[float] = mapped_column(Float, default=0.0)
    urban_density_factor: Mapped[float] = mapped_column(Float, default=1.0)
    assumptions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(128), default="IPCC_AR6_REGIONAL_PROJECTIONS")
    uncertainty_range: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CascadeGraphDB(Base):
    """Cascading infrastructure failure simulation state."""
    __tablename__ = "cascade_graphs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    graph_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    compound_stress_index: Mapped[float] = mapped_column(Float, default=0.0)
    power_stress_level: Mapped[float] = mapped_column(Float, default=0.0)
    water_deficit_level: Mapped[float] = mapped_column(Float, default=0.0)
    cooling_failure_probability: Mapped[float] = mapped_column(Float, default=0.0)
    healthcare_surge_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    nodes: Mapped[List[Any]] = mapped_column(JSON)
    edges: Mapped[List[Any]] = mapped_column(JSON)
    relationship_status: Mapped[str] = mapped_column(String(64), default="MODEL_BASED")
    simulated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdaptationPortfolioDB(Base):
    """Strategic long-term resilience intervention package with multi-objective trade-offs."""
    __tablename__ = "adaptation_portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    portfolio_name: Mapped[str] = mapped_column(String(128))
    target_locations: Mapped[List[str]] = mapped_column(JSON)
    interventions: Mapped[List[Dict[str, Any]]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="PROPOSED", index=True)  # PROPOSED, SIMULATED, REVIEW, APPROVED, IMPLEMENTED, VERIFIED, CANCELLED
    simulated_exposure_reduction_pct: Mapped[float] = mapped_column(Float, default=0.0)
    simulated_risk_delta: Mapped[float] = mapped_column(Float, default=0.0)
    population_protected_count: Mapped[int] = mapped_column(Integer, default=0)
    estimated_capital_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_status: Mapped[str] = mapped_column(String(32), default="ESTIMATED")  # ESTIMATED, COST_DATA_UNAVAILABLE, VERIFIED
    cost_effectiveness_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    equity_disparity_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    feasibility_status: Mapped[str] = mapped_column(String(32), default="FEASIBLE")  # FEASIBLE, PARTIALLY_FEASIBLE, NOT_FEASIBLE, UNKNOWN
    causal_status: Mapped[str] = mapped_column(String(64), default="MODEL_BASED_COUNTERFACTUAL")
    summary: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(64), default="MUNICIPAL_OPERATOR")
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StrategicPlanDB(Base):
    """Sequenced multi-horizon strategic resilience roadmap under human governance."""
    __tablename__ = "strategic_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan_name: Mapped[str] = mapped_column(String(128))
    target_horizon: Mapped[str] = mapped_column(String(32), default="2030", index=True)  # 2030, 2040, 2050, MULTI_YEAR
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)  # DRAFT, REVIEW, APPROVED, IMPLEMENTING, IMPLEMENTED, VERIFIED, REJECTED
    portfolio_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    roadmap_phases: Mapped[Dict[str, Any]] = mapped_column(JSON)  # NOW, SHORT_TERM, MEDIUM_TERM, LONG_TERM
    governance_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="PLANNING_OFFICER")
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
