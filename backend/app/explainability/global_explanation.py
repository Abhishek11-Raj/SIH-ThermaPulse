"""Global explanation and feature importance for KESHAV risk models.

Provides global model importance calculations, feature ranking,
and comparison across model versions or configurations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ..explainability.schemas import (
    GlobalExplanationOutput,
    FeatureImportanceEntry,
    LocalExplanationOutput,
)


logger = logging.getLogger(__name__)


class GlobalExplanationEngine:
    """Engine for computing global model explanations.

    Supports multiple importance methods compatible with the actual trained model.
    """

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        X_reference: Optional[pd.DataFrame] = None,
        model_type: Optional[str] = None,
    ):
        """Initialize global explanation engine.

        Args:
            model: Trained risk model
            feature_names: List of feature names in prediction order
            X_reference: Reference data for permutation importance
            model_type: Detected model type (tree, linear, other)
        """
        self.model = model
        self.feature_names = feature_names
        self.X_reference = X_reference
        self.model_type = model_type or self._detect_model_type()

    def _detect_model_type(self) -> str:
        """Detect model type."""
        if hasattr(self.model, "feature_importances_"):
            return "tree"
        elif hasattr(self.model, "coef_"):
            return "linear"
        return "other"

    def compute_global_importance(
        self,
        method: Literal["shap", "permutation", "model_native"] = "shap",
        X: Optional[pd.DataFrame] = None,
        y: Optional[np.ndarray] = None,
    ) -> GlobalExplanationOutput:
        """Compute global feature importance using specified method.

        Args:
            method: Importance method ("shap", "permutation", "model_native")
            X: Feature data (required for permutation, optional for SHAP)
            y: Target values (required for permutation)

        Returns:
            GlobalExplanationOutput with ranked feature importance
        """
        if method == "shap":
            importance_entries = self._compute_shap_importance(X)
        elif method == "permutation":
            if X is None or y is None:
                logger.warning(
                    "Permutation importance requires X and y. Falling back to model_native."
                )
                importance_entries = self._compute_model_native_importance()
            else:
                importance_entries = self._compute_permutation_importance(X, y)
        else:
            importance_entries = self._compute_model_native_importance()

        # Sort by importance descending
        importance_entries.sort(key=lambda x: x.importance, reverse=True)

        # Get total features
        total_features = len(self.feature_names)

        # Build feature importance list dicts for output
        feature_list = [
            {
                "feature": entry.feature,
                "importance": entry.importance,
                "description": entry.description,
            }
            for entry in importance_entries
        ]

        return GlobalExplanationOutput(
            model_id=getattr(self.model, "model_id", "keshav_risk_v1"),
            model_version=getattr(self.model, "model_version", "1.0"),
            feature_version=getattr(self.model, "feature_version", "1.0"),
            explanation_method=method,
            explanation_version="5.0.0",
            feature_importance=feature_list,
            total_features=total_features,
        )

    def _compute_shap_importance(self, X: Optional[pd.DataFrame] = None) -> List[FeatureImportanceEntry]:
        """Compute mean absolute SHAP feature importance.

        Returns:
            List of FeatureImportanceEntry sorted by importance descending
        """
        if not HAS_SHAP:
            logger.warning("SHAP not available, using model-native fallback")
            return self._compute_model_native_importance(X)

        try:
            # Use reference data if X not provided
            ref_data = self.X_reference if self.X_reference is not None else X
            if ref_data is None:
                logger.error("No reference data available for SHAP importance")
                return self._compute_model_native_importance()

            # Create explainer
            explainer = shap.TreeExplainer(self.model, ref_data[:50])

            # Compute SHAP values
            shap_values = explainer.shap_values(ref_data)

            # Handle binary classification output format
            if isinstance(shap_values, list):
                if len(shap_values) > 1:
                    shap_values = shap_values[1]  # positive class
                else:
                    shap_values = shap_values[0]

            # Mean absolute SHAP importance
            mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

            # Create importance entries
            importance_entries = [
                FeatureImportanceEntry(
                    feature=name,
                    importance=float(imp),
                    description="Mean |SHAP| value across dataset",
                )
                for name, imp in zip(self.feature_names, mean_abs_shap)
            ]

            # Sort by importance descending
            importance_entries.sort(key=lambda x: x.importance, reverse=True)

            return importance_entries

        except Exception as e:
            logger.error(f"SHAP importance computation failed: {e}")
            return self._compute_model_native_importance(X)

    def _compute_permutation_importance(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        n_permutations: int = 10,
    ) -> List[FeatureImportanceEntry]:
        """Compute permutation feature importance.

        Args:
            X: Feature data
            y: True target values
            n_permutations: Number of permutation iterations

        Returns:
            List of FeatureImportanceEntry sorted by importance descending
        """
        from sklearn.inspection import permutation_importance

        try:
            if hasattr(self.model, "predict_proba"):
                scoring = "roc_auc"
            else:
                scoring = "accuracy"

            perm_result = permutation_importance(
                self.model,
                X,
                y,
                n_permutations=n_permutations,
                random_state=42,
                scoring=scoring,
            )

            # Create importance entries
            importance_entries = [
                FeatureImportanceEntry(
                    feature=name,
                    importance=float(imp_mean),
                    description=f"Permutation importance ({n_permutations} permutations)",
                )
                for name, imp_mean in zip(
                    self.feature_names, perm_result.importances_mean
                )
            ]

            # Sort by importance descending
            importance_entries.sort(key=lambda x: x.importance, reverse=True)

            return importance_entries

        except Exception as e:
            logger.error(f"Permutation importance computation failed: {e}")
            return self._compute_model_native_importance(X)

    def _compute_model_native_importance(
        self,
        X: Optional[pd.DataFrame] = None,
    ) -> List[FeatureImportanceEntry]:
        """Compute model-native feature importance where available.

        Returns:
            List of FeatureImportanceEntry
        """
        entries = []

        if hasattr(self.model, "feature_importances_"):
            # Tree-based model importance
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
            # Linear model coefficient magnitudes
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
            logger.warning("Model has no native feature importance attribute")

        # Sort by importance descending
        entries.sort(key=lambda x: x.importance, reverse=True)

        # If no entries generated, create equal-weight entries
        if not entries:
            n_features = len(self.feature_names)
            base_imp = 1.0 / n_features if n_features > 0 else 0.0
            for name in self.feature_names:
                entries.append(
                    FeatureImportanceEntry(
                        feature=name,
                        importance=base_imp,
                        description="Equal weight (no native importance available)",
                    )
                )

        return entries

    def compare_across_versions(
        self,
        model_v1: Any,
        model_v2: Any,
        feature_names_v1: List[str],
        feature_names_v2: List[str],
        X: pd.DataFrame,
        y: np.ndarray,
    ) -> Dict[str, Any]:
        """Compare feature importance across two model versions.

        Args:
            model_v1: First model version
            model_v2: Second model version
            feature_names_v1: Feature names for v1
            feature_names_v2: Feature names for v2
            X: Feature data
            y: Target values

        Returns:
            Dictionary with comparison results
        """
        # Compute importance for both versions
        engine_v1 = GlobalExplanationEngine(model_v1, feature_names_v1, X_reference=X)
        engine_v2 = GlobalExplanationEngine(model_v2, feature_names_v2, X_reference=X)

        importance_v1 = engine_v1.compute_global_importance("model_native")
        importance_v2 = engine_v2.compute_global_importance("model_native")

        # Build comparison
        comparison = {
            "version_1": {
                "model_version": getattr(model_v1, "model_version", "1.0"),
                "top_features": [
                    {"feature": e.feature, "importance": e.importance}
                    for e in importance_v1[:5]
                ],
            },
            "version_2": {
                "model_version": getattr(model_v2, "model_version", "1.0"),
                "top_features": [
                    {"feature": e.feature, "importance": e.importance}
                    for e in importance_v2[:5]
                ],
            },
            "importance_shift": [],
        }

        # Compute per-feature change
        # Align by feature name
        feature_importances_v1 = {e.feature: e.importance for e in importance_v1}
        feature_importances_v2 = {e.feature: e.importance for e in importance_v2}

        all_features = set(feature_importances_v1.keys()) | set(feature_importances_v2.keys())

        for feat in sorted(all_features):
            imp1 = feature_importances_v1.get(feat, 0.0)
            imp2 = feature_importances_v2.get(feat, 0.0)
            shift = imp2 - imp1
            comparison["importance_shift"].append(
                {
                    "feature": feat,
                    "importance_v1": imp1,
                    "importance_v2": imp2,
                    "shift": shift,
                    "direction": "increase" if shift > 0 else "decrease" if shift < 0 else "no_change",
                }
            )

        # Sort by absolute shift descending
        comparison["importance_sort"] = sorted(
            comparison["importance_shift"], key=lambda x: abs(x["shift"]), reverse=True
        )

        return comparison