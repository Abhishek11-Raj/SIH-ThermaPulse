"""Risk prediction models — STEP 4.

Implements baseline and ML models for health risk prediction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline

from .schemas import RiskModelConfig, RiskFeatureConfig


class RiskModel(ABC):
    """Abstract base class for risk prediction models."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "RiskModel":
        """Fit the model."""
        pass

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        pass

    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """Get model parameters."""
        pass

    @abstractmethod
    def set_params(self, **params) -> "RiskModel":
        """Set model parameters."""
        pass


class LogisticRegressionModel(RiskModel):
    """Logistic Regression baseline model for health risk prediction."""

    def __init__(
        self,
        C: float = 1.0,
        class_weight: str = "balanced",
        max_iter: int = 1000,
        random_state: int = 42,
        **kwargs,
    ):
        self.C = C
        self.class_weight = class_weight
        self.max_iter = max_iter
        self.random_state = random_state
        self.kwargs = kwargs

        self.model = LogisticRegression(
            C=C,
            class_weight=class_weight,
            max_iter=max_iter,
            random_state=random_state,
            **kwargs,
        )
        self._fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LogisticRegressionModel":
        self.model.fit(X, y)
        self._fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return self.model.predict_proba(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return self.model.predict(X)

    def get_params(self) -> Dict[str, Any]:
        return {
            "algorithm": "logistic_regression",
            "C": self.C,
            "class_weight": self.class_weight,
            "max_iter": self.max_iter,
            "random_state": self.random_state,
        }

    def set_params(self, **params) -> "LogisticRegressionModel":
        for k, v in params.items():
            setattr(self, k, v)
        self.model.set_params(**params)
        return self


class HistGradientBoostingModel(RiskModel):
    """Histogram Gradient Boosting model for health risk prediction."""

    def __init__(
        self,
        max_iter: int = 200,
        learning_rate: float = 0.1,
        max_depth: Optional[int] = None,
        min_samples_leaf: int = 20,
        class_weight: str = "balanced",
        random_state: int = 42,
        **kwargs,
    ):
        self.max_iter = max_iter
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.class_weight = class_weight
        self.random_state = random_state
        self.kwargs = kwargs

        self.model = HistGradientBoostingClassifier(
            max_iter=max_iter,
            learning_rate=learning_rate,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            class_weight=class_weight,
            random_state=random_state,
            **kwargs,
        )
        self._fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "HistGradientBoostingModel":
        self.model.fit(X, y)
        self._fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return self.model.predict_proba(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return self.model.predict(X)

    def get_feature_importance(self) -> Optional[np.ndarray]:
        if not self._fitted:
            return None
        # HistGradientBoostingClassifier has feature_importances_ attribute
        return getattr(self.model, "feature_importances_", None)

    def get_params(self) -> Dict[str, Any]:
        return {
            "algorithm": "hist_gradient_boosting",
            "max_iter": self.max_iter,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "min_samples_leaf": self.min_samples_leaf,
            "class_weight": self.class_weight,
            "random_state": self.random_state,
        }

    def set_params(self, **params) -> "HistGradientBoostingModel":
        for k, v in params.items():
            setattr(self, k, v)
        self.model.set_params(**params)
        return self


class CalibratedRiskModel(RiskModel):
    """Wrapper that adds probability calibration to any base model."""

    def __init__(
        self,
        base_model: RiskModel,
        method: str = "isotonic",
        cv: int = 3,
    ):
        self.base_model = base_model
        self.method = method
        self.cv = cv
        self.calibrated_model: Optional[CalibratedClassifierCV] = None
        self._fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "CalibratedRiskModel":
        # First fit base model
        self.base_model.fit(X, y)

        # Then calibrate
        # Use the base model's predict_proba as the base estimator
        # For calibration, we need a sklearn-compatible estimator
        from sklearn.base import clone
        from sklearn.calibration import CalibratedClassifierCV

        # Create a wrapper that exposes the base model's predict_proba
        class BaseEstimatorWrapper:
            def __init__(self, model):
                self.model = model

            def fit(self, X, y):
                return self

            def predict_proba(self, X):
                return self.model.predict_proba(X)

            def predict(self, X):
                return self.model.predict(X)

        wrapper = BaseEstimatorWrapper(self.base_model)
        self.calibrated_model = CalibratedClassifierCV(
            wrapper,
            method=self.method,
            cv=self.cv,
        )
        self.calibrated_model.fit(X, y)
        self._fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return self.calibrated_model.predict_proba(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return self.calibrated_model.predict(X)

    def get_params(self) -> Dict[str, Any]:
        params = self.base_model.get_params()
        params["calibration_method"] = self.method
        params["calibration_cv"] = self.cv
        return params

    def set_params(self, **params) -> "CalibratedRiskModel":
        return self


class RiskModelFactory:
    """Factory for creating risk models from config."""

    @staticmethod
    def create_model(config: RiskModelConfig, feature_config: RiskFeatureConfig) -> RiskModel:
        """Create a model from configuration."""
        algorithm = config.algorithm

        if algorithm == "logistic_regression":
            base_model = LogisticRegressionModel(
                C=config.hyperparameters.get("C", 1.0),
                class_weight=config.class_weight,
                max_iter=config.hyperparameters.get("max_iter", 1000),
                random_state=config.random_seed,
            )
        elif algorithm == "hist_gradient_boosting":
            base_model = HistGradientBoostingModel(
                max_iter=config.hyperparameters.get("max_iter", 200),
                learning_rate=config.hyperparameters.get("learning_rate", 0.1),
                max_depth=config.hyperparameters.get("max_depth"),
                min_samples_leaf=config.hyperparameters.get("min_samples_leaf", 20),
                class_weight=config.class_weight,
                random_state=config.random_seed,
            )
        elif algorithm == "xgboost":
            # Try to import xgboost, fallback to hist_gradient_boosting
            try:
                import xgboost as xgb
                base_model = XGBoostModel(
                    n_estimators=config.hyperparameters.get("n_estimators", 200),
                    learning_rate=config.hyperparameters.get("learning_rate", 0.1),
                    max_depth=config.hyperparameters.get("max_depth", 6),
                    min_child_weight=config.hyperparameters.get("min_child_weight", 1),
                    scale_pos_weight=config.hyperparameters.get("scale_pos_weight", 1),
                    random_state=config.random_seed,
                )
            except ImportError:
                # Fallback
                base_model = HistGradientBoostingModel(
                    max_iter=config.hyperparameters.get("max_iter", 200),
                    learning_rate=config.hyperparameters.get("learning_rate", 0.1),
                    max_depth=config.hyperparameters.get("max_depth"),
                    min_samples_leaf=config.hyperparameters.get("min_samples_leaf", 20),
                    class_weight=config.class_weight,
                    random_state=config.random_seed,
                )
        else:
            raise ValueError(f"Unknown algorithm: {config.algorithm}")

        # Apply calibration if requested
        if config.calibration_method != "none":
            base_model = CalibratedRiskModel(
                base_model,
                method=config.calibration_method,
                cv=config.hyperparameters.get("calibration_cv", 3),
            )

        return base_model


# XGBoost model (optional, only if xgboost is installed)
class XGBoostModel(RiskModel):
    """XGBoost model for health risk prediction (optional)."""

    def __init__(
        self,
        n_estimators: int = 200,
        learning_rate: float = 0.1,
        max_depth: int = 6,
        min_child_weight: int = 1,
        scale_pos_weight: float = 1.0,
        random_state: int = 42,
        **kwargs,
    ):
        try:
            import xgboost as xgb
            self.xgb = xgb
        except ImportError:
            raise ImportError("xgboost not installed")

        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.min_child_weight = min_child_weight
        self.scale_pos_weight = scale_pos_weight
        self.random_state = random_state
        self.kwargs = kwargs

        self.model = self.xgb.XGBClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            min_child_weight=min_child_weight,
            scale_pos_weight=scale_pos_weight,
            random_state=random_state,
            use_label_encoder=False,
            eval_metric="logloss",
            **kwargs,
        )
        self._fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "XGBoostModel":
        self.model.fit(X, y)
        self._fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return self.model.predict_proba(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return self.model.predict(X)

    def get_feature_importance(self) -> Optional[np.ndarray]:
        if not self._fitted:
            return None
        return self.model.feature_importances_

    def get_params(self) -> Dict[str, Any]:
        return {
            "algorithm": "xgboost",
            "n_estimators": self.n_estimators,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "min_child_weight": self.min_child_weight,
            "scale_pos_weight": self.scale_pos_weight,
            "random_state": self.random_state,
        }

    def set_params(self, **params) -> "XGBoostModel":
        for k, v in params.items():
            setattr(self, k, v)
        self.model.set_params(**params)
        return self


def create_model_from_config(
    model_config: RiskModelConfig,
    feature_config: RiskFeatureConfig,
) -> RiskModel:
    """Convenience function to create model from config."""
    return RiskModelFactory.create_model(model_config)