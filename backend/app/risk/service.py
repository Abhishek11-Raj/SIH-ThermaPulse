"""Risk prediction service — STEP 4.

Main service orchestrating risk prediction, training, and model management.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..core.enums import QualityFlag
from ..models.risk import (
    RiskPrediction,
    RiskModelRegistry,
    RiskTrainingRun,
    RiskEvaluationMetrics,
    RiskFeatureManifest,
)
from ..models.thermal import ThermalStressResult as ThermalModel
from ..models.vulnerability import VulnerabilityData as VulnModel, HealthOutcome as HealthModel
from ..models.weather import AirQualityObservation as AQModel
from ..schemas.weather import WeatherObservation
from ..schemas.forecast import WeatherForecast
from ..schemas.air_quality import AirQualityObservation
from ..schemas.health import HealthOutcome
from ..schemas.vulnerability import VulnerabilityRecord
from ..utils.time import utcnow

from .schemas import (
    RiskPredictionOutput,
    RiskPredictionList,
    RiskForecastOutput,
    RiskPredictionRequest,
    RiskCalculateRequest,
    RiskMethodsResponse,
    RiskModelConfig,
    RiskFeatureConfig,
    RiskTrainingRequest,
    RiskTrainingResponse,
    RiskTrainingRunOutput,
    RiskModelRegistryOutput,
    RiskEvaluationOutput,
    RiskFeatureManifestOutput,
    RiskCalculateRequest,
)
from .dataset import RiskDatasetBuilder
from .preprocessing import RiskPreprocessor
from .models import RiskModelFactory
from .training import RiskTrainer
from .evaluation import RiskEvaluator
from .calibration import RiskCalibrator
from .prediction import RiskPredictor
from .registry import ModelRegistry, get_production_model, promote_model
from .persistence import save_model, load_model, list_model_artifacts


class RiskService:
    """Main risk prediction service."""

    def __init__(self, db: Session):
        self.db = db
        self.registry = ModelRegistry(db)

    # --- Prediction ---

    def get_current_risk(
        self,
        location_id: str,
        model_id: Optional[str] = None,
    ) -> RiskPredictionOutput:
        """Get current health risk for a location."""
        predictor = RiskPredictor(self.db)
        return predictor.predict_current(location_id, model_id)

    def get_forecast_risk(
        self,
        location_id: str,
        horizon_days: int = 3,
        model_id: Optional[str] = None,
    ) -> RiskForecastOutput:
        """Get forecast health risk for a location."""
        predictor = RiskPredictor(self.db)
        return predictor.predict_forecast(location_id, horizon_days, model_id)

    def calculate_risk(
        self,
        request: RiskCalculateRequest,
        model_id: Optional[str] = None,
    ) -> RiskPredictionOutput:
        """Calculate risk from custom input."""
        predictor = RiskPredictor(self.db)
        return predictor.predict_custom(request, model_id)

    def get_risk_history(
        self,
        location_id: str,
        days: int = 30,
    ) -> RiskPredictionList:
        """Get historical risk predictions for a location."""
        from ..models.risk import RiskPrediction as RiskPredictionModel

        end = datetime.utcnow()
        start = end - timedelta(days=days)

        predictions = self.db.query(RiskPredictionModel).filter(
            RiskPredictionModel.location_id == location_id,
            RiskPredictionModel.prediction_time >= start,
            RiskPredictionModel.prediction_time <= end,
        ).order_by(RiskPredictionModel.prediction_time.desc()).all()

        return RiskPredictionList(
            results=[
                RiskPredictionOutput(
                    prediction_id=p.prediction_id,
                    location_id=p.location_id,
                    latitude=p.latitude,
                    longitude=p.longitude,
                    prediction_time=p.prediction_time,
                    target_date=p.target_date,
                    horizon_days=p.horizon_days,
                    risk_probability=p.risk_probability,
                    risk_category=p.risk_category,
                    model_id=p.model_id,
                    model_version=p.model_version,
                    feature_version=p.feature_version,
                    threshold_version=p.threshold_version,
                    data_completeness=p.data_completeness,
                    input_quality=p.input_quality,
                    missing_features=p.missing_features or [],
                    forecast_uncertainty=p.forecast_uncertainty,
                    source_type=p.source_type,
                    in_distribution=p.in_distribution,
                    ood_score=p.ood_score,
                    prediction_status=p.prediction_status,
                    error_message=p.error_message,
                    provenance=p.provenance,
                    created_at=p.created_at,
                )
                for p in predictions
            ],
            count=len(predictions),
        )

    # --- Model Management ---

    def train_model(
        self,
        request: RiskTrainingRequest,
    ) -> RiskTrainingResponse:
        """Train a new risk model."""
        trainer = RiskTrainer(request.config)

        # Load training data
        from .dataset import load_training_data
        thermal_data, vuln_data, aq_data, health_data = load_training_data(
            self.db,
            request.config.train_end_date,
            request.config.test_end_date,
        )

        return trainer.train(
            thermal_data=thermal_data,
            vulnerability_data=vuln_data,
            air_quality_data=aq_data,
            health_data=health_data,
            db=self.db,
        )

    def get_training_run(self, run_id: str) -> Optional[RiskTrainingRunOutput]:
        """Get training run status."""
        run = self.db.query(RiskTrainingRun).filter(
            RiskTrainingRun.run_id == run_id
        ).first()

        if not run:
            return None

        return RiskTrainingRunOutput(
            run_id=run.run_id,
            started_at=run.started_at,
            completed_at=run.completed_at,
            status=run.status,
            error_message=run.error_message,
            training_start=run.training_start,
            training_end=run.training_end,
            validation_start=run.validation_start,
            validation_end=run.validation_end,
            test_start=run.test_start,
            test_end=run.test_end,
            algorithm=run.algorithm,
            hyperparameters=run.hyperparameters or {},
            feature_version=run.feature_version,
            target_definition=run.target_definition,
            dataset_version=run.dataset_version,
            metrics=run.metrics,
            calibration_metrics=run.calibration_metrics,
            model_artifact_path=run.model_artifact_path,
            duration_ms=run.duration_ms,
        )

    def list_training_runs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[RiskTrainingRunOutput]:
        """List training runs."""
        query = self.db.query(RiskTrainingRun)
        if status:
            query = query.filter(RiskTrainingRun.status == status)
        runs = query.order_by(RiskTrainingRun.started_at.desc()).limit(limit).all()

        return [
            RiskTrainingRunOutput(
                run_id=r.run_id,
                started_at=r.started_at,
                completed_at=r.completed_at,
                status=r.status,
                error_message=r.error_message,
                training_start=r.training_start,
                training_end=r.training_end,
                validation_start=r.validation_start,
                validation_end=r.validation_end,
                test_start=r.test_start,
                test_end=r.test_end,
                algorithm=r.algorithm,
                hyperparameters=r.hyperparameters or {},
                feature_version=r.feature_version,
                target_definition=r.target_definition,
                dataset_version=r.dataset_version,
                metrics=r.metrics,
                calibration_metrics=r.calibration_metrics,
                model_artifact_path=r.model_artifact_path,
                duration_ms=r.duration_ms,
            )
            for r in runs
        ]

    def get_model(self, model_id: str, version: Optional[str] = None) -> Optional[RiskModelRegistryOutput]:
        """Get model from registry."""
        model = self.registry.get_model(model_id, version)
        if not model:
            return None

        return RiskModelRegistryOutput(
            model_id=model.model_id,
            model_version=model.model_version,
            algorithm=model.algorithm,
            hyperparameters=model.hyperparameters or {},
            feature_version=model.feature_version,
            target_definition=model.target_definition,
            dataset_version=model.dataset_version,
            training_run_id=model.training_run_id,
            status=model.status,
            metrics=model.metrics or {},
            calibration_version=model.calibration_version,
            artifact_path=model.artifact_path,
            created_at=model.created_at,
            promoted_at=model.promoted_at,
            promoted_by=model.promoted_by,
            notes=model.notes,
        )

    def list_models(
        self,
        status: Optional[str] = None,
        algorithm: Optional[str] = None,
        limit: int = 50,
    ) -> List[RiskModelRegistryOutput]:
        """List models in registry."""
        models = self.registry.list_models(status=status, algorithm=algorithm, limit=limit)
        return [
            RiskModelRegistryOutput(
                model_id=m.model_id,
                model_version=m.model_version,
                algorithm=m.algorithm,
                hyperparameters=m.hyperparameters or {},
                feature_version=m.feature_version,
                target_definition=m.target_definition,
                dataset_version=m.dataset_version,
                training_run_id=m.training_run_id,
                status=m.status,
                metrics=m.metrics or {},
                calibration_version=m.calibration_version,
                artifact_path=m.artifact_path,
                created_at=m.created_at,
                promoted_at=m.promoted_at,
                promoted_by=m.promoted_by,
                notes=m.notes,
            )
            for m in models
        ]

    def promote_model(
        self,
        model_id: str,
        version: str,
    ) -> bool:
        """Promote a model to production."""
        return promote_model(self.db, model_id, version)

    def retire_model(self, model_id: str, version: str) -> bool:
        """Retire a model."""
        return self.registry.retire_model(model_id, version)

    def get_model_evaluation(
        self,
        model_id: str,
        split: Optional[str] = None,
    ) -> List[RiskEvaluationOutput]:
        """Get model evaluation metrics."""
        metrics = self.registry.get_evaluation_metrics(model_id, split)
        return [
            RiskEvaluationOutput(
                model_id=m.model_id,
                model_version=m.model_version,
                split_name=m.split_name,
                evaluation_date=m.evaluation_date,
                roc_auc=m.roc_auc,
                pr_auc=m.pr_auc,
                precision=m.precision,
                recall=m.recall,
                f1=m.f1,
                specificity=m.specificity,
                sensitivity=m.sensitivity,
                threshold=m.threshold,
                precision_at_threshold=m.precision_at_threshold,
                recall_at_threshold=m.recall_at_threshold,
                pod=m.pod,
                far=m.far,
                csi=m.csi,
                brier_score=m.brier_score,
                calibration_error=m.calibration_error,
                ece=m.ece,
                slice_metrics=m.slice_metrics,
                confusion_matrix=m.confusion_matrix,
                dataset_size=m.dataset_size,
                positive_rate=m.positive_rate,
                configuration=m.configuration,
            )
            for m in metrics
        ]

    def get_feature_manifest(self, version: str) -> Optional[RiskFeatureManifestOutput]:
        """Get feature manifest."""
        manifest = self.registry.get_feature_manifest(version)
        if not manifest:
            return None

        return RiskFeatureManifestOutput(
            feature_version=manifest.feature_version,
            features=[
                FeatureManifestEntry(**f) for f in manifest.features
            ],
            created_at=manifest.created_at,
            description=manifest.description,
        )

    def get_methods(self) -> RiskMethodsResponse:
        """Get available methods and default config."""
        from app.risk.schemas import HealthRiskTarget
        from datetime import timezone

        target = HealthRiskTarget(
            target_name="heat_health_event",
            target_type="binary",
            description="Binary indicator: did any heat-related health event occur?",
            positive_threshold=1.0,
            outcome_window_days=1,
        )
        config = RiskModelConfig(
            target=target,
            algorithm="hist_gradient_boosting",
            train_end_date=datetime.now(timezone.utc) - timedelta(days=30),
            validation_start_date=datetime.now(timezone.utc) - timedelta(days=20),
            validation_end_date=datetime.now(timezone.utc) - timedelta(days=10),
            test_start_date=datetime.now(timezone.utc) - timedelta(days=10),
            test_end_date=datetime.now(timezone.utc),
        )

        return RiskMethodsResponse(
            algorithms=[
                {
                    "name": "logistic_regression",
                    "description": "Logistic regression baseline",
                    "supports_calibration": True,
                },
                {
                    "name": "hist_gradient_boosting",
                    "description": "Histogram-based gradient boosting",
                    "supports_calibration": True,
                },
                {
                    "name": "xgboost",
                    "description": "XGBoost gradient boosting",
                    "supports_calibration": True,
                },
            ],
            default_config=config,
        )

    def get_health(self) -> Dict[str, Any]:
        """Get service health status."""
        prod_model = self.registry.get_production_model()
        return {
            "status": "healthy",
            "model_registry_status": "ok",
            "available_models": len(self.registry.list_models()),
            "production_model": prod_model.model_id if prod_model else None,
            "last_training": None,
            "data_freshness": "ok",
        }

    def list_model_artifacts(self) -> List[Dict[str, Any]]:
        """List available model artifacts on disk."""
        return list_model_artifacts()

    def cleanup_old_artifacts(self, keep_latest: int = 10) -> int:
        """Clean up old model artifacts."""
        from .persistence import cleanup_old_artifacts
        return cleanup_old_artifacts(keep_latest=keep_latest)


def create_risk_service(db: Session) -> RiskService:
    """Factory function to create risk service."""
    return RiskService(db)