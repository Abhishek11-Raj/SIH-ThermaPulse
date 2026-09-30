"""Global and local feature importance for KESHAV risk models.

Supports multiple importance methods:
- Mean absolute SHAP values (for tree-based models)
- Permutation importance
- Model-native importance (coefficients, tree importance)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..explainability.schemas import (
    GlobalExplanationOutput,
    FeatureImportanceEntry,
    LocalExplanationOutput,
)


logger = logging.getLogger(__name__)


class FeatureImportanceEngine:
    """Engine for computing feature importance across multiple methods."""

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        X_reference: Optional[pd.DataFrame] = None,
        model_type: Literal["tree", "linear", "other"] = "tree",
    ):
        """Initialize feature importance engine.

        Args:
            model: Trained model
            feature_names: List of feature names
            X_reference: Reference data for permutation importance (if None, uses training data)
            model_type: Type of model
        """
        self.model = model
        self.feature_names = feature_names
        self.model_type = model_type
        self.X_reference = X_reference

    def compute_shap_importance(self, X: pd.DataFrame, y: Optional[np.ndarray] = None) -> List[FeatureImportanceEntry]:
        """Compute mean absolute SHAP feature importance.

        Args:
            X: Feature data
            y: Target values (optional, for classification)

        Returns:
            List of FeatureImportanceEntry sorted by importance
        """
        if not HAS_SHAP:
            return self._model_native_importance_fallback(X)

        try:
            # Create explainer with reference data
            ref_data = self.X_reference if self.X_reference is not None else X
            explainer = shap.TreeExplainer(self.model, ref_data[:50])

            # Compute SHAP values
            shap_values = explainer.shap_values(X)

            # Handle binary classification output format
            if isinstance(shap_values, list):
                # Positive class
                if len(shap_values) > 1:
                    shap_values = shap_values[1]
                else:
                    shap_values = shap_values[0]

            # Mean absolute SHAP importance
            mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

            # Create importance entries
            importance_entries = [
                FeatureImportanceEntry(
                    feature=name,
                    importance=float(imp),
                    description=f"Mean |SHAP| from {self.model_type} model",
                )
                for name, imp in zip(self.feature_names, mean_abs_shap)
            ]

            # Sort by importance descending
            importance_entries.sort(key=lambda x: x.importance, reverse=True)

            return importance_entries

        except Exception as e:
            logger.error(f"SHAP importance computation failed: {e}")
            return self._model_native_importance_fallback(X)

    def compute_permutation_importance(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        n_permutations: int = 10,
        random_seed: int = 42,
    ) -> List[FeatureImportanceEntry]:
        """Compute permutation feature importance.

        Args:
            X: Feature data
            y: True target values
            n_permutations: Number of permutation iterations
            random_seed: Random seed

        Returns:
            List of FeatureImportanceEntry sorted by importance (descending)
        """
        from sklearn.inspection import permutation_importance

        try:
            # Use model's predict_proba for classification
            if hasattr(self.model, "predict_proba"):
                scoring = "roc_auc"
            else:
                scoring = "accuracy"

            perm_result = permutation_importance(
                self.model,
                X,
                y,
                n_permutations=n_permutations,
                random_state=random_seed,
                scoring=scoring,
            )

            # Create importance entries
            importance_entries = [
                FeatureImportanceEntry(
                    feature=name,
                    importance=float(imp),
                    description=f"Permutation importance ({n_permutations} permutations)",
                )
                for name, imp in zip(self.feature_names, perm_result.importances_mean)
            ]

            # Sort by importance descending
            importance_entries.sort(key=lambda x: x.importance, reverse=True)

            return importance_entries

        except Exception as e:
            logger.error(f"Permutation importance computation failed: {e}")
            return self._model_native_importance_fallback(X)

    def compute_model_native_importance(self) -> List[FeatureImportanceEntry]:
        """Compute model-native importance where available.

        Different models provide different types of importance:
        - Tree models: feature_importances_
        - Linear models: coef_ magnitudes
        - Other: fallback to basic metrics

        Returns:
            List of FeatureImportanceEntry
        """
        entries = []

        if hasattr(self.model, "feature_importances_"):
            # Tree-based model
            importances = self.model.feature_importances_
            for name, imp in zip(self.feature_names, importances):
                entries.append(
                    FeatureImportanceEntry(
                        feature=name,
                        importance=float(imp),
                        description="Tree model feature_importances_",
                    )
                )

        elif hasattr(self.model, "coef_"):
            # Linear model (LogisticRegression)
            coefs = self.model.coef_[0] if self.model.coef_.ndim > 1 else self.model.coef_
            for name, coef in zip(self.feature_names, coefs):
                entries.append(
                    FeatureImportanceEntry(
                        feature=name,
                        importance=float(abs(coef)),
                        description="Linear model |coefficient|",
                    )
                )

        else:
            # No native importance available
            logger.warning("Model has no native feature importance attribute")

        # Sort by importance descending
        entries.sort(key=lambda x: x.importance, reverse=True)

        # If no entries were generated, create equal-weight entries
        if not entries:
            n_features = len(self.feature_names)
            base_imp = 1.0 / n_features if n_features > 0 else 0.0
            for name in self.feature_names:
                entries.append(
                    FeatureImportanceEntry(
                        feature=name,
                        importance=base_imp,
                        description="Equal weight (no native importance)",
                    )
                )

        return entries

    def _model_native_importance_fallback(self, X: pd.DataFrame) -> List[FeatureImportanceEntry]:
        """Fallback when SHAP is unavailable - use model-native importance.

        Does not fabricate SHAP values.
        """
        return self.compute_model_native_importance()


class LocalExplanationEngine:
    """Engine for generating local explanations per prediction."""

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        shap_engine: Optional[SHAPEngine] = None,
    ):
        """Initialize local explanation engine.

        Args:
            model: Trained risk model
            feature_names: List of feature names
            shap_engine: Optional SHAP engine for SHAP-based explanations
        """
        self.model = model
        self.feature_names = feature_names
        self.shap_engine = shap_engine or SHAPEngine(
            model,
            feature_names,
            model_type=self._detect_model_type(),
        )

    def _detect_model_type(self) -> str:
        """Detect the type of model for explainer selection."""
        if hasattr(self.model, "feature_importances_"):
            return "tree"
        elif hasattr(self.model, "coef_"):
            return "linear"
        else:
            return "other"

    def generate_local_explanation(
        self,
        feature_vector: np.ndarray,
        feature_values: Dict[str, float],
        baseline_value: Optional[float] = None,
    ) -> LocalExplanationOutput:
        """Generate a local explanation for a single prediction.

        Args:
            feature_vector: Preprocessed feature vector (1, n_features)
            feature_values: Dictionary of feature_name -> raw value
            baseline_value: Optional explicit baseline probability

        Returns:
            LocalExplanationOutput with all explanation details
        """
        # Get SHAP-based explanation
        shap_result = self.shap_engine.explain_prediction(
            feature_vector, feature_values
        )

        # Use provided baseline or compute from model
        if baseline_value is None:
            # Compute baseline as model's base prediction
            if hasattr(self.model, "predict_proba"):
                try:
                    baseline_prob = float(
                        self.model.predict_proba(
                            np.zeros((1, len(self.feature_vector)) if hasattr(self, 'feature_vector') else feature_vector.reshape(1, -1))
                        )[0, 1]
                    )
                except Exception:
                    baseline_prob = 0.5
            else:
                baseline_prob = 0.5
        else:
            baseline_prob = baseline_value

        # Build top factors from SHAP results
        top_positive = shap_result.get("top_positive_factors", [])
        top_negative = shap_result.get("top_negative_factors", [])

        # If SHAP failed and we have model-native contributions, use those
        if not top_positive and not top_negative:
            contributions = shap_result.get("contributions", {})
            if contributions:
                sorted_items = sorted(
                    contributions.items(), key=lambda x: abs(x[1]), reverse=True
                )
                top_positive = [
                    {
                        "feature": name,
                        "value": feature_values.get(name, "N/A"),
                        "contribution": float(contributions[name]),
                    }
                    for name, _ in sorted_items
                    if contributions[name] > 0
                ][:5]
                top_negative = [
                    {
                        "feature": name,
                        "value": feature_values.get(name, "N/A"),
                        "contribution": float(contributions[name]),
                    }
                    for name, _ in sorted_items
                    if contributions[name] < 0
                ][:5]

        # Determine in-distribution status
        in_distribution = shap_result.get("ood", False) is False

        return LocalExplanationOutput(
            prediction_id=self._generate_prediction_id(),
            risk_probability=self._compute_risk_probability(shap_result),
            baseline_probability=baseline_prob,
            top_positive_factors=top_positive,
            top_negative_factors=top_negative,
            feature_values=feature_values,
            feature_contributions=shap_result.get("contributions", {}),
            model_version=self._get_model_version(),
            feature_version=self._get_feature_version(),
            explanation_method=shap_result.get("explanation_method", "model_native_importance"),
            explanation_version=shap_result.get("explanation_version", "5.0.0"),
            timestamp=datetime.utcnow(),
            in_distribution=in_distribution,
            ood=shap_result.get("ood", False),
            ood_score=shap_result.get("ood_score"),
        )

    def _generate_prediction_id(self) -> str:
        """Generate a unique prediction ID."""
        import uuid
        return f"expl_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

    def _compute_risk_probability(self, shap_result: Dict[str, Any]) -> float:
        """Compute risk probability from SHAP explanation.

        Uses base_value + sum(top contributions) clipped to [0, 1].
        """
        base_value = shap_result.get("base_value", 0.5)
        contributions = shap_result.get("contributions", {})

        # Sum of top contributing factors
        total_contribution = sum(contributions.values()) if contributions else 0.0

        # Probability = base + total_contribution clip
        probability = np.clip(base_value + total_contribution, 0.0, 1.0)
        return float(probability)

    def _get_model_version(self) -> str:
        """Get model version."""
        # Try to get from model metadata
        if hasattr(self.model, "n_features_in_"):
            return "1.0"  # default
        return "1.0"

    def _get_feature_version(self) -> str:
        """Get feature version."""
        return "1.0"

    def generate_batch_local_explanations(
        self,
        feature_vectors: List[np.ndarray],
        feature_values_list: List[Dict[str, float]],
        baseline_values: Optional[List[float]] = None,
    ) -> List[LocalExplanationOutput]:
        """Generate local explanations for a batch of predictions.

        Args:
            feature_vectors: List of preprocessed feature vectors
            feature_values_list: List of feature value dictionaries
            baseline_values: Optional list of baseline probabilities

        Returns:
            List of LocalExplanationOutput
        """
        results = []
        for i, (fv, fvs) in enumerate(zip(feature_vectors, feature_values_list)):
            bl = baseline_values[i] if baseline_values else None
            result = self.generate_local_explanation(fv, fvs, baseline_value=bl)
            results.append(result)
        return results