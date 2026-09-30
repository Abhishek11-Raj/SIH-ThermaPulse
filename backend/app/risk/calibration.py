"""Risk model calibration — STEP 4.

Implements probability calibration for risk models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from ..models.risk import RiskCalibration
from ..utils.time import utcnow
from .schemas import RiskModelConfig


class RiskCalibrator:
    """Calibrates risk model probabilities."""

    def __init__(self, config: RiskModelConfig):
        self.config = config
        self.calibrator: Optional[Any] = None
        self.method = config.calibration_method
        self.calibration_fraction = config.calibration_fraction

    def fit(
        self,
        model: Any,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> "RiskCalibrator":
        """
        Fit calibrator on validation data.

        Args:
            model: Base model with predict_proba method
            X_val: Validation features
            y_val: Validation labels

        Returns:
            Self for chaining
        """
        if self.config.calibration_method == "none":
            return self

        # Get base model predictions
        y_pred_proba = model.predict_proba(X_val)[:, 1]

        # Split for calibration if using holdout
        if self.calibration_fraction < 1.0:
            from sklearn.model_selection import train_test_split
            cal_X, _, cal_y, _ = train_test_split(
                model.predict_proba(X_val)[:, 1].reshape(-1, 1),
                y_val,
                test_size=1 - self.calibration_fraction,
                random_state=42,
                stratify=y_val,
            )
            X_cal = cal_X
            y_cal = cal_y
        else:
            X_cal = model.predict_proba(X_val)[:, 1].reshape(-1, 1)
            y_cal = y_val

        if self.config.calibration_method == "isotonic":
            self.calibrator = IsotonicRegression(out_of_bounds="clip")
            self.calibrator.fit(X_cal.ravel(), y_cal)
        elif self.config.calibration_method == "platt":
            # Platt scaling using logistic regression on predicted probabilities
            platt = LogisticRegression(solver="lbfgs", max_iter=1000)
            platt.fit(X_cal, y_cal)
            self.calibrator = platt
        else:
            raise ValueError(f"Unknown calibration method: {self.method}")

        return self

    def transform(self, y_pred_proba: np.ndarray) -> np.ndarray:
        """
        Apply calibration to predicted probabilities.

        Args:
            y_pred_proba: Raw predicted probabilities (shape: n_samples,)

        Returns:
            Calibrated probabilities
        """
        if self.calibrator is None:
            return y_pred_proba

        if self.config.calibration_method == "isotonic":
            return self.calibrator.transform(y_pred_proba)
        elif self.config.calibration_method == "platt":
            # Platt scaling: logistic regression on predicted probabilities
            probas = y_pred_proba.reshape(-1, 1)
            calibrated = self.calibrator.predict_proba(probas)[:, 1]
            return calibrated
        else:
            return y_pred_proba

    def fit_transform(
        self,
        model: Any,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> np.ndarray:
        """Fit calibrator and transform validation predictions."""
        self.fit(model, X_val, y_val)
        y_pred = model.predict_proba(X_val)[:, 1]
        return self.transform(y_pred)


def calibrate_model(
    model: Any,
    X_val: np.ndarray,
    y_val: np.ndarray,
    method: str = "isotonic",
    calibration_fraction: float = 0.2,
) -> Any:
    """
    Calibrate a model and return a wrapped calibrated model.

    Returns a wrapper that applies calibration automatically.
    """
    from .models import RiskModel

    class CalibratedWrapper:
        def __init__(self, base_model, calibrator):
            self.base_model = base_model
            self.calibrator = calibrator

        def fit(self, X, y):
            self.base_model.fit(X, y)
            return self

        def predict_proba(self, X):
            raw_proba = self.base_model.predict_proba(X)
            # Apply calibration
            calibrated = self.calibrator.transform(raw_proba[:, 1])
            # Return as 2D array for sklearn compatibility
            return np.column_stack([1 - calibrated, calibrated])

        def predict(self, X):
            proba = self.predict_proba(X)
            return (proba[:, 1] >= 0.5).astype(int)

        def get_params(self):
            params = self.base_model.get_params()
            params["calibrated"] = True
            params["calibration_method"] = self.calibrator.method if hasattr(self.calibrator, 'method') else "unknown"
            return params

        def set_params(self, **params):
            return self

    calibrator = RiskCalibrator(
        RiskModelConfig(
            algorithm="dummy",
            train_end_date=datetime.now(),
            validation_start_date=datetime.now(),
            validation_end_date=datetime.now(),
            test_start_date=datetime.now(),
            test_end_date=datetime.now(),
            calibration_method=method,
            calibration_fraction=0.2,
        )
    )
    calibrator.fit(None, X_val, y_val)

    wrapper = CalibratedWrapper(model, calibrator)
    return wrapper


class TemperatureScaling:
    """
    Temperature scaling for calibration (common in deep learning).
    Simplified version for risk models.
    """

    def __init__(self):
        self.temperature = 1.0

    def fit(self, logits: np.ndarray, labels: np.ndarray) -> "TemperatureScaling":
        """Fit temperature parameter."""
        from scipy.optimize import minimize

        def nll(temp):
            scaled = logits / temp
            probs = 1 / (1 + np.exp(-scaled))
            eps = 1e-15
            probs = np.clip(probs, 1e-15, 1 - 1e-15)
            return -np.mean(labels * np.log(probs) + (1 - labels) * np.log(1 - probs))

        result = minimize(nll, 1.0, bounds=[(0.01, 10.0)], method='L-BFGS-B')
        self.temperature = result.x[0]
        return self

    def transform(self, logits: np.ndarray) -> np.ndarray:
        scaled = logits / self.temperature
        return 1 / (1 + np.exp(-scaled))


def create_calibration_record(
    model_id: str,
    model_version: str,
    method: str,
    parameters: Dict[str, Any],
    validation_start: datetime,
    validation_end: datetime,
    n_samples: int,
    brier_before: float,
    brier_after: float,
    cal_error_before: float,
    cal_error_after: float,
    artifact_path: Optional[str] = None,
) -> RiskCalibration:
    """Create a calibration database record."""
    return RiskCalibration(
        calibration_id=f"cal_{model_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        model_id=model_id,
        model_version=model_version,
        method=method.upper(),
        parameters=parameters,
        validation_start=validation_start,
        validation_end=validation_end,
        n_samples=n_samples,
        brier_score_before=brier_before,
        brier_score_after=brier_after,
        calibration_error_before=cal_error_before,
        calibration_error_after=cal_error_after,
        artifact_path=artifact_path,
    )