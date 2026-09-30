"""SQLAlchemy ORM models for Step 9: Operational Decision Support, City-Scale Planning,
Resource Optimization, Scenario Orchestration, and Human-in-the-Loop Response Management.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class OperationalZoneDB(Base):
    """Operational zone / ward aggregating population, vulnerability, and baseline infrastructure."""
    __tablename__ = "operational_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    zone_name: Mapped[str] = mapped_column(String(128))
    population_total: Mapped[int] = mapped_column(Integer, default=50000)
    vulnerable_population: Mapped[int] = mapped_column(Integer, default=15000)
    outdoor_worker_count: Mapped[int] = mapped_column(Integer, default=8000)
    baseline_cooling_capacity: Mapped[int] = mapped_column(Integer, default=500)
    baseline_water_capacity_lpd: Mapped[float] = mapped_column(Float, default=25000.0)
    hospital_beds_count: Mapped[int] = mapped_column(Integer, default=120)
    ambulance_stations_count: Mapped[int] = mapped_column(Integer, default=2)
    operational_risk_level: Mapped[str] = mapped_column(String(32), default="NORMAL", index=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_rank: Mapped[int] = mapped_column(Integer, default=1)
    priority_explanation: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    data_quality_grade: Mapped[str] = mapped_column(String(16), default="HIGH")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class ResourceDB(Base):
    """Protective physical & personnel resources available across the city."""
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)  # COOLING_CENTER, DRINKING_WATER_POINT, HYDRATION_ORS_STATION, AMBULANCE, etc.
    name: Mapped[str] = mapped_column(String(128))
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_capacity: Mapped[float] = mapped_column(Float, default=100.0)
    available_capacity: Mapped[float] = mapped_column(Float, default=100.0)
    capacity_unit: Mapped[str] = mapped_column(String(32), default="PERSONS")
    operating_hours: Mapped[str] = mapped_column(String(64), default="09:00-18:00")
    status: Mapped[str] = mapped_column(String(32), default="AVAILABLE", index=True)  # AVAILABLE, LIMITED, FULL, UNAVAILABLE, UNKNOWN
    confidence: Mapped[str] = mapped_column(String(32), default="VERIFIED")  # VERIFIED, ESTIMATED, UNKNOWN
    source: Mapped[str] = mapped_column(String(64), default="MUNICIPAL_INVENTORY")
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class ResourceGapDB(Base):
    """Quantified resource deficit between modeled demand and available protective infrastructure."""
    __tablename__ = "resource_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gap_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    demanded_capacity: Mapped[float] = mapped_column(Float, default=0.0)
    available_capacity: Mapped[float] = mapped_column(Float, default=0.0)
    deficit_capacity: Mapped[float] = mapped_column(Float, default=0.0)
    coverage_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    travel_distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    travel_time_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unmet_demand_count: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[str] = mapped_column(String(32), default="LOW", index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    identified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class OperationalPlanDB(Base):
    """Coordinated multi-ward response plan requiring human authorization."""
    __tablename__ = "operational_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan_name: Mapped[str] = mapped_column(String(128))
    plan_version: Mapped[int] = mapped_column(Integer, default=1)
    target_date: Mapped[str] = mapped_column(String(16), index=True)
    forecast_horizon_hours: Mapped[int] = mapped_column(Integer, default=48)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)  # DRAFT, REVIEW, APPROVED, REJECTED, EXECUTED, CANCELLED
    priority_level: Mapped[str] = mapped_column(String(32), default="PRIORITY", index=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    forecast_id_basis: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_id_basis: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    sla_target_minutes: Mapped[int] = mapped_column(Integer, default=120)
    sla_status: Mapped[str] = mapped_column(String(32), default="PENDING")  # WITHIN_SLA, BREACHED_SLA, PENDING
    total_tasks_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_tasks_count: Mapped[int] = mapped_column(Integer, default=0)
    plan_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class ActionTaskDB(Base):
    """Specific field or municipal action task dispatched under an operational plan."""
    __tablename__ = "action_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan_id: Mapped[str] = mapped_column(String(64), index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    assigned_team: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(32), default="HIGH")
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PLANNED", index=True)  # PLANNED, APPROVED, ASSIGNED, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResponseExecutionDB(Base):
    """Execution audit feedback verifying real-world implementation of dispatched tasks."""
    __tablename__ = "response_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    plan_id: Mapped[str] = mapped_column(String(64), index=True)
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    reported_action: Mapped[str] = mapped_column(String(128))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED", index=True)
    reported_coverage_count: Mapped[int] = mapped_column(Integer, default=0)
    verified_coverage_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unmet_demand_remaining: Mapped[int] = mapped_column(Integer, default=0)
    response_latency_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OperationalScenarioDB(Base):
    """City-scale scenario simulation connecting resource shifts with Step 6 counterfactuals."""
    __tablename__ = "operational_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scenario_name: Mapped[str] = mapped_column(String(128))
    location_id: Mapped[str] = mapped_column(String(64), index=True)
    baseline_risk_prob: Mapped[float] = mapped_column(Float)
    counterfactual_risk_prob: Mapped[float] = mapped_column(Float)
    risk_delta: Mapped[float] = mapped_column(Float)
    resource_modifications: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    interventions_applied: Mapped[Optional[List[Any]]] = mapped_column(JSON, nullable=True)
    feasibility_status: Mapped[str] = mapped_column(String(32), default="FEASIBLE")  # FEASIBLE, PARTIALLY_FEASIBLE, NOT_FEASIBLE, UNKNOWN
    estimated_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_resource_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    causal_status: Mapped[str] = mapped_column(String(64), default="MODEL_BASED_COUNTERFACTUAL")
    created_by: Mapped[str] = mapped_column(String(64), default="MUNICIPAL_OPERATOR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OperationalPolicyDB(Base):
    """Configurable operational decision policies with versioned weights and SLA targets."""
    __tablename__ = "operational_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    policy_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    policy_name: Mapped[str] = mapped_column(String(128))
    priority_weights: Mapped[Dict[str, Any]] = mapped_column(JSON)
    sla_thresholds_minutes: Mapped[Dict[str, Any]] = mapped_column(JSON)
    equity_constraints: Mapped[Dict[str, Any]] = mapped_column(JSON)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM_ADMIN")

