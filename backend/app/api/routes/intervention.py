"""KESHAV STEP 6: Intervention and Counterfactual Simulation API Endpoints.

Provides REST endpoints for:
- Intervention definition and constraint validation
- Counterfactual scenario creation and execution
- Batch scenario execution and side-by-side comparison
- Equity, data quality, and uncertainty propagation
- Qualified causal boundary enforcement
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...intervention.engine import InterventionEngine
from ...intervention.schemas import (
    BatchScenarioRequest,
    BatchScenarioResponse,
    CounterfactualScenario,
    DataCoverageInfo,
    Intervention,
    InterventionConstraint,
    InterventionDefinition,
    InterventionRegistry,
    InterventionType,
    ScenarioEquityResult,
    ScenarioRequest,
    ScenarioResponse,
)
from ...models.intervention import InterventionScenarioDB
from ...models.risk import RiskModelRegistry, RiskPrediction
from ...risk.persistence import load_model

logger = logging.getLogger("keshav.api.intervention")

router = APIRouter(prefix="/api/v1/intervention", tags=["intervention"])

# In-memory store for generated scenarios within the running process
_SCENARIO_STORE: Dict[str, CounterfactualScenario] = {}


def _save_scenario_to_db(db: Session, scenario: CounterfactualScenario) -> None:
    """Persist counterfactual scenario to database."""
    try:
        existing = db.query(InterventionScenarioDB).filter(InterventionScenarioDB.scenario_id == scenario.scenario_id).first()
        if existing:
            return

        db_obj = InterventionScenarioDB(
            scenario_id=scenario.scenario_id,
            location_id=scenario.location_id,
            scenario_name=scenario.scenario_name,
            description=scenario.description,
            baseline_prediction_id=scenario.baseline_prediction_id,
            model_version=scenario.model_version,
            feature_version=scenario.feature_version,
            status=scenario.status,
            baseline_risk_probability=scenario.baseline_risk_probability,
            counterfactual_risk_probability=scenario.counterfactual_risk_probability,
            risk_delta=scenario.risk_delta,
            absolute_risk_delta=scenario.absolute_risk_delta,
            relative_change=scenario.relative_change,
            risk_category_baseline=scenario.risk_category_baseline,
            risk_category_counterfactual=scenario.risk_category_counterfactual,
            ood_baseline=scenario.ood_baseline,
            ood_counterfactual=scenario.ood_counterfactual,
            data_quality_baseline=scenario.data_quality_baseline,
            data_quality_counterfactual=scenario.data_quality_counterfactual,
            interventions_data=[i.model_dump(mode="json") for i in scenario.interventions] if scenario.interventions else [],
            feature_changes=scenario.feature_changes,
            limitations=scenario.limitations,
            causal_status=scenario.causal_status,
            disclaimer=scenario.disclaimer,
            created_at=scenario.created_at,
        )
        db.add(db_obj)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Failed to persist scenario %s to database: %s", scenario.scenario_id, e)


def _get_engine(db: Session, model_id: Optional[str] = None) -> InterventionEngine:
    """Helper to instantiate InterventionEngine with production or requested model."""
    if model_id:
        reg_entry = db.query(RiskModelRegistry).filter(RiskModelRegistry.model_id == model_id).first()
    else:
        reg_entry = (
            db.query(RiskModelRegistry)
            .filter(RiskModelRegistry.status == "PRODUCTION")
            .order_by(RiskModelRegistry.created_at.desc())
            .first()
        )
        if not reg_entry:
            reg_entry = db.query(RiskModelRegistry).order_by(RiskModelRegistry.created_at.desc()).first()

    if reg_entry:
        try:
            artifact = load_model(reg_entry.model_id)
            if artifact:
                training_ranges = artifact.config.get("training_ranges", {}) if artifact.config else {}
                return InterventionEngine(
                    model=artifact.model,
                    feature_names=artifact.feature_names,
                    preprocessor=artifact.preprocessor,
                    model_version=reg_entry.model_version or "1.0",
                    training_ranges=training_ranges,
                )
        except Exception as e:
            logger.warning("Could not load artifact for model %s: %s", reg_entry.model_id, e)

    # Return engine with default feature set and heuristic predictor
    default_feature_names = [
        "heat_index_c", "wbgt_c", "utci_c", "wet_bulb_c", "mrt_c",
        "outdoor_exposure_hours", "rest_cycle_minutes_per_hour", "shade_fraction",
        "water_access_fraction", "cooling_access_fraction", "power_reliability_fraction",
        "exposure_hour_shift", "exposure_memory", "cumulative_exposure_24h",
        "cumulative_exposure_72h", "cumulative_exposure_168h", "vulnerability_score",
        "heat_index_x_vulnerability", "wbgt_x_vulnerability"
    ]
    return InterventionEngine(feature_names=default_feature_names)


@router.get("/registry", response_model=Dict[str, Any])
def list_interventions() -> Any:
    """List all registered and supported intervention types with default constraints."""
    supported = InterventionRegistry.list_supported()
    return {
        "supported_count": len(supported),
        "interventions": [
            {
                "id": interv.id,
                "name": interv.name,
                "type": interv.type.value,
                "target_variable": interv.target_variable,
                "description": interv.description,
                "constraints": interv.constraints.model_dump() if interv.constraints else None,
                "affects_thermal_stress": interv.affects_thermal_stress,
                "affects_exposure": interv.affects_exposure,
                "affects_vulnerability": interv.affects_vulnerability,
                "affects_operational": interv.affects_operational,
            }
            for interv in supported
        ],
    }


@router.get("/constraints/{intervention_type}", response_model=Dict[str, Any])
def get_intervention_constraints(
    intervention_type: InterventionType,
) -> Any:
    """Get the valid bounds and constraints for a given intervention type."""
    registered = InterventionRegistry.get(intervention_type)
    if registered and registered.constraints:
        return {
            "intervention_type": intervention_type.value,
            "minimum": registered.constraints.minimum,
            "maximum": registered.constraints.maximum,
            "allowed_direction": registered.constraints.allowed_direction,
            "unit": registered.constraints.unit,
        }

    return {
        "intervention_type": intervention_type.value,
        "minimum": None,
        "maximum": None,
        "allowed_direction": "either",
        "unit": None,
    }


@router.post("/validate", response_model=Dict[str, Any])
def validate_intervention(
    intervention: Intervention,
) -> Any:
    """Validate an intervention specification against constraints and feasibility."""
    interv_type = intervention.intervention_type
    supported = InterventionRegistry.is_supported(interv_type)
    warnings: List[str] = []

    if not supported:
        warnings.append(f"Intervention type '{interv_type}' is not currently registered.")

    reg_def = InterventionRegistry.get(interv_type)
    if reg_def and reg_def.constraints:
        c = reg_def.constraints
        if c.minimum is not None and intervention.simulated_value < c.minimum:
            warnings.append(f"Simulated value {intervention.simulated_value} is below minimum {c.minimum} {c.unit or ''}")
        if c.maximum is not None and intervention.simulated_value > c.maximum:
            warnings.append(f"Simulated value {intervention.simulated_value} exceeds maximum {c.maximum} {c.unit or ''}")
        if c.allowed_direction == "decrease" and intervention.simulated_value > intervention.baseline_value:
            warnings.append("Expected simulated value to be less than or equal to baseline value for a reduction intervention.")
        if c.allowed_direction == "increase" and intervention.simulated_value < intervention.baseline_value:
            warnings.append("Expected simulated value to be greater than or equal to baseline value for an enhancement intervention.")

    return {
        "is_valid": supported and len(warnings) == 0,
        "supported": supported,
        "warnings": warnings,
        "intervention_id": intervention.intervention_id,
        "intervention_type": (
            intervention.intervention_type.value
            if isinstance(intervention.intervention_type, InterventionType)
            else str(intervention.intervention_type)
        ),
        "target_variable": intervention.target_variable,
        "baseline_value": intervention.baseline_value,
        "simulated_value": intervention.simulated_value,
        "effective_constraints": intervention.constraints.model_dump() if intervention.constraints else (
            reg_def.constraints.model_dump() if reg_def and reg_def.constraints else None
        ),
    }


@router.post("/scenario", response_model=ScenarioResponse)
def create_scenario(
    request: ScenarioRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Create and execute a counterfactual scenario from a baseline state."""
    # Look up baseline prediction if exists
    baseline_pred = (
        db.query(RiskPrediction)
        .filter(RiskPrediction.prediction_id == request.baseline_prediction_id)
        .first()
    )

    baseline_features: Dict[str, float] = {
        "location_id": request.location_id,
        "heat_index_c": 38.5,
        "wbgt_c": 31.0,
        "utci_c": 37.0,
        "wet_bulb_c": 28.0,
        "mrt_c": 52.0,
        "outdoor_exposure_hours": 8.0,
        "rest_cycle_minutes_per_hour": 0.0,
        "shade_fraction": 0.1,
        "water_access_fraction": 0.4,
        "cooling_access_fraction": 0.2,
        "power_reliability_fraction": 0.7,
        "exposure_hour_shift": 0.0,
        "exposure_memory": 2.2,
        "cumulative_exposure_24h": 6.5,
        "cumulative_exposure_72h": 18.2,
        "cumulative_exposure_168h": 39.0,
        "vulnerability_score": 0.65,
    }

    if baseline_pred:
        if baseline_pred.provenance and isinstance(baseline_pred.provenance, dict):
            feat_dict = baseline_pred.provenance.get("feature_values") or baseline_pred.provenance.get("features")
            if isinstance(feat_dict, dict):
                baseline_features.update(feat_dict)

    # Instantiate engine
    engine = _get_engine(db, request.model_version)

    # Run simulation
    scenario = engine.simulate(
        baseline_features=baseline_features,
        interventions=request.interventions,
        baseline_prediction_id=request.baseline_prediction_id,
        scenario_name=request.scenario_name,
        location_id=request.location_id,
    )

    # Save scenario in process store and database
    _SCENARIO_STORE[scenario.scenario_id] = scenario
    _save_scenario_to_db(db, scenario)

    interpretation = "MODEL_PREDICTED_RISK_NO_CHANGE"
    if scenario.risk_delta < -0.01:
        interpretation = "MODEL_PREDICTED_RISK_DECREASE"
    elif scenario.risk_delta > 0.01:
        interpretation = "MODEL_PREDICTED_RISK_INCREASE"

    return ScenarioResponse(
        scenario_id=scenario.scenario_id,
        status="COMPLETED",
        baseline={
            "risk_probability": scenario.baseline_risk_probability,
            "risk_category": scenario.risk_category_baseline,
            "model_version": scenario.model_version,
            "quality": scenario.data_quality_baseline,
            "ood": scenario.ood_baseline,
        },
        counterfactual={
            "risk_probability": scenario.counterfactual_risk_probability,
            "risk_category": scenario.risk_category_counterfactual,
            "model_version": scenario.model_version,
            "quality": scenario.data_quality_counterfactual,
            "ood": scenario.ood_counterfactual,
        },
        comparison={
            "baseline_risk_probability": scenario.baseline_risk_probability,
            "counterfactual_risk_probability": scenario.counterfactual_risk_probability,
            "risk_delta": scenario.risk_delta,
            "absolute_risk_delta": scenario.absolute_risk_delta,
            "relative_change": scenario.relative_change,
            "interpretation": interpretation,
        },
        changes=scenario.feature_changes,
        limitations=scenario.limitations,
        feature_manifest_version="1.0",
        model_version=scenario.model_version,
        scenario_created_at=scenario.created_at,
        causal_status="MODEL_BASED_COUNTERFACTUAL",
    )


@router.post("/scenario/batch", response_model=BatchScenarioResponse)
def batch_compare_scenarios(
    request: BatchScenarioRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Simulate and compare multiple counterfactual scenarios side-by-side against a baseline."""
    if not request.scenarios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one scenario must be provided in batch request",
        )

    engine = _get_engine(db)

    baseline_features: Dict[str, float] = {
        "location_id": request.location_id,
        "heat_index_c": 38.5,
        "wbgt_c": 31.0,
        "utci_c": 37.0,
        "wet_bulb_c": 28.0,
        "mrt_c": 52.0,
        "outdoor_exposure_hours": 8.0,
        "rest_cycle_minutes_per_hour": 0.0,
        "shade_fraction": 0.1,
        "water_access_fraction": 0.4,
        "cooling_access_fraction": 0.2,
        "power_reliability_fraction": 0.7,
        "exposure_hour_shift": 0.0,
        "exposure_memory": 2.2,
        "cumulative_exposure_24h": 6.5,
        "cumulative_exposure_72h": 18.2,
        "cumulative_exposure_168h": 39.0,
        "vulnerability_score": 0.65,
    }

    baseline_prob, baseline_cat = engine._run_model(baseline_features)

    scenario_responses: List[ScenarioResponse] = []
    comparison_rows: List[Dict[str, Any]] = []

    for sc_req in request.scenarios:
        sc = engine.simulate(
            baseline_features=baseline_features,
            interventions=sc_req.interventions,
            baseline_prediction_id=request.baseline_prediction_id,
            scenario_name=sc_req.scenario_name,
            location_id=request.location_id,
        )
        _SCENARIO_STORE[sc.scenario_id] = sc
        _save_scenario_to_db(db, sc)

        interpretation = "MODEL_PREDICTED_RISK_NO_CHANGE"
        if sc.risk_delta < -0.01:
            interpretation = "MODEL_PREDICTED_RISK_DECREASE"
        elif sc.risk_delta > 0.01:
            interpretation = "MODEL_PREDICTED_RISK_INCREASE"

        resp = ScenarioResponse(
            scenario_id=sc.scenario_id,
            status="COMPLETED",
            baseline={
                "risk_probability": sc.baseline_risk_probability,
                "risk_category": sc.risk_category_baseline,
                "model_version": sc.model_version,
                "quality": sc.data_quality_baseline,
                "ood": sc.ood_baseline,
            },
            counterfactual={
                "risk_probability": sc.counterfactual_risk_probability,
                "risk_category": sc.risk_category_counterfactual,
                "model_version": sc.model_version,
                "quality": sc.data_quality_counterfactual,
                "ood": sc.ood_counterfactual,
            },
            comparison={
                "baseline_risk_probability": sc.baseline_risk_probability,
                "counterfactual_risk_probability": sc.counterfactual_risk_probability,
                "risk_delta": sc.risk_delta,
                "absolute_risk_delta": sc.absolute_risk_delta,
                "relative_change": sc.relative_change,
                "interpretation": interpretation,
            },
            changes=sc.feature_changes,
            limitations=sc.limitations,
            feature_manifest_version="1.0",
            model_version=sc.model_version,
            scenario_created_at=sc.created_at,
            causal_status="MODEL_BASED_COUNTERFACTUAL",
        )
        scenario_responses.append(resp)

        comparison_rows.append({
            "scenario_id": sc.scenario_id,
            "scenario_name": sc.scenario_name,
            "baseline_risk_probability": sc.baseline_risk_probability,
            "counterfactual_risk_probability": sc.counterfactual_risk_probability,
            "risk_delta": sc.risk_delta,
            "relative_change": sc.relative_change,
            "risk_category_counterfactual": sc.risk_category_counterfactual,
            "interventions_applied": len(sc.interventions),
            "ood": sc.ood_counterfactual,
            "data_quality": sc.data_quality_counterfactual,
            "interpretation": interpretation,
        })

    return BatchScenarioResponse(
        location_id=request.location_id,
        baseline_prediction_id=request.baseline_prediction_id,
        baseline={
            "risk_probability": round(baseline_prob, 4),
            "risk_category": baseline_cat,
        },
        scenarios=scenario_responses,
        comparison_table=comparison_rows,
        causal_status="MODEL_BASED_COUNTERFACTUAL",
    )


@router.get("/history", response_model=Dict[str, Any])
def list_scenario_history(
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> Any:
    """List historical counterfactual simulation scenarios from the database."""
    query = db.query(InterventionScenarioDB)
    if location_id:
        query = query.filter(InterventionScenarioDB.location_id == location_id)

    total = query.count()
    records = query.order_by(InterventionScenarioDB.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for r in records:
        items.append({
            "scenario_id": r.scenario_id,
            "location_id": r.location_id,
            "scenario_name": r.scenario_name,
            "baseline_prediction_id": r.baseline_prediction_id,
            "baseline_risk_probability": r.baseline_risk_probability,
            "counterfactual_risk_probability": r.counterfactual_risk_probability,
            "risk_delta": r.risk_delta,
            "risk_category_baseline": r.risk_category_baseline,
            "risk_category_counterfactual": r.risk_category_counterfactual,
            "interventions_count": len(r.interventions_data or []),
            "ood_counterfactual": r.ood_counterfactual,
            "data_quality": r.data_quality_counterfactual,
            "causal_status": r.causal_status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "scenarios": items,
    }


@router.get("/scenario/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve details of a previously computed scenario."""
    sc = _SCENARIO_STORE.get(scenario_id)
    if sc:
        interpretation = "MODEL_PREDICTED_RISK_NO_CHANGE"
        if sc.risk_delta < -0.01:
            interpretation = "MODEL_PREDICTED_RISK_DECREASE"
        elif sc.risk_delta > 0.01:
            interpretation = "MODEL_PREDICTED_RISK_INCREASE"

        return ScenarioResponse(
            scenario_id=sc.scenario_id,
            status="COMPLETED",
            baseline={
                "risk_probability": sc.baseline_risk_probability,
                "risk_category": sc.risk_category_baseline,
                "model_version": sc.model_version,
                "quality": sc.data_quality_baseline,
                "ood": sc.ood_baseline,
            },
            counterfactual={
                "risk_probability": sc.counterfactual_risk_probability,
                "risk_category": sc.risk_category_counterfactual,
                "model_version": sc.model_version,
                "quality": sc.data_quality_counterfactual,
                "ood": sc.ood_counterfactual,
            },
            comparison={
                "baseline_risk_probability": sc.baseline_risk_probability,
                "counterfactual_risk_probability": sc.counterfactual_risk_probability,
                "risk_delta": sc.risk_delta,
                "absolute_risk_delta": sc.absolute_risk_delta,
                "relative_change": sc.relative_change,
                "interpretation": interpretation,
            },
            changes=sc.feature_changes,
            limitations=sc.limitations,
            feature_manifest_version="1.0",
            model_version=sc.model_version,
            scenario_created_at=sc.created_at,
            causal_status="MODEL_BASED_COUNTERFACTUAL",
        )

    # Fallback to database
    db_sc = db.query(InterventionScenarioDB).filter(InterventionScenarioDB.scenario_id == scenario_id).first()
    if not db_sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )
    interpretation = "MODEL_PREDICTED_RISK_NO_CHANGE"
    if db_sc.risk_delta < -0.01:
        interpretation = "MODEL_PREDICTED_RISK_DECREASE"
    elif db_sc.risk_delta > 0.01:
        interpretation = "MODEL_PREDICTED_RISK_INCREASE"

    return ScenarioResponse(
        scenario_id=db_sc.scenario_id,
        status="COMPLETED",
        baseline={
            "risk_probability": db_sc.baseline_risk_probability,
            "risk_category": db_sc.risk_category_baseline,
            "model_version": db_sc.model_version,
            "quality": db_sc.data_quality_baseline,
            "ood": db_sc.ood_baseline,
        },
        counterfactual={
            "risk_probability": db_sc.counterfactual_risk_probability,
            "risk_category": db_sc.risk_category_counterfactual,
            "model_version": db_sc.model_version,
            "quality": db_sc.data_quality_counterfactual,
            "ood": db_sc.ood_counterfactual,
        },
        comparison={
            "baseline_risk_probability": db_sc.baseline_risk_probability,
            "counterfactual_risk_probability": db_sc.counterfactual_risk_probability,
            "risk_delta": db_sc.risk_delta,
            "absolute_risk_delta": db_sc.absolute_risk_delta,
            "relative_change": db_sc.relative_change,
            "interpretation": interpretation,
        },
        changes=db_sc.feature_changes or [],
        limitations=db_sc.limitations or [],
        feature_manifest_version="1.0",
        model_version=db_sc.model_version,
        scenario_created_at=db_sc.created_at,
        causal_status="MODEL_BASED_COUNTERFACTUAL",
    )


@router.get("/scenario/{scenario_id}/comparison", response_model=Dict[str, Any])
def get_scenario_comparison(scenario_id: str) -> Any:
    """Get comparison metrics for a scenario."""
    sc = _SCENARIO_STORE.get(scenario_id)
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )
    return {
        "scenario_id": sc.scenario_id,
        "baseline_risk_probability": sc.baseline_risk_probability,
        "counterfactual_risk_probability": sc.counterfactual_risk_probability,
        "risk_delta": sc.risk_delta,
        "relative_change": sc.relative_change,
        "baseline_category": sc.risk_category_baseline,
        "counterfactual_category": sc.risk_category_counterfactual,
        "causal_status": "MODEL_BASED_COUNTERFACTUAL",
    }


@router.get("/scenario/{scenario_id}/features", response_model=Dict[str, Any])
def get_scenario_features(scenario_id: str) -> Any:
    """Get feature changes for a scenario."""
    sc = _SCENARIO_STORE.get(scenario_id)
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )
    return {
        "scenario_id": sc.scenario_id,
        "feature_changes": sc.feature_changes,
    }


@router.get("/scenario/{scenario_id}/uncertainty", response_model=Dict[str, Any])
def get_scenario_uncertainty(scenario_id: str) -> Any:
    """Get uncertainty and OOD status for a scenario."""
    sc = _SCENARIO_STORE.get(scenario_id)
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )
    return {
        "scenario_id": sc.scenario_id,
        "ood_baseline": sc.ood_baseline,
        "ood_counterfactual": sc.ood_counterfactual,
        "data_quality_baseline": sc.data_quality_baseline,
        "data_quality_counterfactual": sc.data_quality_counterfactual,
    }


@router.get("/scenario/{scenario_id}/explanation", response_model=Dict[str, Any])
def get_scenario_explanation(scenario_id: str) -> Any:
    """Get explanation of feature changes for a scenario."""
    sc = _SCENARIO_STORE.get(scenario_id)
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )
    return {
        "scenario_id": sc.scenario_id,
        "changes": sc.feature_changes,
        "limitations": sc.limitations,
        "causal_status": "MODEL_BASED_COUNTERFACTUAL",
    }


@router.get("/scenario/{scenario_id}/equity", response_model=Dict[str, Any])
def get_scenario_equity(scenario_id: str) -> Any:
    """Get equity analysis for a scenario."""
    sc = _SCENARIO_STORE.get(scenario_id)
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )
    return {
        "scenario_id": sc.scenario_id,
        "location_id": sc.location_id,
        "equity_audit_status": "DATA_AGGREGATED",
        "causal_status": "MODEL_BASED_COUNTERFACTUAL",
        "notes": "Subgroup evaluation requires ward-level disaggregated outcome records.",
    }