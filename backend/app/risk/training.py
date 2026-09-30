"""Risk model training — STEP 4.

Orchestrates model training, evaluation, and registration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.risk import (
    RiskTrainingRun,
    RiskModelRegistry,
    RiskEvaluationMetrics,
    RiskFeatureManifest,
    RiskCalibration,
)
from ..utils.time import utcnow

from .schemas import (
    RiskModelConfig,
    RiskFeatureConfig,
    HealthRiskTarget,
    RiskTrainingResponse,
    RiskTrainingRunOutput,
    RiskModelRegistryOutput,
)
from .dataset import RiskDatasetBuilder, DatasetSplits, load_training_data
from .preprocessing import RiskPreprocessor, validate_data_quality
from .models import RiskModel, RiskModelFactory, CalibratedRiskModel
from .evaluation import RiskEvaluator, evaluate_model
from .calibration import RiskCalibrator, calibrate_model
from .persistence import save_model, load_model
from .registry import register_model, get_production_model


@dataclass
class TrainingResult:
    """Result of a training run."""
    run_id: str
    status: str
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class RiskTrainer:
    """Orchestrates the full training pipeline."""

    def __init__(
        self,
        config: RiskModelConfig,
        feature_config: Optional[RiskFeatureConfig] = None,
        target_config: Optional[Any] = None,
    ):
        self.config = config
        self.feature_config = config.features if hasattr(config, 'features') else RiskFeatureConfig()
        self.target_config = config.target if hasattr(config, 'target') else None
        self.preprocessor: Optional[Any] = None
        self.model: Optional[Any] = None
        self.run_id: Optional[str] = None

    def train(
        self,
        thermal_data: pd.DataFrame,
        vulnerability_data: Optional[pd.DataFrame] = None,
        air_quality_data: Optional[pd.DataFrame] = None,
        health_data: Optional[pd.DataFrame] = None,
        db: Optional[Session] = None,
    ) -> RiskTrainingResponse:
        """
        Execute full training pipeline.

        Args:
            thermal_data: Thermal stress data
            vulnerability_data: Vulnerability data
            air_quality_data: Air quality data
            health_data: Health outcomes
            db: Database session (optional, creates own if not provided)

        Returns:
            Training response with run ID and status
        """
        self.run_id = f"train_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{np.random.randint(1000, 9999)}"

        # Create training run record
        if db:
            self._create_training_run(db)

        try:
            # Update status to running
            if db:
                self._update_training_run(db, status="RUNNING")

            # Build dataset
            X, y = self._build_dataset(
                thermal_data, vulnerability_data, air_quality_data, health_data
            )

            # Validate data quality
            quality_report = self._validate_data(X, y)
            if not quality_report["passed"]:
                raise ValueError(f"Data quality issues: {quality_report['issues']}")

            # Split data
            splits = self._split_data(X, y)

            # Preprocess
            X_train_proc, preprocessor = self._fit_preprocessor(splits.X_train, splits.y_train)
            X_val_proc = preprocessor.transform(splits.X_val)
            X_test_proc = preprocessor.transform(splits.X_test)

            # Train baseline model
            baseline_model = self._train_baseline(splits.X_train, splits.y_train)

            # Train main model
            model = self._train_model(splits.X_train, splits.y_train)

            # Evaluate
            evaluator = RiskEvaluator(self.config)
            metrics = evaluator.evaluate(model, splits.X_val, splits.y_val, splits.X_test, splits.y_test)

            # Calibrate if requested
            if self.config.calibration_method != "none":
                model = self._calibrate_model(model, splits.X_val, splits.y_val)

            # Evaluate calibrated model
            final_metrics = self._evaluate_final(model, splits)

            # Save model and artifacts
            model_id, model_version = self._save_model_artifacts(
                model, preprocessor, final_metrics, db
            )

            # Update training run record
            if db:
                self._update_training_run(
                    db,
                    status="SUCCESS",
                    metrics=final_metrics,
                    model_id=model_id,
                    model_version=model_version,
                )

            return RiskTrainingResponse(
                run_id=self.run_id,
                status="SUCCESS",
                model_id=model_id,
                model_version=model_id.split("_")[-1] if "_" in model_id else None,
            )

        except Exception as e:
            error_msg = str(e)
            if db:
                self._update_training_run(db, status="FAILED", error_message=error_msg)
            return RiskTrainingResponse(
                run_id=self.run_id,
                status="FAILED",
                error_message=error_msg,
            )

    def _build_dataset(
        self,
        thermal_data: pd.DataFrame,
        vulnerability_data: Optional[pd.DataFrame] = None,
        air_quality_data: Optional[pd.DataFrame] = None,
        health_data: Optional[pd.DataFrame] = None,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Build feature matrix and target vector."""
        # Use feature builder
        from .dataset import RiskDatasetBuilder
        from .targets import TargetBuilder

        builder = RiskDatasetBuilder(
            model_config=self.config,
            feature_config=self.feature_config,
            target_config=self.target_config,
        )

        X, y = builder.build_dataset(
            thermal_data=thermal_data,
            vulnerability_data=vulnerability_data,
            air_quality_data=air_quality_data,
            health_data=health_data,
            prediction_time=None,
        )

        return X, y

    def _validate_data(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Validate data quality."""
        from .preprocessing import validate_data_quality
        return validate_data_quality(X, y)

    def _split_data(self, X: pd.DataFrame, y: pd.Series) -> DatasetSplits:
        """Split data using configured temporal splits."""
        from .dataset import RiskDatasetBuilder

        # Build dummy data to reuse builder
        builder = RiskDatasetBuilder(
            model_config=self.config,
            feature_config=self.feature_config,
            target_config=self.target_config,
        )

        # Use time-aware split from builder
        # We need thermal data for this - create dummy
        # In practice, use actual thermal data passed to train()

        # For now, do simple time-based split
        n = len(X)
        train_end = int(0.6 * len(X))
        val_end = int(0.8 * len(X))

        # Assuming data is time-sorted
        X_train = X.iloc[:int(0.6 * len(X))]
        y_train = y.iloc[:int(0.6 * len(y))]
        X_val = X.iloc[int(0.6 * len(X)):int(0.8 * len(X))]
        y_val = y.iloc[int(0.6 * len(y)):int(0.8 * len(y))]
        X_test = X.iloc[int(0.8 * len(X)):]
        y_test = y.iloc[int(0.8 * len(y)):]

        from .dataset import DatasetSplits
        return DatasetSplits(
            X_train=X.iloc[:int(0.6*len(X))],
            y_train=y.iloc[:int(0.6*len(y))],
            X_val=X.iloc[int(0.6*len(X)):int(0.8*len(X))],
            y_val=y.iloc[int(0.6*len(y)):int(0.8*len(y))],
            X_test=X.iloc[int(0.8*len(X)):],
            y_test=y.iloc[int(0.8*len(y)):],
            feature_names=list(X.columns),
            target_name="risk",
            split_info={},
        )

    def _fit_preprocessor(self, X_train: pd.DataFrame, y_train: pd.Series) -> Tuple[np.ndarray, Any]:
        """Fit preprocessor on training data."""
        preprocessor = RiskPreprocessor(self.feature_config, self.model_config)
        preprocessor.fit(X_train, y_train)
        X_train_proc = preprocessor.transform(X_train)
        return X_train_proc, preprocessor

    def _train_baseline(self, X_train: pd.DataFrame, y_train: pd.Series) -> Any:
        """Train baseline logistic regression model."""
        from .models import LogisticRegressionModel

        # Preprocess first
        preprocessor = RiskPreprocessor(self.feature_config, self.model_config)
        preprocessor.fit(X_train, y_train)
        X_proc = preprocessor.transform(X_train)

        model = LogisticRegressionModel(
            class_weight="balanced",
            random_state=42,
        )
        model.fit(X_train, y_train)
        return model

    def _train_model(self, X_train: pd.DataFrame, y_train: pd.Series) -> Any:
        """Train the main model."""
        from .models import RiskModelFactory

        model = RiskModelFactory.create_model(self.config, self.feature_config)
        model.fit(X_train, y_train)
        return model

    def _calibrate_model(
        self,
        model: Any,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> Any:
        """Calibrate model probabilities."""
        from .calibration import calibrate_model

        # Preprocess validation data
        preprocessor = RiskPreprocessor(self.feature_config, self.model_config)
        preprocessor.fit(X_val, None)
        X_val_proc = preprocessor.transform(X_val)

        calibrated = calibrate_model(
            model,
            X_val,
            y_val,
            method=self.model_config.calibration_method,
        )
        return calibrated

    def _evaluate_final(
        self,
        model: Any,
        splits: Any,
    ) -> Dict[str, Any]:
        """Evaluate final model on test set."""
        from .evaluation import evaluate_model

        metrics = evaluate_model(
            model,
            splits.X_val, splits.y_val,
            splits.X_test, splits.y_test,
            config=self.config,
        )
        return metrics

    def _save_model_artifacts(
        self,
        model: Any,
        preprocessor: Any,
        metrics: Dict[str, Any],
        db: Optional[Session],
    ) -> Tuple[str, str]:
        """Save model artifacts and register in registry."""
        model_id = f"keshav_risk_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        model_version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Save model artifact
        model_path = f"data/models/{model_id}.joblib"
        from .persistence import save_model
        save_model(model, self.preprocessor, f"data/models/{self.run_id}.joblib")

        # Register model
        if db:
            register_model(db, self.run_id, model_id, model_version, metrics)

        return model_id, model_version


def train_risk_model(
    config: RiskModelConfig,
    thermal_data: pd.DataFrame,
    vulnerability_data: Optional[pd.DataFrame] = None,
    air_quality_data: Optional[pd.DataFrame] = None,
    health_data: Optional[pd.DataFrame] = None,
    db: Optional[Session] = None,
) -> RiskTrainingResponse:
    """Convenience function to train a risk model."""
    trainer = RiskTrainer(config)
    return trainer.train(
        thermal_data, vulnerability_data, air_quality_data, health_data, db
    )


def retrain_model(
    model_id: str,
    new_data: pd.DataFrame,
    db: Optional[Session] = None,
) -> RiskTrainingResponse:
    """
    Retrain an existing model with new data (for online learning).

    Note: This is a simplified retraining. For production, use proper
    incremental learning or full retraining.
    """
    # Load existing model
    model, preprocessor = load_model(model_id)

    # Get config from registry
    if db:
        model_reg = db.query(RiskModelRegistry).filter(
            RiskModelRegistry.model_id == model_id
        ).first()
        if model_reg:
            config = RiskModelConfig(
                algorithm=model_reg.algorithm,
                hyperparameters=model_reg.hyperparameters,
                class_weight="balanced",
                calibration_method=model_reg.calibration_version or "isotonic",
            )
        else:
            raise ValueError(f"Model {model_id} not found in registry")
    else:
        raise ValueError("Database session required for retraining")

    # For simplicity, delegate to full retraining
    # In production, implement incremental learning
    return RiskTrainingResponse(
        run_id="retrain_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
        status="PARTIAL",
        message="Retraining not fully implemented. Use full training pipeline.",
    )