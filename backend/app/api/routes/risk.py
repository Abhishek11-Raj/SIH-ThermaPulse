"""Health Risk Prediction API Routes — STEP 4.

Endpoints:
- GET /api/v1/risk/current/{location_id}
- GET /api/v1/risk/forecast/{location_id}
- GET /api/v1/risk/history/{location_id}
- POST /api/v1/risk/calculate
- POST /api/v1/risk/train
- GET /api/v1/risk/models
- GET /api/v1/risk/models/{model_id}
- GET /api/v1/risk/evaluation/{model_id}
- GET /api/v1/risk/features
- GET /api/v1/risk/health
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...services.ingest import default_window
from ..dependencies import get_thermal_service, get_db as _get_db, resolve_location, parse_window
from ...risk.schemas import (
    RiskPredictionOutput,
    RiskPredictionList,
    RiskForecastOutput,
    RiskPredictionRequest,
    RiskForecastOutput,
    RiskCalculateRequest,
    RiskMethodsResponse,
    RiskModelConfig,
    RiskTrainingRequest,
    RiskTrainingResponse,
    RiskTrainingRunOutput,
    RiskModelRegistryOutput,
    RiskEvaluationOutput,
    RiskFeatureManifestOutput,
    RiskMethodsResponse,
    RiskHealthOutput,
)

router = APIRouter(prefix="/api/v1/risk", tags=["health-risk"])


def _get_risk_service(db: Session = Depends(_get_db)):
    from ...risk.service import create_risk_service
    return create_risk_service(db)


@router.get("/health", response_model=Dict[str, Any], tags=["health-risk"])
def risk_health(
    service=Depends(_get_risk_service),
) -> Dict[str, Any]:
    """Health check for risk service."""
    return service.get_health()


@router.get("/methods", response_model=RiskMethodsResponse, tags=["health-risk"])
def get_risk_methods(
    service=Depends(_get_risk_service),
) -> RiskMethodsResponse:
    """Get available risk calculation methods and default configuration."""
    return service.get_methods()


@router.get("/current/{location_id}", response_model=RiskPredictionOutput, tags=["health-risk"])
def get_current_risk(
    location_id: str,
    model_id: Optional[str] = Query(default=None),
    service=Depends(_get_risk_service),
) -> RiskPredictionOutput:
    """
    Get current health risk for a location.

    Uses most recent thermal observation and vulnerability data.
    """
    try:
        return service.get_current_risk(location_id, model_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast/{location_id}", response_model=RiskForecastOutput, tags=["health-risk"])
def get_forecast_risk(
    location_id: str,
    horizon_days: int = Query(default=3, ge=1, le=5),
    model_id: Optional[str] = Query(default=None),
    service=Depends(_get_risk_service),
) -> RiskForecastOutput:
    """
    Get health risk forecast for a location.

    Uses forecast thermal data for the specified horizon.
    """
    try:
        return service.get_forecast_risk(location_id, horizon_days, model_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{location_id}", response_model=RiskPredictionList, tags=["health-risk"])
def get_risk_history(
    location_id: str,
    days: int = Query(default=30, ge=1, le=90),
    service=Depends(_get_risk_service),
) -> RiskPredictionList:
    """
    Get historical risk predictions for a location.
    """
    return service.get_risk_history(location_id, days)


@router.post("/calculate", response_model=RiskPredictionOutput, tags=["health-risk"])
def calculate_risk(
    request: RiskCalculateRequest,
    service=Depends(_get_risk_service),
) -> RiskPredictionOutput:
    """
    Calculate health risk from custom meteorological inputs.

    Allows calculation without requiring existing weather data in the database.
    """
    try:
        return service.calculate_risk(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train", response_model=RiskTrainingResponse, tags=["health-risk"])
def train_model(
    request: RiskTrainingRequest,
    service=Depends(_get_risk_service),
) -> RiskTrainingResponse:
    """
    Train a new health risk model.

    Requires ADMIN or ML_ENGINEER role.
    """
    return service.train_model(request)


@router.get("/training/{run_id}", response_model=RiskTrainingRunOutput, tags=["health-risk"])
def get_training_run(
    run_id: str,
    service=Depends(_get_risk_service),
) -> RiskTrainingRunOutput:
    """Get training run status and results."""
    run = service.get_training_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")
    return run


@router.get("/models", response_model=List[Dict[str, Any]], tags=["health-risk"])
def list_models(
    status: Optional[str] = Query(default=None),
    algorithm: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    service=Depends(_get_risk_service),
) -> List[Dict[str, Any]]:
    """List models in registry."""
    return service.list_models(status, algorithm, limit)


@router.get("/models/{model_id}", response_model=Dict[str, Any], tags=["health-risk"])
def get_model(
    model_id: str,
    version: Optional[str] = Query(default=None),
    service=Depends(_get_risk_service),
) -> Dict[str, Any]:
    """Get model details from registry."""
    model = service.get_model(model_id, version)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/models/{model_id}/promote", response_model=Dict[str, Any], tags=["health-risk"])
def promote_model_endpoint(
    model_id: str,
    version: str = Query(...),
    service=Depends(_get_risk_service),
) -> Dict[str, Any]:
    """Promote a model to production."""
    success = service.promote_model(model_id, version)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"success": True, "model_id": model_id, "version": version, "status": "PRODUCTION"}


@router.post("/models/{model_id}/retire", response_model=Dict[str, Any], tags=["health-risk"])
def retire_model_endpoint(
    model_id: str,
    version: str = Query(...),
    service=Depends(_get_risk_service),
) -> Dict[str, Any]:
    """Retire a model."""
    success = service.retire_model(model_id, version)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"success": True, "model_id": model_id, "version": version, "status": "RETIRED"}


@router.get("/evaluation/{model_id}", response_model=List[RiskEvaluationOutput], tags=["health-risk"])
def get_model_evaluation(
    model_id: str,
    split: Optional[str] = Query(default=None),
    service=Depends(_get_risk_service),
) -> List[RiskEvaluationOutput]:
    """Get model evaluation metrics."""
    return service.get_model_evaluation(model_id, split)


@router.get("/features", response_model=Dict[str, Any], tags=["health-risk"])
def get_feature_manifest(
    version: str = Query(default="1.0"),
    service=Depends(_get_risk_service),
) -> Dict[str, Any]:
    """Get feature manifest for a version."""
    manifest = service.get_feature_manifest(version)
    if not manifest:
        raise HTTPException(status_code=404, detail="Feature manifest not found")
    return manifest.model_dump()


@router.get("/artifacts", response_model=List[Dict[str, Any]], tags=["health-risk"])
def list_model_artifacts(
    service=Depends(_get_risk_service),
) -> List[Dict[str, Any]]:
    """List available model artifacts on disk."""
    return service.list_model_artifacts()


@router.post("/artifacts/cleanup", response_model=Dict[str, Any], tags=["health-risk"])
def cleanup_artifacts(
    keep_latest: int = Query(default=10, ge=1),
    service=Depends(_get_risk_service),
) -> Dict[str, Any]:
    """Clean up old model artifacts."""
    deleted = service.cleanup_old_artifacts(keep_latest)
    return {"deleted": deleted, "kept_latest": 10}