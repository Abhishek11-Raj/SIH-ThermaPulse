"""Risk model registry — STEP 4.

Manages model registration, versioning, and promotion.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.risk import (
    RiskModelRegistry,
    RiskEvaluationMetrics,
    RiskFeatureManifest,
)
from ..utils.time import utcnow


class ModelRegistry:
    """Manages risk model registry."""

    def __init__(self, db: Session):
        self.db = db

    def register(
        self,
        model_id: str,
        model_version: str,
        algorithm: str,
        hyperparameters: Dict[str, Any],
        feature_version: str,
        target_definition: str,
        dataset_version: str,
        training_run_id: str,
        metrics: Dict[str, Any],
        artifact_path: Optional[str] = None,
        calibration_version: Optional[str] = None,
    ) -> RiskModelRegistry:
        """Register a new model version."""
        model = RiskModelRegistry(
            model_id=model_id,
            model_version=model_version,
            algorithm=algorithm,
            hyperparameters=hyperparameters,
            feature_version=feature_version,
            target_definition=target_definition,
            dataset_version=dataset_version,
            training_run_id=training_run_id,
            status="EXPERIMENTAL",
            metrics=metrics,
            calibration_version=calibration_version,
            artifact_path=None,
        )

        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)

        return model

    def get_model(self, model_id: str, version: Optional[str] = None) -> Optional[Any]:
        """Get a model from registry."""
        query = self.db.query(RiskModelRegistry).filter(
            RiskModelRegistry.model_id == model_id
        )
        if version:
            query = query.filter(RiskModelRegistry.model_version == version)
        return query.order_by(RiskModelRegistry.created_at.desc()).first()

    def get_production_model(self) -> Optional[Any]:
        """Get the current production model."""
        return self.db.query(RiskModelRegistry).filter(
            RiskModelRegistry.status == "PRODUCTION"
        ).order_by(RiskModelRegistry.created_at.desc()).first()

    def get_models_by_status(self, status: str) -> List[Any]:
        """Get all models with a given status."""
        return self.db.query(RiskModelRegistry).filter(
            RiskModelRegistry.status == status
        ).order_by(RiskModelRegistry.created_at.desc()).all()

    def promote_model(
        self,
        model_id: str,
        version: str,
        promoted_by: str,
    ) -> bool:
        """
        Promote a model to PRODUCTION status.

        Demotes current production model if exists.
        """
        # Demote current production
        current_prod = self.get_production_model()
        if current_prod:
            current_prod.status = "RETIRED"
            self.db.commit()

        # Promote new model
        model = self.db.query(RiskModelRegistry).filter(
            RiskModelRegistry.model_id == model_id,
            RiskModelRegistry.model_version == version,
        ).first()

        if not model:
            return False

        model.status = "PRODUCTION"
        model.promoted_at = datetime.utcnow()
        model.promoted_by = "system"

        self.db.commit()
        return True

    def retire_model(self, model_id: str, version: str) -> bool:
        """Retire a model."""
        model = self.db.query(RiskModelRegistry).filter(
            RiskModelRegistry.model_id == model_id,
            RiskModelRegistry.model_version == version,
        ).first()

        if not model:
            return False

        model.status = "RETIRED"
        self.db.commit()
        return True

    def list_models(
        self,
        status: Optional[str] = None,
        algorithm: Optional[str] = None,
        limit: int = 50,
    ) -> List[Any]:
        """List models with optional filters."""
        query = self.db.query(RiskModelRegistry)

        if status:
            query = query.filter(RiskModelRegistry.status == status)
        if algorithm:
            query = query.filter(RiskModelRegistry.algorithm == algorithm)

        return query.order_by(RiskModelRegistry.created_at.desc()).limit(limit).all()

    def get_evaluation_metrics(
        self,
        model_id: str,
        split: Optional[str] = None,
    ) -> List[Any]:
        """Get evaluation metrics for a model."""
        query = self.db.query(RiskEvaluationMetrics).filter(
            RiskEvaluationMetrics.model_id == model_id
        )
        if split:
            query = query.filter(RiskEvaluationMetrics.split_name == split)
        return query.order_by(RiskEvaluationMetrics.evaluation_date.desc()).all()

    def register_evaluation(
        self,
        model_id: str,
        model_version: str,
        split_name: str,
        metrics: Dict[str, Any],
        confusion_matrix: Optional[Dict[str, int]] = None,
        slice_metrics: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Register evaluation metrics for a model."""
        metrics_obj = RiskEvaluationMetrics(
            model_id=model_id,
            model_version=model_version,
            split_name=split_name,
            evaluation_date=datetime.utcnow(),
            **metrics,
            confusion_matrix=confusion_matrix,
            slice_metrics=confusion_matrix,
        )
        self.db.add(metrics_obj)
        self.db.commit()
        return metrics_obj

    def register_feature_manifest(
        self,
        feature_version: str,
        features: List[Dict[str, Any]],
        description: Optional[str] = None,
    ) -> RiskFeatureManifest:
        """Register a feature manifest."""
        manifest = RiskFeatureManifest(
            feature_version=feature_version,
            features=features,
            description=description,
        )
        self.db.add(manifest)
        self.db.commit()
        return manifest

    def get_feature_manifest(self, version: str) -> Optional[Any]:
        """Get feature manifest by version."""
        return self.db.query(RiskFeatureManifest).filter(
            RiskFeatureManifest.feature_version == version
        ).first()


def register_model(
    db: Session,
    training_run_id: str,
    model_id: str,
    model_version: str,
    metrics: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Register a trained model in the registry.

    Returns (model_id, model_version)
    """
    registry = ModelRegistry(db)

    # Extract config from metrics or use defaults
    algorithm = "hist_gradient_boosting"  # default
    hyperparameters = {}
    feature_version = "1.0"
    target_definition = "heat_health_event"
    dataset_version = "1.0"

    model = registry.register(
        model_id=model_id,
        model_version=metrics.get("model_version", "1.0"),
        algorithm=algorithm,
        hyperparameters=hyperparameters,
        feature_version=feature_version,
        target_definition=target_definition,
        dataset_version=dataset_version,
        training_run_id=training_run_id,
        metrics=metrics,
    )

    return model.model_id, model.model_version


def get_production_model(db: Session) -> Optional[Any]:
    """Get the current production model."""
    registry = ModelRegistry(db)
    return registry.get_production_model()


def promote_model(
    db: Session,
    model_id: str,
    version: str,
    promoted_by: str = "system",
) -> bool:
    """Promote a model to production."""
    registry = ModelRegistry(db)
    return registry.promote_model(model_id, version, promoted_by)


def get_model_registry(db: Session) -> List[Dict[str, Any]]:
    """Get list of all models in registry."""
    registry = ModelRegistry(db)
    models = registry.list_models(limit=100)
    return [
        {
            "model_id": m.model_id,
            "model_version": m.model_version,
            "algorithm": m.algorithm,
            "status": m.status,
            "metrics": m.metrics,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "promoted_at": m.promoted_at.isoformat() if m.promoted_at else None,
        }
        for m in models
    ]