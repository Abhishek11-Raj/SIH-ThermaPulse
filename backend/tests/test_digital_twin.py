"""Unit and Integration Tests for Step 10:
Heat Resilience Digital Twin, Climate Scenario Simulation, Long-Term Adaptation Planning,
Infrastructure Resilience, and Policy / Investment Decision Support.
"""
from __future__ import annotations

from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine, get_db, init_db, SessionLocal
from app.digital_twin.adaptation_engine import StrategicAdaptationEngine
from app.digital_twin.cascade_engine import ResilienceCascadeEngine
from app.digital_twin.climate_scenario_engine import ClimateScenarioEngine
from app.digital_twin.resilience_engine import ResilienceFrameworkEngine
from app.digital_twin.strategic_roadmap import StrategicRoadmapEngine
from app.digital_twin.twin_engine import DigitalTwinEngine
from app.digital_twin.schemas import (
    AdaptationInterventionSpec,
    AdaptationPortfolioCreate,
    CascadeSimulationRequest,
    ClimateScenarioCreate,
    ClimateSimulationRequest,
    PortfolioApprovalRequest,
    ScenarioCategory,
    StrategicInterventionType,
    StrategicPlanCreate,
    TimeDimension,
    TwinSnapshotCreate,
)
from app.main import app
from app.models.digital_twin import (
    AdaptationPortfolioDB,
    CascadeGraphDB,
    ClimateScenarioDB,
    ResilienceProfileDB,
    StrategicPlanDB,
    TwinSnapshotDB,
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ============================================================
# 1. Digital Twin State & Snapshot Engine Tests
# ============================================================

def test_digital_twin_engine_state_and_snapshots(db_session):
    state = DigitalTwinEngine.get_current_twin_state(db_session, "LOC_DELHI_001")

    assert state.location_id == "LOC_DELHI_001"
    assert state.time_dimension == TimeDimension.CURRENT
    assert state.state_hash is not None
    assert len(state.state_hash) > 0
    assert "temperature_c" in state.thermal_layer
    assert "risk_score" in state.risk_layer
    assert "elderly_ratio" in state.vulnerability_layer
    assert "cooling_shelters_active" in state.infrastructure_layer
    assert "composite_score" in state.resilience_summary

    # Snapshot creation
    snap_req = TwinSnapshotCreate(
        location_id="LOC_DELHI_001",
        time_dimension=TimeDimension.CURRENT,
        target_year=2026,
        description="Test Baseline Snapshot",
    )
    snap = DigitalTwinEngine.create_snapshot(db_session, snap_req, user_id="TEST_OPERATOR")

    assert snap.snapshot_id.startswith("snap_")
    assert snap.location_id == "LOC_DELHI_001"
    assert snap.target_year == 2026
    assert snap.state_hash is not None

    # Snapshot listing
    snapshots = DigitalTwinEngine.list_snapshots(db_session, "LOC_DELHI_001")
    assert len(snapshots) >= 1
    assert any(s.snapshot_id == snap.snapshot_id for s in snapshots)


# ============================================================
# 2. 10-Dimension Resilience Framework & Gap Tests
# ============================================================

def test_resilience_framework_profile_and_gaps(db_session):
    profile = ResilienceFrameworkEngine.evaluate_profile(db_session, "LOC_DELHI_001", target_resilience_score=80.0)

    assert profile.location_id == "LOC_DELHI_001"
    assert 0.0 <= profile.composite_resilience_score <= 100.0
    assert profile.resilience_grade in ["VERY_LOW", "LOW", "MODERATE", "HIGH", "VERY_HIGH"]
    assert len(profile.dimension_scores) == 10

    # Ensure all 10 standard dimensions are scored
    expected_dims = [
        "HEAT_EXPOSURE", "NIGHTTIME_RECOVERY", "HEALTHCARE_ACCESS", "COOLING_ACCESS",
        "WATER_ACCESS", "POWER_RESILIENCE", "GREEN_INFRASTRUCTURE", "EMERGENCY_RESPONSE",
        "DATA_READINESS", "COMMUNITY_PROTECTION"
    ]
    for dim in expected_dims:
        assert dim in profile.dimension_scores
        score_obj = profile.dimension_scores[dim]
        assert 0.0 <= score_obj.score <= 100.0

    assert isinstance(profile.strengths, list)
    assert isinstance(profile.weaknesses, list)
    assert profile.adaptation_gap >= 0.0

    # Gaps Evaluation
    gaps_resp = ResilienceFrameworkEngine.calculate_gaps(db_session, "LOC_DELHI_001", target_score=85.0)
    assert gaps_resp.location_id == "LOC_DELHI_001"
    assert gaps_resp.target_score == 85.0
    assert len(gaps_resp.dimension_gaps) == 10
    assert len(gaps_resp.top_priority_dimensions) >= 1

    for g in gaps_resp.dimension_gaps:
        assert g.gap >= 0.0
        assert len(g.recommended_actions) >= 1


# ============================================================
# 3. Climate Scenario Simulation Engine Tests
# ============================================================

def test_climate_scenario_engine_simulation(db_session):
    ClimateScenarioEngine.seed_builtin_scenarios(db_session)
    scenarios = ClimateScenarioEngine.list_scenarios(db_session)
    assert len(scenarios) >= 5

    ssp2_2030 = next(s for s in scenarios if s.scenario_id == "SSP2_45_2030")
    assert ssp2_2030.delta_tmax_c == 1.2
    assert ssp2_2030.time_horizon == "2030"

    # Simulate Climate Scenario
    sim_req = ClimateSimulationRequest(
        location_id="LOC_DELHI_001",
        scenario_id="SSP2_45_2030",
        base_temperature_c=40.0,
        base_humidity_pct=50.0,
    )
    sim_res = ClimateScenarioEngine.simulate_scenario(db_session, sim_req)

    assert sim_res.location_id == "LOC_DELHI_001"
    assert sim_res.scenario_id == "SSP2_45_2030"
    assert sim_res.projected_tmax > sim_res.baseline_tmax
    assert sim_res.projected_risk_probability >= sim_res.baseline_risk_probability
    assert sim_res.risk_multiplier >= 1.0
    assert sim_res.vulnerable_population_exposed > 0
    assert sim_res.scientific_disclaimer == "PROJECTION_ONLY_NOT_DETERMINISTIC_FORECAST"

    # Custom Scenario Creation
    custom_req = ClimateScenarioCreate(
        scenario_id="CUSTOM_HOT_2045",
        scenario_name="Custom Hot Summer 2045",
        category=ScenarioCategory.EXTREME_HEAT,
        time_horizon="2040",
        delta_tmax_c=2.8,
        delta_tmin_c=3.2,
        delta_heatwave_days=15.0,
    )
    custom_scen = ClimateScenarioEngine.create_scenario(db_session, custom_req)
    assert custom_scen.scenario_id == "CUSTOM_HOT_2045"
    assert custom_scen.delta_tmax_c == 2.8


# ============================================================
# 4. Cascading Infrastructure Failure Simulation Tests
# ============================================================

def test_cascade_graph_simulation_and_edges(db_session):
    casc_req = CascadeSimulationRequest(
        location_id="LOC_DELHI_001",
        scenario_id="SSP5_85_2050",
        power_grid_contingency=True,
        water_system_strain=True,
        cooling_failure_rate_pct=35.0,
    )
    casc = ResilienceCascadeEngine.simulate_cascade(db_session, casc_req)

    assert casc.graph_id.startswith("casc_")
    assert casc.location_id == "LOC_DELHI_001"
    assert 0.0 <= casc.compound_stress_index <= 1.0
    assert casc.power_stress_level >= 0.50
    assert casc.cooling_failure_probability >= 0.40
    assert casc.healthcare_surge_multiplier >= 1.5

    assert len(casc.nodes) >= 6
    assert len(casc.edges) >= 5
    assert len(casc.critical_failure_path) >= 3
    assert casc.relationship_status == "MODEL_BASED"

    for edge in casc.edges:
        assert edge.relationship_status.value == "MODEL_BASED"
        assert 0.0 <= edge.coupling_strength <= 1.0


# ============================================================
# 5. Strategic Adaptation & Pareto Frontier Tests
# ============================================================

def test_adaptation_portfolio_simulation_and_pareto_frontier(db_session):
    # Catalog
    catalog = StrategicAdaptationEngine.get_intervention_catalog()
    assert len(catalog) >= 7
    assert any(c["intervention_type"] == "COOL_ROOF_RETROFIT" for c in catalog)

    # Simulation
    interventions = [
        AdaptationInterventionSpec(
            intervention_type=StrategicInterventionType.COOL_ROOF_RETROFIT,
            coverage_pct=40.0,
        ),
        AdaptationInterventionSpec(
            intervention_type=StrategicInterventionType.DISTRIBUTED_COOLING_HUBS,
            coverage_pct=30.0,
        ),
        AdaptationInterventionSpec(
            intervention_type=StrategicInterventionType.HEAT_ADAPTIVE_WORK_ORDINANCE,
            coverage_pct=80.0,
        ),
    ]

    sim = StrategicAdaptationEngine.simulate_portfolio(
        db=db_session,
        target_locations=["LOC_DELHI_001"],
        interventions=interventions,
        portfolio_name="Test Resilience Package",
    )

    assert sim.simulated_exposure_reduction_pct > 15.0
    assert sim.simulated_risk_delta < 0.0  # Risk reduction is negative delta
    assert sim.population_protected_count > 0
    assert sim.estimated_capital_cost is not None
    assert sim.cost_status == "ESTIMATED"
    assert sim.causal_status == "MODEL_BASED_COUNTERFACTUAL"

    # Creation & Approval
    port_req = AdaptationPortfolioCreate(
        portfolio_name="Formally Proposed Portfolio",
        target_locations=["LOC_DELHI_001"],
        interventions=interventions,
        summary="Formal portfolio proposal",
    )
    port = StrategicAdaptationEngine.create_and_persist_portfolio(db_session, port_req, user_id="OPERATOR_A")
    assert port.status == "PROPOSED"

    approved_port = StrategicAdaptationEngine.approve_portfolio(
        db_session, port.portfolio_id, approved_by="CHIEF_HEALTH_OFFICER", notes="Approved for 2026-2028 deployment"
    )
    assert approved_port.status == "APPROVED"
    assert approved_port.approved_by == "CHIEF_HEALTH_OFFICER"

    # Pareto Frontier
    pareto = StrategicAdaptationEngine.compute_pareto_frontier(db_session, "LOC_DELHI_001")
    assert pareto.location_id == "LOC_DELHI_001"
    assert pareto.portfolios_evaluated_count >= 4
    assert len(pareto.pareto_optimal_portfolios) >= 1
    assert any(p.is_pareto_optimal for p in pareto.all_candidates)


# ============================================================
# 6. Strategic Roadmaps & Plans Engine Tests
# ============================================================

def test_strategic_roadmap_generation_and_plan_lifecycle(db_session):
    roadmap = StrategicRoadmapEngine.generate_roadmap(db_session, "LOC_DELHI_001", target_horizon="2030")

    assert roadmap.location_id == "LOC_DELHI_001"
    assert len(roadmap.phases) == 4

    phase_names = [p.phase.value for p in roadmap.phases]
    assert phase_names == ["NOW", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"]

    for phase in roadmap.phases:
        assert len(phase.actions) >= 1
        assert phase.expected_resilience_gain > 0.0
        for action in phase.actions:
            assert action.action_id is not None
            assert action.responsible_agency is not None
            assert len(action.milestone_success_metric) > 5

    # Plan creation
    plan_req = StrategicPlanCreate(
        plan_name="Delhi 2030 Heat Adaptation Master Plan",
        target_horizon="2030",
        target_locations=["LOC_DELHI_001"],
        notes="First official draft for committee review",
    )
    plan = StrategicRoadmapEngine.create_strategic_plan(db_session, plan_req, user_id="PLANNER_1")
    assert plan.plan_id.startswith("plan_")
    assert plan.status == "DRAFT"
    assert "NOW" in plan.roadmap_phases

    # Status transitions
    updated_plan = StrategicRoadmapEngine.update_plan_status(
        db_session, plan.plan_id, new_status="APPROVED", user_id="HEALTH_MINISTER", notes="Authorized by municipal council"
    )
    assert updated_plan.status == "APPROVED"
    assert updated_plan.approved_by == "HEALTH_MINISTER"


# ============================================================
# 7. REST API Endpoints & RBAC Integration Tests
# ============================================================

def test_digital_twin_api_endpoints_and_rbac(client):
    headers_operator = {"X-User-Role": "MUNICIPAL_OPERATOR"}
    headers_health = {"X-User-Role": "HEALTH_OFFICIAL"}
    headers_analyst = {"X-User-Role": "ANALYST"}
    headers_public = {"X-User-Role": "PUBLIC"}

    # 1. State Endpoint (Public/Any)
    res_state = client.get("/api/v1/twin/state?location_id=LOC_DELHI_001")
    assert res_state.status_code == 200
    assert res_state.json()["location_id"] == "LOC_DELHI_001"

    # 2. Snapshot Creation (MUNICIPAL_OPERATOR authorized, PUBLIC rejected)
    snap_payload = {
        "location_id": "LOC_DELHI_001",
        "city_id": "DELHI_NCR",
        "time_dimension": "CURRENT",
        "target_year": 2026,
        "description": "API snapshot test",
    }
    res_snap_pub = client.post("/api/v1/twin/snapshots", json=snap_payload, headers=headers_public)
    assert res_snap_pub.status_code == 403

    res_snap_op = client.post("/api/v1/twin/snapshots", json=snap_payload, headers=headers_operator)
    assert res_snap_op.status_code == 201
    assert res_snap_op.json()["snapshot_id"].startswith("snap_")

    # 3. Resilience Profile & Gaps
    res_prof = client.get("/api/v1/resilience/profile?location_id=LOC_DELHI_001")
    assert res_prof.status_code == 200
    assert "composite_resilience_score" in res_prof.json()

    res_gaps = client.get("/api/v1/resilience/gaps?location_id=LOC_DELHI_001")
    assert res_gaps.status_code == 200
    assert len(res_gaps.json()["dimension_gaps"]) == 10

    # 4. Climate Scenarios & Simulation
    res_scens = client.get("/api/v1/scenarios/climate")
    assert res_scens.status_code == 200
    assert len(res_scens.json()) >= 5

    sim_payload = {
        "location_id": "LOC_DELHI_001",
        "scenario_id": "SSP2_45_2030",
        "base_temperature_c": 41.5,
        "base_humidity_pct": 48.0,
    }
    res_sim = client.post("/api/v1/scenarios/climate/simulate", json=sim_payload)
    assert res_sim.status_code == 200
    assert res_sim.json()["projected_risk_probability"] > 0.0

    # 5. Cascade Simulation
    casc_payload = {
        "location_id": "LOC_DELHI_001",
        "scenario_id": "SSP5_85_2050",
        "power_grid_contingency": True,
        "water_system_strain": True,
        "cooling_failure_rate_pct": 25.0,
    }
    res_casc = client.post("/api/v1/scenarios/cascade/simulate", json=casc_payload)
    assert res_casc.status_code == 200
    assert res_casc.json()["relationship_status"] == "MODEL_BASED"

    # 6. Adaptation Catalog, Simulation, Portfolio Creation & Approval
    res_cat = client.get("/api/v1/adaptation/interventions")
    assert res_cat.status_code == 200
    assert len(res_cat.json()["interventions"]) >= 7

    port_payload = {
        "portfolio_name": "API Proposed Portfolio",
        "target_locations": ["LOC_DELHI_001"],
        "interventions": [
            {"intervention_type": "COOL_ROOF_RETROFIT", "coverage_pct": 35.0, "implementation_horizon_months": 12},
            {"intervention_type": "PUBLIC_SHADE_NETWORK", "coverage_pct": 50.0, "implementation_horizon_months": 6},
        ],
        "summary": "Proposed via API",
    }
    res_create_port = client.post("/api/v1/adaptation/portfolios", json=port_payload, headers=headers_operator)
    assert res_create_port.status_code == 201
    port_id = res_create_port.json()["portfolio_id"]

    # Approval RBAC: HEALTH_OFFICIAL allowed, PUBLIC rejected
    appr_payload = {"approved_by": "DR_DIRECTOR", "notes": "Approved in executive review"}
    res_appr_pub = client.post(f"/api/v1/adaptation/portfolios/{port_id}/approve", json=appr_payload, headers=headers_public)
    assert res_appr_pub.status_code == 403

    res_appr_ok = client.post(f"/api/v1/adaptation/portfolios/{port_id}/approve", json=appr_payload, headers=headers_health)
    assert res_appr_ok.status_code == 200
    assert res_appr_ok.json()["status"] == "APPROVED"

    # 7. Pareto Frontier
    res_pareto = client.get("/api/v1/adaptation/pareto?location_id=LOC_DELHI_001")
    assert res_pareto.status_code == 200
    assert res_pareto.json()["portfolios_evaluated_count"] >= 4

    # 8. Strategic Roadmap & Plan Creation
    res_rdmp = client.get("/api/v1/strategic-plans/roadmap?location_id=LOC_DELHI_001")
    assert res_rdmp.status_code == 200
    assert len(res_rdmp.json()["phases"]) == 4

    plan_payload = {
        "plan_name": "API Strategic Plan 2030",
        "target_horizon": "2030",
        "target_locations": ["LOC_DELHI_001"],
        "portfolio_ids": [port_id],
        "notes": "Drafted via API",
    }
    res_plan = client.post("/api/v1/strategic-plans", json=plan_payload, headers=headers_operator)
    assert res_plan.status_code == 201
    plan_id = res_plan.json()["plan_id"]

    res_plan_list = client.get("/api/v1/strategic-plans")
    assert res_plan_list.status_code == 200
    assert len(res_plan_list.json()) >= 1


# ============================================================
# 8. Scientific Boundary & Data State Verification Tests
# ============================================================

def test_scientific_boundary_adherence_and_data_states(db_session, client):
    # Check that climate simulations explicitly emit non-deterministic disclaimers
    sim_res = ClimateScenarioEngine.simulate_scenario(
        db_session,
        ClimateSimulationRequest(
            location_id="LOC_DELHI_001",
            scenario_id="SSP5_85_2050",
            base_temperature_c=42.0,
            base_humidity_pct=45.0,
        ),
    )
    assert sim_res.scientific_disclaimer == "PROJECTION_ONLY_NOT_DETERMINISTIC_FORECAST"
    assert "lower_bound_p10" in sim_res.uncertainty_bounds
    assert "upper_bound_p90" in sim_res.uncertainty_bounds

    # Check that cascade failure graphs emit MODEL_BASED relationship status
    casc_res = ResilienceCascadeEngine.simulate_cascade(
        db_session,
        CascadeSimulationRequest(
            location_id="LOC_DELHI_001",
            scenario_id="SSP5_85_2050",
        ),
    )
    assert casc_res.relationship_status == "MODEL_BASED"
    for edge in casc_res.edges:
        assert edge.relationship_status.value == "MODEL_BASED"

    # Check that portfolio simulations emit MODEL_BASED_COUNTERFACTUAL
    port_sim = StrategicAdaptationEngine.simulate_portfolio(
        db=db_session,
        target_locations=["LOC_DELHI_001"],
        interventions=[
            AdaptationInterventionSpec(
                intervention_type=StrategicInterventionType.URBAN_CANOPY_AFFORESTATION,
                coverage_pct=30.0,
            )
        ],
    )
    assert port_sim.causal_status == "MODEL_BASED_COUNTERFACTUAL"


# ============================================================
# 9. Strategic Plan Status Governance & Lifecycle Transitions
# ============================================================

def test_strategic_plan_status_governance_transitions(client):
    headers_operator = {"X-User-Role": "MUNICIPAL_OPERATOR"}
    headers_health = {"X-User-Role": "HEALTH_OFFICIAL"}
    headers_public = {"X-User-Role": "PUBLIC"}

    # Create plan
    create_res = client.post(
        "/api/v1/strategic-plans",
        json={
            "plan_name": "Governance Test Strategic Plan",
            "target_horizon": "2040",
            "target_locations": ["LOC_DELHI_001"],
        },
        headers=headers_operator,
    )
    assert create_res.status_code == 201
    plan_id = create_res.json()["plan_id"]
    assert create_res.json()["status"] == "DRAFT"

    # Transition to REVIEW
    rev_res = client.post(
        f"/api/v1/strategic-plans/{plan_id}/status?status_update=REVIEW&notes=Submitted+for+formal+review",
        headers=headers_health,
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["status"] == "REVIEW"

    # Transition to APPROVED (Public rejected, Health official approved)
    appr_fail = client.post(
        f"/api/v1/strategic-plans/{plan_id}/status?status_update=APPROVED",
        headers=headers_public,
    )
    assert appr_fail.status_code == 403

    appr_ok = client.post(
        f"/api/v1/strategic-plans/{plan_id}/status?status_update=APPROVED&notes=Authorized+by+health+commissioner",
        headers=headers_health,
    )
    assert appr_ok.status_code == 200
    assert appr_ok.json()["status"] == "APPROVED"
    assert appr_ok.json()["approved_by"] == "health_official"


# ============================================================
# 10. Resilience Missing Data Penalty & Confidence Level
# ============================================================

def test_resilience_missing_data_penalty_handling(db_session):
    # Evaluate for an unknown location with missing telemetry
    prof_unknown = ResilienceFrameworkEngine.evaluate_profile(
        db_session, "LOC_NON_EXISTENT_999", target_resilience_score=80.0
    )
    assert prof_unknown.location_id == "LOC_NON_EXISTENT_999"
    assert prof_unknown.missing_dimensions_count >= 2
    assert prof_unknown.confidence_level in ["MEDIUM", "LOW"]
    assert prof_unknown.uncertainty_score > 0.10

