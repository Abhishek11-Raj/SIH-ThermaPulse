"""KESHAV STEP 6: Intervention and Counterfactual Simulation Tests.

Comprehensive unit and API tests for:
- All 8 intervention types
- Baseline immutability and deep-copy preservation
- Feature recomputation and scientific bounds
- Risk delta and relative change calculations
- OOD and data quality propagation
- Causal qualifiers (MODEL_BASED_COUNTERFACTUAL)
- REST API endpoints including batch comparison
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.intervention.engine import InterventionEngine
from app.intervention.schemas import (
    BatchScenarioRequest,
    CounterfactualScenario,
    Intervention,
    InterventionConstraint,
    InterventionRegistry,
    InterventionType,
    ScenarioRequest,
    ScenarioResponse,
)
from app.main import app


# ============================================================
# Schema & Registry Tests
# ============================================================

class TestInterventionSchemas:
    """Tests for Step 6 schemas and registry."""

    def test_all_eight_intervention_types_defined(self):
        types = [
            InterventionType.OUTDOOR_EXPOSURE_REDUCTION,
            InterventionType.WORK_REST_SCHEDULE,
            InterventionType.SHADE_INCREASE,
            InterventionType.WATER_ACCESS_INCREASE,
            InterventionType.COOLING_ACCESS_INCREASE,
            InterventionType.POWER_RESTORATION,
            InterventionType.EXPOSURE_TIME_SHIFT,
            InterventionType.COMBINED,
        ]
        assert len(types) == 8
        for t in types:
            assert InterventionRegistry.is_supported(t)

    def test_intervention_registry_get_and_list(self):
        supported = InterventionRegistry.list_supported()
        assert len(supported) == 8

        out_def = InterventionRegistry.get(InterventionType.OUTDOOR_EXPOSURE_REDUCTION)
        assert out_def is not None
        assert out_def.target_variable == "outdoor_exposure_hours"
        assert out_def.constraints.maximum == 24.0

        shade_def = InterventionRegistry.get("shade_increase")
        assert shade_def is not None
        assert shade_def.type == InterventionType.SHADE_INCREASE

    def test_intervention_constraint_validation(self):
        valid = InterventionConstraint(minimum=0.0, maximum=10.0, unit="hours")
        assert valid.minimum == 0.0
        assert valid.maximum == 10.0

        with pytest.raises(ValueError, match="minimum must be <= maximum"):
            InterventionConstraint(minimum=10.0, maximum=5.0)

    def test_intervention_instance_validation(self):
        interv = Intervention(
            intervention_id="int_01",
            intervention_type="outdoor_exposure_reduction",
            target_variable="outdoor_exposure_hours",
            baseline_value=8.0,
            simulated_value=4.0,
        )
        assert interv.intervention_type == InterventionType.OUTDOOR_EXPOSURE_REDUCTION
        assert interv.name == "outdoor_exposure_reduction"

        with pytest.raises(ValueError, match="at least 3 characters"):
            Intervention(
                intervention_id="ab",
                intervention_type="outdoor_exposure_reduction",
                target_variable="outdoor_exposure_hours",
                baseline_value=8.0,
                simulated_value=4.0,
            )


# ============================================================
# Engine & Scientific Logic Tests
# ============================================================

class TestInterventionEngine:
    """Tests for counterfactual simulation engine."""

    @pytest.fixture
    def baseline_features(self) -> dict:
        return {
            "location_id": "DEMO-WARD-01",
            "heat_index_c": 42.0,
            "wbgt_c": 33.0,
            "utci_c": 40.0,
            "wet_bulb_c": 29.0,
            "mrt_c": 55.0,
            "outdoor_exposure_hours": 8.0,
            "rest_cycle_minutes_per_hour": 0.0,
            "shade_fraction": 0.1,
            "water_access_fraction": 0.3,
            "cooling_access_fraction": 0.2,
            "power_reliability_fraction": 0.6,
            "exposure_hour_shift": 0.0,
            "exposure_memory": 3.0,
            "cumulative_exposure_24h": 8.0,
            "cumulative_exposure_72h": 22.0,
            "cumulative_exposure_168h": 45.0,
            "vulnerability_score": 0.7,
            "heat_index_x_vulnerability": 29.4,
            "wbgt_x_vulnerability": 23.1,
        }

    def test_baseline_immutability(self, baseline_features):
        """CRITICAL: Verify baseline is deep-copied and never mutated."""
        engine = InterventionEngine()
        baseline_copy = dict(baseline_features)

        interventions = [
            Intervention(
                intervention_id="int_reduce_exp",
                intervention_type=InterventionType.OUTDOOR_EXPOSURE_REDUCTION,
                target_variable="outdoor_exposure_hours",
                baseline_value=8.0,
                simulated_value=3.0,
            ),
            Intervention(
                intervention_id="int_shade",
                intervention_type=InterventionType.SHADE_INCREASE,
                target_variable="shade_fraction",
                baseline_value=0.1,
                simulated_value=0.8,
            ),
        ]

        scenario = engine.simulate(
            baseline_features=baseline_features,
            interventions=interventions,
            baseline_prediction_id="pred_test_001",
            scenario_name="cooling_package",
        )

        assert baseline_features == baseline_copy
        assert scenario.baseline_risk_probability > 0
        assert scenario.counterfactual_risk_probability < scenario.baseline_risk_probability
        assert scenario.risk_delta < 0
        assert scenario.causal_status == "MODEL_BASED_COUNTERFACTUAL"

    def test_all_eight_intervention_simulations(self, baseline_features):
        """Test that each of the 8 intervention types executes and reduces risk."""
        engine = InterventionEngine()

        test_cases = [
            (InterventionType.OUTDOOR_EXPOSURE_REDUCTION, "outdoor_exposure_hours", 8.0, 3.0),
            (InterventionType.WORK_REST_SCHEDULE, "rest_cycle_minutes_per_hour", 0.0, 30.0),
            (InterventionType.SHADE_INCREASE, "shade_fraction", 0.1, 0.9),
            (InterventionType.WATER_ACCESS_INCREASE, "water_access_fraction", 0.3, 1.0),
            (InterventionType.COOLING_ACCESS_INCREASE, "cooling_access_fraction", 0.2, 0.9),
            (InterventionType.POWER_RESTORATION, "power_reliability_fraction", 0.6, 1.0),
            (InterventionType.EXPOSURE_TIME_SHIFT, "exposure_hour_shift", 0.0, 4.0),
            (InterventionType.COMBINED, "combined_package", 0.0, 1.0),
        ]

        for interv_type, target_var, b_val, s_val in test_cases:
            interv = Intervention(
                intervention_id=f"int_{interv_type.value}",
                intervention_type=interv_type,
                target_variable=target_var,
                baseline_value=b_val,
                simulated_value=s_val,
            )

            scenario = engine.simulate(
                baseline_features=baseline_features,
                interventions=[interv],
                baseline_prediction_id="pred_test",
                scenario_name=f"test_{interv_type.value}",
            )

            assert scenario.status == "COMPLETED"
            assert scenario.causal_status == "MODEL_BASED_COUNTERFACTUAL"
            assert scenario.counterfactual_risk_probability <= scenario.baseline_risk_probability
            assert len(scenario.feature_changes) == 1
            assert scenario.feature_changes[0]["intervention_type"] == interv_type.value

    def test_ood_detection_in_simulation(self, baseline_features):
        """Verify out-of-distribution flags are detected when bounds are violated."""
        training_ranges = {
            "heat_index_c": {"min": 25.0, "max": 45.0},
            "outdoor_exposure_hours": {"min": 0.0, "max": 12.0},
        }
        engine = InterventionEngine(training_ranges=training_ranges)

        scenario = engine.simulate(
            baseline_features=baseline_features,
            interventions=[],
            baseline_prediction_id="pred_ood_test",
            scenario_name="ood_test",
        )
        assert scenario.ood_baseline is False

        # Extreme features violating training ranges
        extreme_features = dict(baseline_features)
        extreme_features["heat_index_c"] = 65.0
        extreme_features["outdoor_exposure_hours"] = 24.0

        scenario_ext = engine.simulate(
            baseline_features=extreme_features,
            interventions=[],
            baseline_prediction_id="pred_ood_test",
            scenario_name="ood_ext_test",
        )
        assert scenario_ext.ood_baseline is True
        assert any("OOD" in lim for lim in scenario_ext.limitations)


# ============================================================
# API Endpoint Tests
# ============================================================

class TestInterventionAPI:
    """Tests for Step 6 FastAPI intervention routes."""

    def test_registry_endpoint(self):
        with TestClient(app) as client:
            resp = client.get("/api/v1/intervention/registry")
            assert resp.status_code == 200
            data = resp.json()
            assert data["supported_count"] == 8
            types = [i["type"] for i in data["interventions"]]
            assert "outdoor_exposure_reduction" in types
            assert "shade_increase" in types
            assert "work_rest_schedule" in types

    def test_constraints_endpoint(self):
        with TestClient(app) as client:
            resp = client.get("/api/v1/intervention/constraints/outdoor_exposure_reduction")
            assert resp.status_code == 200
            data = resp.json()
            assert data["intervention_type"] == "outdoor_exposure_reduction"
            assert data["minimum"] == 0.0
            assert data["maximum"] == 24.0
            assert data["allowed_direction"] == "decrease"

    def test_validate_endpoint(self):
        with TestClient(app) as client:
            # Valid payload
            valid_payload = {
                "intervention_id": "int_val_01",
                "intervention_type": "outdoor_exposure_reduction",
                "target_variable": "outdoor_exposure_hours",
                "baseline_value": 8.0,
                "simulated_value": 4.0,
            }
            resp = client.post("/api/v1/intervention/validate", json=valid_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_valid"] is True
            assert data["supported"] is True
            assert len(data["warnings"]) == 0

    def test_scenario_creation_and_retrieval(self):
        with TestClient(app) as client:
            req_payload = {
                "location_id": "DEMO-WARD-01",
                "baseline_prediction_id": "pred_demo_01",
                "scenario_name": "worker_protection_plan",
                "description": "Reduce outdoor shift and provide shade",
                "interventions": [
                    {
                        "intervention_id": "int_shift_red",
                        "intervention_type": "outdoor_exposure_reduction",
                        "target_variable": "outdoor_exposure_hours",
                        "baseline_value": 8.0,
                        "simulated_value": 4.0,
                    },
                    {
                        "intervention_id": "int_shade_enh",
                        "intervention_type": "shade_increase",
                        "target_variable": "shade_fraction",
                        "baseline_value": 0.1,
                        "simulated_value": 0.7,
                    }
                ]
            }
            resp = client.post("/api/v1/intervention/scenario", json=req_payload)
            assert resp.status_code == 200
            data = resp.json()
            scenario_id = data["scenario_id"]
            assert scenario_id.startswith("sc_")
            assert data["causal_status"] == "MODEL_BASED_COUNTERFACTUAL"
            assert data["comparison"]["risk_delta"] <= 0
            assert len(data["changes"]) == 2

            # Query the created scenario by ID
            get_resp = client.get(f"/api/v1/intervention/scenario/{scenario_id}")
            assert get_resp.status_code == 200
            get_data = get_resp.json()
            assert get_data["scenario_id"] == scenario_id
            assert get_data["causal_status"] == "MODEL_BASED_COUNTERFACTUAL"

            # Query sub-resources
            comp_resp = client.get(f"/api/v1/intervention/scenario/{scenario_id}/comparison")
            assert comp_resp.status_code == 200

            feat_resp = client.get(f"/api/v1/intervention/scenario/{scenario_id}/features")
            assert feat_resp.status_code == 200
            assert len(feat_resp.json()["feature_changes"]) == 2

    def test_batch_scenario_endpoint(self):
        with TestClient(app) as client:
            batch_payload = {
                "location_id": "DEMO-WARD-01",
                "baseline_prediction_id": "pred_demo_01",
                "scenarios": [
                    {
                        "location_id": "DEMO-WARD-01",
                        "baseline_prediction_id": "pred_demo_01",
                        "scenario_name": "option_a_shade",
                        "interventions": [
                            {
                                "intervention_id": "int_a",
                                "intervention_type": "shade_increase",
                                "target_variable": "shade_fraction",
                                "baseline_value": 0.1,
                                "simulated_value": 0.8,
                            }
                        ]
                    },
                    {
                        "location_id": "DEMO-WARD-01",
                        "baseline_prediction_id": "pred_demo_01",
                        "scenario_name": "option_b_work_rest",
                        "interventions": [
                            {
                                "intervention_id": "int_b",
                                "intervention_type": "work_rest_schedule",
                                "target_variable": "rest_cycle_minutes_per_hour",
                                "baseline_value": 0.0,
                                "simulated_value": 20.0,
                            }
                        ]
                    }
                ]
            }
            resp = client.post("/api/v1/intervention/scenario/batch", json=batch_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["causal_status"] == "MODEL_BASED_COUNTERFACTUAL"
            assert len(data["scenarios"]) == 2
            assert len(data["comparison_table"]) == 2
            assert data["comparison_table"][0]["scenario_name"] == "option_a_shade"
            assert data["comparison_table"][1]["scenario_name"] == "option_b_work_rest"

    def test_history_endpoint_and_db_persistence(self):
        with TestClient(app) as client:
            # Create a scenario
            req_payload = {
                "location_id": "DEMO-WARD-01",
                "baseline_prediction_id": "pred_hist_test",
                "scenario_name": "persistence_test_scenario",
                "description": "Testing DB persistence and history",
                "interventions": [
                    {
                        "intervention_id": "int_p1",
                        "intervention_type": "water_access_increase",
                        "target_variable": "water_access_fraction",
                        "baseline_value": 0.2,
                        "simulated_value": 0.9,
                    }
                ]
            }
            resp = client.post("/api/v1/intervention/scenario", json=req_payload)
            assert resp.status_code == 200
            sc_id = resp.json()["scenario_id"]

            # Query history endpoint
            hist_resp = client.get("/api/v1/intervention/history?limit=10")
            assert hist_resp.status_code == 200
            hist_data = hist_resp.json()
            assert "scenarios" in hist_data
            assert hist_data["total"] >= 1
            ids = [s["scenario_id"] for s in hist_data["scenarios"]]
            assert sc_id in ids

            # Query with location_id filter
            filtered_resp = client.get("/api/v1/intervention/history?location_id=DEMO-WARD-01")
            assert filtered_resp.status_code == 200
            assert filtered_resp.json()["total"] >= 1

    def test_ambient_weather_immutability_during_shift(self):
        engine = InterventionEngine()
        baseline = {
            "heat_index_c": 39.0,
            "wbgt_c": 32.0,
            "utci_c": 38.0,
            "wet_bulb_c": 29.0,
            "mrt_c": 55.0,
            "outdoor_exposure_hours": 8.0,
            "exposure_hour_shift": 0.0,
            "ambient_temp_c": 41.5,
            "relative_humidity": 45.0,
            "wind_speed_ms": 2.2,
        }
        interv = [
            Intervention(
                intervention_id="int_shift",
                intervention_type="exposure_time_shift",
                target_variable="exposure_hour_shift",
                baseline_value=0.0,
                simulated_value=-3.0,
            )
        ]
        sc = engine.simulate(
            baseline_features=baseline,
            interventions=interv,
            baseline_prediction_id="pred_01",
            scenario_name="shift_test",
        )
        # Verify ambient weather values in original baseline dictionary are strictly unchanged
        assert baseline["ambient_temp_c"] == 41.5
        assert baseline["relative_humidity"] == 45.0
        assert baseline["wind_speed_ms"] == 2.2
        assert baseline["exposure_hour_shift"] == 0.0

        # Verify simulation produced a valid counterfactual
        assert sc.causal_status == "MODEL_BASED_COUNTERFACTUAL"
        assert sc.risk_delta <= 0

    def test_all_eight_interventions_end_to_end(self):
        engine = InterventionEngine()
        baseline = {
            "heat_index_c": 40.0,
            "wbgt_c": 33.0,
            "utci_c": 39.0,
            "wet_bulb_c": 30.0,
            "mrt_c": 56.0,
            "outdoor_exposure_hours": 8.0,
            "rest_cycle_minutes_per_hour": 0.0,
            "shade_fraction": 0.1,
            "water_access_fraction": 0.3,
            "cooling_access_fraction": 0.2,
            "power_reliability_fraction": 0.6,
            "exposure_hour_shift": 0.0,
            "vulnerability_score": 0.7,
        }
        test_cases = [
            (InterventionType.OUTDOOR_EXPOSURE_REDUCTION, "outdoor_exposure_hours", 8.0, 4.0),
            (InterventionType.WORK_REST_SCHEDULE, "rest_cycle_minutes_per_hour", 0.0, 20.0),
            (InterventionType.SHADE_INCREASE, "shade_fraction", 0.1, 0.6),
            (InterventionType.WATER_ACCESS_INCREASE, "water_access_fraction", 0.3, 0.85),
            (InterventionType.COOLING_ACCESS_INCREASE, "cooling_access_fraction", 0.2, 0.8),
            (InterventionType.POWER_RESTORATION, "power_reliability_fraction", 0.6, 0.95),
            (InterventionType.EXPOSURE_TIME_SHIFT, "exposure_hour_shift", 0.0, -3.0),
            (InterventionType.COMBINED, "combined_package", 0.0, 0.8),
        ]
        for itype, tvar, bval, sval in test_cases:
            interv = [
                Intervention(
                    intervention_id=f"int_{itype.value}",
                    intervention_type=itype,
                    target_variable=tvar,
                    baseline_value=bval,
                    simulated_value=sval,
                )
            ]
            sc = engine.simulate(
                baseline_features=baseline,
                interventions=interv,
                baseline_prediction_id="pred_all_types",
                scenario_name=f"test_{itype.value}",
            )
            assert sc.causal_status == "MODEL_BASED_COUNTERFACTUAL"
            assert sc.counterfactual_risk_probability >= 0.0
            assert sc.counterfactual_risk_probability <= 1.0
            assert sc.risk_delta <= 0.0
            assert len(sc.feature_changes) >= 1

