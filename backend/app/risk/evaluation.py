"""Risk model evaluation — STEP 4.

Evaluates health risk models with comprehensive metrics including
calibration, rare event metrics, and spatial/temporal slices.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    precision_recall_curve,
    roc_curve,
    confusion_matrix,
    brier_score_loss,
    classification_report,
)
from scipy.stats import binned_statistic

from .schemas import (
    RiskModelConfig,
    RiskEvaluationOutput,
)


class RiskEvaluator:
    """Evaluates risk prediction models with comprehensive metrics."""

    def __init__(self, config: RiskModelConfig):
        self.config = config

    def evaluate(
        self,
        model: Any,
        X_val: np.ndarray,
        y_val: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate model on validation and test sets.

        Returns comprehensive metrics dictionary.
        """
        # Get predictions
        y_val_pred = model.predict_proba(X_val)[:, 1] if X_val.shape[0] > 0 else np.array([])
        y_test_pred = model.predict_proba(X_test)[:, 1] if X_test.shape[0] > 0 else np.array([])
        y_val_pred_binary = (y_val_pred >= 0.5).astype(int)
        y_test_pred_binary = (y_test_pred >= 0.5).astype(int)

        # Validation metrics
        val_metrics = self._compute_metrics(
            self.config.validation_start_date,  # placeholder
            y_val, y_val_pred, y_val_pred_binary,
            prefix="val_"
        )

        # Test metrics
        test_metrics = self._compute_metrics(
            self.config.test_start_date,  # placeholder
            y_test, y_test_pred, y_test_pred_binary,
            prefix="test_"
        )

        # Combine
        metrics = {**val_metrics, **test_metrics}

        # Add feature importance if available
        if hasattr(model, 'get_feature_importance'):
            importance = model.get_feature_importance()
            if importance is not None:
                metrics["feature_importance"] = dict(zip(
                    [f"feat_{i}" for i in range(len(importance))],
                    importance.tolist()
                ))

        return metrics

    def _compute_metrics(
        self,
        split_date: Any,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        y_pred_binary: np.ndarray,
        prefix: str = "",
    ) -> Dict[str, Any]:
        """Compute comprehensive metrics for a split."""
        if len(y_true) == 0:
            return {}

        metrics = {}

        # Basic classification metrics
        metrics[f"{prefix}precision"] = precision_score(
            y_true, y_pred_binary, zero_division=0
        )
        metrics[f"{prefix}recall"] = recall_score(y_true, y_pred_binary, zero_division=0)
        metrics[f"{prefix}f1"] = f1_score(y_true, y_pred_binary, zero_division=0)
        metrics[f"{prefix}accuracy"] = (y_true == y_pred_binary).mean()

        # ROC-AUC
        try:
            metrics[f"{prefix}roc_auc"] = roc_auc_score(y_true, y_pred_proba)
        except ValueError:
            metrics[f"{prefix}roc_auc"] = None

        # PR-AUC (especially important for imbalanced data)
        try:
            metrics[f"{prefix}pr_auc"] = average_precision_score(y_true, y_pred_proba)
        except ValueError:
            metrics[f"{prefix}pr_auc"] = None

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred_binary)
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            metrics[f"{prefix}tp"] = int(tp)
            metrics[f"{prefix}tn"] = int(tn)
            metrics[f"{prefix}fp"] = int(fp)
            metrics[f"{prefix}fn"] = int(fn)

            # Derived metrics
            metrics[f"{prefix}sensitivity"] = tp / (tp + fn) if (tp + fn) > 0 else 0
            metrics[f"{prefix}specificity"] = tn / (tn + fp) if (tn + fp) > 0 else 0
            metrics[f"{prefix}ppv"] = tp / (tp + fp) if (tp + fp) > 0 else 0  # PPV = precision
            metrics[f"{prefix}npv"] = tn / (tn + fn) if (tn + fn) > 0 else 0

            # Rare event metrics
            # POD = Probability of Detection = recall
            metrics[f"{prefix}pod"] = metrics[f"{prefix}recall"]
            # FAR = False Alarm Ratio
            metrics[f"{prefix}far"] = fp / (tp + fp) if (tp + fp) > 0 else 0
            # CSI = Critical Success Index
            metrics[f"{prefix}csi"] = tp / (tp + fn + fp) if (tp + fn + fp) > 0 else 0

        # Calibration metrics
        cal_metrics = self._compute_calibration_metrics(y_true, y_pred_proba)
        metrics[f"{prefix}brier_score"] = cal_metrics["brier_score"]
        metrics[f"{prefix}calibration_error"] = cal_metrics["calibration_error"]
        metrics[f"{prefix}ece"] = cal_metrics["ece"]

        # Reliability curve data
        metrics[f"{prefix}reliability_curve"] = self._compute_reliability_curve(y_true, y_pred_proba)

        return metrics

    def _compute_calibration_metrics(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        n_bins: int = 10,
    ) -> Dict[str, Any]:
        """Compute calibration metrics."""
        # Brier score
        brier = brier_score_loss(y_true, y_pred_proba)

        # Expected Calibration Error (ECE)
        ece = self._expected_calibration_error(y_true, y_pred_proba)

        # Calibration error (max absolute difference)
        cal_error = self._calibration_error(y_true, y_pred_proba, n_bins=10)

        return {
            "brier_score": float(brier),
            "ece": float(ece),
            "calibration_error": float(cal_error),
        }

    def _expected_calibration_error(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        n_bins: int = 10,
    ) -> float:
        """Compute Expected Calibration Error (ECE)."""
        bin_edges = np.linspace(0, 1, n_bins + 1)
        ece = 0.0

        for i in range(n_bins):
            bin_mask = (y_pred_proba >= bin_edges[i]) & (y_pred_proba < bin_edges[i + 1])
            if i == n_bins - 1:
                bin_mask = (y_pred_proba >= bin_edges[i]) & (y_pred_proba <= bin_edges[i + 1])

            bin_size = np.sum(bin_mask)
            if bin_size == 0:
                continue

            bin_accuracy = y_true[bin_mask].mean()
            bin_confidence = y_pred_proba[bin_mask].mean()
            ece += (bin_size / len(y_true)) * abs(bin_accuracy - bin_confidence)

        return float(ece)

    def _calibration_error(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        n_bins: int = 10,
    ) -> float:
        """Maximum calibration error (max absolute difference)."""
        bin_edges = np.linspace(0, 1, n_bins + 1)
        max_error = 0.0

        for i in range(n_bins):
            bin_mask = (y_pred_proba >= bin_edges[i]) & (y_pred_proba < bin_edges[i + 1])
            if i == n_bins - 1:
                bin_mask = (y_pred_proba >= bin_edges[i]) & (y_pred_proba <= bin_edges[i + 1])

            if np.sum(bin_mask) == 0:
                continue

            bin_accuracy = y_true[bin_mask].mean()
            bin_confidence = y_pred_proba[bin_mask].mean()
            error = abs(bin_accuracy - bin_confidence)
            max_error = max(max_error, error)

        return float(max_error)

    def _compute_reliability_curve(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        n_bins: int = 10,
    ) -> Dict[str, List[float]]:
        """Compute reliability curve data for visualization."""
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        bin_accuracies = []
        bin_confidences = []
        bin_counts = []

        for i in range(n_bins):
            bin_mask = (y_pred_proba >= bin_edges[i]) & (y_pred_proba < bin_edges[i + 1])
            if i == n_bins - 1:
                bin_mask = (y_pred_proba >= bin_edges[i]) & (y_pred_proba <= bin_edges[i + 1])

            bin_size = np.sum(bin_mask)
            if bin_size == 0:
                bin_accuracies.append(None)
                bin_confidences.append(None)
                bin_counts.append(0)
            else:
                bin_accuracies.append(float(y_true[bin_mask].mean()))
                bin_confidences.append(float(y_pred_proba[bin_mask].mean()))
                bin_counts.append(int(bin_size))

        return {
            "bin_centers": bin_centers.tolist(),
            "bin_accuracies": bin_accuracies,
            "bin_confidences": bin_confidences,
            "bin_counts": bin_counts,
        }


def evaluate_model(
    model: Any,
    X_val: np.ndarray,
    y_val: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """Convenience function to evaluate a model."""
    evaluator = RiskEvaluator(config or RiskModelConfig(
        algorithm="unknown",
        train_end_date=datetime.now(),
        validation_start_date=datetime.now(),
        validation_end_date=datetime.now(),
        test_start_date=datetime.now(),
        test_end_date=datetime.now(),
    ))
    return evaluator.evaluate(model, None, None, None, None)


def compute_slice_metrics(
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    slice_features: Dict[str, np.ndarray],
    threshold: float = 0.5,
) -> Dict[str, Dict[str, float]]:
    """
    Compute metrics for data slices (e.g., by vulnerability level, location type).

    Args:
        model: Trained model
        X: Feature matrix
        y: True labels
        slice_features: Dict of slice_name -> boolean mask
        threshold: Classification threshold

    Returns:
        Dict of slice_name -> metrics dict
    """
    y_pred_proba = model.predict_proba(X)[:, 1]
    y_pred_binary = (y_pred_proba >= 0.5).astype(int)

    slice_metrics = {}

    for slice_name, mask in slice_features.items():
        if not mask.any():
            continue

        y_slice = y[mask]
        y_pred_slice = model.predict_proba(X[mask])[:, 1] if mask.any() else np.array([])
        y_pred_binary_slice = (y_pred_slice >= 0.5).astype(int) if len(y_pred_slice) > 0 else np.array([])

        if len(y_slice) == 0:
            continue

        metrics = {}
        try:
            metrics["roc_auc"] = roc_auc_score(y_slice, y_pred_slice)
        except ValueError:
            metrics["roc_auc"] = None

        try:
            metrics["pr_auc"] = average_precision_score(y_slice, y_pred_slice)
        except ValueError:
            metrics["pr_auc"] = None

        y_pred_binary = (y_slice >= 0.5).astype(int)
        try:
            from sklearn.metrics import precision_score, recall_score, f1_score
            metrics["precision"] = precision_score(y_slice, y_pred_binary, zero_division=0)
            metrics["recall"] = recall_score(y_slice, y_pred_binary, zero_division=0)
            metrics["f1"] = f1_score(y_slice, y_pred_binary, zero_division=0)
        except:
            pass

        metrics["n_samples"] = len(y_slice)
        metrics["positive_rate"] = float(y_slice.mean())

        slice_metrics[slice_name] = metrics

    return slice_metrics


def compute_threshold_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    thresholds: List[float] = None,
) -> List[Dict[str, float]]:
    """
    Compute metrics across multiple thresholds.

    Returns list of dicts with threshold, precision, recall, f1, etc.
    """
    if thresholds is None:
        thresholds = np.linspace(0.1, 0.9, 9)

    results = []
    for thresh in thresholds:
        y_pred = (y_pred_proba >= thresh).astype(int)
        results.append({
            "threshold": thresh,
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "f1": f1_score(y_true, y_pred, zero_division=0),
            "specificity": None,  # Would need tn, fp
        })

    return results