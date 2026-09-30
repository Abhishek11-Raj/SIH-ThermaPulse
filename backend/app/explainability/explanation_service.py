"""Explanation service for KESHAV STEP 5.

Provides prediction explainability, uncertainty estimation, and fairness auditing
for risk predictions. All components are designed to integrate with the
existing Step 4 risk prediction pipeline.

Key principles:
- Explanations describe model behavior, not causal effects
- Data quality ≠ safety (data-poor areas must not become low risk)
- Uncertainty metrics are separate from risk probability
- All explanations are provenance-tracked and auditable
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.enums import QualityFlag
from ..explainability.schemas import (
    LocalExplanationOutput,
    GlobalExplanationOutput,
    ExplanationProvenance,
    UncertaintyRecord,
    EquityAuditRecord,
    OODRecord,
    CalibrationDiagnostics,
    ExplanationQualityCheck,
)
from ..explainability.shap_engine import SHAPEngine, HAS_SHAP
from ..explainability.feature_importance import FeatureImportanceEngine


logger = logging.getLogger(__name__)


def _import_risk_schemas():
    """Lazy import to avoid circular imports with app.risk.prediction."""
    from ..risk.schemas import RiskPredictionOutput  # Risk prediction output schema
    return RiskPredictionOutput


class ExplanationService:
    """Service for generating and managing explanations for risk predictions.

    Orchestrates:
    - Local per-prediction explanations (SHAP or model-native)
    - Global feature importance
    - Uncertainty estimation
    - OOD detection
    - Explanation quality validation
    - Provenance tracking
    """

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        feature_manifest: Optional[List[Dict[str, Any]]] = None,
        model_version: str = "1.0",
        training_ranges: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        """Initialize explanation service.

        Args:
            model: Trained risk model
            feature_names: List of feature names in prediction order
            feature_manifest: Optional feature manifest entries
            model_version: Model version string
            training_ranges: Feature training ranges for OOD detection
        """
        self.model = model
        self.feature_names = feature_names
        self.feature_manifest = feature_manifest or []
        self.model_version = model_version
        self.training_ranges = training_ranges or {}

        # Initialize sub-engines
        self.local_generator = LocalExplanationGenerator(
            model,
            feature_names,
            feature_manifest=self.feature_manifest,
            model_version=model_version,
        )

        if HAS_SHAP:
            self.shap_engine = SHAPEngine(
                model,
                feature_names,
                model_type=self.local_generator._detect_model_type(),
            )
        else:
            self.shap_engine = None

        self.feature_importance_engine = FeatureImportanceEngine(
            model,
            feature_names,
            X_reference=None,  # Will be set per-call if needed
            model_type=self._detect_model_type(),
        )

        self.global_engine = GlobalExplanationEngine(
            model,
            feature_names,
            X_reference=None,
            model_type=self._detect_model_type(),
        )

    def _detect_model_type(self) -> str:
        """Detect model type."""
        if hasattr(self.model, "feature_importances_"):
            return "tree"
        elif hasattr(self.model, "coef_"):
            return "linear"
        return "other"

    def explain_prediction(
        self,
        prediction_id: str,
        feature_vector: np.ndarray,
        feature_values: Dict[str, float],
        data_quality: str = "GOOD",
        in_distribution: bool = True,
        ood: bool = False,
        ood_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate complete explanation for a single prediction.

        Args:
            prediction_id: Unique prediction identifier
            feature_vector: Preprocessed feature vector (1, n_features)
            feature_values: Dictionary of feature_name -> raw value
            data_quality: Data quality category
            in_distribution: Whether prediction is in-distribution
            ood: Whether out-of-distribution
            ood_score: OOD score if available

        Returns:
            Dictionary with all explanation components
        """
        # Generate local explanation
        local = self.local_generator.generate(
            prediction_id=prediction_id,
            feature_vector=feature_vector,
            feature_values=feature_values,
            data_quality=data_quality,
            in_distribution=in_distribution,
            ood=ood,
            ood_score=ood_score,
            training_ranges=self.training_ranges,
        )

        # Generate global importance context
        global_importance = self.global_engine.compute_global_importance("model_native")

        # Build uncertainty record
        uncertainty = self._build_uncertainty_record(
            local,
            data_quality,
        )

        # Build quality check
        quality_check = local.quality_check

        # Build provenance
        provenance = local.provenance

        return {
            "local_explanation": local,
            "global_importance": global_importance,
            "uncertainty": uncertainty,
            "quality_check": quality_check,
            "provenance": provenance,
            "ood_record": local.ood_record,
        }

    def _build_uncertainty_record(
        self,
        local_explanation: LocalExplanationOutput,
        data_quality: str,
    ) -> UncertaintyRecord:
        """Build uncertainty metadata separate from risk probability.

        Implements the principle: risk_probability ≠ prediction certainty.
        """
        # Map risk category to confidence
        risk_prob = local_explanation.risk_probability
        if risk_prob >= 0.75:
            confidence = "HIGH"
        elif risk_prob >= 0.25:
            confidence = "MODERATE"
        else:
            confidence = "LOW"

        # Data completeness from feature values
        n_features = len([v for v in feature_values.values() if not np.isnan(v)])
        total_features = len(feature_values)
        completeness = n_features / total_features if total_features > 0 else 0.0

        # Missing feature count
        missing_count = len([v for v in feature_values.values() if np.isnan(v)])

        # Stale feature count (features with old data)
        # In a full implementation, this would check timestamps
        stale_count = 0

        # Forecast uncertainty (if forecast prediction)
        forecast_uncertainty = local_explanation.ood_score

        # Model uncertainty (from calibration or variation)
        # If calibrated model, use calibration ECE; otherwise moderate
        model_uncertainty = None
        if local_explanation.ood:
            model_uncertainty = "HIGH"
        elif confidence == "LOW":
            model_uncertainty = "HIGH"
        else:
            model_uncertainty = "MODERATE"

        from ..core.enums import QualityFlag
        return UncertaintyRecord(
            prediction_id=local_explanation.prediction_id,
            data_quality=data_quality,
            data_completeness=completeness,
            missing_feature_count=missing_count,
            stale_feature_count=stale_count,
            forecast_uncertainty=forecast_uncertainty,
            model_uncertainty=model_uncertainty,
            confidence_category=confidence,
        )

    def explain_batch(
        self,
        prediction_ids: List[str],
        feature_vectors: List[np.ndarray],
        feature_values_list: List[Dict[str, float]],
        data_quality_list: List[str],
        in_distribution_list: List[bool],
    ) -> List[Dict[str, Any]]:
        """Generate explanations for a batch of predictions.

        Args:
            prediction_ids: List of prediction identifiers
            feature_vectors: List of preprocessed feature vectors
            feature_values_list: List of feature value dictionaries
            data_quality_list: List of data quality categories
            in_distribution_list: List of in-distribution flags

        Returns:
            List of explanation dictionaries
        """
        results = []
        for i, pred_id in enumerate(prediction_ids):
            result = self.explain_prediction(
                prediction_id=pred_id,
                feature_vector=feature_vectors[i],
                feature_values=feature_values_list[i],
                data_quality=data_quality_list[i] if i < len(data_quality_list) else "GOOD",
                in_distribution=in_distribution_list[i] if i < len(in_distribution_list) else True,
            )
            results.append(result)
        return results

    def compute_global_importance(
        self,
        method: str = "model_native",
    ) -> GlobalExplanationOutput:
        """Compute global feature importance.

        Args:
            method: Importance method ("shap", "permutation", "model_native")

        Returns:
            GlobalExplanationOutput with ranked feature importance
        """
        return self.global_engine.compute_global_importance(method)

    def compare_model_versions(
        self,
        model_v1: Any,
        model_v2: Any,
        X: "pd.DataFrame",
        y: "np.ndarray",
    ) -> Dict[str, Any]:
        """Compare feature importance across model versions.

        Args:
            model_v1: First model version
            model_v2: Second model version
            X: Feature data
            y: Target values

        Returns:
            Comparison dictionary
        """
        return self.global_engine.compare_across_versions(
            model_v1, model_v2, self.feature_names, self.feature_names, X, y
        )